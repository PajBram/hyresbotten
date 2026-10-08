import json
import os
import unittest
from unittest import mock

from hyresbotten.adapters import heimstaden, rikshem, wallenstam
from hyresbotten.adapters.heimstaden import Heimstaden, split_area
from hyresbotten.adapters.rikshem import Rikshem
from hyresbotten.adapters.wallenstam import Wallenstam, parse_attributes
from hyresbotten.places import municipality_for

from .helpers import FIXTURES, FakeHttp, fixture


def text_fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


class HeimstadenHttp(FakeHttp):
    """Answers the regular and the student search from their saved samples."""

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        self.request_count += 1
        student = "properties_true_false[]=student" in params["query_string"]
        return fixture("heimstaden_search_student.json" if student else "heimstaden_search.json")


class HeimstadenTest(unittest.TestCase):
    def setUp(self):
        self.http = HeimstadenHttp({})
        self.listings = {i.external_id: i for i in Heimstaden().fetch(self.http, {})}

    def test_two_requests_regular_and_student(self):
        self.assertEqual(len(self.http.calls), 2)
        self.assertTrue(all(params["hose_data_detail_level"] == "level_2" for _, params in self.http.calls))

    def test_maps_fields(self):
        item = self.listings["6944162-1203"]
        self.assertEqual(item.address, "Rådjursvägen 30")
        self.assertEqual(item.municipality, "Haninge")
        self.assertEqual(item.area, "Västerhaninge")
        self.assertEqual((item.rent, item.sqm, item.rooms, item.floor), (10970, 76, 2, 2))
        self.assertTrue(item.url.startswith("https://heimstaden.com/se/sok-lagenhet/"))
        self.assertTrue(item.requires_queue)
        self.assertEqual(item.type, "vanlig")

    def test_postal_town_decides_municipality(self):
        # area_name says "Stockholm - Åkersberga", but Åkersberga is Österåker.
        akersberga = [i for i in self.listings.values() if i.area == "Åkersberga"]
        for item in akersberga:
            self.assertEqual(item.municipality, "Österåker")

    def test_only_stockholm_region_and_student_type(self):
        students = [i for i in self.listings.values() if i.type == "student"]
        self.assertEqual(len(students), 1)  # the Umeå one is dropped
        self.assertEqual(students[0].municipality, "Huddinge")

    def test_split_area(self):
        self.assertEqual(split_area("Täby - Tibble"), ("Täby", "Tibble"))
        self.assertEqual(split_area("Järfälla- Jakobsberg"), ("Järfälla", "Jakobsberg"))
        self.assertEqual(split_area("Upplands-Bro - Kungsängen"), ("Upplands-Bro", "Kungsängen"))

    def test_changed_format_raises(self):
        class Broken(HeimstadenHttp):
            def get_json(self, url, params=None):
                return {"html": "<div>new search</div>"}
        with self.assertRaises(ValueError):
            Heimstaden().fetch(Broken({}), {})


class WallenstamHttp(FakeHttp):
    def post_form(self, url, fields):
        self.calls.append((url, fields))
        self.request_count += 1
        return json.dumps(self.responses[url])


class WallenstamTest(unittest.TestCase):
    def setUp(self):
        raw = fixture("wallenstam_lediga.json")
        self.http = WallenstamHttp({wallenstam.PAGE: raw})
        self.listings = Wallenstam().fetch(self.http, {})

    def test_sends_only_filled_in_fields(self):
        self.assertEqual(self.http.calls, [(wallenstam.PAGE, {"Status": "Available", "Region": "Stockholm"})])

    def test_rental_project_kept_condo_project_dropped(self):
        ids = [i.external_id for i in self.listings]
        self.assertIn("p-47877", ids)      # Årstaberg, hyresrätt under uthyrning
        self.assertNotIn("p-53508", ids)   # Vida Årstaberg, bostadsrätt
        # The Göteborg flats in the sample are outside the region.
        self.assertEqual(ids, ["p-47877"])
        project = self.listings[0]
        self.assertEqual(project.area, "Årstaberg")
        self.assertEqual(project.municipality, "Stockholm")

    def test_flat_attributes(self):
        self.assertEqual(parse_attributes(["1 rok", "40 m²", "3:e våningen"]), (1, 40, 3))
        self.assertEqual(parse_attributes(["2 rok", "55,5 m²", "Bottenvåning"]), (2, 55.5, 0))

    def test_flat_in_stockholm(self):
        raw = fixture("wallenstam_lediga.json")
        flat = dict(next(o for o in raw["Objects"] if o["PageType"] == "BostadPageModel"), City="Stockholm", Area="Hagastaden")
        item = wallenstam.parse_objects([flat])[0]
        self.assertEqual((item.rent, item.sqm, item.rooms, item.floor), (7195, 40, 1, 3))
        self.assertEqual(item.municipality, "Stockholm")
        self.assertTrue(item.url.startswith("https://www.wallenstam.se/sv/bostader/lediga-bostader/"))

    def test_empty_stockholm_is_fine_but_changed_format_raises(self):
        self.assertEqual(Wallenstam().fetch(WallenstamHttp({wallenstam.PAGE: {"Filters": [], "Objects": []}}), {}), [])
        with self.assertRaises(ValueError):
            Wallenstam().fetch(WallenstamHttp({wallenstam.PAGE: {"Items": []}}), {})


