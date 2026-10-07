"""Tests for the shared-platform adapters: Vitec, Momentum and FAST2."""

import json
import unittest
from unittest import mock

from hyresbotten.adapters import momentum
from hyresbotten.adapters.fast2 import Skb, Sssb, unwrap_jsonp
from hyresbotten.adapters.momentum import Momentum, floor, ms_date
from hyresbotten.adapters.vitec import Vitec, listing_type, strip_town

from .helpers import FakeHttp, fixture
from .test_private_landlords import text_fixture

TELGE = "https://kundportal.telge.se"
VICTORIA = "https://minasidor.victoriahem.se"


class VitecHttp(FakeHttp):
    def get_json(self, url, params=None, headers=None):
        self.calls.append(url)
        self.request_count += 1
        return self.responses[url]


class VitecTest(unittest.TestCase):
    def fetch(self, adapter, fixture_name, base):
        url = f"{base}/rentalobject/Listapartment/published"
        http = VitecHttp({url: fixture(fixture_name)})
        return {i.external_id: i for i in adapter.fetch(http, {})}, http

    def test_maps_fields(self):
        listings, http = self.fetch(Vitec("telge", "Telge Bostäder", TELGE, municipality="Södertälje"),
                                    "vitec_telge.json", TELGE)
        self.assertEqual(len(http.calls), 1)
        item = listings["043-16435"]
        self.assertEqual(item.url, "https://kundportal.telge.se/ledigt/detalj/id/043-16435")
        self.assertEqual(item.address, "Björknäsvägen 13")
        self.assertEqual((item.municipality, item.area), ("Södertälje", "Karlhov"))
        self.assertEqual((item.rent, item.sqm, item.rooms, item.floor), (7104, 61, 2, 3))
        self.assertEqual((item.published, item.deadline), ("2026-10-07", "2026-10-14"))
        self.assertTrue(item.requires_queue)

    def test_youth_flat_and_lottery(self):
        listings, _ = self.fetch(Vitec("telge", "Telge", TELGE, municipality="Södertälje"),
                                 "vitec_telge.json", TELGE)
        self.assertIn("ungdom", [i.type for i in listings.values()])
        self.assertIn(False, [i.requires_queue for i in listings.values()])  # ShowRandomSort

    def test_country_wide_portal_keeps_only_the_region(self):
        listings, _ = self.fetch(Vitec("victoriahem", "Victoriahem", VICTORIA), "vitec_victoriahem.json", VICTORIA)
        self.assertEqual([i.municipality for i in listings.values()], ["Södertälje"])  # Eskilstuna dropped

    def test_changed_format_raises(self):
        with self.assertRaises(ValueError):
            Vitec("x", "X", TELGE).parse({"status": "error"})
        with self.assertRaises(ValueError):
            Vitec("x", "X", TELGE).parse("<html>")

    def test_helpers(self):
        self.assertEqual(strip_town("Södertälje - Geneta"), "Geneta")
        self.assertEqual(strip_town("Karlhov"), "Karlhov")
        self.assertEqual(listing_type("1 rum och kokskåp, ung"), "ungdom")
        self.assertEqual(listing_type("2 rok Trygghetsboende"), "senior")
        self.assertEqual(listing_type("2 Rum och kök (R)"), "vanlig")


SETTINGS = {"apiBaseUrl": "https://api.example.se/", "xApiKey": "test-key", "appInstanceId": "test-client"}
CONFIG = {"market": {"types": [
    {"id": "residential", "displayName": "Bostad"},
    {"id": "parking", "displayName": "Fordonsplats"},
    {"id": "direct", "displayName": "Ledig direkt bostad"},
]}}


class MomentumHttp(FakeHttp):
    def __init__(self, detail_city="Kungsängen"):
        super().__init__({})
        self.detail_city = detail_city

    def get_json(self, url, params=None, headers=None):
        self.calls.append((url, params))
        self.request_count += 1
        if url.endswith("/assets/app-settings.json"):
            return SETTINGS
        assert headers["X-Api-Key"] == "test-key" and headers["Accept"] == "application/json"
        if url.endswith("v2/client/configuration"):
            return CONFIG
        if url.endswith("v2/market/objects"):
            if params["type"] == "parking":
                raise AssertionError("parking should never be fetched")
            return fixture("momentum_list.json") if params["type"] == "residential" else {"count": 0, "items": []}
        detail = fixture("momentum_detail.json")
        detail["location"]["address"]["city"] = self.detail_city
        return detail


