import unittest

from hyresbotten.http import USER_AGENT
from hyresbotten.robots import Robots

HEIMSTADEN = """User-agent: *
Disallow: /wp-admin/
Allow: /wp-admin/admin-ajax.php
"""


class RobotsTest(unittest.TestCase):
    def test_longest_match_wins(self):
        robots = Robots(HEIMSTADEN)
        self.assertTrue(robots.can_fetch(USER_AGENT, "https://x.se/wp-admin/admin-ajax.php?action=a"))
        self.assertFalse(robots.can_fetch(USER_AGENT, "https://x.se/wp-admin/options.php"))
        self.assertTrue(robots.can_fetch(USER_AGENT, "https://x.se/se/sok-lagenhet/"))

    def test_specific_group_beats_star(self):
        robots = Robots("User-agent: *\nDisallow: /\n\nUser-agent: Hyresbotten\nDisallow: /private\n")
        self.assertTrue(robots.can_fetch(USER_AGENT, "https://x.se/listings"))
        self.assertFalse(robots.can_fetch(USER_AGENT, "https://x.se/private/1"))

    def test_wildcards_and_end_anchor(self):
        robots = Robots("User-agent: *\nDisallow: /*.json$\nDisallow: /search*q=\n")
        self.assertFalse(robots.can_fetch(USER_AGENT, "https://x.se/data/all.json"))
        self.assertTrue(robots.can_fetch(USER_AGENT, "https://x.se/data/all.json?v=2"))
        self.assertFalse(robots.can_fetch(USER_AGENT, "https://x.se/search?q=stockholm"))

    def test_empty_disallow_allows_everything(self):
        self.assertTrue(Robots("User-agent: *\nDisallow:\n").can_fetch(USER_AGENT, "https://x.se/a"))

    def test_disallow_all(self):
        self.assertFalse(Robots(disallow_all=True).can_fetch(USER_AGENT, "https://x.se/"))


if __name__ == "__main__":
    unittest.main()
