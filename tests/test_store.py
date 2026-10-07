import datetime as dt
import unittest

from hyresbotten import store
from hyresbotten.__main__ import run
from hyresbotten.adapters.base import Adapter
from hyresbotten.model import Listing

T0 = dt.datetime(2026, 10, 7, 12, 0, tzinfo=dt.timezone.utc)


def listing(external_id, source="a", **fields):
    return Listing(source=source, external_id=external_id, url=f"https://example.se/{external_id}", **fields)


class FixedAdapter(Adapter):
    def __init__(self, name, result):
        self.name = self.label = name
        self.result = result

    def fetch(self, http, previous):
        if isinstance(self.result, Exception):
            raise self.result
        return list(self.result)


class MergeTest(unittest.TestCase):
    def test_first_import_backdates_to_publish_date(self):
        state = store.empty_state()
        store.merge(state, "a", [listing("1", published="2026-09-01"), listing("2")], T0)
        self.assertEqual(state["listings"]["a:1"]["first_seen"], "2026-09-01T00:00:00Z")
        self.assertEqual(state["listings"]["a:2"]["first_seen"], "2026-10-07T12:00:00Z")

    def test_first_import_without_date_is_marked_undated(self):
        state = store.empty_state()
        store.merge(state, "a", [listing("1", published="2026-09-01"), listing("2")], T0)
        rows = {row["external_id"]: row for row in store.public_listings(state)}
        self.assertNotIn("undated", rows["1"])
        self.assertTrue(rows["2"]["undated"])
        self.assertNotIn("boot", rows["1"])

    def test_later_listings_keep_their_discovery_time(self):
        state = store.empty_state()
        store.merge(state, "a", [listing("1")], T0)
        later = T0 + dt.timedelta(hours=1)
        store.merge(state, "a", [listing("1"), listing("2", published="2026-09-01")], later)
        self.assertEqual(state["listings"]["a:1"]["first_seen"], "2026-10-07T12:00:00Z")
        self.assertEqual(state["listings"]["a:1"]["last_seen"], "2026-10-07T13:00:00Z")
        self.assertEqual(state["listings"]["a:2"]["first_seen"], "2026-10-07T13:00:00Z")

    def test_missing_listing_is_marked_gone_and_hidden(self):
        state = store.empty_state()
        store.merge(state, "a", [listing("1"), listing("2")], T0)
        store.merge(state, "a", [listing("1")], T0 + dt.timedelta(minutes=15))
        self.assertEqual(state["listings"]["a:2"]["gone_at"], "2026-10-07T12:15:00Z")
        self.assertEqual([row["external_id"] for row in store.public_listings(state)], ["1"])

    def test_listing_that_comes_back_is_shown_again(self):
        state = store.empty_state()
        store.merge(state, "a", [listing("1"), listing("2")], T0)
        store.merge(state, "a", [listing("1")], T0 + dt.timedelta(minutes=15))
        store.merge(state, "a", [listing("1"), listing("2")], T0 + dt.timedelta(minutes=30))
        self.assertNotIn("gone_at", state["listings"]["a:2"])
        self.assertEqual(state["listings"]["a:2"]["first_seen"], "2026-10-07T12:00:00Z")

    def test_other_sources_are_untouched(self):
        state = store.empty_state()
        store.merge(state, "a", [listing("1")], T0)
        store.merge(state, "b", [listing("1", source="b")], T0)
        store.merge(state, "a", [listing("9")], T0 + dt.timedelta(minutes=15))
        self.assertNotIn("gone_at", state["listings"]["b:1"])

    def test_gone_listings_are_pruned_after_a_while(self):
        state = store.empty_state()
        store.merge(state, "a", [listing("1"), listing("2")], T0)
        store.merge(state, "a", [listing("1")], T0)
        store.prune(state, T0 + dt.timedelta(days=store.KEEP_GONE_DAYS + 1))
        self.assertEqual(list(state["listings"]), ["a:1"])

    def test_sudden_drop_is_suspicious(self):
        state = store.empty_state()
        store.merge(state, "a", [listing(str(n)) for n in range(100)], T0)
        with self.assertRaises(store.SuspiciousResult):
            store.check_plausible(state, "a", [listing("1")])
        with self.assertRaises(store.SuspiciousResult):
            store.check_plausible(state, "a", [])
        store.check_plausible(state, "a", [listing(str(n)) for n in range(60)])


class RunTest(unittest.TestCase):
    def test_a_broken_source_does_not_stop_the_others(self):
        state = store.empty_state()
        store.merge(state, "broken", [listing("old", source="broken")], T0)
        adapters = [FixedAdapter("broken", RuntimeError("new HTML")),
                    FixedAdapter("fine", [listing("1", source="fine")])]
        failed = run(state, adapters, http=type("H", (), {"request_count": 0})(), now=T0)
        self.assertEqual(failed, ["broken"])
        self.assertFalse(state["sources"]["broken"]["ok"])
        self.assertIn("new HTML", state["sources"]["broken"]["error"])
        self.assertTrue(state["sources"]["fine"]["ok"])
        # The broken source keeps showing what it had.
        self.assertNotIn("gone_at", state["listings"]["broken:old"])
        self.assertIn("fine:1", state["listings"])


if __name__ == "__main__":
    unittest.main()
