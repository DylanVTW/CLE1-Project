# CPX-READER - UITLEG IN MAKKELIJKE TAAL
# Alles achter een # is uitleg. Python voert deze uitleg niet uit.
# Leesvolgorde: onderdelen laden -> geheugenfuncties -> licht/geluid -> namen -> scanlus.
# Een functie (def) is een benoemd stappenplan. Het wordt pas uitgevoerd als we de functie aanroepen.
# De inspringing laat zien welke regels bij een if, functie of lus horen.
# = bewaart een waarde; == vergelijkt; != betekent niet gelijk; True/False betekent waar/onwaar.
# Een byte is een getal van 0 tot 255. Een UID is het unieke nummer van een tag.
# Bij r[a:b] lezen we vanaf plek a tot VOOR plek b. De eerste plek heet 0.
# Hexadecimale tekst gebruikt 0-9 en A-F. %02X maakt twee van die tekens van een byte.
# % 256 betekent de rest na delen door 256. Hier gebruiken we dat als eenvoudig controlegetal.
# Statusgetal: Finn=1, Taynn=2, James=4, Dylan=8. Tel de ingecheckte personen op.
# Voorbeeld: 5 = 1+4, dus Finn en James ingecheckt. 0 = iedereen uit; 15 = iedereen in.
# Namen staan in de code; de UID-koppelingen van James/Dylan en alle statussen staan in NVM.
# print verstuurt tekst via USB. Node.js leest deze tekst; verander de berichtteksten niet zomaar.
# Dit is de bewerkbare broncode. De CPX draait de compacte versie checkin_main.mpy via code.py.
# Alleen dit bestand opslaan verandert de CPX dus nog niet; het moet eerst opnieuw worden omgezet.


# Hiermee kunnen we wachten en meten hoeveel tijd voorbij is.
import time
# Hierin staan de namen van de aansluitingen op de CPX, zoals TX, RX en SPEAKER.
import board
# Dit onderdeel maakt de seriele verbinding met de PN532-reader mogelijk.
import busio
# Hiermee zetten we aansluitingen en het kleine rode lampje aan of uit.
import digitalio
# Dit onderdeel kan ongebruikt werkgeheugen vrijmaken.
import gc
# Dit geeft toegang tot het permanente geheugen van de CPX.
import microcontroller
# Hiermee sturen we de tien gekleurde lampjes op de CPX aan.
import neopixel_write
# Hiermee sturen we geluid naar de ingebouwde luidspreker.
import audioio
# Hiermee maken we van een lijst geluidswaarden een afspeelbaar geluid.
import audiocore
# Maak ongebruikt werkgeheugen vrij. De CPX heeft daar maar weinig van.
gc.collect()
# Haal de PN532-library erbij. Die kent de opdrachten die de reader begrijpt.
from adafruit_pn532.uart import PN532_UART


# Maak de functie load: lees een opgeslagen tag. slot is de beginplek; marker is het herkenningslabel.
def load(slot, marker):
    # Lees 16 geheugenplekjes vanaf slot. NVM bewaart de inhoud ook zonder stroom. Noem het resultaat r.
    r = bytes(microcontroller.nvm[slot:slot+16])
    # Controleer de eerste vier plekjes: staat hier het juiste herkenningslabel?
    if r[:4] != marker:
        # Geen passend label gevonden: geef terug dat er geen opgeslagen tag is.
        return None
    # Een UID hoort hier 4, 7 of 10 bytes lang te zijn. Controleer ook of het controlegetal nog klopt.
    if r[4] not in (4,7,10) or sum(r[:15]) % 256 != r[15]:
        # Stop deze handeling met een foutmelding als de opgeslagen taggegevens niet kloppen.
        raise RuntimeError('Stored tag record damaged')
    # Lees de UID en maak er herkenbare tekst van, bijvoorbeeld A0:9B:19:5C. Geef die tekst terug.
    return ':'.join('%02X' % b for b in r[5:5+r[4]])


