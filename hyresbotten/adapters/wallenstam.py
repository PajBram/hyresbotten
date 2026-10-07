"""Wallenstam (wallenstam.se).

The "Lediga bostäder" page answers a form POST with JSON ({Filters, Objects}).
Only the non-empty form fields may be sent: the full empty form returns
nothing. One request per run.

Wallenstam lets its flats through its own queue (köpoäng). In Stockholm it
often has no single flats out at all, only new-build projects; a project
that is being let ("Under uthyrning") is shown as one row.
"""

import json
import re

from ..model import Listing, clean, place, to_float, to_int
from ..places import municipality_for
from .base import Adapter

BASE = "https://www.wallenstam.se"
PAGE = f"{BASE}/sv/bostader/lediga-bostader/"


class Wallenstam(Adapter):
    name = "wallenstam"
    label = "Wallenstam"
    homepage = PAGE
    allow_empty = True  # Stockholm is often empty

    def fetch(self, http, previous):
        data = json.loads(http.post_form(PAGE, {"Status": "Available", "Region": "Stockholm"}))
        if not isinstance(data, dict) or not isinstance(data.get("Objects"), list):
            raise ValueError("Wallenstam answered without an Objects list")
        return parse_objects(data["Objects"])


def parse_objects(objects):
    listings = []
    for obj in objects:
        if obj.get("City") not in (None, "Stockholm"):
            continue
        if obj.get("PageType") == "BostadPageModel":
            listings.append(parse_flat(obj))
        elif obj.get("PageType") == "ProjectPageModel" and is_rental_project(obj):
            listings.append(parse_project(obj))
    return listings


def is_rental_project(obj):
    return "Hyresrätt" in (obj.get("Attributes") or []) and obj.get("Status") == "Under uthyrning"


def municipality(obj):
    return municipality_for(obj.get("Area")) or "Stockholm"


def parse_attributes(attributes):
    rooms = sqm = floor = None
    for text in attributes or []:
        text = str(text).strip().lower()
        if m := re.match(r"^(\d+(?:[.,]\d+)?)\s*(rok|rum)", text):
            rooms = to_float(m.group(1))
        elif m := re.match(r"^(\d+(?:[.,]\d+)?)\s*m", text):
            sqm = to_float(m.group(1))
        elif "bottenvåning" in text or text == "bv":
            floor = 0
        elif m := re.match(r"^(-?\d+)\D*våning", text):
            floor = to_int(m.group(1))
    return rooms, sqm, floor


def parse_flat(obj):
    rooms, sqm, floor = parse_attributes(obj.get("Attributes"))
    if rooms is None and (m := re.match(r"^(\d+)", obj.get("NumberOfRoomsText") or "")):
        rooms = to_float(m.group(1))
    area = place(obj.get("Area"))
    kommun = municipality(obj)
    return Listing(
        source=Wallenstam.name,
        external_id=str(obj["Id"]),
        url=BASE + obj["Url"],
        address=clean(obj.get("Headline")),
        area=None if area == kommun else area,
        municipality=kommun,
        rent=to_int(obj.get("Rent")),
        sqm=sqm,
        rooms=rooms,
        floor=floor,
        requires_queue=True,
        type="korttid" if "korttid" in (obj.get("NumberOfRoomsText") or "").lower() else "vanlig",
    )


def parse_project(obj):
    area = place(obj.get("Area"))
    kommun = municipality(obj)
    return Listing(
        source=Wallenstam.name,
        external_id=f"p-{obj['Id']}",
        url=BASE + obj["Url"],
        address=clean(obj.get("Headline")),
        area=None if area == kommun else area,
        municipality=kommun,
        requires_queue=True,
    )
