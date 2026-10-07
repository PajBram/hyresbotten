# Hyresbotten

Bevakar lediga **förstahandshyresrätter i Stockholms län** och visar dem på
[rastegar.se/hyra](https://rastegar.se/hyra/). Besökare filtrerar fram det som
passar och klickar vidare till originalannonsen för att söka.

Tjänsten bara läser öppna annonslistor. Den loggar aldrig in någonstans och
gör aldrig intresseanmälningar.

## Så hänger det ihop

```
GitHub Actions, var 15:e minut            GitHub Pages (repot PajBram/rastegar)
┌──────────────────────────────┐          ┌───────────────────────────────────┐
│ python -m hyresbotten        │          │ rastegar.se/hyra/                 │
│  ├ Bostadsförmedlingen (JSON)│  push    │  public/hyra/index.html           │
│  ├ Homeq (JSON-API)          │ ───────► │  hämtar listings.json från        │
│  ├ Heimstaden (JSON)         │  grenen  │  raw.githubusercontent.com och    │
│  ├ Wallenstam (JSON)         │  "data"  │  filtrerar i webbläsaren          │
│  └ Rikshem (RSS + annonssida)│          └───────────────────────────────────┘
└──────────────────────────────┘
```

- **Scrapern** är Python med enbart standardbiblioteket, så inget behöver installeras.
  Den läser förra körningens `state.json` från grenen `data`, kör varje källa,
  slår ihop resultatet och skriver tillbaka `state.json` och `listings.json`.
  Grenen `data` skrivs om som en enda commit varje gång och växer därför aldrig.
- **Sidan** är en statisk HTML-fil i sajtrepot, byggd på samma sätt som `/val/`.
  Den har inga beroenden och ingen backend.
- **Ingen Loopia, ingen databas och inga hemligheter.** rastegar.se ligger på
  GitHub Pages, så en PHP-sida går inte att köra på rastegar.se/hyra. Actions
  använder sin inbyggda `GITHUB_TOKEN` för att pusha datan, så du behöver inte
  lägga in någon GitHub Secret.

## Källor

| Källa | Hur | Anrop per körning | Kräver kötid | Sista ansökningsdag |
|---|---|---|---|---|
| Bostadsförmedlingen | `GET /AllaAnnonser/`, samma JSON som deras lista använder | 1 | Ja, utom "Bostad snabbt" | Ja |
| Homeq | `POST api.homeq.se/api/v3/search` (Stockholms län) + detaljer per ny annons | 1–2 + högst 60 detaljer | Ja vid köpoäng, nej vid "först till kvarn"/lottning | Finns inte |
| Heimstaden | WordPress `admin-ajax.php?action=hose_search`, vanliga + student | 2 | Ja (registreringsdatum är vägledande) | Finns inte |
| Wallenstam | Formulär-POST till "Lediga bostäder", svarar med JSON | 1 | Ja (egen kö) | Finns inte |
| Rikshem | RSS-flödet + annonssidan en gång per ny annons | 1 + nya annonser | Ja, om annonsen inte säger "först till kvarn" | Ja |

- **Akelius** är inte med. Bolaget sålde alla sina svenska bostäder till
  Heimstaden 2021 och har inga annonser i Sverige.
- **Rikshem** hyr ut sina lägenheter i Stockholm, Solna och Upplands Väsby via
  Bostadsförmedlingen, så de kommer redan med den vägen. Det som återstår i länet
  är främst Södertälje.
- **robots.txt** läses för varje värd innan första anropet och tolkas enligt
  RFC 9309, där den längsta matchande regeln vinner.
- **User-Agent:** `Hyresbotten/1.0 (+https://rastegar.se/hyra; …)`.
- **Takt:** minst 0,5 s mellan anrop till samma värd och extra paus mellan
  Homeqs detaljanrop. Om Homeq svarar 429 hämtas resten av detaljerna nästa körning.
- **Första körningen** hämtar Homeq-detaljerna för cirka 1 000 annonser i omgångar
  om 60. Det tar några timmar innan alla har våning och kökrav. Fram till dess
  står det "Våning hämtas" respektive "Kökrav hämtas" på sidan.

## Datamodell

Varje annons normaliseras till samma fält (se [`hyresbotten/model.py`](hyresbotten/model.py)):

| Fält | Betydelse |
|---|---|
| `source`, `external_id`, `url` | Källa, källans id och länk till originalannonsen |
| `address`, `area`, `municipality` | Gatuadress, område/stadsdel, kommun |
| `rent`, `sqm`, `rooms`, `floor` | Hyra kr/mån, kvm, antal rum, våning (0 = bottenvåning) |
| `requires_queue` | Kräver kötid: `true`, `false` eller saknas (okänt) |
| `type` | `vanlig`, `ungdom`, `student`, `senior`, `korttid` eller `annat` |
| `published`, `deadline` | Publiceringsdatum och sista ansökningsdag, om de finns |
| `first_seen`, `last_seen` | När annonsen först respektive senast sågs (ISO 8601, UTC) |
| `units`, `rent_max`, `sqm_max`, `rooms_max`, `floor_max` | Nyproduktion med flera lägenheter visas som en rad med spann |

**Borttagna annonser:** en annons som inte längre syns i en lyckad körning får
`gone_at` och döljs. Den sparas i 30 dagar och tas sedan bort. Kommer den
tillbaka visas den igen.

**När en källa går sönder** fångas felet och skrivs i loggen. Källan markeras
`ok: false` i datafilen, dess annonser ligger kvar som de var och sidan visar en
varning. Övriga källor fortsätter som vanligt, och Actions-körningen blir röd så
att du får ett mejl. Om en stor källa plötsligt ger under 30 % av sina tidigare
annonser, eller noll, behandlas det också som ett fel. Annars skulle ett ändrat
format dölja alla annonser.

## Köra lokalt

```bash
python3 -m unittest discover -s tests -t .
```

```bash
python3 -m hyresbotten --state out/state.json --out out
```

```bash
python3 -m hyresbotten --only bostadsformedlingen heimstaden
```

Varje adapter har tester med sparade exempelsvar i `tests/fixtures/`. De är
bantade, så bilder och annonstexter är borttagna. Testerna gör inga nätverksanrop.

Så förhandsgranskar du sidan med lokal data:

```bash
cd ~/rastegar.se && python3 build.py && cp ~/Hyresbotten/out/listings.json dist/hyra/
```

```bash
python3 -m http.server 8791 --directory ~/rastegar.se/dist
```

Öppna sedan <http://localhost:8791/hyra/>. På `localhost` läser sidan
`listings.json` bredvid sig själv i stället för från GitHub.

## Driftsätta

Det här gör du en gång. Allt sker i GitHub, och inget behöver göras hos Loopia.

1. **Skapa repot** `PajBram/hyresbotten` som *publikt*. Actions-minuter är gratis
   för publika repon; en körning var 15:e minut drar cirka 2 500 minuter i
   månaden, vilket är mer än gratiskvoten för privata repon.
2. **Pusha koden:**
   ```bash
   cd ~/Hyresbotten && git remote add origin https://github.com/PajBram/hyresbotten.git && git push -u origin main
   ```
3. **Kör första gången för hand:** gå till fliken *Actions*, välj **Scrape** och
   klicka **Run workflow**. Efter någon minut finns grenen `data` med
   `listings.json`. Därefter kör schemat av sig självt.
4. **Lägg ut sidan:** filen `public/hyra/index.html` i sajtrepot `~/rastegar.se`
   committas och pushas till `main`. Den vanliga deployen publicerar den då på
   rastegar.se/hyra/. Inget annat i sajten ändras. Vill du ha en länk i menyn
   lägger du till den i `content/site.json`.

**Bra att veta om GitHubs schema:**

- Körningarna kan bli försenade eller ibland hoppas över när GitHub har mycket
  att göra.
- I ett publikt repo stänger GitHub av schemalagda körningar efter 60 dagar utan
  aktivitet i repot. Du får ett mejl innan det händer. Klicka då *Enable
  workflow* under Actions, eller pusha en commit.

## Lägga till en källa

1. Skapa `hyresbotten/adapters/<namn>.py` med en klass som ärver `Adapter`.
   Sätt `name`, `label` och `homepage` och implementera `fetch(http, previous)`.
   Lägg tolkningen i vanliga funktioner som tar det råa svaret, så att de går
   att testa.
2. Använd `http.get_json` / `get_text` / `post_json` / `post_form`. De sköter
   User-Agent, robots.txt, takt och omförsök.
3. Behöver källan ett detaljanrop per annons, låna det du redan vet från
   `previous` (se Homeq och Rikshem) och sätt ett tak per körning.
4. Ange bara postort? Översätt med `places.municipality_for()` och släng
   annonser utanför Stockholms län.
5. Lägg till klassen i `hyresbotten/adapters/__init__.py`.
6. Spara ett bantat exempelsvar i `tests/fixtures/` och skriv ett test.

## Begränsningar

- Homeq och Heimstaden anger postort snarare än stadsdel. För Stockholms kommun
  blir "område" därför ibland postorten (t.ex. Bandhagen, Spånga) och ibland
  saknas det.
- För nyproduktion som visas som en rad gäller filtren om *någon* lägenhet i
  spannet kan passa.
- Rikshems annonser anger inte alltid typ. Korttid och "först till kvarn" känns
  igen bara när annonsens egna faktafält säger det.
- Rikshems uthyrningspolicy förbjuder tjänster som söker automatiskt åt
  någon. Den här tjänsten bevakar bara och hänvisar till källan.