# Maak de functie save: sla een tagnummer op op de opgegeven geheugenplek.
def save(slot, marker, uid):
    # Lees eerst wat er nu op die 16 geheugenplekjes staat.
    old = bytes(microcontroller.nvm[slot:slot+16])
    # Ga alleen verder als dit ons eigen record is of elk plekje 0 of 255 bevat: dat behandelen we als leeg.
    if old[:4] != marker and any(b not in (0,255) for b in old):
        # Geef een foutmelding in plaats van onbekende bestaande gegevens te overschrijven.
        raise RuntimeError('Tag storage slot occupied')
    # Maak een veranderbaar lijstje met 16 nullen voor het nieuwe geheugenrecord.
    r = bytearray(16)
    # Zet het herkenningslabel in de eerste vier plekjes, genummerd 0 tot en met 3.
    r[:4] = marker
    # Zet op plek 4 hoeveel bytes het tagnummer heeft. len betekent: tel het aantal.
    r[4] = len(uid)
    # Zet het tagnummer zelf vanaf plek 5 in het lijstje.
    r[5:5+len(uid)] = uid
    # Tel de eerste 15 waarden op en neem de rest na delen door 256. Bewaar dat controlegetal op plek 15.
    r[15] = sum(r[:15]) % 256
    # Schrijf het hele lijstje naar het permanente CPX-geheugen.
    microcontroller.nvm[slot:slot+16] = r
    # Zet de losse UID-bytes om naar tekst: twee hexadecimale tekens per byte, met dubbele punten ertussen.
    value = ':'.join('%02X' % b for b in uid)
    # Lees de opgeslagen tag terug en vergelijk die met wat we wilden opslaan.
    if load(slot, marker) != value:
        # Geef een foutmelding als de tag niet correct is opgeslagen.
        raise RuntimeError('Tag save verification failed')
    # Geef het opgeslagen tagnummer als tekst terug aan de code die deze functie aanriep.
    return value


# Maak de functie die de laatste in-/uitcheckstatus van alle vier de personen leest.
def load_status():
    # Lees de acht geheugenplekjes 48 tot en met 55. Daar staan de aanwezigheidsstatussen.
    r = bytes(microcontroller.nvm[48:56])
    # STA1 betekent: dit is ons statusrecord. Controleer of dat label aanwezig is.
    if r[:4] != b'STA1':
        # Als het label ontbreekt: kijk of de plekjes toch andere gegevens bevatten.
        if any(b not in (0,255) for b in r):
            # Stop met een foutmelding als die geheugenplek al andere gegevens bevat.
            raise RuntimeError('Status storage slot occupied')
        # Nog geen status opgeslagen: begin met iedereen uitgecheckt. Het getal 0 betekent: alle vier uit.
        return 0
    # Vier aan/uit-keuzes passen in een getal van 0 tot 15. Controleer dat bereik en het controlegetal.
    if r[4] > 15 or sum(r[:7]) % 256 != r[7]:
        # Geef een foutmelding als de bewaarde statussen niet kloppen.
        raise RuntimeError('Stored status damaged')
    # Geef het getal met de vier aanwezigheidsstatussen terug.
    return r[4]


# Maak de functie die alle vier de statussen opslaat. mask is het getal met die statussen.
def save_status(mask):
    # Controleer eerst of de bestaande opslag geldig is of nog leeg is.
    load_status()
    # Maak acht bytes: het label STA1 en vier nullen. Een \0 in de code is een nul-byte.
    r = bytearray(b'STA1\0\0\0\0')
    # Zet het statusgetal op plek 4 van dit record.
    r[4] = mask
    # Bereken het controlegetal voor de eerste zeven plekjes en zet het op plek 7.
    r[7] = sum(r[:7]) % 256
    # Schrijf dit statusrecord naar het permanente geheugen.
    microcontroller.nvm[48:56] = r
    # Lees de status terug en controleer of die hetzelfde is als wat we wilden bewaren.
    if load_status() != mask:
        # Geef een foutmelding als de opgeslagen status niet klopt.
        raise RuntimeError('Status save verification failed')

