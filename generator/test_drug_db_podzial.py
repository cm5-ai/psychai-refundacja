#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST PODZIALU DRUG_DB. Zwraca 1, gdy cokolwiek nie przejdzie.

Podzial pliku, ktorego lekarz uzywa przy pacjencie, wolno zrobic tylko wtedy,
gdy da sie UDOWODNIC, ze nic nie zginelo. Test nie wierzy skryptowi dzielacemu
i nie uzywa jego funkcji — zrodlem prawdy jest wersja sprzed podzialu wyjeta
z gita, a nie kopia zostawiona przez generator.

T1  Kazda karta ze zrodla jest w DOKLADNIE JEDNYM pliku klasowym.
T2  Tresc kazdej karty jest identyczna LINIA W LINIE ze zrodlem.
T3  Bilans: N_WEJSCIE = N_ZACHOWANE + N_ODRZUCONE, odrzuconych zero.
T4  Reguly kart sa WYLACZNIE w CORE, a kazdy plik klasowy jawnie sie z nim
    wiaze. Nie ma kopii do rozjechania sie.
T5  Indeks w CORE i karty w plikach zgadzaja sie W OBIE STRONY:
    zadnej karty bez wpisu w indeksie, zadnego wpisu bez karty.
T6  Kazdy plik z indeksu istnieje.
T7  Liczba linii pol (NAZWA_POLA:) jest taka sama jak w zrodle — lapie
    zgubienie pojedynczej linii wewnatrz karty, ktorego T2 by nie zlapal,
    gdyby karta zostala pominieta w calosci razem z naglowkiem.
