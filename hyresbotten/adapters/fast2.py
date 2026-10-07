"""FAST2 widget portals: SSSB (student housing) and SKB (cooperative rentals).

Both sites build their "Lediga lägenheter" list from one JSONP call to
/widgets/. SSSB answers with structured data; SKB answers with the finished
HTML list, which is parsed here. One request per run each.

Neither gives a municipality. Both are almost entirely in Stockholm city, so
an area that places.py doesn't know counts as Stockholm.
"""

import html
import json
import re

from ..model import Listing, clean, place, to_float, to_int
from ..places import municipality_for
from .base import Adapter

WIDGET = "objektlistabilder@lagenheter"
# Areas places.py can't know because they are names of buildings or blocks.
AREA_MUNICIPALITY = {"Kungshamra": "Solna", "Flemingsberg": "Huddinge"}


def widget_url(base):
    return (f"{base}/widgets/?pagination=0&paginationantal=500&callback=cb"
            f"&widgets%5B%5D={WIDGET.replace('@', '%40')}")


def unwrap_jsonp(text):
    start, end = text.find("("), text.rfind(")")
    if start < 0 or end < start:
        raise ValueError("expected a JSONP answer")
    return json.loads(text[start + 1:end])


def municipality_of(area):
    return AREA_MUNICIPALITY.get(area) or municipality_for(area) or "Stockholm"


class Sssb(Adapter):
    name = "sssb"
    label = "SSSB"
    homepage = "https://sssb.se/"
    base = "https://minasidor.sssb.se"

    def fetch(self, http, previous):
        data = unwrap_jsonp(http.get_text(widget_url(self.base))).get("data") or {}
        items = data.get(WIDGET)
        if not isinstance(items, list):
            raise ValueError("SSSB widget answered without a listing list")
        return [parse_sssb(item) for item in items]


def parse_sssb(item):
    area = place(item.get("omrade"))
    municipality = municipality_of(area)
    url = item["detaljUrl"]
    return Listing(
        source=Sssb.name,
        external_id=str(item["objektNr"]),
        url=re.sub(r"^(https?:)?//", "https://", url),
        address=clean(re.sub(r"\s*/\s*\d+$", "", item.get("adress") or "")),  # drop "/ 1152" flat no.
        area=area if area != municipality else None,
        municipality=municipality,
        rent=to_int(re.sub(r"\D", "", str(item.get("hyra") or ""))),
        sqm=to_float(item.get("yta")),
        rooms=1 if "rum" in (item.get("typOvergripande") or "").lower() else rooms(item.get("typ")),
        floor=to_int(item.get("vaning")),
        # SSSB lets every place by study-queue days.
        requires_queue=True,
        type="student",
        published=day(item.get("publiceratDatum")),
        deadline=day(item.get("publiceratSistaDatum")),
    )


class Skb(Adapter):
    name = "skb"
    label = "SKB"
    homepage = "https://www.skb.org/"
    base = "https://www.skb.org"
    allow_empty = True

    def fetch(self, http, previous):
        answer = unwrap_jsonp(http.get_text(widget_url(self.base)))
        markup = (answer.get("html") or {}).get(WIDGET)
        if not isinstance(markup, str):
            raise ValueError("SKB widget answered without the listing HTML")
        return parse_skb(markup)


def field(block, name):
    match = re.search(rf'<dd class="{name}[^"]*">(.*?)</dd>', block, re.S)
    return clean(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))) if match else None


def parse_skb(markup):
    listings = []
    for block in markup.split('class="Box ObjektListItem')[1:]:
        link = re.search(r'<h4 class="ObjektAdress"><a href="([^"]+)">(.*?)</a>', block, re.S)
        kind = re.search(r'<h3 class="ObjektTyp"><a[^>]*>(.*?)</a>', block, re.S)
        ref = field(block, "ObjektNummer")
        if not link or not ref:
            raise ValueError("unexpected SKB listing markup")
        area = place(field(block, "ObjektOmrade"))
        municipality = municipality_of(area)
        floor_text = field(block, "ObjektVaning") or ""
        floor_match = re.match(r"^(-?\d+)", floor_text)
        address = clean(html.unescape(link.group(2)))
        listings.append(Listing(
            source=Skb.name,
            external_id=ref,
            url=html.unescape(link.group(1)),
            address=re.sub(r"\s+Lgh\s+\d+$", "", address or ""),
            area=area if area != municipality else None,
            municipality=municipality,
            rent=to_int(re.sub(r"\D", "", field(block, "ObjektHyra") or "")),
            sqm=to_float((re.match(r"^([\d,.]+)", field(block, "ObjektYta") or "") or [None, None])[1]),
            rooms=rooms(html.unescape(kind.group(1)) if kind else None),
            floor=to_int(floor_match.group(1)) if floor_match else None,
            # SKB lets to members by membership time.
            requires_queue=True,
            type="vanlig",
        ))
    return listings


def rooms(text):
    match = re.match(r"^\s*(\d+(?:[.,]\d+)?)", text or "")
    return to_float(match.group(1)) if match else None


def day(value):
    return value[:10] if value and re.match(r"^\d{4}-\d{2}-\d{2}", value) else None
