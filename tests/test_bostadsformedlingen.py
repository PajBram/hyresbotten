import unittest

from hyresbotten.adapters.bostadsformedlingen import Bostadsformedlingen, parse_listings

from .helpers import FakeHttp, fixture


class BostadsformedlingenTest(unittest.TestCase):
    def setUp(self):
        self.raw = fixture("bostadsformedlingen_alla_annonser.json")
        self.listings = {item.external_id: item for item in parse_listings(self.raw)}

    def test_parses_every_ad(self):
        self.assertEqual(len(self.listings), len(self.raw))

    def test_regular_ground_floor_flat(self):
        item = self.listings["202516873"]
        self.assertEqual(item.url, "https://bostad.stockholm.se/bostad/202516873/")
        self.assertEqual(item.address, "Fornminnesvägen 1C")
        self.assertEqual(item.area, "Vallentuna C")
        self.assertEqual(item.municipality, "Vallentuna")
        self.assertEqual((item.rent, item.sqm, item.rooms, item.floor), (11998, 33, 1.5, 0))
        self.assertEqual(item.type, "vanlig")
        self.assertTrue(item.requires_queue)
        self.assertEqual(item.published, "2026-10-03")
        self.assertEqual(item.deadline, "2026-10-11")

    def test_project_with_many_flats_carries_ranges(self):
        item = next(i for i in self.listings.values() if i.units > 1)
        self.assertIsNotNone(item.rent)
        self.assertLessEqual(item.rent, item.rent_max)
        self.assertLessEqual(item.sqm, item.sqm_max)

    def test_bostad_snabbt_needs_no_queue_time(self):
        snabbt = [a for a in self.raw if a["BostadSnabbt"]]
        self.assertTrue(snabbt)
        for ad in snabbt:
            self.assertFalse(self.listings[str(ad["LägenhetId"])].requires_queue)

    def test_special_housing_types(self):
        by_kind = {a["Lagenhetstyp"]: self.listings[str(a["LägenhetId"])].type for a in self.raw}
        self.assertEqual(by_kind["Studentlägenhet"], "student")
        self.assertEqual(by_kind["Ungdomslägenhet"], "ungdom")
        self.assertEqual(by_kind["UngdomKorttid"], "korttid")
        self.assertEqual(by_kind["SeniorbostadPlus65"], "senior")
        self.assertEqual(by_kind["Korttidskontrakt"], "korttid")

    def test_fetch_uses_the_json_endpoint_once(self):
        http = FakeHttp({"https://bostad.stockholm.se/AllaAnnonser/": self.raw})
        Bostadsformedlingen().fetch(http, {})
        self.assertEqual(http.calls, ["https://bostad.stockholm.se/AllaAnnonser/"])

    def test_changed_format_raises(self):
        with self.assertRaises(ValueError):
            parse_listings({"unexpected": "object"})
        with self.assertRaises(KeyError):
            parse_listings([{"Gatuadress": "no id"}])


if __name__ == "__main__":
    unittest.main()
