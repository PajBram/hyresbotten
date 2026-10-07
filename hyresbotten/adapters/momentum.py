"""Momentum "Mina sidor" portals (minasidor.<landlord>.se).

The portal is a single-page app. Every anonymous visitor's browser first
loads /assets/app-settings.json, which names the API and holds the portal's
public client key, and then calls:

    GET <api>v2/client/configuration?market=true   the market's listing types
    GET <api>v2/market/objects?type=<id>&limit=500  the listings of one type
    GET <api>v2/market/objects/<object id>          one listing in full

The scraper does exactly the same, reading the key from app-settings.json on
every run rather than storing it. No login is involved.

The list gives address, rent, size and rooms; the full listing adds floor,
postal town and the last day to apply, so it is read once per new ad and
carried over afterwards. Portals of landlords outside Stockholm too (K2A,
ByggVesta) only reveal the town in the full listing; ads found to be outside
Stockholms län are remembered so they are not looked up again.
"""

import datetime as dt
import logging
import re
import time

from ..http import HttpError, RateLimited
from ..model import Listing, clean, place, to_float, to_int
from ..places import municipality_for
from .base import Adapter

log = logging.getLogger(__name__)

DETAIL_DELAY = 1.0
SKIP_TYPES = re.compile(r"fordon|parkering|p-plats|garage|bilplats|\bmc\b|förråd|lokal|kontor|verksamhet", re.I)
FIRST_COME = re.compile(r"först till kvarn|direkt", re.I)
SPECIAL_TYPES = (
    (re.compile(r"student", re.I), "student"),
    (re.compile(r"ungdom", re.I), "ungdom"),
    (re.compile(r"senior|trygghet|\b55\+|\b65\+", re.I), "senior"),
    (re.compile(r"korttid", re.I), "korttid"),
)
DETAIL_FIELDS = ("floor", "deadline", "municipality", "area", "rooms", "sqm")

try:
    from zoneinfo import ZoneInfo
    STOCKHOLM = ZoneInfo("Europe/Stockholm")
except Exception:  # noqa: BLE001 - no tz database: close enough for a date
    STOCKHOLM = dt.timezone(dt.timedelta(hours=1))


