# Eastron SDM Energy Meters

[English](README.md) | [Nederlands](README.nl.md) | **Deutsch**

> Home-Assistant-Custom-Integration für Eastron-SDM230/SDM630/SDM120/SDM72Modbus-V2-Energiezähler über Modbus (TCP, RTU-over-TCP oder lokal seriell), mit Abfrageintervallen pro Zähler für Dashboards oder schnelle Nulleinspeisungs-/Lastausgleichs-Anwendungen.

## Was sie tut

Dies ist eine Custom-Integration für Home Assistant für Eastron-SDM230- (einphasig), SDM630- (dreiphasig), SDM120- (einphasig, kompakt) und SDM72Modbus-V2- (dreiphasig, kompakt) Modbus-Energiezähler. Sie kommuniziert mit Ihrem/Ihren Zähler(n) über das Modbus-Protokoll und stellt jeden Messwert als nativen Home-Assistant-Sensor bereit - Spannung, Strom, Wirk-/Schein-/Blindleistung, Leistungsfaktor, Frequenz, Import-/Exportenergie, THD%, Demand-Werte und mehr - mit der richtigen Device-Class, Einheit und Unterstützung für Langzeitstatistiken von Haus aus.

## Was sie bietet

- Drei Verbindungstypen, im Einrichtungsassistenten auswählbar: ein transparentes RS485-auf-TCP-Gateway (z. B. Elfin EW11, USR-W610/TCP232), ein natives Modbus-TCP-Gateway (z. B. Waveshare RS485-to-ETH im Modbus-TCP-Modus) oder ein lokaler USB-RS485-Adapter, direkt am Home-Assistant-Host angeschlossen.
- Mehrere Zähler an einem RS485-Bus, eine Integration. Ein Konfigurationseintrag repräsentiert das physische Gateway/die Verbindung; jeder Zähler an diesem Bus wird als leichtgewichtiges Sub-Gerät hinzugefügt, entweder in einer Schleife bei der Ersteinrichtung oder später über "+ Gerät hinzufügen" - ohne die Gateway-Einstellungen jedes Mal erneut eingeben zu müssen.
- Eine gemeinsame, serialisierte Verbindung pro Gateway. RS485 ist Halbduplex, daher teilen sich alle Zähler am selben Bus eine einzige dauerhafte Modbus-Verbindung mit einer Sperre, die garantiert, dass immer nur eine Anfrage gleichzeitig unterwegs ist - von Natur aus sicher, selbst wenn mehrere Zähler in Reihe geschaltet sind.
- Effiziente Registerlesevorgänge. Die vollständige Eastron-Registerkarte wird pro Abfrage in so wenige Modbus-Transaktionen wie möglich gruppiert, unter Beachtung des Herstellerlimits von 40 Parametern/80 Registern pro Anfrage.
- Abfrageintervall pro Zähler, vollständig konfigurierbar (1-3600s, Standard 30s). Belassen Sie es für normale Überwachung und Dashboards beim Standard, oder beschleunigen Sie einen einzelnen Zähler auf bis zu wenige Sekunden, wenn Sie einen Nulleinspeisungs- oder Lastausgleichsregler mit nahezu Echtzeitdaten versorgen - mit einem Hinweis in der Oberfläche, der den Kompromiss erklärt (schnelleres Abfragen an einem Zähler erzeugt mehr Verkehr für jeden Zähler an diesem Bus).
- Einstellbares Timing für störanfällige Hardware. Eine konfigurierbare Pause zwischen Modbus-Anfragen hilft bei günstigen RS485-Gateways/-Adaptern, die zwischen Transaktionen einen Moment zur Erholung brauchen.
- Rekonfigurierbar ohne Verlust der Historie. Sowohl die Gateway-Verbindung als auch die Einstellungen einzelner Zähler (Name, Modell, Adresse, Abfrageintervall) können nachträglich über die Home-Assistant-Oberfläche geändert werden, ohne Entitäten zu entfernen und neu anzulegen.
- Für Home Assistants moderne Config-Subentries-Architektur gebaut und erfordert Python 3.12+ (über die tmodbus-Bibliothek).

