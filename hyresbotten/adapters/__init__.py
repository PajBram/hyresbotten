"""The list of sources. To add one, write an adapter and add it here.

Landlords on a shared platform (Vitec, Momentum) only need a line below.
"""

from .bostadsformedlingen import Bostadsformedlingen
from .fast2 import Skb, Sssb
from .heimstaden import Heimstaden
from .homeq import Homeq
from .momentum import Momentum
from .rikshem import Rikshem
from .vitec import Vitec
from .wallenstam import Wallenstam

# Not here on purpose:
# - Akelius sold all its Swedish homes to Heimstaden in 2021.
# - Sigtuna Bostadsförmedling's data host (ponduspro.se) disallows all
#   crawling in robots.txt.
# - Qasa/Blocket Bostad: their first-hand ads are the same as on Homeq.
# - Stena, Ikano, Olov Lindgren, Botrygg: let through Homeq or
#   Bostadsförmedlingen.


def all_adapters():
    return [
        Bostadsformedlingen(),
        Homeq(),
        Heimstaden(),
        Wallenstam(),
        Rikshem(),
        # Vitec portals
        Vitec("telge", "Telge Bostäder", "https://kundportal.telge.se", municipality="Södertälje"),
        # The whole country in one 9 MB answer, about 70 of them in the region.
        Vitec("victoriahem", "Victoriahem", "https://minasidor.victoriahem.se", every_minutes=60),
        Vitec("sveafastigheter", "Sveafastigheter", "https://minasidor.sveafastigheter.se", every_minutes=30),
        Vitec("wahlin", "Wåhlin Fastigheter", "https://minasidor.wahlinfastigheter.se"),
        Vitec("tyreso", "Tyresö Bostadsförmedling", "https://www.bostadtyreso.se", municipality="Tyresö"),
        Vitec("forvaltaren", "Förvaltaren", "https://minsida.forvaltaren.se", municipality="Sundbyberg"),
        Vitec("haningebostader", "Haninge Bostäder", "https://minasidor.haningebostader.se",
              groups=("apartment", "studentapartment"), municipality="Haninge"),
        Vitec("sollentunahem", "Sollentunahem", "https://minasidor.sollentunahem.se", municipality="Sollentuna"),
        Vitec("varmdobostader", "Värmdö Bostäder", "https://varmdobo.se", municipality="Värmdö"),
        Vitec("ekerobostader", "Ekerö Bostäder", "https://minasidor.ekerobostader.se", municipality="Ekerö"),
        # Momentum portals
        Momentum("k2a", "K2A", "minasidor.k2a.se"),
        Momentum("byggvesta", "ByggVesta", "minasidor.byggvesta.se"),
        Momentum("johnmattson", "John Mattson", "minasidor.johnmattson.se"),
        Momentum("nynasbo", "Nynäshamnsbostäder", "minasidor.nynasbo.se", municipality="Nynäshamn"),
        Momentum("upplandsbrohus", "Upplands-Brohus", "minasidor.upplands-brohus.se", municipality="Upplands-Bro"),
        Momentum("jarfallahus", "Järfällahus", "minasidor.jarfallahus.se", municipality="Järfälla"),
        Momentum("armada", "Armada Bostäder", "minasidor.armadafast.se", municipality="Österåker"),
        Momentum("nykvarnsbostader", "Nykvarnsbostäder", "minasidor.nybo.se", municipality="Nykvarn"),
        # FAST2 widget portals
        Sssb(),
        Skb(),
    ]
