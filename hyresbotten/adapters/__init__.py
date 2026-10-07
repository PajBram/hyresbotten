"""The list of sources. To add one, write an adapter and add it here."""

from .bostadsformedlingen import Bostadsformedlingen
from .heimstaden import Heimstaden
from .homeq import Homeq
from .rikshem import Rikshem
from .wallenstam import Wallenstam

# Akelius is not here on purpose: it sold all its Swedish homes to Heimstaden
# in 2021 and lists nothing in Sweden any more.


def all_adapters():
    return [
        Bostadsformedlingen(),
        Homeq(),
        Heimstaden(),
        Wallenstam(),
        Rikshem(),
    ]
