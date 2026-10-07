"""Remembers listings between runs: first_seen, last_seen and gone_at.

The state is one JSON document:

    {"version": 1,
     "sources":  {name: {label, homepage, ok, last_run, last_success, count, error}},
     "listings": {"source:external_id": {...listing, first_seen, last_seen, gone_at?}}}
"""

import datetime as dt

VERSION = 1
KEEP_GONE_DAYS = 30
# A source that suddenly returns far fewer ads has most likely changed its
# format. Treat that as a failure instead of hiding everything it had.
MIN_SHARE_OF_PREVIOUS = 0.3
MIN_COUNT_FOR_SHARE_CHECK = 20


class SuspiciousResult(Exception):
    pass


def empty_state():
    return {"version": VERSION, "sources": {}, "listings": {}}


def iso(moment):
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def active(state, source=None):
    return [rec for rec in state["listings"].values()
            if not rec.get("gone_at") and (source is None or rec["source"] == source)]


def previous_for(state, source):
    """Stored records of one source keyed by external_id, for the adapter."""
    return {rec["external_id"]: rec for rec in state["listings"].values() if rec["source"] == source}


def check_plausible(state, source, listings, allow_empty=False):
    before = len(active(state, source))
    if not listings and not allow_empty:
        raise SuspiciousResult("the source returned no listings at all")
    if before >= MIN_COUNT_FOR_SHARE_CHECK and len(listings) < before * MIN_SHARE_OF_PREVIOUS:
        raise SuspiciousResult(f"only {len(listings)} listings, down from {before}")


def merge(state, source, listings, now):
    """Fold one successful scrape of `source` into the state."""
    stamp = iso(now)
    bootstrap = not previous_for(state, source)
    seen = set()
    for listing in listings:
        key = listing.key
        seen.add(key)
        record = listing.to_dict()
        old = state["listings"].get(key)
        if old:
            record["first_seen"] = old["first_seen"]
            if old.get("boot"):
                record["boot"] = True
        else:
            record["first_seen"] = stamp
            if bootstrap:
                # The very first import: "seen first" would make every ad look
                # brand new. Mark it so the publish date can take over.
                record["boot"] = True
        if record.get("boot") and record.get("published"):
            published = f"{record['published']}T00:00:00Z"
            record["first_seen"] = min(record["first_seen"], published)
        record["last_seen"] = stamp
        state["listings"][key] = record

    for key, record in state["listings"].items():
        if record["source"] == source and key not in seen and not record.get("gone_at"):
            record["gone_at"] = stamp


def prune(state, now):
    cutoff = iso(now - dt.timedelta(days=KEEP_GONE_DAYS))
    state["listings"] = {key: rec for key, rec in state["listings"].items()
                         if not rec.get("gone_at") or rec["gone_at"] >= cutoff}


def public_listings(state):
    """What the page needs: active listings without bookkeeping fields."""
    rows = []
    for record in active(state):
        row = {k: v for k, v in record.items() if k not in ("last_seen", "boot", "gone_at")}
        if record.get("boot") and not record.get("published"):
            # Found in the first import and still without a publish date:
            # its first_seen says nothing about how new the ad is.
            row["undated"] = True
        rows.append(row)
    rows.sort(key=lambda row: "" if row.get("undated") else row["first_seen"], reverse=True)
    return rows
