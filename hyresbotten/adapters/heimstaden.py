"""Heimstaden (heimstaden.com/se).

The search page on heimstaden.com asks WordPress' admin-ajax for the action
"hose_search". With hose_data_detail_level=level_2 the answer holds full
objects, so two requests per run cover the Stockholm region: one for regular
flats and one for student flats, which the search leaves out by default.
robots.txt explicitly allows /wp-admin/admin-ajax.php.

Heimstaden picks tenants among those who registered interest, with the
registration date as the guide, so queue time counts.
"""

import re

from ..model import Listing, clean, place, to_float, to_int
from ..places import municipality_for
from .base import Adapter

ENDPOINT = "https://heimstaden.com/se/wp-admin/admin-ajax.php"
REGION = "Stor-Stockholm"
# The endpoint fails with a WordPress error unless every range is present.
QUERY = ("text=Stockholm&number_of_rooms_min=1&number_of_rooms_max=20&rent_min=0&rent_max=200000"
         "&size_min=0&size_max=1000&search_version=1.5&object_type=apartments&tracking_object_type=Apartment")


class Heimstaden(Adapter):
    name = "heimstaden"
    label = "Heimstaden"
    homepage = "https://heimstaden.com/se/"
    allow_empty = True  # a few dozen flats at most; zero is possible

    def fetch(self, http, previous):
        objects = []
        for query in (QUERY, QUERY + "&properties_true_false[]=student"):
            data = http.get_json(ENDPOINT, {
                "action": "hose_search",
                "query_string": query,
                "hose_data_detail_level": "level_2",
            })
            if not isinstance(data, dict) or not isinstance(data.get("objects"), list):
                raise ValueError("Heimstaden search answered without an objects list")
            objects.extend(data["objects"])
        return parse_objects(objects)


def parse_objects(objects):
    listings, seen = [], set()
    for obj in objects:
        if obj.get("district_name") != REGION or obj.get("publish_status", "published") != "published":
            continue
        listing = parse_object(obj)
        if listing.external_id not in seen:
            seen.add(listing.external_id)
            listings.append(listing)
    return listings


def split_area(area_name):
    """"Täby - Tibble" -> ("Täby", "Tibble"); "Järfälla- Jakobsberg" too."""
    parts = re.split(r"\s+-\s*|\s*-\s+", area_name or "", maxsplit=1)
    if len(parts) == 2:
        return place(parts[0]), place(parts[1])
    return None, place(area_name)


def parse_object(obj):
    city = place(obj.get("city"))
    prefix, area = split_area(obj.get("area_name"))
    # The area prefix is sometimes just "Stockholm" for the whole region, so
    # the postal town is the better guide to the municipality.
    municipality = municipality_for(city) or municipality_for(area) or municipality_for(prefix) or city
    if area and area == municipality:
        area = None
    labels = [str(label).lower() for label in obj.get("labels") or []]
    kind = "vanlig"
    for label, value in (("student", "student"), ("ungdom", "ungdom"), ("youth", "ungdom"),
                         ("senior", "senior"), ("korttid", "korttid")):
        if label in labels:
            kind = value
            break
    return Listing(
        source=Heimstaden.name,
        external_id=str(obj["rental_object_id"]),
        url=obj["permalink"],
        address=clean(obj.get("street_address")),
        area=area,
        municipality=municipality,
        rent=to_int(re.sub(r"\D", "", str(obj.get("rental_cost") or ""))),
        sqm=to_float(obj.get("size_main")),
        rooms=to_float(obj.get("rooms_value")),
        floor=to_int(obj.get("floor")),
        requires_queue=True,
        type=kind,
    )