class RikshemHttp(FakeHttp):
    def get_text(self, url, params=None):
        self.calls.append(url)
        self.request_count += 1
        if url == rikshem.FEED:
            return text_fixture("rikshem_apartment.xml")
        return text_fixture("rikshem_detail.html")


@mock.patch.object(rikshem, "DETAIL_DELAY", 0)
class RikshemTest(unittest.TestCase):
    def test_keeps_only_stockholms_lan_and_reads_details(self):
        http = RikshemHttp({})
        listings = Rikshem().fetch(http, {})
        self.assertEqual(len(listings), 3)  # Östersund dropped
        item = next(i for i in listings if i.external_id == "6901-13916")
        self.assertEqual(item.url, "https://minasidor.rikshem.se/ledigt/detalj/id/6901-13916")
        self.assertEqual(item.municipality, "Södertälje")
        self.assertEqual(item.area, "Blombacka")
        self.assertEqual((item.rooms, item.sqm, item.rent), (1, 38, 7709))
        self.assertEqual(item.floor, 0)
        self.assertEqual(item.deadline, "2026-10-11")
        self.assertTrue(item.requires_queue)
        self.assertIsNotNone(item.published)
        self.assertEqual(len(http.calls), 1 + 3)  # feed + one detail per ad

    def test_first_come_only_counts_in_the_ad_facts(self):
        listing = rikshem.parse_feed(text_fixture("rikshem_apartment.xml"))[0]
        area_text = '<div id="x_lblAreaInfoAbstract">Parkering: först till kvarn.</div>'
        rikshem.apply_detail(listing, text_fixture("rikshem_detail.html") + area_text)
        self.assertTrue(listing.requires_queue)
        fact = '<span id="x_lblInfoText">Uthyrs enligt Först till kvarn</span>'
        rikshem.apply_detail(listing, text_fixture("rikshem_detail.html") + fact)
        self.assertFalse(listing.requires_queue)

    def test_details_are_not_fetched_twice(self):
        http = RikshemHttp({})
        previous = {i.external_id: i.to_dict() for i in Rikshem().fetch(http, {})}
        http.calls.clear()
        again = Rikshem().fetch(http, previous)
        self.assertEqual(http.calls, [rikshem.FEED])
        self.assertTrue(all(i.deadline == "2026-10-11" for i in again))

    def test_changed_feed_raises(self):
        broken = text_fixture("rikshem_apartment.xml").replace("kvm, hyra:", "m2 – pris")
        with self.assertRaises(ValueError):
            rikshem.parse_feed(broken)


class PlacesTest(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(municipality_for("Åkersberga"), "Österåker")
        self.assertEqual(municipality_for("RÖNNINGE"), "Salem")
        self.assertEqual(municipality_for("Märsta"), "Sigtuna")
        self.assertEqual(municipality_for("Solna"), "Solna")
        self.assertIsNone(municipality_for("Östersund"))

    def test_stockholm_districts(self):
        from hyresbotten.places import stockholm_district
        self.assertEqual(stockholm_district("Hägersten"), "Hägersten-Älvsjö")
        self.assertEqual(stockholm_district("Midsommarkransen"), "Hägersten-Älvsjö")
        self.assertEqual(stockholm_district("HållBo Kista Äng 2"), "Rinkeby-Kista")
        self.assertEqual(stockholm_district("Hässelby gård"), "Hässelby-Vällingby")
        self.assertEqual(stockholm_district("FARSTA STRAND"), "Farsta")
        self.assertIsNone(stockholm_district("Kistagången"))  # no partial-word matches
        self.assertIsNone(stockholm_district(None))


if __name__ == "__main__":
    unittest.main()
