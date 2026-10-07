import json
import os

from hyresbotten.http import RateLimited

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return json.load(handle)


class FakeHttp:
    """Answers requests from a dict of URL -> response; records every call."""

    def __init__(self, responses, rate_limit_after=None):
        self.responses = responses
        self.calls = []
        self.request_count = 0
        self.rate_limit_after = rate_limit_after

    def _answer(self, url):
        self.calls.append(url)
        self.request_count += 1
        if self.rate_limit_after is not None and len(self.calls) > self.rate_limit_after:
            raise RateLimited(f"HTTP 429 for {url}")
        if url not in self.responses:
            raise AssertionError(f"unexpected request to {url}")
        answer = self.responses[url]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def get_json(self, url, params=None):
        return self._answer(url)

    def post_json(self, url, payload):
        return self._answer(url)
