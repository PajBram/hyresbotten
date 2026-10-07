"""A small, polite HTTP client: one User-Agent, robots.txt, pacing and retries.

Standard library only, so the scraper has nothing to install.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .robots import Robots

USER_AGENT = "Hyresbotten/1.0 (+https://rastegar.se/hyra; bevakar lediga hyresratter)"
MAX_RETRY_AFTER = 30  # seconds; a longer wait means "come back next run"


def retry_after(value):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


class HttpError(Exception):
    pass


class RobotsDisallowed(HttpError):
    pass


class RateLimited(HttpError):
    pass


class Http:
    def __init__(self, min_interval=0.5, timeout=30, retries=2, user_agent=USER_AGENT):
        self.min_interval = min_interval  # seconds between requests to one host
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent
        self.request_count = 0
        self._last_request = {}
        self._robots = {}

    # -- public ----------------------------------------------------------

    def get_json(self, url, params=None):
        return json.loads(self.get_text(url, params))

    def post_json(self, url, payload):
        body = json.dumps(payload).encode()
        return json.loads(self._request(url, data=body, content_type="application/json"))

    def post_form(self, url, fields):
        body = urllib.parse.urlencode(fields).encode()
        return self._request(url, data=body, content_type="application/x-www-form-urlencoded")

    def get_text(self, url, params=None):
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self._request(url)

    # -- internals -------------------------------------------------------

    def _request(self, url, data=None, content_type=None):
        self._check_robots(url)
        headers = {"User-Agent": self.user_agent, "Accept": "application/json, text/html;q=0.9"}
        if content_type:
            headers["Content-Type"] = content_type
        last_error = None
        for attempt in range(self.retries + 1):
            self._pace(url)
            request = urllib.request.Request(url, data=data, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    self.request_count += 1
                    return response.read().decode(response.headers.get_content_charset() or "utf-8")
            except urllib.error.HTTPError as error:
                self.request_count += 1
                if error.code == 429:
                    last_error = RateLimited(f"HTTP 429 for {url}")
                    delay = retry_after(error.headers.get("Retry-After"))
                    if delay is None or delay > MAX_RETRY_AFTER:
                        raise last_error from error
                    time.sleep(delay)
                    continue
                last_error = HttpError(f"HTTP {error.code} for {url}")
                if error.code < 500:
                    raise last_error from error
            except (urllib.error.URLError, TimeoutError) as error:
                last_error = HttpError(f"{error} for {url}")
            time.sleep(2 * (attempt + 1))
        raise last_error

    def _pace(self, url):
        host = urllib.parse.urlsplit(url).netloc
        wait = self._last_request.get(host, 0) + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request[host] = time.monotonic()

    def _check_robots(self, url):
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        if not self._robots[origin].can_fetch(self.user_agent, url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")

    def _load_robots(self, origin):
        request = urllib.request.Request(f"{origin}/robots.txt", headers={"User-Agent": self.user_agent})
        self._pace(origin)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                self.request_count += 1
                text = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            self.request_count += 1
            # Same convention as RFC 9309: 4xx means there are no rules,
            # 5xx means the site is unsure, so stay out until next run.
            if error.code >= 500:
                return Robots(disallow_all=True)
            return Robots(allow_all=True)
        # Some sites answer /robots.txt with an HTML page; that holds no rules.
        return Robots("" if text.lstrip().startswith("<") else text)
