"""Run every adapter once and write the state plus the page's data file.

    python -m hyresbotten --state out/state.json --out out

One broken source never stops the others: its error is logged and recorded in
the data file, its listings stay as they were, and the process exits with
status 1 at the end so the GitHub Actions run shows up as failed.
"""

import argparse
import datetime as dt
import json
import logging
import os
import sys
import traceback

from . import store
from .adapters import all_adapters
from .http import Http

log = logging.getLogger("hyresbotten")


def load_state(path):
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except FileNotFoundError:
        log.info("no previous state at %s, starting fresh", path)
        return store.empty_state()
    if state.get("version") != store.VERSION:
        raise SystemExit(f"state version {state.get('version')} is not {store.VERSION}")
    return state


def write_json(path, data, pretty=False):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        if pretty:
            json.dump(data, handle, ensure_ascii=False, indent=1, sort_keys=True)
        else:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def due(status, adapter, now):
    """True when the adapter's interval has passed since its last success."""
    if adapter.every_minutes <= 15 or not status.get("ok") or not status.get("last_success"):
        return True
    last = dt.datetime.strptime(status["last_success"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    # A few minutes of slack: GitHub's schedule drifts.
    return now - last >= dt.timedelta(minutes=adapter.every_minutes - 5)


def run(state, adapters, http, now):
    failed = []
    for adapter in adapters:
        status = state["sources"].setdefault(adapter.name, {})
        status.update(label=adapter.label, homepage=adapter.homepage)
        if not due(status, adapter, now):
            log.info("%s: fetched recently, skipping this run", adapter.name)
            continue
        status["last_run"] = store.iso(now)
        adapter.memo = status.setdefault("memo", {})
        before = http.request_count
        try:
            listings = adapter.fetch(http, store.previous_for(state, adapter.name))
            store.check_plausible(state, adapter.name, listings, adapter.allow_empty)
            store.merge(state, adapter.name, listings, now)
        except Exception as error:  # noqa: BLE001 - isolate every source
            log.error("%s failed: %s\n%s", adapter.name, error, traceback.format_exc())
            status.update(ok=False, error=f"{type(error).__name__}: {error}")
            failed.append(adapter.name)
            continue
        pending = sum(1 for item in listings if item.pending)
        status.update(ok=True, error=None, last_success=store.iso(now), count=len(listings))
        log.info("%s: %d listings (%d awaiting details), %d requests",
                 adapter.name, len(listings), pending, http.request_count - before)
    store.prune(state, now)
    return failed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state", default="out/state.json")
    parser.add_argument("--out", default="out", help="directory for state.json and listings.json")
    parser.add_argument("--only", nargs="*", help="run only these sources")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    now = dt.datetime.now(dt.timezone.utc)
    state = load_state(args.state)
    adapters = [a for a in all_adapters() if not args.only or a.name in args.only]
    failed = run(state, adapters, Http(), now)

    os.makedirs(args.out, exist_ok=True)
    write_json(os.path.join(args.out, "state.json"), state, pretty=True)
    write_json(os.path.join(args.out, "listings.json"), {
        "generated_at": store.iso(now),
        "sources": {name: {k: v for k, v in status.items() if k != "memo"}
                    for name, status in state["sources"].items()},
        "listings": store.public_listings(state),
    })

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(f"failed={' '.join(failed)}\n")
    if failed:
        log.error("failed sources: %s", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
