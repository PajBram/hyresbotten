"""Bostadsförmedlingen i Stockholm (bostad.stockholm.se).

Their own listing page loads every ad from one JSON endpoint,
/AllaAnnonser/, without login. One request per run covers the whole region.
"""

from ..model import Listing, clean, place, to_float, to_int
from .base import Adapter

BASE = "https://bostad.stockholm.se"


class Bostadsformedlingen(Adapter):
    name = "bostadsformedlingen"
    label = "Bostadsförmedlingen"
    homepage = BASE

    def fetch(self, http, previous):
        return parse_listings(http.get_json(f"{BASE}/AllaAnnonser/"))


def parse_listings(data):
    if not isinstance(data, list):
        raise ValueError("expected a JSON list from /AllaAnnonser/")
    listings = []
    for ad in data:
        # Bostadsrätter and other forms of tenure never show up here today,
        # but only first-hand rentals belong on the page.
        if ad.get("Lagenhetstyp") in ("Bostadsrätt", "Andrahand"):
            continue
        listings.append(parse_ad(ad))
    return listings


def parse_ad(ad):
    units = to_int(ad.get("Antal")) or 1
    listing = Listing(
        source=Bostadsformedlingen.name,
        external_id=str(ad["LägenhetId"]),
        url=BASE + ad["Url"],
        address=clean(ad.get("Gatuadress")),
        area=place(ad.get("Stadsdel")),
        municipality=place(ad.get("Kommun")),
        rent=to_int(ad.get("Hyra")),
        sqm=to_float(ad.get("Yta")),
        rooms=to_float(ad.get("AntalRum")),
        floor=to_int(ad.get("Vaning")),
        # "Bostad snabbt" goes to whoever is first or drawn by lot; every
        # other ad goes to the longest queue time.
        requires_queue=not ad.get("BostadSnabbt"),
        type=listing_type(ad),
        published=ad.get("AnnonseradFran"),
        deadline=ad.get("AnnonseradTill"),
        units=units,
    )
    if units > 1:
        # A project with several flats carries ranges instead of single values.
        listing.rent = to_int(ad.get("LägstaHyran"))
        listing.rent_max = to_int(ad.get("HögstaHyran"))
        listing.sqm = to_float(ad.get("LägstaYtan"))
        listing.sqm_max = to_float(ad.get("HögstaYtan"))
        listing.rooms = to_float(ad.get("LägstaAntalRum"))
        listing.rooms_max = to_float(ad.get("HögstaAntalRum"))
    return listing


def listing_type(ad):
    kind = ad.get("Lagenhetstyp") or ""
    if ad.get("Korttid") or "Korttid" in kind:
        return "korttid"
    if ad.get("Student") or kind.startswith("Student"):
        return "student"
    if ad.get("Ungdom") or kind.startswith("Ungdom") or ad.get("KompisUngdom"):
        return "ungdom"
    if ad.get("Senior") or kind.startswith("Senior"):
        return "senior"
    if ad.get("Vanlig") or kind in ("Hyresrätt", "Hyresradhus"):
        return "vanlig"
    return "annat"
