# Eastron SDM Energy Meters

[English](README.md) | **Nederlands** | [Deutsch](README.de.md)

> Home Assistant custom integration voor Eastron SDM230/SDM630 energiemeters via Modbus (TCP, RTU-over-TCP of lokaal serieel), met een per-meter instelbaar poll-interval voor dashboards of snelle zero-export/load-balancing toepassingen.

## Wat dit doet

Dit is een custom Home Assistant-integratie voor Eastron **SDM230** (1-fase) en **SDM630** (3-fase) Modbus-energiemeters. Het praat via het Modbus-protocol met je meter(s) en zet elke uitlezing om in een native Home Assistant-sensor - spanning, stroom, actief/schijnbaar/reactief vermogen, power factor, frequentie, import/export-energie, THD%, demand-waarden en meer - meteen met de juiste device class, eenheid en ondersteuning voor langetermijnstatistieken.

## Wat dit biedt

- **Drie verbindingstypes**, te kiezen in de setup-wizard: een transparante RS485-naar-TCP gateway (bijv. Elfin EW11, USR-W610/TCP232), een native Modbus TCP-gateway (bijv. Waveshare RS485-to-ETH in Modbus TCP-modus), of een lokale USB-RS485-adapter die rechtstreeks in de Home Assistant-host zit.
- **Meerdere meters op één RS485-bus, één integratie.** Eén config entry vertegenwoordigt de fysieke gateway/verbinding; elke meter op die bus wordt als lichtgewicht sub-device toegevoegd, ofwel in een lus tijdens de eerste setup of later via "+ Apparaat toevoegen" - zonder de gateway-instellingen opnieuw in te voeren.
- **Eén gedeelde, geserialiseerde verbinding per gateway.** RS485 is half-duplex, dus alle meters op dezelfde bus delen één persistente Modbus-verbinding met een lock die garandeert dat er nooit meer dan één request tegelijk onderweg is - veilig van opzet, ook met meerdere meters in een daisychain.
- **Efficiënte register-uitlezing.** De volledige Eastron-registerkaart wordt per poll gegroepeerd tot zo min mogelijk Modbus-transacties, binnen de door de fabrikant gedocumenteerde limiet van 40 parameters/80 registers per request.
- **Per-meter poll-interval, volledig instelbaar (1-3600s, standaard 30s).** Laat het op de standaard voor normale monitoring en dashboards, of versnel een individuele meter tot enkele seconden wanneer je een zero-export- of load-balancing-controller voedt die bijna-realtime data nodig heeft - met een uitleg in de UI over de afweging (sneller pollen op één meter geeft meer verkeer voor elke meter op die bus).
- **Instelbare timing voor lastige hardware.** Een instelbare pauze tussen Modbus-requests helpt bij goedkope RS485-gateways/adapters die even tijd nodig hebben tussen transacties.
- **Herconfigureerbaar zonder historie te verliezen.** Zowel de gateway-verbinding als de individuele meter-instellingen (naam, model, adres, poll-interval) zijn achteraf aan te passen vanuit de Home Assistant-UI, zonder entiteiten te verwijderen en opnieuw toe te voegen.
- Gebouwd voor Home Assistant's moderne **config subentries**-architectuur en vereist Python 3.12+ (via de `tmodbus`-library).

---

