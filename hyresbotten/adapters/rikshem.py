"""Rikshem (rikshem.se).

Rikshem's "Ledigt just nu" lives in a Vitec portal at minasidor.rikshem.se,
which has no JSON API but publishes every vacancy in one RSS feed. The feed
carries address, rooms, size, rent and publish date; the ad page adds floor
and the last day to apply, so it is read once per new ad.

Rikshem's flats in Stockholm, Solna and Upplands Väsby are let through
Bostadsförmedlingen and already show up there. What remains in Stockholms
län is mostly Södertälje.
"""

import datetime as dt
import email.utils
import html
import logging
import re
import time
import xml.etree.ElementTree as ET

from ..http import RateLimited
from ..model import Listing, clean, place, to_float, to_int
from ..places import municipality_for
from .base import Adapter

log = logging.getLogger(__name__)

FEED = "https://minasidor.rikshem.se/RSS/apartment.aspx"
DETAIL_DELAY = 1.0
# Elements on the ad page that describe the flat itself (not the area).
FACT_ELEMENTS = ("_blProperties", "_lblInfoText", "_lblMisc", "_lblFact", "_lblPlanning")
# "2:a, 59 kvm, hyra: 6270 kr. Rådhusgatan 87 A, 831 44 Östersund"
DESCRIPTION = re.compile(
    r"^\s*(?P<rooms>\d+(?:[.,]\d+)?)\s*:\s*\w*\s*,\s*(?P<sqm>\d+(?:[.,]\d+)?)\s*kvm\s*,"
    r"\s*hyra:\s*(?P<rent>[\d\s]+)\s*kr\.?\s*(?P<address>.*?),\s*(?P<zip>\d{3}\s?\d{2})\s+(?P<town>.+?)\s*$",
    re.IGNORECASE)


class Rikshem(Adapter):
    name = "rikshem"
    label = "Rikshem"
    homepage = "https://www.rikshem.se/"
    allow_empty = True  # only a handful in Stockholms län at a time

    def __init__(self, max_details=30):
        self.max_details = max_details

    def fetch(self, http, previous):
        listings = parse_feed(http.get_text(FEED))
        missing = []
        for listing in listings:
            old = previous.get(listing.external_id)
            if old and not old.get("pending"):
                listing.floor = old.get("floor")
                listing.deadline = old.get("deadline")
                listing.requires_queue = old.get("requires_queue")
                listing.type = old.get("type", listing.type)
                listing.pending = False
            else:
                missing.append(listing)
        for listing in missing[: self.max_details]:
            try:
                apply_detail(listing, http.get_text(listing.url))
            except RateLimited:
                log.warning("rikshem: rate limited, details left for later")
                break
            time.sleep(DETAIL_DELAY)
        return listings


def parse_feed(text):
    root = ET.fromstring(text.encode("utf-8") if isinstance(text, str) else text)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Rikshem feed has no channel")
    listings = []
    for item in channel.findall("item"):
        listing = parse_item(item)
        if listing is not None:
            listings.append(listing)
    return listings


def parse_item(item):
    link = (item.findtext("link") or "").strip()
    match = re.search(r"/id/([\w-]+)", link)
    description = DESCRIPTION.match(html.unescape(item.findtext("description") or ""))
    if not match or not description:
        raise ValueError(f"unexpected Rikshem feed item: {link or item.findtext('title')}")
    town = place(description.group("town"))
    municipality = municipality_for(town)
    if municipality is None:
        return None  # outside Stockholms län
    area = place(item.findtext("category"))
    return Listing(
        source=Rikshem.name,
        external_id=match.group(1),
        url=link,
        address=clean(item.findtext("title")) or clean(description.group("address")),
        area=area if area and area != municipality else None,
        municipality=municipality,
        rent=to_int(re.sub(r"\s", "", description.group("rent"))),
        sqm=to_float(description.group("sqm")),
        rooms=to_float(description.group("rooms")),
        published=parse_date(item.findtext("pubDate")),
        pending=True,
    )


def parse_date(value):
    if not value:
        return None
    try:
        moment = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return moment.astimezone(dt.timezone.utc).date().isoformat()


def labelled(page, element_id):
    """Text of the element whose id ends with element_id, tags stripped."""
    match = re.search(r'id="[^"]*' + re.escape(element_id) + r'"[^>]*>(.*?)</(?:span|ul)>', page, re.S)
    if not match:
        return None
    return clean(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1))))


def apply_detail(listing, page):
    deadline = labelled(page, "_lblLastRegDate")
    if deadline and re.match(r"^\d{4}-\d{2}-\d{2}$", deadline):
        listing.deadline = deadline
    floor = labelled(page, "_ulFloor")  # "Våning: 0 av 3"
    if floor and (m := re.search(r"(-?\d+)\s*av", floor)):
        listing.floor = to_int(m.group(1))
    # Only the ad's own fact fields count: the area description further down
    # the page talks about "först till kvarn" for parking spaces.
    facts = " ".join(labelled(page, element) or "" for element in FACT_ELEMENTS).lower()
    listing.requires_queue = "först till kvarn" not in facts
    if "korttid" in facts:
        listing.type = "korttid"
    listing.pending = False
