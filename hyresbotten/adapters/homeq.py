"""Homeq (homeq.se).

Homeq's own site uses an open JSON API:

* POST /api/v3/search lists every ad in Stockholms län (shape "county.1") with
  address, rent, size, rooms and target group, 1000 per page.
* GET /api/v1/object/{id} and /api/v1/projects/{id} add what the search lacks:
  floor, publish date and how tenants are picked (queue points, first come or
  lottery).

Details only change when the ad does, so they are looked up once per ad and
then carried over from earlier runs. A cap per run keeps the first import from
firing a thousand requests at once; the rest follow in the next runs.
"""

import logging
import time

from ..http import RateLimited
from ..model import Listing, clean, place, to_float, to_int
from .base import Adapter

log = logging.getLogger(__name__)

API = "https://api.homeq.se"
SITE = "https://www.homeq.se"
STOCKHOLMS_LAN = "county.1"
PAGE_SIZE = 1000
MAX_PAGES = 5
DETAIL_DELAY = 1.5  # extra seconds between detail lookups; Homeq rate-limits
DETAIL_FIELDS = ("floor", "floor_max", "requires_queue", "published",
                 "sqm", "sqm_max", "rooms", "rooms_max", "rent", "rent_max")


class Homeq(Adapter):
    name = "homeq"
    label = "Homeq"
    homepage = SITE

    def __init__(self, max_details=60):
        self.max_details = max_details

    def fetch(self, http, previous):
        results = []
        for page in range(1, MAX_PAGES + 1):
            data = http.post_json(f"{API}/api/v3/search", {
                "shapes": [STOCKHOLMS_LAN], "page": page, "amount": PAGE_SIZE,
            })
            batch = data.get("results")
            if not isinstance(batch, list):
                raise ValueError("Homeq search answered without a results list")
            results.extend(batch)
            if len(batch) < PAGE_SIZE or len(results) >= data.get("total_hits", 0):
                break

        listings = parse_search(results)
        missing = []
        for listing in listings:
            old = previous.get(listing.external_id)
            if old and not old.get("pending"):
                carry_details(listing, old)
            else:
                missing.append(listing)

        # Projects first (there are few), then the newest ads: they are the
        # ones visitors care about most.
        missing.sort(key=lambda item: (item.external_id.startswith("p-"),
                                       int(split_id(item.external_id)[1])), reverse=True)
        for listing in missing[: self.max_details]:
            kind, number = split_id(listing.external_id)
            try:
                if kind == "project":
                    apply_project(listing, http.get_json(f"{API}/api/v1/projects/{number}"))
                else:
                    apply_object(listing, http.get_json(f"{API}/api/v1/object/{number}")["object_ad"])
            except RateLimited:
                # The listings themselves are fine; the rest of the details
                # wait for the next run.
                log.warning("homeq: rate limited, %d details left for later",
                            sum(1 for item in missing if item.pending))
                break
            time.sleep(DETAIL_DELAY)
        return listings


def split_id(external_id):
    if external_id.startswith("p-"):
        return "project", external_id[2:]
    return "object", external_id


def parse_search(results):
    listings = []
    seen = set()
    for item in results:
        if item.get("type") == "individual":
            listing = parse_individual(item)
        elif item.get("type") == "project":
            listing = parse_project(item)
        else:
            continue
        if listing.external_id not in seen:  # pages can overlap if ads move
            seen.add(listing.external_id)
            listings.append(listing)
    return listings


def audience_type(item):
    if item.get("is_short_lease"):
        return "korttid"
    audience = item.get("audience") or []
    if isinstance(audience, str):
        audience = [audience]
    if not audience or "everyone" in audience:
        return "vanlig"
    for value, kind in (("student", "student"), ("youth", "ungdom"), ("senior", "senior")):
        if value in audience:
            return kind
    return "annat"


def area_name(item):
    """Homeq gives the postal town, which is a fair stand-in for the area.

    Postal towns that only repeat the municipality, or say "Stockholm" for an
    address in another municipality, add nothing and are dropped.
    """
    city = place(item.get("city"))
    municipality = place(item.get("municipality"))
    if not city or city == municipality or (city == "Stockholm" and municipality != "Stockholm"):
        return None
    return city


def parse_individual(item):
    return Listing(
        source=Homeq.name,
        external_id=str(item["id"]),
        url=SITE + item["uri"],
        address=clean(item.get("title")),
        area=area_name(item),
        municipality=place(item.get("municipality")),
        rent=to_int(item.get("rent")),
        sqm=to_float(item.get("area")),
        rooms=to_float(item.get("rooms")),
        type=audience_type(item),
        pending=True,
    )


def parse_project(item):
    low, high = (list(item.get("rent_range") or []) + [None, None])[:2]
    return Listing(
        source=Homeq.name,
        external_id=f"p-{item['id']}",
        url=SITE + item["uri"],
        address=clean(item.get("title")),
        area=area_name(item),
        municipality=place(item.get("municipality")),
        rent=to_int(low),
        rent_max=to_int(high),
        type=audience_type(item),
        units=to_int(item.get("active_ads")) or 1,
        pending=True,
    )


def queue_required(mode):
    if mode == "queue_points":
        return True
    if mode in ("first_come_first", "random"):
        return False
    return None


def apply_object(listing, ad):
    listing.floor = to_int(ad.get("floor"))
    listing.published = ad.get("date_publish")
    listing.requires_queue = queue_required(ad.get("candidate_sorting_mode"))
    if ad.get("is_short_lease"):
        listing.type = "korttid"
    listing.pending = False


def apply_project(listing, project):
    ranges = project.get("range_information") or {}

    def pick(name, convert):
        values = list(ranges.get(name) or []) + [None, None]
        return convert(values[0]), convert(values[1])

    listing.sqm, listing.sqm_max = pick("area", to_float)
    listing.rooms, listing.rooms_max = pick("rooms", to_float)
    listing.floor, listing.floor_max = pick("floor", to_int)
    if listing.rent is None and ranges.get("rent"):
        listing.rent, listing.rent_max = pick("rent", to_int)
    published = project.get("republish_date") or project.get("publish_date")
    listing.published = published[:10] if published else None
    listing.requires_queue = queue_required(project.get("candidate_sorting_mode"))
    if project.get("is_short_lease"):
        listing.type = "korttid"
    listing.pending = False


def carry_details(listing, old):
    for field in DETAIL_FIELDS:
        # The search result is fresher for the fields it carries itself.
        if getattr(listing, field) is None and old.get(field) is not None:
            setattr(listing, field, old[field])
    if old.get("type") == "korttid":
        listing.type = "korttid"
    listing.pending = False