---

Eine Custom-Integration für Home Assistant, um mehrere Eastron-SDM230- (einphasig) und/oder SDM630- (dreiphasig) Modbus-Energiezähler direkt über RS485 auszulesen, ohne Cloud-Abhängigkeit. Aufgebaut auf [tmodbus](https://github.com/wlcrs/tmodbus), derselben modernen, asynchronen Modbus-Bibliothek, die auch Home Assistants eigene "Modernizing Modbus"-Architektur (Release 2026.9) verwendet. Registeradressen und Datentypen stammen direkt aus den offiziellen Eastron-Modbus-Protokolldokumenten (SDM230Modbus V1.4, SDM630Modbus V1.8, SDM120-Modbus-Protokoll, SDM72DM-V2-Benutzerhandbuch V1.1). Die Registerkarten für SDM120 und SDM72Modbus-V2 wurden noch nicht an echter Hardware getestet - bitte melden, falls eine Abweichung auffällt.

## Was dies tut/nicht tut

- Auslesen (nur lesend): Spannung, Strom, Leistung (W/VA/VAr), Leistungsfaktor, Frequenz, Energie (Import/Export/Gesamt, pro Phase beim SDM630), THD% usw. - als Sensoren, mit der richtigen `device_class` und `state_class` für das Energy-Dashboard.
- Keine Schreibfunktionen: Die Konfigurations-Holding-Register (Netzwerkeinstellungen, Impulsausgang, Reset) werden bewusst nicht bereitgestellt - das verringert das Risiko, dass eine fehlerhafte Automation den Zähler versehentlich neu konfiguriert. Dies lässt sich mit der vorhandenen `registers.py` leicht erweitern, falls Sie das später doch wollen.
- Eine gemeinsame Verbindung pro Gateway: Mehrere Zähler an derselben RS485-Reihenschaltung/demselben Gateway teilen sich automatisch im Hintergrund eine einzige Modbus-Verbindung - wichtig, weil RS485 Halbduplex ist und viele günstige RS485-auf-TCP-Gateways ohnehin nur eine TCP-Sitzung gleichzeitig akzeptieren.
- Deaktivierte Entitäten werden nicht abgefragt: Deaktivieren Sie den Sensor eines Zählers unter Einstellungen -> Entitäten, fragt dieser Zähler das zugehörige Register ab sofort auch nicht mehr ab - weniger Modbus-Verkehr auf dem gemeinsamen Bus, statt nur einer verborgenen Entität. Das wirkt sofort (kein Neustart nötig), und eine Entität später wieder zu aktivieren nimmt sie auch wieder in die nächste Abfrage auf.

## Installation

1. Kopieren Sie den Ordner `custom_components/eastron_sdm` nach `<Ihre HA-Konfiguration>/custom_components/eastron_sdm` (via Samba, SSH oder das Add-on Studio Code Server). Alternativ: Fügen Sie das Repository als "Custom repository" in HACS hinzu (Kategorie Integration).
2. Starten Sie Home Assistant neu.
3. Einstellungen -> Geräte & Dienste -> Integration hinzufügen -> nach "Eastron SDM" suchen.
4. Durchlaufen Sie den Ablauf unten - Sie konfigurieren das Gateway/den RS485-Bus einmal und fügen danach im selben Assistenten so viele Zähler hinzu, wie Sie an diesem Bus haben.

## Den Konfigurationsablauf durchlaufen

**Schritt 1 - Verbindungstyp.** Wählen Sie, was zu Ihrer Hardware passt:

- *RS485-auf-TCP-Gateway, transparent* - die häufigste Situation bei einem günstigen RS485<->WLAN/LAN-Adapter (Elfin EW11, USR-W610/TCP232 usw.) im Modus "transparent"/"serial bridge": Das Gateway leitet die rohen RTU-Bytes (inklusive CRC) eins zu eins über einen TCP-Socket weiter. Beginnen Sie hiermit, wenn Sie nicht sicher sind, welchen Gateway-Typ Sie haben.
- *Modbus-TCP-Gateway, nativ* - für Gateways, die eine echte Modbus-TCP-Übersetzung durchführen (MBAP-Header, kein CRC auf der Leitung zwischen HA und Gateway), z. B. ein Waveshare RS485-to-ETH im Modbus-TCP-Modus.
- *Lokale serielle Schnittstelle* - ein USB-RS485-Adapter, der direkt in der Maschine steckt, auf der Home Assistant läuft (z. B. `/dev/ttyUSB0`).

**Schritt 2 - Gateway-Adresse.** Host/IP + Port (Netzwerk) oder das serielle Gerät + Baudrate/Parität/Stoppbits/Byte-Größe (seriell, der Eastron-Standard ist meist 9600-N-1, prüfen Sie dies aber am Zähler selbst). Dies geben Sie nun nur einmal ein, für den gesamten Bus.

Bei beiden Varianten finden Sie hier auch **"Pause zwischen Anfragen (ms)"** - eine minimale Stille, die nach jeder Modbus-Antwort eingefügt wird, bevor die nächste Anfrage gesendet wird. Standard 30ms für serielle/RTU-over-TCP-Verbindungen und 20ms für ein natives Modbus-TCP-Gateway. `tmodbus` selbst verwendet standardmäßig 0ms; manche günstigen RS485-Gateways brauchen nach einer Antwort einen Moment und reagieren ohne Pause mit Timeouts oder fehlerhaften Messwerten. Sehen Sie dieses Verhalten, erhöhen Sie diesen Wert (z. B. 50-100ms); bei einem stabilen Bus können Sie ihn dagegen verringern für schnelleres Abfragen. Eine Anpassung ist nachträglich über **Rekonfigurieren** möglich, ohne die Zähler zu verlieren.

**Schritt 3 - erster Zähler.** Name, Modell (SDM230, SDM630, SDM120 oder SDM72Modbus V2) und die Modbus-Adresse (Unit ID / Slave ID, 1-247 - jeder Zähler am Bus muss eine eindeutige Adresse haben).

**Schritt 4 - weiterer Zähler oder abschließen.** Nach jedem Zähler erhalten Sie die Auswahl "Weiteren Zähler hinzufügen" oder "Einrichtung abschließen".

**Später noch einen Zähler hinzufügen?** Öffnen Sie das Eastron-Gateway unter Einstellungen -> Geräte & Dienste und klicken Sie auf "+ Gerät hinzufügen" auf dieser Integrationskarte - das öffnet dieselben Zählerfragen, ohne die Gateway-Einstellungen erneut einzugeben. Einen Zähler entfernen oder rekonfigurieren können Sie über das "..."-Menü an diesem Gerät.

## Wie dies funktioniert

Ein Konfigurationseintrag = eine Gateway-/RS485-Verbindung. Jeder Zähler an diesem Bus ist darunter ein eigener "Zähler"-Subentry (mit einem eigenen Device in Home Assistant), keine separate Integration. `modbus_client.py` hält pro physischem Gateway genau eine `tmodbus`-Verbindung offen, unabhängig davon, wie viele Zähler an diesem Bus hängen. Für jeden Zähler wird über `AsyncModbusClient.for_unit_id()` ein leichtgewichtiges Client-Objekt erzeugt, das dieselbe zugrunde liegende Verbindung wiederverwendet, aber mit der eigenen Modbus-Adresse kommuniziert. Ein `asyncio.Lock` pro Gateway sorgt dafür, dass nie zwei Anfragen gleichzeitig auf die Leitung gehen. `registers.py` enthält die vollständige Registerkarte aus den Eastron-Handbüchern und gruppiert zusammenhängende Register automatisch zu so wenigen Modbus-Anfragen wie möglich (mit einem Spielraum unter dem Limit von 40 Parametern/80 Registern pro Transaktion).

`coordinator.py` baut diese Leseblöcke nicht aus der vollständigen Registerkarte, sondern nur aus den Registern, deren Sensor-Entität gerade aktiviert ist (über die Entity Registry, mit einem `entity_registry_enabled_default`-Fallback, solange eine Entität noch nicht existiert). Ein Listener auf Entity-Registry-Änderungen (eingerichtet, nachdem die Sensoren in `__init__.py` erstellt wurden) berechnet diese Blöcke neu, sobald Sie eine Entität aktivieren oder deaktivieren, und fordert sofort eine neue Abfrage an - das funktioniert also live, ohne Neustart. `sensor.py` erstellt weiterhin für jedes Register eine Entität (auch deaktivierte), sodass eine zuvor deaktivierte Entität einfach wieder aktiviert werden kann, ohne die Integration neu hinzuzufügen.

## Bekannte Einschränkungen / selbst zu prüfende Punkte

- Diese Integration läuft live gegen echte SDM230/SDM630-Zähler über ein RS485-auf-TCP-Gateway (6 Zähler an einem Bus) - getestet einschließlich Langzeitstabilität, Durchsatz des gemeinsamen Busses bei kurzen Abfrageintervallen und dem Aktivieren/Deaktivieren von Entitäten. Testen Sie bei einer neuen Installation dennoch zuerst mit einem einzelnen Zähler, bevor Sie die übrigen hinzufügen, und schauen Sie in Einstellungen -> System -> Protokolle, falls etwas nicht sofort funktioniert.
- `tmodbus` erfordert Python 3.12+; aktuelle Home-Assistant-Core-Versionen erfüllen dies.
- Einige Entitäten (Phasenwinkel, THD%, Demand/Energie pro Phase beim SDM630) sind standardmäßig deaktiviert, um die Entitätenliste überschaubar zu halten - aktivieren Sie sie über Einstellungen -> Entitäten, wenn Sie sie benötigen.
- Das Abfrageintervall ist pro Zähler einstellbar (1-3600s). Empfehlung: Belassen Sie es für normale Überwachung beim Standard (30s). Verringern Sie es nur für eine Nulleinspeisungs- oder Lastausgleichs-Anwendung; bedenken Sie, dass alle Anfragen seriell über eine einzige Sperre laufen, sodass ein schnellerer Zähler mehr Verkehr für alle an diesem Bus bedeutet. Gehen Sie nicht viel unter 3 Sekunden.
- Dies nutzt Home Assistants "Config-Subentries"-System. Das Hinzufügen von Zählern ist am besten verifiziert; das Rekonfigurieren eines bestehenden Zählers oder Gateways stützt sich auf dieselbe API, ist aber etwas unsicherer - sollte eine Schaltfläche nicht funktionieren, ist Entfernen und erneutes Hinzufügen ein vollkommen brauchbarer Umweg.

## Symbol für die Integration

Home Assistant bezieht das Integrationssymbol immer von [brands.home-assistant.io](https://brands.home-assistant.io/), auch für custom_components, über `custom_integrations/eastron_sdm/icon.png` im öffentlichen GitHub-Repository [home-assistant/brands](https://github.com/home-assistant/brands). Es gibt kein manifest.json-Feld und keine lokale Datei, mit der eine custom_component dies selbst überschreiben könnte. Wenn Sie das offizielle Eastron-Logo in dieser Übersicht sehen möchten, ist ein Pull Request an dieses Brands-Repository nötig (`icon.png` 256x256, transparenter Hintergrund). Bis dahin zeigen die Sensoren gewöhnliche Material-Design-Symbole je Messtyp.

## Lizenz

Apache-2.0 - Woon IoT BV, gemeinsam mit René van der Gaag. https://github.com/wooniot/ha-modbus-bridge