# Maak een bestuurbare aansluiting voor de gekleurde lampjes. pixel is de naam die we eraan geven.
pixel = digitalio.DigitalInOut(board.NEOPIXEL)
# Stel deze aansluiting in om opdrachten naar de lampjes te sturen.
pixel.switch_to_output()
# Maak de aansluiting waarmee we de luidsprekerversterker aan- en uitzetten.
enable = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
# Maak er een uitgang van en begin met de versterker uit. False betekent uit.
enable.switch_to_output(value=False)
# Maak de geluidsuitgang die het geluid naar de ingebouwde luidspreker stuurt.
speaker = audioio.AudioOut(board.SPEAKER)
# Maak een golfje van 32 geluidswaarden: 16 keer hoog en 16 keer laag. Dit levert ons piepje op.
wave = bytearray([240]*16 + [16]*16)
# Maak het golfje afspeelbaar: 32000 waarden per seconde / 32 waarden per golf = een toon van 1000 Hz.
tone = audiocore.RawSample(wave, sample_rate=32000)


# Bewaar wanneer de gekleurde lampjes uit moeten. 0 betekent: er staat geen uitschakeltijd gepland.
off_at = 0

# Maak de functie die controleert of de twee seconden licht voorbij zijn.
def update():
    # Gebruik dezelfde off_at als buiten deze functie, zodat we die ook kunnen veranderen.
    global off_at
    # Als er een uitschakeltijd is en die tijd bereikt is: doe de lampjes uit. monotonic is een oplopende klok.
    if off_at and time.monotonic() >= off_at:
        # Stuur 30 nullen naar de lampjes: tien lampjes met elk drie kleurwaarden. Alle kleuren worden dus uit.
        neopixel_write.neopixel_write(pixel, bytes(30))
        # Bewaar wanneer de gekleurde lampjes uit moeten. 0 betekent: er staat geen uitschakeltijd gepland.
        off_at = 0

# Maak de functie voor licht en geluid. inside is True bij inchecken en False bij uitchecken.
def signal(inside):
    # Gebruik dezelfde off_at als buiten deze functie, zodat we die ook kunnen veranderen.
    global off_at
    # Plan het uitschakelen van de lampjes op twee seconden vanaf nu.
    off_at = time.monotonic() + 2.0
    # Deze lampjes verwachten groen-rood-blauw. Kies groen bij inside=True, anders rood. Herhaal voor alle tien lampjes.
    neopixel_write.neopixel_write(pixel, bytes((128,0,0) if inside else (0,128,0))*10)
    # Zet de luidsprekerversterker aan.
    enable.value = True
    # Probeer de ingesprongen code. De bijbehorende finally of except hieronder bepaalt wat er daarna gebeurt.
    try:
        # Begin het piepje. loop=True herhaalt het korte golfje zolang we het niet stoppen.
        speaker.play(tone, loop=True)
        # Wacht 0,12 seconde: zo lang duurt het piepje.
        time.sleep(0.12)
    # Voer de volgende regels altijd uit, ook als het afspelen een fout geeft.
    finally:
        # Stop het afspelen van het piepje.
        speaker.stop()
        # Zet de luidsprekerversterker weer uit.
        enable.value = False
    # Schrijf in de USB-console welke reactie is gegeven: groen met piepje of rood met piepje.
    print('[SIGNAL]', 'GREEN + BEEP' if inside else 'RED + BEEP')

# Stuur 30 nullen naar de lampjes: tien lampjes met elk drie kleurwaarden. Alle kleuren worden dus uit.
neopixel_write.neopixel_write(pixel, bytes(30))

# Maak ook het kleine rode controlelampje bestuurbaar. Dit staat los van de tien gekleurde lampjes.
led = digitalio.DigitalInOut(board.LED)
# Stel het kleine controlelampje in als uitgang, zodat de code het kan aan- en uitzetten.
led.direction = digitalio.Direction.OUTPUT
# Open de verbinding met de PN532: CPX TX/A7 naar RXD, CPX RX/A6 naar TXD, met 115200 bits per seconde. Deze UART wacht maximaal 0,1 seconde per leesopdracht.
uart = busio.UART(board.TX, board.RX, baudrate=115200, timeout=0.1)
# Maak een woordenboek: links staat het unieke tagnummer en rechts de bijbehorende naam.
names = {'A0:9B:19:5C': 'Finn Oostveen', 'B7:7A:FF:6D': 'Taynn Angel'}