Gebouwd op [tmodbus](https://github.com/wlcrs/tmodbus), dezelfde moderne, async Modbus-bibliotheek die Home Assistant's eigen "Modernizing Modbus"-architectuur (release 2026.9) gebruikt. Registeradressen en datatypes komen rechtstreeks uit de officiële Eastron Modbus-protocoldocumenten (SDM230Modbus V1.4, SDM630Modbus V1.8).

## Wat dit wel/niet doet

- **Uitlezen (read-only)**: spanning, stroom, vermogen (W/VA/VAr), power factor, frequentie, energie (import/export/totaal, per fase bij de SDM630), THD%, enzovoort — als sensoren, met de juiste `device_class` en `state_class` voor het Energy Dashboard.
- **Geen schrijffuncties**: de configuratie-holding-registers (netwerkinstellingen, pulse-output, reset) worden bewust niet blootgesteld — dat verkleint het risico dat een verkeerde automation de meter per ongeluk herconfigureert. Dit is met de bestaande `registers.py` eenvoudig uit te breiden als je dat later alsnog wilt.
- **Eén gedeelde verbinding per gateway**: meerdere meters op dezelfde RS485-daisychain/gateway delen automatisch onderliggend één Modbus-verbinding — belangrijk omdat RS485 half-duplex is en veel goedkope RS485-naar-TCP gateways sowieso maar één TCP-sessie tegelijk accepteren.
- **Uitgeschakelde entiteiten worden niet uitgelezen**: zet je in Instellingen → Entiteiten een sensor van een meter uit, dan laat die meter het bijbehorende register voortaan ook niet meer opvragen — minder Modbus-verkeer op de gedeelde bus, in plaats van alleen een verborgen entiteit. Dit werkt direct (geen herstart nodig) en een entiteit later weer aanzetten laat 'm ook weer meedraaien in de volgende poll.

## Installatie

1. Kopieer de map `custom_components/eastron_sdm` naar `<jouw HA-config>/custom_components/eastron_sdm` (via Samba, SSH, of de Studio Code Server add-on). Alternatief: voeg de repo toe als "Custom repository" in HACS (categorie Integration).
2. Herstart Home Assistant.
3. Instellingen → Apparaten & diensten → Integratie toevoegen → zoek "Eastron SDM".
4. Doorloop de flow hieronder — je configureert de gateway/RS485-bus **één keer**, en voegt daarna in dezelfde wizard net zoveel meters toe als je op die bus hebt.

## De config flow doorlopen

**Stap 1 — verbindingstype.** Kies wat past bij jouw hardware:

- *RS485-naar-TCP gateway, transparant* — de meest voorkomende situatie bij een goedkope RS485↔WiFi/LAN-adapter (Elfin EW11, USR-W610/TCP232, enz.) in "transparent"/"serial bridge"-modus: de gateway stuurt de ruwe RTU-bytes (inclusief CRC) 1-op-1 door over een TCP-socket. Begin hiermee als je niet zeker weet welk type gateway je hebt.
- *Modbus TCP gateway, native* — voor gateways die een echte Modbus-TCP-vertaling doen (MBAP-header, geen CRC op de kabel tussen HA en de gateway), bijv. een Waveshare RS485-to-ETH in Modbus TCP-modus.
- *Lokale seriële poort* — een USB-RS485 adapter die rechtstreeks in de machine zit waar Home Assistant op draait (bijv. `/dev/ttyUSB0`).

**Stap 2 — gateway-adres.** Host/IP + poort (netwerk) of het seriële device + baudrate/pariteit/stopbits/bytesize (serieel, standaard bij Eastron meestal 9600-N-1, maar controleer dit op de meter zelf). Dit vul je nu maar één keer in, voor de hele bus.

Bij beide varianten vind je hier ook **"Pauze tussen requests (ms)"** — een minimale stilte die na elk Modbus-antwoord wordt ingelast voor de volgende request wordt verstuurd. Standaard 30ms voor seriële/RTU-over-TCP verbindingen en 20ms voor een native Modbus TCP-gateway. `tmodbus` zelf gebruikt standaard 0ms; sommige goedkope RS485-gateways hebben na een antwoord even tijd nodig en reageren zonder pauze met timeouts of corrupte uitlezingen. Zie je dat gedrag, zet deze waarde dan hoger (bijv. 50-100ms); bij een stabiele bus kun je 'm juist verlagen voor snellere polling. Aanpassen kan achteraf via **Herconfigureren** zonder de meters kwijt te raken.

**Stap 3 — eerste meter.** Naam, model (SDM230 of SDM630), en het Modbus-adres (unit ID / slave ID, 1-247 — elke meter op de bus moet een uniek adres hebben).

**Stap 4 — nog een meter, of afronden.** Na elke meter krijg je de keuze "Nog een meter toevoegen" of "Installatie afronden". Zo voeg je in één doorlopende wizard alle meters op deze bus toe.

**Later nog een meter toevoegen?** Open de Eastron-gateway onder Instellingen → Apparaten & diensten en klik op "+ Apparaat toevoegen" op die integratiekaart — dat opent dezelfde metervragen, zonder de gateway-instellingen opnieuw in te voeren. Een meter verwijderen of herconfigureren (naam/model/adres/poll-interval) kan via het "..."-menu op dat apparaat.

## Hoe dit werkt (voor wie het wil snappen)

Eén config entry = één gateway/RS485-verbinding. Elke meter op die bus is daaronder een losse "meter"-subentry (met een eigen Device in Home Assistant), niet een aparte integratie — dat is wat het mogelijk maakt om meerdere meters in één wizard toe te voegen én later via "+" nog meer toe te voegen zonder de gateway-instellingen te herhalen.

`modbus_client.py` houdt per fysieke gateway precies één `tmodbus`-verbinding open, ongeacht hoeveel meters er op die bus zitten. Voor elke meter wordt via `AsyncModbusClient.for_unit_id()` een lichtgewicht client-object aangemaakt dat dezelfde onderliggende verbinding hergebruikt maar met het eigen Modbus-adres praat. Een `asyncio.Lock` per gateway zorgt dat er nooit twee requests tegelijk de kabel op gaan.

`registers.py` bevat de volledige registerkaart uit de Eastron-manuals, en groepeert aaneengesloten registers automatisch tot zo min mogelijk Modbus-requests (met een marge onder de door Eastron gedocumenteerde limiet van 40 parameters/80 registers per transactie), zodat elke polling-cyclus efficiënt blijft ook bij de uitgebreide SDM630-registerset.

`coordinator.py` bouwt die leesblokken niet uit de volledige registerkaart, maar uit alleen de registers waarvan de bijbehorende sensor-entiteit op dat moment ingeschakeld is (via de entity registry, met een `entity_registry_enabled_default`-fallback zolang een entiteit nog niet bestaat, bijv. bij een verse installatie). Een luisteraar op entity-registry-wijzigingen (opgezet ná het aanmaken van de sensoren in `__init__.py`) herberekent die blokken zodra je een entiteit aan- of uitzet, en vraagt meteen een nieuwe poll aan — dus dat werkt live, zonder herstart. `sensor.py` blijft wel voor élk register een entiteit aanmaken (ook uitgeschakelde), zodat je een eerder uitgezette entiteit gewoon weer kunt aanzetten zonder de integratie opnieuw te hoeven toevoegen.

## Bekende beperkingen / dingen om zelf te verifiëren

- Deze integratie draait inmiddels live tegen echte SDM230/SDM630-meters via een RS485-naar-TCP gateway (6 meters op één bus) — getest inclusief lange-termijn stabiliteit, gedeeld-bus-doorvoer bij korte poll-intervallen, en het aan/uitzetten van entiteiten. Test bij een nieuwe installatie alsnog eerst met één meter voor je de rest toevoegt, en kijk in Instellingen → Systeem → Logboeken als er iets niet meteen werkt.
- `tmodbus` vereist Python 3.12+; recente Home Assistant Core-versies voldoen hieraan.
- Sommige entiteiten (fasehoeken, THD%, per-fase demand/energie op de SDM630) staan standaard uitgeschakeld om de entiteitenlijst behapbaar te houden — zet ze aan via Instellingen → Entiteiten als je ze nodig hebt.
- De poll-interval is per meter instelbaar (1-3600s). Aanbevolen: laat dit op de standaard (30s) voor normale monitoring. Verlaag dit alleen voor een zero-export- of load-balancing-toepassing; bedenk dat alle requests serieel via één lock lopen, dus een snellere meter betekent meer verkeer voor iedereen op die bus. Ga niet veel onder de 3 seconden.
- Dit gebruikt Home Assistant's "config subentries"-systeem. Het toevoegen van meters is het best geverifieerd; het herconfigureren van een bestaande meter of gateway leunt op dezelfde API maar is iets minder zeker — mocht zo'n knop niet werken, dan is verwijderen en opnieuw toevoegen een prima werkende omweg (je entiteiten-ID's kunnen daarbij wel wijzigen).

## Icoon voor de integratie

Home Assistant haalt het integratie-icoon altijd op van [brands.home-assistant.io](https://brands.home-assistant.io/), ook voor custom_components, via `custom_integrations/eastron_sdm/icon.png` in de publieke [home-assistant/brands](https://github.com/home-assistant/brands) GitHub-repo. Er is geen manifest.json-veld of lokaal bestand waarmee een custom_component dat zelf kan overschrijven. Wil je het officiële Eastron-logo in dat overzicht zien, dan is een PR naar die brands-repo nodig (`icon.png` 256×256, transparante achtergrond). Tot die tijd tonen de sensoren gewone Material Design-iconen per type meting.

## Licentie

Apache-2.0 — Woon IoT BV, samen met René van der Gaag. https://github.com/wooniot/ha-modbus-bridge
