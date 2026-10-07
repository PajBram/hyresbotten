"""What every source adapter looks like.

An adapter knows one source. `fetch` talks to the network and returns the
source's current listings; keep the parsing in plain functions that take the
raw response, so the tests can feed them saved samples.
"""

from typing import Dict, List

from ..http import Http
from ..model import Listing


class Adapter:
    name = ""   # stable key, stored with every listing
    label = ""  # shown on the page
    homepage = ""
    # Small sources can legitimately have nothing out; big ones returning
    # nothing almost certainly broke.
    allow_empty = False

    def fetch(self, http: Http, previous: Dict[str, dict]) -> List[Listing]:
        """Return every listing the source shows right now.

        `previous` maps external_id to the stored record from earlier runs, so
        an adapter can reuse details it already looked up instead of asking
        the source again.
        """
        raise NotImplementedError