@mock.patch.object(momentum, "DETAIL_DELAY", 0)
class MomentumTest(unittest.TestCase):
    def test_list_plus_detail(self):
        adapter = Momentum("ubh", "Upplands-Brohus", "minasidor.upplands-brohus.se", municipality="Upplands-Bro")
        adapter.memo = {}
        listings = {i.external_id: i for i in adapter.fetch(MomentumHttp(), {})}
        item = listings["VQVyYrtRXGpDh7vqGQj7DCrD"]
        self.assertEqual(item.url, "https://minasidor.upplands-brohus.se/market/residential/VQVyYrtRXGpDh7vqGQj7DCrD")
        self.assertEqual(item.address, "Kokillbacken 7")
        self.assertEqual((item.rent, item.sqm, item.rooms, item.floor), (12526, 65.2, 3, 2))
        self.assertEqual(item.municipality, "Upplands-Bro")
        self.assertEqual(item.deadline, "2026-10-14")
        self.assertTrue(item.requires_queue)
        self.assertFalse(item.pending)

    def test_details_are_reused(self):
        adapter = Momentum("ubh", "Upplands-Brohus", "minasidor.upplands-brohus.se", municipality="Upplands-Bro")
        adapter.memo = {}
        http = MomentumHttp()
        previous = {i.external_id: i.to_dict() for i in adapter.fetch(http, {})}
        http.calls.clear()
        again = adapter.fetch(http, previous)
        self.assertEqual(len(http.calls), 4)  # settings, configuration, two lists; no details
        self.assertTrue(all(i.floor == 2 for i in again))

    def test_outside_region_is_remembered(self):
        adapter = Momentum("byggvesta", "ByggVesta", "minasidor.byggvesta.se")  # no home municipality
        adapter.memo = {}
        http = MomentumHttp(detail_city="Linköping")
        self.assertEqual(adapter.fetch(http, {}), [])
        self.assertEqual(len(adapter.memo["outside"]), 2)
        http.calls.clear()
        adapter.fetch(http, {})
        self.assertFalse(any("/v2/market/objects/" in url for url, _ in http.calls))

    def test_helpers(self):
        self.assertEqual(floor("Våning 2"), 2)
        self.assertEqual(floor("Bottenvåning"), 0)
        self.assertIsNone(floor(None))
        self.assertEqual(ms_date("/Date(1792015140000)/"), "2026-10-14")


class Fast2Http(FakeHttp):
    def __init__(self, name):
        super().__init__({})
        self.name = name

    def get_text(self, url, params=None, headers=None):
        self.calls.append(url)
        self.request_count += 1
        return text_fixture(self.name)


class Fast2Test(unittest.TestCase):
    def test_sssb(self):
        listings = {i.external_id: i for i in Sssb().fetch(Fast2Http("fast2_sssb.jsonp"), {})}
        idun = listings["3622-9904-158"]
        self.assertEqual(idun.address, "Norra Stationsgatan 99")
        self.assertEqual((idun.municipality, idun.area), ("Stockholm", "Idun"))
        self.assertEqual((idun.rent, idun.sqm, idun.rooms, idun.floor), (6429, 19, 1, 1))
        self.assertEqual(idun.type, "student")
        self.assertEqual(idun.published, "2026-10-07")
        self.assertTrue(idun.url.startswith("https://minasidor.sssb.se/"))
        self.assertEqual(listings["6202-2102-1008"].municipality, "Solna")  # Kungshamra

    def test_skb(self):
        listings = {i.external_id: i for i in Skb().fetch(Fast2Http("fast2_skb.jsonp"), {})}
        item = listings["74963"]
        self.assertEqual(item.address, "Föllingebacken 25")
        self.assertEqual((item.municipality, item.area), ("Stockholm", "Tensta"))
        self.assertEqual((item.rent, item.sqm, item.rooms, item.floor), (11437, 118, 5, 1))
        self.assertTrue(item.url.startswith("https://www.skb.org/sok-ledigt/"))
        self.assertIn("Botkyrka", [i.municipality for i in listings.values()])  # Norsborg

    def test_changed_format_raises(self):
        with self.assertRaises(ValueError):
            unwrap_jsonp("<html>maintenance</html>")
        broken = Fast2Http("fast2_sssb.jsonp")
        broken.get_text = lambda url, params=None, headers=None: 'cb({"data":{}})'
        with self.assertRaises(ValueError):
            Sssb().fetch(broken, {})


if __name__ == "__main__":
    unittest.main()
