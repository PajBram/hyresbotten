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


# Stockholm city's 13 stadsdelsområden and the stadsdelar, postal towns and
# housing names that belong to each. Sources name areas at different levels
# ("Hägersten", "Hägerstensåsen", "Midsommarkransen"); grouping them lets a
# visitor pick "Hägersten-Älvsjö" and get all of them.
STOCKHOLM_DISTRICTS = {
    "Rinkeby-Kista": ["Rinkeby", "Kista", "Husby", "Akalla", "Kista Äng"],
    "Spånga-Tensta": ["Spånga", "Tensta", "Hjulsta", "Bromsten", "Flysta", "Solhem", "Sundby", "Lunda",
                      "Grön Bostad Järva"],
    "Hässelby-Vällingby": ["Vällingby", "Hässelby", "Hässelby gård", "Hässelby strand", "Hässelby villastad",
                           "Blackeberg", "Grimsta", "Råcksta", "Kälvesta", "Vinsta", "Nälsta", "Johannelund"],
    "Bromma": ["Bromma", "Abrahamsberg", "Alvik", "Beckomberga", "Brommaplan", "Eneby", "Höglandet", "Mariehäll",
               "Nockeby", "Nockebyhov", "Norra Ängby", "Södra Ängby", "Olovslund", "Riksby", "Smedslätten",
               "Stora Mossen", "Traneberg", "Ulvsunda", "Ålsten", "Äppelviken", "Åkeshov", "Bällsta", "Minneberg"],
    "Kungsholmen": ["Kungsholmen", "Kristineberg", "Stadshagen", "Fredhäll", "Lilla Essingen", "Stora Essingen",
                    "Marieberg", "Hornsberg"],
    "Norrmalm": ["Norrmalm", "Vasastaden", "Vasastan", "Hagastaden", "City", "Sibirien", "Lucidor", "Idun"],
    "Östermalm": ["Östermalm", "Ladugårdsgärdet", "Gärdet", "Norra Djurgården", "Norra Djurgårdsstaden",
                  "Hjorthagen", "Frihamnen", "Djurgården", "Ropsten", "Lappkärrsberget", "Jerum", "Nyponet"],
    "Södermalm": ["Södermalm", "Södra Hammarbyhamnen", "Hammarby Sjöstad", "Reimersholme", "Långholmen",
                  "Gamla stan"],
    "Enskede-Årsta-Vantör": ["Enskede", "Gamla Enskede", "Enskede gård", "Enskededalen", "Johanneshov", "Årsta",
                             "Bandhagen", "Högdalen", "Rågsved", "Hagsätra", "Stureby", "Örby"],
    "Skarpnäck": ["Skarpnäck", "Skarpnäcksfältet", "Bagarmossen", "Kärrtorp", "Björkhagen", "Hammarbyhöjden"],
    "Farsta": ["Farsta", "Farsta strand", "Fagersjö", "Gubbängen", "Hökarängen", "Larsboda", "Sköndal",
               "Tallkrogen", "Svedmyra"],
    "Hägersten-Älvsjö": ["Hägersten", "Hägerstensåsen", "Midsommarkransen", "Fruängen", "Västertorp", "Västberga",
                         "Mälarhöjden", "Aspudden", "Liljeholmen", "Gröndal", "Årstadal", "Årstaberg",
                         "Telefonplan", "Älvsjö", "Solberga", "Liseberg", "Långbro", "Herrängen", "Långsjö"],
    "Skärholmen": ["Skärholmen", "Bredäng", "Sätra", "Vårberg"],
}

_NAME_TO_DISTRICT = {
    name.lower(): district
    for district, names in STOCKHOLM_DISTRICTS.items()
    for name in names + [district]
}


def stockholm_district(area):
    """The stadsdelsområde of an area in Stockholm city, or None if unknown.

    Exact names first; then a known name inside a longer one, longest first,
    so "HållBo Kista Äng 2" lands in Rinkeby-Kista.
    """
    name = (place(area) or "").lower()
    if not name:
        return None
    if name in _NAME_TO_DISTRICT:
        return _NAME_TO_DISTRICT[name]
    for known in sorted(_NAME_TO_DISTRICT, key=len, reverse=True):
        if len(known) > 3 and f" {known} " in f" {name} ":
            return _NAME_TO_DISTRICT[known]
    return None
