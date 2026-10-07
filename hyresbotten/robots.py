"""robots.txt matching as RFC 9309 describes it.

Python's urllib.robotparser applies the first rule that matches, but the
standard (and Google, Bing) let the longest matching rule win. That matters
for sites like Heimstaden, which disallow /wp-admin/ and then allow
/wp-admin/admin-ajax.php inside it.
"""

import re
import urllib.parse


class Robots:
    def __init__(self, text="", allow_all=False, disallow_all=False):
        self.allow_all = allow_all
        self.disallow_all = disallow_all
        self.groups = parse(text)

    def can_fetch(self, user_agent, url):
        if self.disallow_all:
            return False
        if self.allow_all:
            return True
        rules = self._rules_for(user_agent)
        parts = urllib.parse.urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        best = None  # (length, allowed)
        for allowed, pattern in rules:
            if pattern == "":
                continue  # "Disallow:" with no path allows everything
            if matches(pattern, path):
                candidate = (len(pattern), allowed)
                if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and allowed):
                    best = candidate
        return True if best is None else best[1]

    def _rules_for(self, user_agent):
        token = user_agent.split("/")[0].strip().lower()
        specific = [rules for agents, rules in self.groups if token in agents]
        if specific:
            return [rule for rules in specific for rule in rules]
        return [rule for agents, rules in self.groups if "*" in agents for rule in rules]


def parse(text):
    """Return [(set of user-agent tokens, [(allowed, pattern), ...]), ...]."""
    groups = []
    agents, rules = set(), []
    last_was_agent = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if not last_was_agent and agents:
                groups.append((agents, rules))
                agents, rules = set(), []
            agents.add(value.lower())
            last_was_agent = True
        elif field in ("allow", "disallow"):
            if agents:
                rules.append((field == "allow", value))
            last_was_agent = False
        else:
            last_was_agent = False
    if agents:
        groups.append((agents, rules))
    return groups


def matches(pattern, path):
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pattern.rstrip("$"))
    if pattern.endswith("$"):
        regex += "$"
    return re.match(regex, urllib.parse.unquote(path)) is not None or re.match(regex, path) is not None
