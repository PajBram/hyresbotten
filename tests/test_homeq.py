import unittest
from unittest import mock

from hyresbotten.adapters import homeq
from hyresbotten.adapters.homeq import Homeq, parse_search

from .helpers import FakeHttp, fixture

SEARCH = "https://api.homeq.se/api/v3/search"
OBJECT = "https://api.homeq.se/api/v1/object/285632"
PROJECT = "https://api.homeq.se/api/v1/projects/1022"


def detail_responses(search):
    """Every detail URL answers with the saved sample of its kind."""
    responses = {SEARCH: search}
    for item in search["results"]:
        if item["type"] == "project":
            responses[f"https://api.homeq.se/api/v1/projects/{item['id']}"] = fixture("homeq_project_1022.json")
        else:
            responses[f"https://api.homeq.se/api/v1/object/{item['id']}"] = fixture("homeq_object_285632.json")
    return responses


@mock.patch.object(homeq, "DETAIL_DELAY", 0)
class HomeqTest(unittest.TestCase):
    def setUp(self):
        self.search = fixture("homeq_search.json")

    def test_search_results_map_to_listings(self):
        listings = {i.external_id: i for i in parse_search(self.search["results"])}
        item = listings["285632"]
        self.assertEqual(item.url, "https://www.homeq.se/lagenhet/285632-3rum-stockholm-stockholms-län-segersällsvägen-19")
        self.assertEqual(item.address, "Segersällsvägen 19")
        self.assertEqual(item.municipality, "Järfälla")
        self.assertIsNone(item.area)  # postal town "Stockholm" is not in Järfälla
        self.assertEqual((item.rent, item.sqm, item.rooms), (16614, 80, 3))
        self.assertTrue(item.pending)

    def test_audience_becomes_type(self):
        listings = {i.external_id: i for i in parse_search(self.search["results"])}
        self.assertEqual(listings["285424"].type, "student")
        self.assertEqual(listings["285424"].area, "Enskede")
        self.assertEqual(listings["285352"].type, "ungdom")
        self.assertEqual(listings["285213"].type, "korttid")
        self.assertEqual(listings["p-1205"].type, "vanlig")  # youth AND everyone

    def test_project_is_one_row_with_rent_range(self):
        project = {i.external_id: i for i in parse_search(self.search["results"])}["p-1022"]
        self.assertEqual(project.url, "https://www.homeq.se/projekt/1022")
        self.assertEqual((project.rent, project.rent_max), (9680, 20964))
        self.assertGreater(project.units, 1)

    def test_fetch_adds_details(self):
        listings = {i.external_id: i for i in Homeq().fetch(FakeHttp(detail_responses(self.search)), {})}
        flat = listings["285632"]
        self.assertEqual(flat.floor, 5)
        self.assertEqual(flat.published, "2026-10-07")
        self.assertFalse(flat.requires_queue)  # first_come_first
        self.assertFalse(flat.pending)
        project = listings["p-1022"]
        self.assertEqual((project.floor, project.floor_max), (1, 16))
        self.assertEqual((project.sqm, project.sqm_max), (2, 102))
        self.assertEqual(project.rent, 9680)  # the search range wins
        self.assertFalse(project.pending)

    def test_details_are_reused_from_earlier_runs(self):
        http = FakeHttp(detail_responses(self.search))
        first = Homeq().fetch(http, {})
        previous = {i.external_id: i.to_dict() for i in first}
        http.calls.clear()
        again = {i.external_id: i for i in Homeq().fetch(http, previous)}
        self.assertEqual(http.calls, [SEARCH])
        self.assertEqual(again["285632"].floor, 5)
        self.assertFalse(again["285632"].pending)

    def test_detail_cap_leaves_the_rest_pending(self):
        listings = Homeq(max_details=2).fetch(FakeHttp(detail_responses(self.search)), {})
        self.assertEqual(sum(1 for i in listings if not i.pending), 2)
        # Projects come first, since there are few of them.
        self.assertTrue(all(i.external_id.startswith("p-") for i in listings if not i.pending))

    def test_rate_limit_keeps_the_listings(self):
        http = FakeHttp(detail_responses(self.search), rate_limit_after=3)
        listings = Homeq().fetch(http, {})
        self.assertEqual(len(listings), len(self.search["results"]))
        self.assertEqual(sum(1 for i in listings if not i.pending), 2)

    def test_changed_format_raises(self):
        with self.assertRaises(ValueError):
            Homeq().fetch(FakeHttp({SEARCH: {"hits": []}}), {})


class QueueModeTest(unittest.TestCase):
    def test_modes(self):
        self.assertTrue(homeq.queue_required("queue_points"))
        self.assertFalse(homeq.queue_required("first_come_first"))
        self.assertFalse(homeq.queue_required("random"))
        self.assertIsNone(homeq.queue_required("something_new"))


if __name__ == "__main__":
    unittest.main()