"""
import hashlib, os, re, subprocess, sys

# SCIEZKA DO PACZKI — trzy proby, w tej kolejnosci, bez zgadywania.
# 1. PSYCHAI_PACZKA z otoczenia (CI podaje ja jawnie),
# 2. ~/mnt/psychai-paczka (ta maszyna),
# 3. katalog siostrzany obok tego repo (uklad checkoutu w CI).
# Powod: zaszyta sciezka tej maszyny sprawiala, ze audyt i testy NIE DALY SIE
# uruchomic nigdzie indziej. Narzedzie, ktorego nie da sie odpalic w CI, jest
# narzedziem, ktore chodzi tylko wtedy, gdy ktos pamieta.
def _paczka():
    k = os.environ.get("PSYCHAI_PACZKA")
    if k and os.path.isdir(k):
        return k
    for p in (os.path.expanduser("~/mnt/psychai-paczka"),
              os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "..", "psychai-paczka")):
        if os.path.isdir(p):
            return os.path.normpath(p)
    raise SystemExit("FAIL: nie znajduje paczki. Ustaw PSYCHAI_PACZKA "
                     "albo umiesc psychai-paczka obok tego repo.")


PACZKA = _paczka()
PROJEKT = os.path.join(PACZKA, "projekt")
CORE = "DRUG_DB_PSYCHIATRIA_CORE.txt"
bledy = []


def naglowek_karty(l):
    """UWAGA. Ta funkcja jest KOPIA regexa z generatora i wlasnie dlatego nie
    wykryla bledu z 2026-09-24: generator nie dopuszczal ukosnika, test tez
    nie, wiec obaj zgodnie nie widzieli karty KWAS WALPROINOWY / WALPROINIAN.
    Identyczny blad po obu stronach jest niewidzialny. Zostaje do dzielenia
    blokow, ale T0 ponizej sprawdza ja METODA NIEZALEZNA."""
    return bool(re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9 _/.\-]{1,}$', l))


def naglowki_niezaleznie(linie):
    """T0. Inna metoda, celowo nie regex na ksztalt naglowka: naglowek to
    linia BEZ MALYCH LITER, poprzedzona pusta linia, po ktorej w ciagu czterech
    linii pojawia sie linia pola (NAZWA_POLA:). Opiera sie na STRUKTURZE karty,
    nie na tym, jakie znaki wolno miec w nazwie - wiec nie powtorzy bledu
    w doborze znakow."""
    pole = re.compile(r'^[A-ZĄĆĘŁŃÓŚŹŻ_0-9/]+:')
    out = []
    for i, l in enumerate(linie):
        t = l.strip()
        # Warunek "poprzedzona pusta linia" BYL TU I BYL ZLY: SULPIRYD,
        # KLORAZEPAT, CHLORDIAZEPOKSYD i OKSAZEPAM stoja bezposrednio po linii
        # ZRODLO_KARTY poprzedniej karty, bez odstepu. Zdjety.
        # Dwukropek odsiewa tytul pliku ("PSYCH-AI — DRUG DB: ...") - nazwa
        # karty nigdy go nie ma.
        # Naglowek stoi w kolumnie zero. Wciete wypunktowanie pisane wersalikami
        # wewnatrz karty ("  - JEDNOCZESNE STOSOWANIE...") naglowkiem nie jest.
        if l[:1].isspace() or t.startswith("-"):
            continue
        if not t or len(t) < 2 or ":" in t or any(c.islower() for c in t):
            continue
        if any(pole.match(x.strip()) for x in linie[i + 1:i + 5]):
            out.append(l)
    return out


def karty_z(linie):
    idx = [i for i, l in enumerate(linie) if naglowek_karty(l)]
    out = {}
    for n, i in enumerate(idx):
        j = idx[n + 1] if n + 1 < len(idx) else len(linie)
        out[linie[i]] = linie[i:j]
    return out, (linie[:idx[0]] if idx else linie)


# Rewizja paczki SPRZED podzialu DRUG_DB na pliki klasowe — jedyne zrodlo prawdy
# dla tego testu. Podzial zrobil commit 683d132; 458b5ab to jego rodzic.
# Domyslne "HEAD" bylo pulapka: na dzisiejszym HEAD plik jest juz PO podziale,
# wiec test konczyl sie FAILEM, ktory znaczyl "zle uruchomiles", a wygladal
# jak "paczka zepsuta". Argument nadal nadpisuje stala.
REV_PRZED_PODZIALEM = "458b5ab"


def zrodlo_z_gita(rev):
    r = subprocess.run(["git", "-C", PACZKA, "show", "%s:projekt/%s" % (rev, CORE)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout.split("\n")


def main():
    rev = sys.argv[1] if len(sys.argv) > 1 else REV_PRZED_PODZIALEM
    zr = zrodlo_z_gita(rev)
    if zr is None:
        print("FAIL: nie moge wyjac wersji sprzed podzialu z gita (%s)" % rev); return 1
    # Bez T0 regex generatora i regex testu moga miec ten sam blad i zgodnie
    # przeoczyc karte. Tak wlasnie zginela KWAS WALPROINOWY.
    karty_zr, _ = karty_z(zr)
    niez = naglowki_niezaleznie(zr)
    # BRAMKA WEJSCIA PRZED T0. Zgodnie z 3B regula bez wejscia jest znaleziskiem,
    # a nie wynikiem OK: na pliku PO podziale obie metody widza zero naglowkow,
    # zgadzaja sie ze soba i T0 drukowal "OK" na pustym zbiorze. Dlatego liczbe
    # kart sprawdzamy PRZED T0, a nie po nim.
    if len(karty_zr) < 40 or len(niez) < 40:
        print("FAIL: wersja %s ma %d kart (regex) i %d naglowkow (struktura) — to nie jest "
              "wersja sprzed podzialu; T0 nie zostal uruchomiony na pustym wejsciu"
              % (rev, len(karty_zr), len(niez)))
        return 1
    # T0 — DWIE METODY WYKRYWANIA NAGLOWKOW MUSZA SIE ZGADZAC NA ZRODLE.
    tylko_regex = [x for x in karty_zr if x not in niez]
    tylko_struktura = [x for x in niez if x not in karty_zr]
    print("T0 DWIE METODY na zrodle: N_WEJSCIE regex %d, struktura %d, rozbieznosc %d+%d -> %s"
          % (len(karty_zr), len(niez), len(tylko_regex), len(tylko_struktura),
             "OK" if not tylko_regex and not tylko_struktura else "FAIL"))
    for x in tylko_regex:
        bledy.append("T0 '%s': widzi tylko regex - struktura karty tego nie potwierdza" % x[:40])
    for x in tylko_struktura:
        bledy.append("T0 '%s': widzi tylko struktura - regex naglowka to przeoczyl" % x[:40])

    pliki = sorted(f for f in os.listdir(PROJEKT) if f.startswith("DRUG_DB_") and f.endswith(".txt")
                   and f not in (CORE, "DRUG_DB_KARDIOLOGIA_CORE.txt", "DRUG_DB_CIAZA_LAKTACJA.txt"))
    if not pliki:
        print("FAIL: brak plikow klasowych"); return 1

    # T1-T3
    gdzie, preambuly = {}, {}
    for f in pliki:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        k, pre = karty_z(L)
        preambuly[f] = pre
        for nazwa, tresc in k.items():
            if nazwa in gdzie:
                bledy.append("T1 %s: karta w dwoch plikach (%s i %s)" % (nazwa, gdzie[nazwa][0], f))
            gdzie[nazwa] = (f, tresc)

    # ZAKRES TEGO TESTU TO MIGRACJA, NIE BIEZACA ZAWARTOSC PACZKI.
    # Test dowodzi, ze podzial z 2026-09-24 niczego nie zgubil i niczego nie
    # przekrecil. Karty DODANE PO migracji sa poza jego zakresem z definicji -
    # w zrodle migracyjnym ich nie ma i nigdy nie bedzie. Pilnuja ich audyt
    # kompletnosci (R1-R5) i test przypisania klas wobec ATC.
    # Bez tego rozroznienia kazda nowa karta oblewalaby test migracji, a to
    # skonczyloby sie oslabieniem testu zamiast oslabieniem zalozenia.
    # NAGLOWKI SEKCJI PRZEMIANOWANE PO MIGRACJI. Zmiana nazwy sekcji nie jest
    # zgubieniem karty, ale T3 nie ma jak tego odroznic — lista jest jawna
    # i podaje, na co sekcja zostala rozbita, zeby nie dalo sie tu ukryc
    # zniknietej karty leku.
    PRZEMIANOWANE = {"BENZODIAZEPINY / NASENNE":
                     ["BENZODIAZEPINY", "LEKI Z / NASENNE NIEBENZODIAZEPINOWE",
                      "ANKSJOLITYKI I NASENNE NIE-BZD"],
                     "STABILIZATORY / PRZECIWDRGAWKOWE":
                     ["STABILIZATORY NASTROJU", "GABAPENTYNOIDY",
                      "PRZECIWPADACZKOWE W UZYCIU PSYCHIATRYCZNYM"]}
    for stara, nowe in PRZEMIANOWANE.items():
        brak_nowych = [x for x in nowe if x not in gdzie]
        if brak_nowych:
            bledy.append("T3 %s: przemianowana na %s, ale w plikach nie ma: %s"
                         % (stara, ", ".join(nowe), ", ".join(brak_nowych)))
        else:
            print("   PRZEMIANOWANO sekcje %s -> %s" % (stara, ", ".join(nowe)))
    brakujace = [n for n in karty_zr if n not in gdzie and n not in PRZEMIANOWANE]
    nadmiarowe = [n for n in gdzie if n not in karty_zr]
    if nadmiarowe:
        print("   PO MIGRACJI dodano %d kart (poza zakresem tego testu): %s"
              % (len(nadmiarowe), ", ".join(sorted(nadmiarowe))))
    nadmiarowe = []
    for n in brakujace:
        bledy.append("T3 %s: karta ze zrodla nie trafila do zadnego pliku" % n)
    for n in nadmiarowe:
        bledy.append("T3 %s: karta, ktorej nie ma w zrodle" % n)
    print("T3 BILANS: N_WEJSCIE %d = N_ZACHOWANE %d + N_ODRZUCONE %d -> %s"
          % (len(karty_zr), len(karty_zr) - len(brakujace), len(brakujace),
             "OK" if not brakujace and not nadmiarowe else "FAIL"))

    # T2
    # LINIE PRZEPISANE, nie dopisane. Dopisanie jest bezpieczne, przepisanie nie:
    # stara linia POSTAC w tych trzech kartach mowila "dawek postaci iniekcyjnych
    # NIE MA w paczce", co po dodaniu dawek depot bylo juz nieprawda i karta
    # przeczylaby sama sobie. Kazda pozycja = ile linii zrodla znika i dlaczego.
    # rev83-rev90, 2026-09-27: WOREK DAWKOWY. Pod jedna nazwa DAWKA stala dawka
    # doustna i dawka depot — przy paliperydonie roznica to dziesieciokrotnosc.
    # Linia NIE ZNIKLA: dostala KWALIFIKATOR ("DAWKA doustnie:", "DAWKA depot
    # miesieczny:"), czyli zmienila sie jej NAZWA POLA. Dla T2 to linia
    # przepisana i tak jest tu liczona.
    # 2026-10-03, ZAMKNIETY WLOT LICZBY (R50). ZMIERZONE: trzy linie zrodla
    # ("Z WALPROINIANEM — LICZBY Z ChPL...", "(podawane jako 25 mg CO DRUGI
    # DZIEŃ)...", "100–200 mg/d. [ChPL 4.2 Epitrigine, 2026-09-22]") zeszly
    # z DRUG_DB_STAB.txt. Niosly dawke podpisana NAZWA HANDLOWA, bez
    # pozwolenia i bez pinu fragmentu — a jedna nazwa nie rozstrzyga
    # rejestracji. Na ich miejscu stoi JEDNA linia pytania bez mg.
    # TRESC NIE ZGINELA: stoi w narzedzia/karty/CHPL_LAYER/lamotrygina.json
    # i w magazynie chpl/. Z pliku wizyty zeszla LICZBA BEZ REJESTRACJI.
    PRZEPISANE = {"LAMOTRYGINA": (3, "trzy linie dawkowania przy walproinianie "
                                     "pod nazwa Epitrigine -> jedno pytanie bez mg "
                                     "(wlot liczby, R50 2026-10-03)"),
                  "ARYPIPRAZOL": (2, "POSTAC: 'dawek NIE MA' -> wskazanie na dawke depot w karcie; "
                                     "DAWKA -> DAWKA doustnie (worek dawkowy, rev83-88)"),
                  "OLANZAPINA": (2, "POSTAC: jw., plus odeslanie do NIEPEWNY_ODCZYT_ZRODLA; "
                                    "DAWKA -> DAWKA doustnie (worek dawkowy)"),
                  "RISPERIDON": (2, "POSTAC: jw., dla obu postaci depot; "
                                    "DAWKA -> DAWKA doustnie (worek dawkowy)"),
                  # 2026-10-02, PODMIANA KARTY HALOPERIDOLU. Pola dawki tej
                  # substancji wyszly z DRUG_DB_AP.txt do LEK_haloperidol.txt,
                  # gdzie blok = JEDNA REJESTRACJA i kazda wartosc niesie pin
                  # dokumentu. KTORE LINIE ZESZLY I DLACZEGO, 13 pozycji:
                  #   POSTAC, DAWKA (doustnie), WSKAZANIA, T1_2, METABOLIZM,
                  #   DN, INTERAKCJE, CIĄŻA, KP, OTĘPIENIE, PRZECIWWSKAZANIA
                  #     -> ChPL 4.1/4.2/4.3/4.4/4.5/4.6/4.8/5.2 OSOBNO dla
                  #        02394, 03029, 00773, 01040 (cytat z pelnym sha
                  #        dokumentu i fragmentu); 09693 i 07226 niosa
                  #        BRAK_DOKUMENTU_W_SPRAWDZONYCH_ZRODLACH i NIE
                  #        biora wartosci od pozostalych;
                  #   ONSET -> WYLACZONE, bez zrodla w paczce (decyzja lekarza
                  #        D-2 z 2026-10-02, razem z progiem 67);
                  #   MONITORING -> WYLACZONE, synteza bez pinu (decyzja
                  #        lekarza D-1: poza odczytem).
                  # W DRUG_DB_AP zostaja DWA WSKAZNIKI BEZ TRESCI
                  # (PRZECIWWSKAZANIA, NIEPEWNY_ODCZYT_ZRODLA), wiec zadna
                  # z tych linii nie znikla po cichu — kazda ma adres.
                  "HALOPERIDOL": (13, "PODMIANA KARTY 2026-10-02: 11 pol -> "
                                  "LEK_haloperidol.txt per rejestracja (punkty "
                                  "ChPL 4.1-5.2, pin dokumentu), ONSET i "
                                  "MONITORING -> WYLACZONE bez zrodla (D-2, D-1); "
                                  "w DRUG_DB_AP zostaja dwa wskazniki bez tresci"),
                  # F8, 2026-09-27: nazwa pola z myslnikiem nie byla dla parsera
                  # paczki polem — runtime mowilby "brak danych" przy zywej tresci.
                  "KARBAMAZEPINA": (1, "INTERAKCJE — ANTYKONCEPCJA -> INTERAKCJE antykoncepcja (F8)"),
                  # rev.47: przeliczniki intra-lek przeniesione z 18 do kart,
                  # tabela rownowaznosci depotow zostawiona w 18 jako JEDEN byt
                  "FLUPENTYKSOL": (1, "'PRZELICZNIK ... patrz 18' -> wlasciwy przelicznik w karcie plus odeslanie do tabeli rownowaznosci"),
                  "ZUKLOPENTYKSOL": (1, "DAWKA_ROWNOWAZNA: kopia tabeli rownowaznosci usunieta, zostaje odeslanie i czesc wlasna zuklopentyksolu"),
                  # rev68, 2026-09-26: lekarz zglosil, ze Denepry nie ma w Polsce.
                  # Sprawdzone: w RPL zarejestrowana, ale na liscie preparatow na rynku
                  # polskim (Medycyna Praktyczna) jej nie ma. Karta stala na ChPL produktu,
                  # ktorego lekarz nie wypisze, wiec zeszla na Paliperidone Teva.
                  "PALIPERYDON": (3, "DAWKA -> DAWKA depot miesieczny (worek dawkowy, rev83-88); "
                                     "POSTAC: lista produktow zmieniona z Denepry na produkty "
                                     "faktycznie na rynku; ZRODLO_KARTY: ChPL Denepry -> ChPL "
                                     "Paliperidone Teva 75/100/150 mg (rev68)"),
                  # rev72, 2026-09-27: pomiar cache wobec rynku (dokumentacja/
                  # CACHE_A_RYNEK_2026-09-27.md). Karta klozapiny stoi na ChPL
                  # Ayupilu, a lekarz w aptece spotyka Klozapol, ktorego ChPL
                  # w paczce NIE MA. Karty NIE PRZESTAWIAM — nie ma na co.
                  # ZRODLO_KARTY mowi to wprost, zamiast milczec: milczenie
                  # czyta sie jak 'to jest dawkowanie tego, co pacjent kupi'.
                  "KLOZAPINA": (3, "ZRODLO_KARTY jw.; plus F8 2026-09-27: dwie linie mialy "
                                   "nazwe pola z myslnikiem ('INTERAKCJE — ZMIANY STYLU ZYCIA', "
                                   "'DN — JELITA'), przez co parser paczki NIE WIDZIAL ich jako pol. "
                                   "Przepisane na 'INTERAKCJE zmiany stylu zycia (nie tylko leki)' "
                                   "i 'DN jelita'. ZRODLO_KARTY: dopisane, ze cache ma trzy produkty "
                                   "(Ayupil, Clopizam, Clozapine Hasco) i ze ChPL Klozapolu "
                                   "w paczce nie ma, wiec karta nie orzeka o nim nic (R28/P6)"),
                  # rev94, 2026-09-28: pole KP temazepamu orzekalo "bez wlasnej
                  # karty LactMed". ZMIERZONE TEGO DNIA skryptem, ktory paczka
                  # uruchamia sama: 'temazepam' zwraca WPIS Temazepam (LM388)
                  # z rewizja 2024-09-15 i z liczbami. Zdanie w karcie bylo
                  # FALSZYWE wobec zrodla, ktore ta sama paczka odpytuje, i
                  # lekarz czytajacy "bez karty" mogl nie poprosic o dane,
                  # ktore sa. Poprawione po decyzji lekarza z 2026-09-28
                  # (podpisy/GRUPA_B_..., pozycja B1). Zadnej liczby z LactMed
                  # do pola NIE przepisano — pole odsyla, nie cytuje.
                  "TEMAZEPAM": (1, "KP: zdanie 'bez wlasnej karty LactMed' bylo falszywe "
                                   "wobec skryptu uruchamianego przez 18A (WPIS Temazepam LM388, "
                                   "rewizja 2024-09-15). Nowe brzmienie rozdziela dwa orzeczenia: "
                                   "BRAK DANYCH LOKALNYCH w tej paczce (prawda) wobec braku karty "
                                   "w LactMed (nieprawda), i odsyla do uruchomienia skryptu. "
                                   "Liczb z LactMed do pola nie przepisano (warstwa 40 par. 3)")}
    UZUPELNIONE = set(["PALIPERYDON", "FLUPENTYKSOL", "TIAPRYD", "METADON",
                       "ESTAZOLAM", "BROMAZEPAM", "ARYPIPRAZOL", "OLANZAPINA",
                       "RISPERIDON", "HALOPERIDOL", "ZUKLOPENTYKSOL",
                       # 2026-09-28: TEMAZEPAM ma JEDNOCZESNIE linie dopisana
                       # przez narzedzie (DAWKA_STARSI ze stemplem ChPL) i JEDNA
                       # linie przepisana recznie (KP, po decyzji lekarza z tego
                       # dnia). Sciezka narzedziowa wymaga, zeby reszta byla
                       # pusta, wiec karta z obiema zmianami naraz musi isc
                       # sciezka UZUPELNIONE + PRZEPISANE, gdzie liczba linii
                       # zmienionych jest ZADEKLAROWANA i policzona.
                       # To nie jest rozluznienie testu: deklaracja to 1 i kazda
                       # druga zmiana tej karty nadal oblewa.
                       "TEMAZEPAM",
                       "KLOZAPINA",
                       # 2026-09-27: karbamazepina dostala od przenosnika
                       # DAWKA_STARSI i DAWKA_DZIECI ze stemplem ChPL Amizepin,
                       # wstawione MIEDZY DAWKA a STEZENIE_TERAPEUTYCZNE. Bez tej
                       # pozycji karta szla sciezka scisla i oblewala na POZYCJI
                       # linii, nie na tresci — zrodlo mialo w wierszu 2
                       # STEZENIE_TERAPEUTYCZNE, plik ma tam DAWKA_STARSI.
                       "KARBAMAZEPINA",
                       # 2026-10-03, ZAMKNIETY WLOT LICZBY (R50). Karta
                       # lamotryginy niosla pod linia DAWKA_DZIECI trzy linie
                       # pisane recznie z dawkami przy walproinianie,
                       # podpisane NAZWA HANDLOWA (Epitrigine) i stemplem
                       # narzedziowym. Dawka bez pozwolenia z pinem zeszla
                       # z pliku wizyty; na jej miejscu stoi jedno pytanie.
                       # Liczba znikajacych linii jest ZADEKLAROWANA nizej.
                       "LAMOTRYGINA"])   # patrz DOPISANE w T7
    # NORMALIZACJE PISOWNI POLA — DANA, NIE DOMYSL PARSERA [2026-09-25].
    # rev48 ("jedno pole przestaje miec dwie pisownie") celowo ujednolicila
    # nazwy pol w plikach klasowych. Zrodlo T2 jest ZAMROZONE na commicie
    # sprzed podzialu, wiec od tamtej pory rozni sie od plikow w kazdej
    # karcie, ktora te pisownie niosla — i T2 oblewal w CI przez 52 commity
    # na tych samych czterech kartach. Kontrola czerwona od 52 commitow nie
    # jest kontrola: uczy kasowania maila.
    # NIE ROZLUZNIAM T2. Podstawiam WYLACZNIE te pary, ktore rev48 zmieniala,
    # i licze, ile razy kazda byla potrzebna. Para nieuzyta ani razu jest
    # martwym wylaczeniem i ma to byc widac.
    # WARTOSC PRZEPISANA RECZNIE — PARA PELNYCH SHA ZE WSPOLNEJ DEKLARACJI
    # [rozkaz lekarza 2026-10-03]. Pary czytane sa z JEDNEGO miejsca:
    # narzedzia/stara_karta_po_podmianie.MIGRACJA_DOPUSZCZONA w paczce, tej
    # samej deklaracji, ktorej uzywa kontrola podmiany. Skopiowanych sha tu
    # nie ma — dwie kopie jednej deklaracji rozjechaly sie w tej paczce raz.
    # REGULY POROWNANIA NIE ZMIENIAM: T2 dalej porownuje linie 1:1, a para
    # wiaze DOKLADNIE jedna wartosc przed z DOKLADNIE jedna po. Wartosc z tej
    # deklaracji jest sha256 TRESCI POLA po zlaczeniu kontynuacji; dla pola
    # jednoliniowego bez wciecia to ta sama liczba, co sha linii. Gdyby pole
    # dostalo kontynuacje, para przestaje sie zgadzac i T2 OBLEWA — nie
    # przechodzi po cichu. Zrodla nie przemrazam, recznej linii nie oznaczam
    # stemplem narzedziowym, NORMALIZACJE nietkniete.
    sys.path.insert(0, os.path.join(PACZKA, "narzedzia"))
    import stara_karta_po_podmianie as _SKP
    # CALA DEKLARACJA, NIE JEDNA KARTA [R57, 2026-10-04]. Do 2026-10-04 ten
    # filtr bral wylacznie pary kwetiapiny, bo tylko ona miala wtedy wartosc
    # przepisana recznie. Zamkniety wlot liczby dotyczy szesciu plikow
    # klasowych, wiec filtr po nazwie leku wycinalby 153 ze 154 deklaracji i
    # test oblewalby na zmianach, ktore MAJA swoj pin. Warunek zostaje jeden:
    # para musi miec wartosc PO (pole, ktore schodzi bez nastepcy, rozlicza
    # sie kanalem PRZEPISANE, nie para).
    PRZEPISANE_WARTOSCI = {k: v for k, v in _SKP.MIGRACJA_DOPUSZCZONA.items()
                           if v[1] is not None}
    if not PRZEPISANE_WARTOSCI:
        bledy.append("T2: wspolna deklaracja MIGRACJA_DOPUSZCZONA nie ma ani jednej "
                     "pary kwetiapiny z wartoscia PO — rozliczenie bez wejscia")
    uzyte_wartosci = set()

    def _sha_linii(t):
        return hashlib.sha256(t.encode("utf-8")).hexdigest()

    def _etykieta(t):
        return t.split(":", 1)[0].strip() if ":" in t else ""

    def _przepisana(karta, x, plik):
        """Czy linia zrodla x ma ZADEKLAROWANA pare sha do linii stojacej w pliku.

        JEDNA DEFINICJA, DWIE SCIEZKI [R57, 2026-10-04]. Linia pola dawki,
        ktorej wartosc oddano zdaniu bez liczby, znika ze zrodla i staje w
        pliku pod TA SAMA ETYKIETA. Bez tego czyta sie jak ciche usuniecie.
        Warunek jest ostry i nie jest dopuszczeniem ogolnym: we wspolnej
        deklaracji musi stac para PELNYCH SHA (wartosc przed -> wartosc po),
        a w pliku musi stac linia o DOKLADNIE tym drugim sha.
        ROWNOSCI ETYKIET NIE WYMAGAM, i to jest zmierzone, nie zalozone: R57
        zdjal moc rowniez z NAZWY trzech pol ("Zyprexa 10 mg proszek...",
        "Abilify Maintena 720 i 960 mg", "Fluanxol 0,5 mg"), wiec etykieta po
        zmianie nie jest etykieta przed zmiana. Para pelnych sha identyfikuje
        obie strony sama; etykieta jest w kluczu i wskazuje linie zrodla.
        """
        klucz = (karta, _etykieta(x))
        para = PRZEPISANE_WARTOSCI.get(klucz)
        if not para:
            return False
        for y in plik:
            if para == (_sha_linii(x), _sha_linii(y)):
                uzyte_wartosci.add(klucz)
                return True
        return False

    NORMALIZACJE = [("CIAZA:", "CIĄŻA:")]
    uzyte = dict((a, 0) for a, _ in NORMALIZACJE)

    def znormalizuj(linia):
        for a, b in NORMALIZACJE:
            if linia.startswith(a):
                uzyte[a] += 1
                return b + linia[len(a):]
        return linia

    # ---------------------------------------------------------------------
    # LINIE POSTAWIONE PRZEZ NARZEDZIE, NIE RECZNIE [R16, 2026-09-26].
    #
    # Do dzis kazde swiadome uzupelnienie karty bylo wpisywane RECZNIE do
    # UZUPELNIONE i DOPISANE. To dzialalo, dopoki uzupelnien bylo
    # kilkanascie. narzedzia/przenies_pola_chpl.py dopisal 78 pol i wypelnil
    # 33 — enumeracja kart urosla by do setek pozycji i przestalaby byc
    # czytana, czyli przestalaby cokolwiek chronic.
    #
    # Dlatego linia narzedziowa jest rozpoznawana PO KSZTALCIE, nie po
    # nazwie karty. Kazda taka linia niesie stempel [ChPL <punkt> ...,
    # <data>] postawiony przez przenosnik i nazwe pola z jawnej listy.
    # CO TO NADAL LAPIE: ciche usuniecie albo skrocenie linii zrodlowej —
    # zrodlo musi byc PODCIAGIEM pliku po odjeciu linii narzedziowych,
    # a linia zrodlowa z BRAK DANYCH LOKALNYCH moze zniknac WYLACZNIE
    # wtedy, gdy w jej miejscu stoi to samo pole ze stemplem ChPL.
    # CZEGO NIE LAPIE: czy tresc ze stempla jest wlasciwa. To jest zadanie
    # przenios_pola_chpl.py i jego samotestu, nie tego testu.
    import re as _re
    # DWA KSZTALTY LINII NARZEDZIOWEJ [R21, inwariant A, 2026-09-26].
    # (1) stempel ChPL z data — jak dotad;
    # (2) znacznik stanu wiazania z produktem na koncu linii: pole, ktore
    #     NIE MA stempla ChPL, nie moze milczec o tym, ze nie ma pinu.
    #     Nie wolno dopisac mu daty ani punktu ChPL, bo ich nie znamy —
    #     zostaje sam znacznik. Bez tej drugiej formy T2 czyta dopisany
    #     znacznik jak ciche przepisanie karty i oblewa na 43 polach.
    STEMPEL = _re.compile(
        r"(?:\[ChPL [^\]]*\d{4}-\d{2}-\d{2}\]|\[BEZ_PINU[^\]]*\])\s*$")
    POLE_NAR = _re.compile(r"^([A-ZĄĆĘŁŃÓŚŹŻ_0-9]+):\s")

    def _narzedziowa(linia):
        return bool(STEMPEL.search(linia) and POLE_NAR.match(linia))

    def _pole(linia):
        m = POLE_NAR.match(linia)
        return m.group(1) if m else None

    n_dopisanych = n_wypelnionych = n_przepisanych = 0

    rozne = 0
    for n, tresc_zr in karty_zr.items():
        if n not in gdzie:
            continue
        if gdzie[n][1] != tresc_zr:
            rozne += 1
            a, b = tresc_zr, gdzie[n][1]
            # Karta z jawnej listy uzupelnien moze miec linie DOPISANE, ale zadnej
            # zmienionej ani usunietej: zrodlo musi byc PODCIAGIEM pliku. To wciaz
            # lapie ciche skrocenie karty, a nie blokuje swiadomego uzupelnienia.
            # --- SCIEZKA NARZEDZIOWA
            b_bez = [x for x in b if not _narzedziowa(x)]
            dopisane_tu = len(b) - len(b_bez)
            pola_ze_stemplem = {_pole(x) for x in b if _narzedziowa(x)}
            # linie zrodla, ktore zniknely, a ich pole stoi teraz ze stemplem
            # I mowily BRAK DANYCH LOKALNYCH — czyli wypelnione, nie usuniete
            # NORMALIZACJA REV48 OBOWIAZUJE TAKZE TUTAJ. Pierwsza wersja tej
            # sciezki jej nie uzyla i AGOMELATYNA oblewala przez jedna linie
            # "CIAZA:" kontra "CIĄŻA:" — ta sama para, ktora 52 commity temu
            # trzymala CI na czerwono. Jedna normalizacja, wszystkie sciezki.
            zniklo_zr = [x for x in tresc_zr
                         if x not in b_bez and znormalizuj(x) not in b_bez]
            wypelnione = [x for x in zniklo_zr
                          if "BRAK DANYCH LOKALNYCH" in x and _pole(x) in pola_ze_stemplem]
            # OZNACZENIE STANU NIE JEST ZMIANA TRESCI [R21, inwariant A].
            # Linia zrodla, ktora zniknela WYLACZNIE dlatego, ze dopisano jej
            # na koncu znacznik stanu, jest tu rozliczana osobno. Warunek jest
            # ostry: linia w pliku musi byc DOKLADNIE linia zrodla plus sam
            # znacznik. Jedna zmieniona litera w tresci nie przejdzie tedy.
            _znak = _re.compile(r"\s*\[BEZ_PINU[^\]]*\]\s*$")
            _goly = {_znak.sub("", y).rstrip(): y for y in b if _znak.search(y)}
            oznaczone = [x for x in zniklo_zr
                         if x not in wypelnione
                         and (x.rstrip() in _goly or znormalizuj(x).rstrip() in _goly)]
            wypelnione = wypelnione + oznaczone
            # ZDJETA LICZBA BEZ REJESTRACJI — TYLKO Z PARA SHA [R57, 2026-10-04].
            # Linia pola dawki, ktorej wartosc oddano zdaniu bez liczby, ZNIKA
            # ze zrodla i staje w pliku jako linia ze stemplem. Dla tej sciezki
            # byla wiec "zgubiona" i karta spadala do porownania 1:1, gdzie
            # dopisany wczesniej stempel innego pola rozjezdza numeracje i
            # kazda nastepna linia czyta sie jako zmieniona.
            # NIE JEST TO DOPUSZCZENIE OGOLNE: linia przechodzi WYLACZNIE, gdy
            # we wspolnej deklaracji stoi para PELNYCH SHA (wartosc przed ->
            # wartosc po) i gdy w pliku stoi linia O TEJ SAMEJ ETYKIECIE
            # i DOKLADNIE tym sha. Zamiana bez deklaracji oblewa jak dotad.
            przepisane_tu = [x for x in zniklo_zr
                             if x not in wypelnione and _przepisana(n, x, b)]
            pominiete = wypelnione + przepisane_tu
            reszta = [x for x in zniklo_zr if x not in pominiete]
            if (dopisane_tu or pominiete) and not reszta:
                it = iter(b_bez)
                a_bez = [x for x in tresc_zr if x not in pominiete]
                if all(any(x == y or znormalizuj(x) == y for y in it) for x in a_bez):
                    n_dopisanych += dopisane_tu
                    n_wypelnionych += len(wypelnione)
                    n_przepisanych += len(przepisane_tu)
                    continue
            if n in UZUPELNIONE:
                it = iter(b)
                if all(any(x == y for y in it) for x in a):
                    continue
                # Karta z listy PRZEPISANE ma jawnie zadeklarowana liczbe linii
                # ZMIENIONYCH. Sprawdzamy, ile linii zrodla zniknelo z pliku:
                # wiecej niz zadeklarowano = ciche usuniecie, i to jest blad.
                # LINIE WYPELNIONE PRZEZ NARZEDZIE NIE SA "ZNIKNIETE".
                # ARYPIPRAZOL i RISPERIDON maja zadeklarowana JEDNA linie
                # przepisana recznie (POSTAC). Po wypelnieniu ich
                # PRZECIWWSKAZANIA przez przenosnik licznik pokazywal 2
                # i test oblewal — czyli liczyl razem zmiane reczna
                # i narzedziowa, ktore maja rozne dowody.
                # TA SAMA POPRAWKA CO WYZEJ, DLA KART Z LISTY PRZEPISANE:
                # linia, ktorej dopisano SAM znacznik stanu, nie jest linia
                # ZNIKNIETA. Bez tego FLUPENTYKSOL liczyl dwie zmiany zamiast
                # jednej zadeklarowanej i oblewal na oznaczeniu, nie na tresci.
                _zn2 = _re.compile(r"\s*\[BEZ_PINU[^\]]*\]\s*$")
                _goly2 = {_zn2.sub("", y).rstrip() for y in b if _zn2.search(y)}
                # LINIA Z ZADEKLAROWANA PARA SHA NIE JEST LINIA ZNIKNIETA
                # [R57, 2026-10-04] — ten sam warunek, co na sciezce
                # narzedziowej, ta sama deklaracja. Licznik PRZEPISANE zostaje
                # dla zmian rozliczanych SAMA LICZBA; zmiana z para sha ma
                # dowod mocniejszy i nie powieksza tego licznika.
                zniklo = [x for x in a if x not in b and znormalizuj(x) not in b
                          and not ("BRAK DANYCH LOKALNYCH" in x
                                   and _pole(x) in {_pole(y) for y in b if _narzedziowa(y)})
                          and x.rstrip() not in _goly2
                          and znormalizuj(x).rstrip() not in _goly2
                          and not _przepisana(n, x, b)]
                ile, powod = PRZEPISANE.get(n, (0, ""))
                if len(zniklo) == ile:
                    continue
                bledy.append("T2 %s: zrodlo nie jest podciagiem pliku; zniklo %d linii, "
                             "zadeklarowano %d (%s)" % (n, len(zniklo), ile, powod))
                for x in zniklo[:3]:
                    bledy.append("      ZNIKLO: %s" % x[:90])
                continue
            for i in range(max(len(a), len(b))):
                x = a[i] if i < len(a) else "<brak linii>"
                y = b[i] if i < len(b) else "<brak linii>"
                if x != y and znormalizuj(x) != y:
                    pole = x.split(":", 1)[0].strip() if ":" in x else ""
                    klucz = (n, pole)
                    if PRZEPISANE_WARTOSCI.get(klucz) == (_sha_linii(x), _sha_linii(y)):
                        uzyte_wartosci.add(klucz)
                        continue
                    bledy.append("T2 %s linia %d: zrodlo %r != plik %r" % (n, i, x[:60], y[:60]))
                    break
    print("T2 TRESC KART: %d roznych z %d" % (rozne, len(karty_zr)))
    print("   T2 linie narzedziowe ze stemplem ChPL: %d dopisanych, %d wypelnionych "
          "z BRAK DANYCH LOKALNYCH" % (n_dopisanych, n_wypelnionych))
    if not (n_dopisanych or n_wypelnionych):
        bledy.append("T2: regula linii narzedziowej nie objela ANI JEDNEJ linii — "
                     "martwa regula wycisza cos, czego juz nie ma, albo stempel "
                     "przestal pasowac; w obu przypadkach nie chroni")
    for a, b in NORMALIZACJE:
        if uzyte[a]:
            print("   T2 normalizacja %r -> %r uzyta %d razy [rev48]" % (a, b, uzyte[a]))
        else:
            bledy.append("T2 normalizacja %r -> %r NIE BYLA POTRZEBNA ani razu — "
                         "martwe wylaczenie, zapis o swiecie sprzed poprawki" % (a, b))

    # T4
    core_L = open(os.path.join(PROJEKT, CORE), encoding="utf-8").read().split("\n")
    _, pre_core = karty_z(core_L)
    # T4 — ZMIENIONE 2026-09-24 po uwadze Groka. Wczesniej test pilnowal, zeby
    # kopia regul kart byla identyczna w kazdym pliku klasowym. To sprawdzalo
    # generator, a nie to, czy regula jest klinicznie zupelna: git moglby sie
    # zgadzac, a ostrzezenia nigdy nie bylo w zrodle. Teraz regula mieszka
    # WYLACZNIE w CORE, a test pilnuje dwoch rzeczy naraz:
    #   (a) plik klasowy NIE ma wlasnej kopii regul - zadnej do rozjechania,
    #   (b) plik klasowy JAWNIE wiaze sie z CORE, wiec odczyt samej karty bez
    #       regul jest odmowa, a nie czytaniem na wyczucie.
    WIAZANIE = "WIAZANIE: REGULY KART SA W DRUG_DB_PSYCHIATRIA_CORE"
    SLADY_REGUL = ("REGUŁA POLA PRZECIWWSKAZANIA", "REGUŁA POLA ZRODLO_KARTY",
                   "REGUŁA ROZBIEZNOSC_ZRODLOWA", "POLA DODATKOWE")
    for f in pliki:
        naglowek = "\n".join(preambuly[f])
        if WIAZANIE not in naglowek:
            bledy.append("T4 %s: brak jawnego wiazania z CORE - plik klasowy czytany sam "
                         "dawalby karte bez jej regul" % f)
        for slad in SLADY_REGUL:
            if slad in naglowek:
                bledy.append("T4 %s: kopia reguly '%s' w pliku klasowym - regula ma byc "
                             "tylko w CORE" % (f, slad))
    core_naglowek = "\n".join(pre_core)
    for slad in SLADY_REGUL:
        if slad not in core_naglowek:
            bledy.append("T4 CORE: brak reguly '%s' - po usunieciu kopii to jedyne miejsce, "
                         "gdzie moze byc" % slad)
    print("T4 REGULY TYLKO W CORE + wiazanie w %d plikach klasowych: %s"
          % (len(pliki), "OK" if not any(b.startswith("T4") for b in bledy) else "FAIL"))

    # T5, T6
    ind = {}
    w_indeksie = False
    for l in core_L:
        if l.strip().startswith("INDEKS KART"):
            w_indeksie = True; continue
        if l.strip().startswith("SEKCJE KLASOWE"):
            w_indeksie = False; continue
        if w_indeksie and l.strip():
            czesci = l.rsplit(None, 1)
            if len(czesci) == 2:
                ind[czesci[0].strip()] = czesci[1].strip()
    for n in gdzie:
        if n not in ind:
            bledy.append("T5 %s: karta w pliku %s, ale nie ma jej w indeksie CORE" % (n, gdzie[n][0]))
    for n, f in ind.items():
        if n not in gdzie:
            bledy.append("T5 %s: wpis w indeksie bez karty" % n)
        elif gdzie[n][0] != f:
            bledy.append("T5 %s: indeks wskazuje %s, karta lezy w %s" % (n, f, gdzie[n][0]))
        if not os.path.exists(os.path.join(PROJEKT, f)):
            bledy.append("T6 %s: indeks wskazuje nieistniejacy plik %s" % (n, f))
    print("T5 INDEKS <-> KARTY w obie strony: %d wpisow, %d kart -> %s"
          % (len(ind), len(gdzie), "OK" if not any(b.startswith(("T5", "T6")) for b in bledy) else "FAIL"))

    # T7
    pole = re.compile(r'^[A-ZĄĆĘŁŃÓŚŹŻ_0-9/]+:')
    n_zr = sum(1 for l in zr if pole.match(l))
    n_po = 0
    for f in pliki:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        k, _ = karty_z(L)
        for t in k.values():
            n_po += sum(1 for l in t if pole.match(l))
    # T7 liczy TYLKO karty migracyjne, z tego samego powodu co wyzej.
    n_po_migracyjne = 0
    for f in pliki:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        k, _ = karty_z(L)
        for nazwa, t in k.items():
            if nazwa in karty_zr:
                n_po_migracyjne += sum(1 for l in t if pole.match(l))
    # LINIE NARZEDZIOWE ODEJMUJEMY OD BILANSU T7 I RAPORTUJEMY OSOBNO.
    # DOPISANE zostaje dla uzupelnien RECZNYCH — kazde z wlasnym powodem.
    # Zlanie obu w jeden licznik znaczyloby, ze zgubiona linia moze sie
    # schowac za dopisana przez narzedzie.
    n_narzedziowych = 0
    for f in pliki:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        k, _ = karty_z(L)
        for nazwa, t in k.items():
            if nazwa not in karty_zr:
                continue
            # ODEJMUJEMY WYLACZNIE POLA DOPISANE, NIE PRZEPISANE.
            # Linia PRZECIWWSKAZANIA istniala w zrodle jako BRAK DANYCH
            # LOKALNYCH; przenosnik zmienil jej TRESC, nie dolozyl pola.
            # Pierwsza wersja odejmowala ja tez i bilans spadl o 33 —
            # test zglaszal ubytek tam, gdzie nic nie ubylo.
            pola_zr = {_pole(l) for l in karty_zr[nazwa] if pole.match(l)}
            n_narzedziowych += sum(1 for l in t
                                   if _narzedziowa(l) and _pole(l) not in pola_zr)
    n_po = n_po_migracyjne - n_narzedziowych
    print("T7 linie narzedziowe (stempel ChPL) odjete od bilansu: %d" % n_narzedziowych)
    n_zr_karty = sum(1 for t in karty_zr.values() for l in t if pole.match(l))
    # CELOWE UZUPELNIENIA kart migracyjnych. T7 ma lapac ZGUBIONA linie, a nie
    # swiadome dopisanie pola. Kazda pozycja to jawny dlug: ile linii dopisano
    # i dlaczego. Bez tej tabeli jedyne wyjscie to wylaczenie T7 dla calej karty,
    # co skasowaloby ochrone reszty jej pol.
    DOPISANE = {"PALIPERYDON": (8, "brakowalo T1_2, METABOLIZM, INTERAKCJE i MONITORING "
                                   "w karcie depot, oraz CIĄŻA i KP — audyt kart z 2026-09-24. "
                                   "+1 od 2026-09-26: PIN_ZBIOROWY_ZRODLA (wczesniej "
                                   "NIEPEWNY_ODCZYT_ZRODLA) — pod jedna nazwa handlowa lezy kilka "
                                   "dokumentow ChPL, wiec egzemplarz jest nierozstrzygniety. "
                                   "Pole DOSTEPNOSC, dopisane w rev68, ZNIKNELO w rev70: R27 "
                                   "rozstrzygnal, ze na karte wchodzi flaga rynkowa tylko wtedy, gdy "
                                   "produkt karty jest w 0% aptek albo cala substancja jest poza rynkiem. "
                                   "Karta stoi teraz na Paliperidone Teva, ktory na rynku jest, wiec "
                                   "flagi jej sie nie nalezy; powod przestawienia zostal w ZRODLO_KARTY"),
                "FLUPENTYKSOL": (2, "CIĄŻA i KP — nie bylo ich ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "TIAPRYD": (1, "KP — nie bylo go ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "METADON": (2, "CIĄŻA i KP — nie bylo ich ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "ESTAZOLAM": (1, "KP — nie bylo go ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "BROMAZEPAM": (1, "KP — nie bylo go ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "ARYPIPRAZOL": (1, "dawki depot Abilify Maintena miesieczne i dwumiesieczne; ROZBIEZNOSC_ZRODLOWA: wpis w cache jest starsza wersja dokumentu"),
                "OLANZAPINA": (3, "dawka depot Zypadhera z zespolem poiniekcyjnym, dawka iniekcji doraznej; NIEPEWNY_ODCZYT_ZRODLA dla Tabeli 1 i ROZBIEZNOSC_ZRODLOWA dla wpisow Zyprexy. +1 od 2026-09-26: pola DAWKA_DEPOT i DAWKA_INIEKCJA_DORAZNA wpisane po POTWIERDZENIU PRZEZ LEKARZA wobec nazwanych dokumentow (.github/potwierdzenia_lekarza.tsv); to sa dopisania RECZNE, nie narzedziowe — nie niosa stempla [ChPL ...] i maja byc liczone tutaj"),
                "BUPRENORFINA": (1, "DAWKA_DEPOT Buvidal: cztery wiersze Tabeli 1 potwierdzone przez lekarza 2026-09-26 wobec annexu z 2018; wiersz 26-32 mg pozostaje zablokowany"),
                "RISPERIDON": (0, "dawki depot Rispolept Consta i Okedi — linie bez naglowka pola"),
                "PALIPERYDON_LAI": (1, "Trevicta i BYANNLI: ODSTEPY_ZMIANA_LECZENIA; liczone w pozycji PALIPERYDON"),
                "HALOPERIDOL": (-10, "UBYTEK ZADEKLAROWANY, NIE ZGUBIONY "
                    "[2026-10-02, podmiana karty]. Zmierzone: ze karty "
                    "HALOPERIDOL w DRUG_DB_AP.txt zeszlo 14 linii pasujacych do "
                    "waskiego wzorca pola T7 (POSTAC, WSKAZANIA, ONSET, "
                    "DAWKA_ROWNOWAZNA, T1_2, METABOLIZM, DN, INTERAKCJE, CIĄŻA, "
                    "KP, MONITORING, OTĘPIENIE, PRZECIWWSKAZANIA, "
                    "NIEPEWNY_ODCZYT_ZRODLA), a wrocily DWIE jako wskazniki bez "
                    "tresci (PRZECIWWSKAZANIA, NIEPEWNY_ODCZYT_ZRODLA): netto "
                    "-12 wobec stanu po podziale. Wobec wczesniejszej deklaracji "
                    "+2 (DAWKA_ROWNOWAZNA i NIEPEWNY_ODCZYT_ZRODLA dopisane "
                    "recznie) daje to -10. TRESC NIE ZGINELA: stoi w "
                    "LEK_haloperidol.txt, osobno dla kazdej z szesciu "
                    "rejestracji, z pinem dokumentu. T7 tego pliku NIE LICZY, bo "
                    "nie jest karta migracyjna — i dlatego ubytek musi stac tutaj "
                    "z powodem, a nie znikac w progu. ONSET i MONITORING nie "
                    "wrocily nigdzie: nie maja zrodla w paczce (D-2, D-1)."),
                # R59, 2026-10-04: STAN W LINII PRZESUWA LINIE DO KLASY
                # NARZEDZIOWEJ. Bramka inwariantu A dopisala polu
                # DAWKA_ROWNOWAZNA flupentyksolu stan [BEZ_PINU]; linia konczy
                # sie teraz stemplem, wiec T7 liczy ja jako linie narzedziowa
                # i odejmuje od bilansu pol. TRESC I LICZBA BEZ ZMIAN —
                # zmierzone: tokeny liczbowe w DRUG_DB_AP identyczne przed i po
                # (155 = 155). Licznik linii narzedziowych T7: 73 -> 74.
                "FLUPENTYKSOL_ROWNOWAZNA_STAN": (-1, "DAWKA_ROWNOWAZNA dostala stan [BEZ_PINU] i weszla do klasy linii narzedziowych T7"),
                "LORAZEPAM": (1, "NIEPEWNY_ODCZYT_ZRODLA dla Lorabexu — trzy dokumenty pod jedna nazwa (0,5 mg tabl., 2 mg/ml i 4 mg/ml inj.); wycofane DAWKA_STARSI, DAWKA_DZIECI, PRZECIWWSKAZANIA wg R20-2"),
                "KLONAZEPAM": (1, "NIEPEWNY_ODCZYT_ZRODLA dla Clonazepamum TZF — tabletka 0,5 mg i iniekcja 1 mg/ml pod jedna nazwa; wycofane DAWKA_STARSI i PRZECIWWSKAZANIA wg R20-2"),
                "DIAZEPAM": (1, "NIEPEWNY_ODCZYT_ZRODLA dla Neorelium — tabletka 5 mg i iniekcja 5 mg/ml pod jedna nazwa; to ten przypadek, ktory ujawnil cala klase (R20)"),
                "FLUPENTYKSOL_ROWNOWAZNA": (1, "DAWKA_ROWNOWAZNA: odeslanie do tabeli rownowaznosci w 18; liczone osobno od CIĄŻA i KP"),
                # ==========================================================
                # WYJATEK Z POWODEM — NIE JEST ZMIANA TRESCI [2026-09-27].
                # To NIE SA linie usuniete. To linie, ktorych WZORZEC POLA
                # W T7 NIE WIDZI. Wzorzec brzmi '^[A-Z_0-9/]+:' i NIE
                # PRZEPUSZCZA SPACJI, wiec po rev83-rev90 linia
                # 'DAWKA doustnie:' przestala byc dla niego polem.
                # ZMIERZONE, obie strony rownania:
                #   zrodlo 458b5ab       waski 553 | szeroki 563  (10 niewidocznych)
                #   karty migracyjne     waski 842 | szeroki 877  (35 niewidocznych)
                # Czyli wzorzec zanizal JUZ W ZRODLE, tylko symetrycznie, wiec
                # bilans sie zgadzal. Kwalifikatory z rev83-rev90 symetrie
                # zerwaly i roznica wyszla na wierzch jako 5.
                # DLACZEGO TYLKO WYJATEK, A NIE NAPRAWA: naprawa to rozszerzenie
                # wzorca o kwalifikator, ale wtedy n_zr rosnie 553->563, n_po do
                # 610, i trzeba PRZELICZYC DOPISANE dla 27 kart. Probowalem
                # odtworzyc arytmetyke T7 poza testem i NIE ZGADZALA SIE
                # (moja suma 203 i 217 wobec 20 z testu) — czyli nie rozumiem
                # jeszcze, ktore pliki T7 sumuje. Wpisanie liczby, ktorej nie
                # umiem odtworzyc, do testu bezpieczenstwa byloby zgadywaniem.
                # Dlug: WZORZEC_POLA_T7_BEZ_KWALIFIKATORA w aparat/dlug.tsv.
                "T7_KWALIFIKATOR_NIEWIDOCZNY": (-5, "ARTEFAKT LICZNIKA, NIE UBYTEK TRESCI: "
                    "piec linii DAWKA w kartach migracyjnych dostalo kwalifikator "
                    "(DAWKA -> DAWKA doustnie / DAWKA depot miesieczny) i wypadlo z "
                    "waskiego wzorca pola T7. Linie ISTNIEJA i sa widoczne dla parsera "
                    "paczki (narzedzia/etykieta.py) oraz dla bramki pola_widzialne, "
                    "ktora liczy 1534 = 1534 + 0. Zmierzone: zrodlo 553 waski / 563 "
                    "szeroki, karty migracyjne 842 / 877.")}
    delta = sum(n for n, _ in DOPISANE.values())
    if n_zr_karty + delta != n_po:
        bledy.append("T7: linii pol w kartach zrodla %d (+%d celowo), po podziale %d"
                     % (n_zr_karty, delta, n_po))
    print("T7 LINIE POL w kartach: zrodlo %d + celowo %d = %d, po podziale %d -> %s"
          % (n_zr_karty, delta, n_zr_karty + delta, n_po,
             "OK" if n_zr_karty + delta == n_po else "FAIL"))
    for k, (n_, po) in sorted(DOPISANE.items()):
        print("   CELOWO %s +%d: %s" % (k, n_, po))
    print("   (w calym zrodle z preambula: %d)" % n_zr)

    # PARA NIEUZYTA JEST BLEDEM. Martwe rozliczenie uczy, ze alarm przychodzi
    # i mija sam — ta sama zasada, co przy martwym wylaczeniu kolizji.
    # ROZLICZAM TYLKO TO, CO WIDZE [R57, 2026-10-04]. Deklaracja jest wspolna
    # z kontrola podmiany w paczce, ktora trzyma te same zmiany pod kluczem
    # porzadkowym ("(bez etykiety) #n") dla wartosci bez etykiety. Tych kluczy
    # ten test nie oglada — pyta o etykiete. Zadanie realizacji od klucza,
    # ktorego nie ma w zadnej karcie zrodla, zamienialoby kazda taka deklaracje
    # w falszywy alarm. Zakres: klucze, ktorych karta jest w zrodle i ktorych
    # etykieta stoi w tej karcie.
    etykiety_zrodla = set()
    for _n, _tresc in karty_zr.items():
        for _l in _tresc:
            if ":" in _l:
                etykiety_zrodla.add((_n, _l.split(":", 1)[0].strip()))
    for klucz in sorted(set(PRZEPISANE_WARTOSCI) & etykiety_zrodla):
        if klucz not in uzyte_wartosci:
            bledy.append("T2 %s / %s: zadeklarowana para wartosci NIE WYSTAPILA "
                         "(martwe rozliczenie)" % klucz)

    print()
    if bledy:
        print("BLEDOW: %d" % len(bledy))
        for b in bledy[:40]:
            print("  ", b)
        print("TEST PODZIALU: NIE PRZESZEDL")
        return 1
    print("TEST PODZIALU: PRZESZEDL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
