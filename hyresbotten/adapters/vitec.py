"""Vitec rental portals ("Mina sidor" / "Ledigt just nu").

Many landlords run the same Vitec portal, and its listing page loads every
published flat from one open JSON endpoint:

    GET https://<portal>/rentalobject/List<group>/published?sortOrder=NEWEST
    -> {"status": "success", "data": "<the listings, as a JSON string>"}

so one adapter class covers all of them; each portal is its own source in
adapters/__init__.py. The listing carries everything the page needs, so
there is no per-ad request.

Rikshem's older portal lacks this endpoint and has its own adapter.
"""

import json
import re

from ..model import Listing, clean, place, to_float, to_int
from ..places import municipality_for
from .base import Adapter

SPECIAL_TYPES = (
    (re.compile(r"student", re.I), "student"),
    (re.compile(r"\bung(dom)?\b", re.I), "ungdom"),
    (re.compile(r"senior|trygghet|\b55\+|\b65\+", re.I), "senior"),
    (re.compile(r"korttid", re.I), "korttid"),
)


class Vitec(Adapter):
    def __init__(self, name, label, base, groups=("apartment",), municipality=None,
                 every_minutes=15, allow_empty=True):
        self.name = name
        self.label = label
        self.base = base.rstrip("/")
        self.homepage = self.base + "/"
        self.groups = groups
        # The portal's home municipality, for addresses missing from places.py.
        # None for landlords spread over the country: unknown towns are dropped.
        self.municipality = municipality
        self.every_minutes = every_minutes
        self.allow_empty = allow_empty

    def fetch(self, http, previous):
        listings = []
        for group in self.groups:
            answer = http.get_json(f"{self.base}/rentalobject/List{group}/published",
                                   {"sortOrder": "NEWEST"})
            listings.extend(self.parse(answer))
        return listings

    def parse(self, answer):
        if not isinstance(answer, dict) or answer.get("status") != "success":
            raise ValueError(f"{self.label}: unexpected answer from the portal")
        items = answer.get("data")
        if isinstance(items, str):
            items = json.loads(items)
        if not isinstance(items, list):
            raise ValueError(f"{self.label}: listings are not a list")
        listings = []
        for item in items:
            listing = self.parse_item(item)
            if listing is not None:
                listings.append(listing)
        return listings

    def parse_item(self, item):
        if item.get("StateId") not in (None, "PUBLISHED"):
            return None
        town = place(item.get("Adress3"))
        municipality = municipality_for(town) or self.municipality
        if municipality is None:
            return None  # outside Stockholms län
        area = strip_town(place(item.get("AreaName")))
        kind_text = " ".join(filter(None, [item.get("ObjectTypeName"), item.get("ObjectGroupName")]))
        return Listing(
            source=self.name,
            external_id=str(item["Id"]),
            url=self.base + item["DetailsUrl"],
            address=clean(item.get("Adress1")),
            area=area if area and area != municipality else (town if town and town != municipality else None),
            municipality=municipality,
            rent=to_int(item.get("Cost") if item.get("Cost") is not None else item.get("TotalCost")),
            sqm=to_float(item.get("Size")),
            rooms=to_float(item.get("NoOfRooms")),
            floor=to_int(item.get("Floor")),
            # Direct search is first come, first served; random sort is a lottery.
            requires_queue=not (item.get("ShowDirectSearch") or item.get("ShowRandomSort")),
            type=listing_type(kind_text),
            published=date(item.get("ShowDateStart")),
            deadline=date(item.get("ShowDateEnd")),
        )


def strip_town(area):
    """"Södertälje - Geneta" -> "Geneta": the town prefix repeats the kommun."""
    match = re.match(r"^(.+?)\s+-\s+(.+)$", area or "")
    if match and municipality_for(match.group(1)):
        return match.group(2)
    return area


def listing_type(text):
    for pattern, kind in SPECIAL_TYPES:
        if pattern.search(text or ""):
            return kind
    return "vanlig"


def date(value):
    if value and re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    return None
