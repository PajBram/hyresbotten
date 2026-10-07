"""The normalized listing that every adapter produces."""

from dataclasses import asdict, dataclass
from typing import Optional

# Allowed values for Listing.type. Everything except "vanlig" counts as a
# special-purpose home that the page hides by default.
TYPES = ("vanlig", "ungdom", "student", "senior", "korttid", "annat")


@dataclass
class Listing:
    source: str                 # adapter name, e.g. "bostadsformedlingen"
    external_id: str            # the source's own id for the ad
    url: str                    # link to the original ad
    address: Optional[str] = None
    area: Optional[str] = None          # stadsdel / område
    municipality: Optional[str] = None  # kommun
    rent: Optional[int] = None          # kr/mån (lowest, for projects)
    sqm: Optional[float] = None         # lowest, for projects
    rooms: Optional[float] = None       # lowest, for projects
    floor: Optional[int] = None         # 0 = bottenvåning (lowest, for projects)
    requires_queue: Optional[bool] = None  # kräver kötid; None = unknown
    type: str = "vanlig"
    published: Optional[str] = None     # YYYY-MM-DD
    deadline: Optional[str] = None      # sista ansökningsdag, YYYY-MM-DD
    # New-build projects shown as one row: the fields above hold the low end
    # of each range and these hold the high end.
    units: int = 1
    rent_max: Optional[int] = None
    sqm_max: Optional[float] = None
    rooms_max: Optional[float] = None
    floor_max: Optional[int] = None
    # True while the adapter still owes a detail lookup (floor, queue, ...).
    pending: bool = False

    @property
    def key(self) -> str:
        return f"{self.source}:{self.external_id}"

    def to_dict(self) -> dict:
        if self.type not in TYPES:
            raise ValueError(f"unknown listing type {self.type!r}")
        data = {k: v for k, v in asdict(self).items() if v is not None}
        # Leave out the defaults that hold for almost every listing.
        if data["units"] == 1:
            del data["units"]
        if not data["pending"]:
            del data["pending"]
        return data


def to_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def clean(text) -> Optional[str]:
    if text is None:
        return None
    text = " ".join(str(text).split())
    return text or None


def place(text) -> Optional[str]:
    """A place name as people write it: "KUNGSÄNGEN" -> "Kungsängen"."""
    text = clean(text)
    if text and text.isupper():
        text = "-".join(part.capitalize() for part in text.split("-"))
        text = " ".join(word[:1].upper() + word[1:] for word in text.split(" "))
    return text