class Momentum(Adapter):
    def __init__(self, name, label, host, municipality=None, max_details=40, allow_empty=True):
        self.name = name
        self.label = label
        self.host = host
        self.homepage = f"https://{host}/"
        # The portal's home municipality, or None for landlords that are
        # spread over the country.
        self.municipality = municipality
        self.max_details = max_details
        self.allow_empty = allow_empty

    def fetch(self, http, previous):
        settings = http.get_json(f"https://{self.host}/assets/app-settings.json")
        try:
            api = settings["apiBaseUrl"].rstrip("/") + "/"
            headers = {
                "X-Api-Key": settings["xApiKey"],
                "X-Momentum-Client": "momentum.se-fastighetminasidor",
                "X-Momentum-Client-Id": settings["appInstanceId"],
                "Accept": "application/json",
                "Accept-Language": "sv-SE",
            }
        except (KeyError, AttributeError) as error:
            raise ValueError(f"{self.label}: app-settings.json changed ({error})") from error

        config = http.get_json(f"{api}v2/client/configuration", {"market": "true"}, headers)
        types = (config.get("market") or {}).get("types")
        if not isinstance(types, list):
            raise ValueError(f"{self.label}: no market types in the configuration")

        memo = self.memo if self.memo is not None else {}
        outside = set(memo.get("outside", []))
        seen_ids = set()
        listings, missing = [], []
        for market_type in types:
            type_name = market_type.get("displayName") or ""
            if SKIP_TYPES.search(type_name):
                continue
            answer = http.get_json(f"{api}v2/market/objects",
                                   {"type": market_type["id"], "limit": "500"}, headers)
            items = answer.get("items")
            if not isinstance(items, list):
                raise ValueError(f"{self.label}: market list without items")
            for item in items:
                seen_ids.add(item["id"])
                if item["id"] in outside:
                    continue
                listing = self.parse_item(item, market_type["id"], type_name)
                old = previous.get(listing.external_id)
                if old and not old.get("pending"):
                    for field in DETAIL_FIELDS:
                        # Fresh values from the list win; stored details fill gaps.
                        if getattr(listing, field) is None and old.get(field) is not None:
                            setattr(listing, field, old[field])
                    listing.pending = False
                    listings.append(listing)
                else:
                    missing.append(listing)

        for listing in missing[: self.max_details]:
            try:
                detail = http.get_json(f"{api}v2/market/objects/{listing.external_id}", None, headers)
            except RateLimited:
                log.warning("%s: rate limited, details left for later", self.name)
                break
            except HttpError as error:
                log.warning("%s: no details for %s (%s)", self.name, listing.external_id, error)
                continue
            if self.apply_detail(listing, detail):
                listings.append(listing)
            else:
                outside.add(listing.external_id)
                listing.municipality = None  # keeps it out of the list below
            time.sleep(DETAIL_DELAY)

        # Ads still waiting for details are shown when their municipality is
        # already known; otherwise they wait for a later run.
        listings.extend(item for item in missing[self.max_details:] if item.municipality)
        listings.extend(item for item in missing[: self.max_details] if item.pending and item.municipality)
        memo["outside"] = sorted(outside & seen_ids)
        return listings

    def parse_item(self, item, type_id, type_name):
        size = item.get("size") or {}
        location = item.get("location") or {}
        towns = [place(part.get("displayName")) for part in location.get("areaPath") or []]
        area = place((location.get("area") or {}).get("displayName"))
        municipality = next(filter(None, map(municipality_for, towns + [area])), None) or self.municipality
        kind = "vanlig"
        for pattern, value in SPECIAL_TYPES:
            if pattern.search(type_name):
                kind = value
                break
        return Listing(
            source=self.name,
            external_id=item["id"],
            url=f"https://{self.host}/market/{type_id}/{item['id']}",
            address=clean(item.get("displayName")),
            area=pick_area(towns, area, municipality),
            municipality=municipality,
            rent=to_int((item.get("pricing") or {}).get("price")),
            sqm=to_float(size.get("area")),
            rooms=rooms(size.get("roomsDisplayName") or size.get("shortRoomsDisplayName")),
            requires_queue=not FIRST_COME.search(type_name),
            type=kind,
            pending=True,
        )

    def apply_detail(self, listing, detail):
        """Fill in floor, deadline and town. False if outside Stockholms län."""
        location = detail.get("location") or {}
        address = location.get("address") or {}
        city = place(address.get("city"))
        if city:
            # The postal town is the best answer; a town places.py doesn't
            # know is outside the region unless this is a local landlord.
            municipality = municipality_for(city) or self.municipality
        else:
            municipality = listing.municipality
        if municipality is None:
            return False
        listing.municipality = municipality
        if not listing.area and city and city != municipality:
            listing.area = city
        listing.floor = floor(location.get("floorDisplayName"))
        listing.deadline = ms_date((detail.get("application") or {}).get("openTo"))
        size = detail.get("size") or {}
        if listing.sqm is None:
            listing.sqm = to_float(size.get("area"))
        if listing.rooms is None:
            listing.rooms = rooms(size.get("roomsDisplayName") or size.get("shortRoomsDisplayName"))
        listing.pending = False
        return True


def pick_area(towns, area, municipality):
    for name in reversed(towns + [area]):
        # Skip region labels ("Stockholm Huddinge") and company names that
        # some portals put where the area should be ("K2A Hyresbostäder ... AB").
        if (name and name != municipality and not name.startswith("Stockholm ")
                and not re.search(r"\bAB\b|hyresbostäder", name, re.I)):
            return name
    return None


def rooms(text):
    match = re.match(r"^\s*(\d+(?:[.,]\d+)?)", text or "")
    return to_float(match.group(1)) if match else None


def floor(text):
    text = (text or "").lower()
    if "botten" in text or text.strip() in ("bv", "entréplan", "markplan"):
        return 0
    match = re.search(r"(-?\d+)", text)
    return to_int(match.group(1)) if match else None


def ms_date(value):
    """'/Date(1792015140000)/' -> '2026-10-11' in Swedish time."""
    match = re.search(r"(-?\d+)", value or "")
    if not match:
        return None
    moment = dt.datetime.fromtimestamp(int(match.group(1)) / 1000, dt.timezone.utc)
    return moment.astimezone(STOCKHOLM).date().isoformat()