# Lees de eerder opgeslagen tag van James vanaf geheugenplek 16. JAM1 is het herkenningslabel, geen naam op de tag.
james_uid = load(16, b'JAM1')
# Als er een opgeslagen tagnummer van James is, voer de volgende regel uit.
if james_uid:
    # Voeg de koppeling tussen dat tagnummer en James toe aan het woordenboek.
    names[james_uid] = 'James de Beer'

# Lees Dylans opgeslagen tagnummer vanaf geheugenplek 32, herkenbaar aan het label DYL1.
dylan_uid = load(32, b'DYL1')
# Als er een opgeslagen tagnummer van Dylan is, voeg dat hieronder toe.
if dylan_uid:
    # Koppel dit tagnummer aan de naam Dylan van t woud.
    names[dylan_uid] = 'Dylan van t woud'
# Anders: voer dit stukje uit als de voorgaande if niet waar is.
else:
    # Meld via USB dat de eerstvolgende onbekende tag voor Dylan zal worden opgeslagen.
    print('Next unknown tag will be saved as Dylan van t woud.')
# Leg de vaste volgorde vast: Finn, Taynn, James, Dylan. Hun statussen hebben elk een eigen bit in het statusgetal.
labels = ('Finn Oostveen', 'Taynn Angel', 'James de Beer', 'Dylan van t woud')
# Haal het bewaarde statusgetal op. Zo weet de CPX na herstart wie al ingecheckt is.
state_mask = load_status()
# Stuur het opgehaalde statusgetal via USB. Node.js gebruikt dit om de website gelijk te zetten.
print('[STORAGE] Restored status bits:', state_mask)
# Begin zonder laatst gescande tag. Hiermee voorkomen we dat een stilgehouden tag steeds opnieuw telt.
active = None
# Begin zonder tijdstip waarop de tag verdween. None betekent: nog geen waarde.
missing_since = None
# Toon een opstarttitel in de USB-console. Dit is alleen een titel, niet de volledige namenlijst.
print('CHECK-IN READER - Finn Oostveen / Taynn Angel')
# Stuur alle bekende tagnummers en namen via USB naar Node.js.
print('[STORAGE] Registered tags:', names)
# Blijf de volgende stappen herhalen. De code stopt pas bij een onderbreking, fout buiten de opvang of stroomuitval.
while True:
    # Probeer de ingesprongen code. De bijbehorende finally of except hieronder bepaalt wat er daarna gebeurt.
    try:
        # Maak contact met de PN532 via de eerder geopende UART. p is onze reader; uitgebreide library-logs staan uit.
        p = PN532_UART(uart, debug=False)
        # Vraag de firmwareversie van de reader op en toon die om de verbinding te controleren.
        print('PN532 firmware:', p.firmware_version)
        # Zet de PN532 klaar om NFC-tags te lezen. De library regelt de bijbehorende opdracht.
        p.SAM_configuration()
        # Meld dat scannen kan en dat je de tag minstens een seconde moet weghalen tussen twee scans.
        print('READY - scan tag; remove for one second between scans.')
        # Blijf de volgende stappen herhalen. De code stopt pas bij een onderbreking, fout buiten de opvang of stroomuitval.
        while True:
            # Controleer of de gekleurde lampjes al twee seconden aanstaan en dus uit moeten.
            update()
            # Zoek maximaal 0,2 seconde naar een ondersteunde tag. uid krijgt het tagnummer, of None als er geen is.
            uid = p.read_passive_target(timeout=0.2)
            # Controleer of de gekleurde lampjes al twee seconden aanstaan en dus uit moeten.
            update()
            # Onthoud de huidige stand van de oplopende klok, om verstreken tijd te meten.
            now = time.monotonic()
            # Als er nu geen tag is gevonden, controleer dan hieronder hoe lang die al weg is.
            if uid is None:
                # Als we nog niet bijhielden dat de tag weg was, begin daar nu mee.
                if missing_since is None:
                    # Bewaar het tijdstip waarop we voor het eerst geen tag zagen.
                    missing_since = now
                # Is er minstens een hele seconde geen tag gezien?
                if now - missing_since >= 1.0:
                    # Vergeet de vorige tag: na een seconde afwezigheid mag die opnieuw worden gescand.
                    active = None
                    # Zet het kleine rode controlelampje uit.
                    led.value = False
                # Sla de rest van deze ronde over en begin de volgende ronde van de binnenste while-lus.
                continue
            # Er is weer een tag: zet het bijhouden van de afwezigheidstijd terug op geen waarde.
            missing_since = None
            # Zet de losse UID-bytes om naar tekst: twee hexadecimale tekens per byte, met dubbele punten ertussen.
            value = ':'.join('%02X' % b for b in uid)
            # Is dit dezelfde tag die we nog steeds voor de reader houden?
            if active == value:
                # Sla de rest van deze ronde over en begin de volgende ronde van de binnenste while-lus.
                continue
            # Onthoud dat deze tag nu is verwerkt. Hij telt pas opnieuw nadat hij tussendoor lang genoeg weg is geweest.
            active = value
            # Zet het kleine rode controlelampje aan als teken dat er een tag is gezien.
            led.value = True
            # Stuur het gescande tagnummer via USB. Node.js onthoudt welk tagnummer bij het volgende scanbericht hoort.
            print('[SCAN] UID:', value)
            # Als de tag onbekend is en Dylan nog geen opgeslagen tag heeft, registreer deze tag dan voor Dylan.
            if value not in names and dylan_uid is None:
                # Sla Dylans nieuwe tagnummer permanent op vanaf geheugenplek 32.
                dylan_uid = save(32, b'DYL1', uid)
                # Koppel dit tagnummer aan de naam Dylan van t woud.
                names[dylan_uid] = 'Dylan van t woud'
                # Meld via USB dat Dylans tag permanent is opgeslagen.
                print('[SAVED PERMANENTLY] Dylan van t woud UID=' + dylan_uid)
            # Controleer of de tag na eventuele registratie nog steeds onbekend is.
            if value not in names:
                # Meld dat een onbekende tag niemand in- of uitcheckt.
                print('Unknown tag - not checked in or out.')
                # Sla de rest van deze ronde over en begin de volgende ronde van de binnenste while-lus.
                continue
            # Zoek de persoon in labels. Maak met 1 << zijn eigen schakelaar en draai die met ^ om: uit wordt aan, aan wordt uit.
            new_mask = state_mask ^ (1 << labels.index(names[value]))
            # Sla de nieuwe aanwezigheidsstatus permanent op voordat we succes melden.
            save_status(new_mask)
            # Gebruik vanaf nu de nieuwe opgeslagen status in het lopende programma.
            state_mask = new_mask
            # Bekijk met & alleen het bit van deze persoon. bool maakt daar True (ingecheckt) of False (uitgecheckt) van.
            inside = bool(state_mask & (1 << labels.index(names[value])))
            # Meld via USB dat de nieuwe status is opgeslagen.
            print('[SAVED] Status stored permanently')
            # Stuur de naam met CHECKED IN of CHECKED OUT. Dit is het bericht waarmee Node.js de scan bewaart.
            print(names[value] + (' - CHECKED IN' if inside else ' - CHECKED OUT'))
            # Geef de bijpassende reactie: groen of rood licht, een piepje en licht uit na ongeveer twee seconden.
            signal(inside)
    # Vang een fout uit de buitenste try op, zodat de reader na een pauze opnieuw kan proberen.
    except Exception as error:
        # Stuur de foutmelding via USB. repr toont het soort fout en de bijbehorende tekst.
        print('[ERROR]', repr(error))
        # Wacht drie seconden voordat de buitenste while-lus de reader opnieuw probeert te starten.
        time.sleep(3)
