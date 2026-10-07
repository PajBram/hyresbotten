"""Postal towns in Stockholms län and the municipality (kommun) each belongs to.

Some landlords only give the postal town ("Åkersberga", "Västerhaninge").
The page groups listings by municipality, so adapters translate here. A town
missing from the table is not in Stockholms län as far as we know.
"""

from .model import place

MUNICIPALITY_TOWNS = {
    "Botkyrka": ["Tumba", "Tullinge", "Norsborg", "Hallunda", "Alby", "Fittja", "Grödinge", "Vårsta", "Storvreten"],
    "Danderyd": ["Danderyd", "Djursholm", "Stocksund", "Enebyberg"],
    "Ekerö": ["Ekerö", "Färentuna", "Stenhamra", "Drottningholm", "Skå", "Munsö", "Adelsö"],
    "Haninge": ["Haninge", "Handen", "Västerhaninge", "Jordbro", "Tungelsta", "Brandbergen", "Vendelsö", "Dalarö", "Muskö"],
    "Huddinge": ["Huddinge", "Flemingsberg", "Skogås", "Trångsund", "Stuvsta", "Segeltorp", "Vårby", "Kungens Kurva", "Sjödalen", "Snättringe", "Glömsta"],
    "Järfälla": ["Järfälla", "Jakobsberg", "Kallhäll", "Viksjö", "Barkarby", "Stäket"],
    "Lidingö": ["Lidingö"],
    "Nacka": ["Nacka", "Nacka Strand", "Saltsjö-Boo", "Saltsjöbaden", "Älta", "Orminge", "Fisksätra", "Sickla", "Boo", "Kummelnäs", "Saltsjö-Duvnäs"],
    "Norrtälje": ["Norrtälje", "Rimbo", "Hallstavik", "Grisslehamn", "Älmsta", "Edsbro", "Herräng"],
    "Nykvarn": ["Nykvarn"],
    "Nynäshamn": ["Nynäshamn", "Ösmo", "Sorunda", "Stora Vika"],
    "Salem": ["Salem", "Rönninge"],
    "Sigtuna": ["Sigtuna", "Märsta", "Rosersberg", "Arlandastad", "Steninge", "Stockholm-Arlanda"],
    "Sollentuna": ["Sollentuna", "Rotebro", "Häggvik", "Norrviken", "Edsberg", "Tureberg", "Helenelund"],
    "Solna": ["Solna", "Bergshamra", "Ulriksdal", "Frösunda", "Råsunda"],
    "Stockholm": ["Stockholm", "Bromma", "Hägersten", "Johanneshov", "Enskede", "Enskede Gård", "Enskededalen",
                  "Årsta", "Bandhagen", "Farsta", "Skarpnäck", "Bagarmossen", "Älvsjö", "Vällingby", "Hässelby",
                  "Spånga", "Kista", "Skärholmen", "Sköndal", "Stockholm-Globen", "Liljeholmen", "Hökarängen",
                  "Vårberg", "Rinkeby", "Tensta", "Akalla", "Husby", "Hägerstensåsen"],
    "Sundbyberg": ["Sundbyberg", "Rissne", "Hallonbergen", "Ursvik"],
    "Södertälje": ["Södertälje", "Järna", "Hölö", "Mölnbo", "Enhörna"],
    "Tyresö": ["Tyresö"],
    "Täby": ["Täby", "Näsbypark", "Arninge", "Gribbylund"],
    "Upplands Väsby": ["Upplands Väsby", "Väsby"],
    "Upplands-Bro": ["Upplands-Bro", "Bro", "Kungsängen"],
    "Vallentuna": ["Vallentuna", "Kårsta", "Lindholmen"],
    "Vaxholm": ["Vaxholm"],
    "Värmdö": ["Värmdö", "Gustavsberg", "Hemmesta", "Djurö", "Brunn", "Ingarö", "Värmdö-Evlinge"],
    "Österåker": ["Österåker", "Åkersberga", "Österskär", "Ljusterö"],
}

_TOWN_TO_MUNICIPALITY = {
    town.lower(): municipality
    for municipality, towns in MUNICIPALITY_TOWNS.items()
    for town in towns + [municipality]
}


def municipality_for(town):
    """The kommun a postal town belongs to, or None outside Stockholms län."""
    town = place(town)
    if not town:
        return None
    return _TOWN_TO_MUNICIPALITY.get(town.lower())
