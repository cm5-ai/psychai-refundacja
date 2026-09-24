#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AUDYT KOMPLETNOSCI — jeden przebieg na klase bledu "czy to w ogole istnieje".

POWOD. 2026-09-24 znalazlem szesc bledow i wszystkie byly tym samym orzecznikiem:
  1. ChPL piracetamu to skan -> wpis z zerem punktow i stanem OK
  4. manifest: SUMA sie zgadza, wykaz hashy nieaktualny
  5. EKSPOZYCJA tylko w 187 z 395 wpisow
  6. 18 decyduje o 31 lekach, ktore nie maja karty
Kazdy znaleziony PRZYPADKIEM, przy innej robocie. Dotychczasowe testy pytaly
"czy znane pole X jest POPRAWNE", nigdy "czy X W OGOLE ISTNIEJE".
Grok nazwal predykat: GREEN-ON-EMPTY - test przechodzi, bo zbior wejsciowy
jest pusty albo pole nie istnieje, wiec nie ma czego oblac.

ZASADA. Nie lista pol, ktore akurat pamietam. Zlaczenie zbiorow i WYMAGALNOSC
WYPROWADZONA Z ROLI:
  KARTA            -> naglowek + sekcja-wlasciciel + wpis indeksu + pole dawki
  SEKCJA           -> ma pod soba karte
  WPIS INDEKSU     -> istniejaca karta we wskazanym pliku
  WPIS CACHE (OK)  -> warstwa tekstowa (punkty>0) + postac + EKSPOZYCJA
  PRODUKT DEPOT    -> interwal podawania w tresci
  POZYCJA MANIFESTU-> plik istnieje + hash sie zgadza + ZBIOR plikow = zbior wykazu
  PLIK WYDANIA     -> identyczny z projekt/
  LEK W 18         -> karta albo jawny, zatwierdzony brak
  SUBSTANCJA CACHE -> plik istnieje i deklaruje te sama substancje

KAZDA REGULA RAPORTUJE N_WEJSCIE. Regula z N_WEJSCIE = 0 jest sama w sobie
znaleziskiem: nie ma czego sprawdzac, wiec jej zielony kolor nic nie znaczy.
To jest wlasnie green-on-empty i dlatego audyt mowi o tym glosno.

PARSER NIEZALEZNY OD GENERATORA. Naglowki kart wykrywamy STRUKTURALNIE
(kolumna zero, bez malych liter, bez dwukropka, linia pola w ciagu czterech
linii), a nie regexem dopuszczonych znakow. Dzisiejszy blad z ukosnikiem
przeszedl wlasnie dlatego, ze test powtarzal regex generatora.
"""
import glob, hashlib, json, os, re, sys

KAT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(KAT)
sys.path.insert(0, os.path.join(REPO, "slownik"))
import inn

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
def _wydanie():
    """Najnowszy katalog wydania, NIE zaszyty numer. Pierwsza wersja miala
    wpisane 'rev34'; po przejsciu na rev35 regula R9 dostala ZERO WEJSCIA
    i swiecila na zielono, nie sprawdzajac niczego. Audyt zlapal sam siebie -
    dokladnie po to kazda regula raportuje N_WEJSCIE."""
    k = os.path.join(PACZKA, "wydanie")
    kat = sorted(d for d in os.listdir(k) if d.startswith("rev")) if os.path.isdir(k) else []
    return os.path.join(k, kat[-1]) if kat else os.path.join(k, "BRAK")


WYDANIE = _wydanie()
KLASOWE = ["DRUG_DB_AD.txt", "DRUG_DB_AP.txt", "DRUG_DB_BZD.txt",
           "DRUG_DB_STAB.txt", "DRUG_DB_ADHD_UZAL.txt"]
CORE = "DRUG_DB_PSYCHIATRIA_CORE.txt"
POLE = re.compile(r'^[A-ZĄĆĘŁŃÓŚŹŻ_0-9/]+:')
# CELOWO BEZ STALEJ "ile lekow z 18 nie ma karty". Stala BRAK_KARTY_ZATWIERDZONY
# = 31 stala tu, nikt jej nie czytal, a stan dawno byl inny (dzis 2). Liczba
# zapisana w kodzie i nieweryfikowana to ten sam blad, ktory audyt ma lapac.
# Zrodlem tej liczby jest test_pokrycie_18, ktory ja WYLICZA.

wyniki = []


def zglos(regula, n_we, znaleziska, opis):
    wyniki.append({"regula": regula, "n_we": n_we, "znaleziska": znaleziska, "opis": opis})


def plaski(s):
    return re.sub(r"[^a-z0-9]", "", inn.bez_ogonkow(s or "").lower())


def naglowki(linie):
    """STRUKTURALNIE, nie regexem dozwolonych znakow."""
    # Prog 2 znaki, nie 4: karta LIT byla niewidoczna dla obu detektorow.
    out = []
    for i, l in enumerate(linie):
        t = l.strip()
        if l[:1].isspace() or t.startswith("-"):
            continue
        if not t or len(t) < 2 or ":" in t or any(c.islower() for c in t):
            continue
        if any(POLE.match(x.strip()) for x in linie[i + 1:i + 5]):
            out.append((i, l))
    return out


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    # ---------------------------------------------------------- zbiory
    # Sekcja to naglowek, ktory NIE MA pod soba pola dawki bezposrednio -
    # rozpoznajemy po jawnej liscie plus po ukosniku w nazwie. Jawnie, zeby
    # nie zgadywac: kazda nowa sekcja ma byc tu dopisana, a nie wykryta.
    # PELNA, JAWNA LISTA SEKCJI. Pierwsza wersja audytu uznawala za sekcje
    # kazdy naglowek Z UKOSNIKIEM - i natychmiast wpadla w ten sam dol co rano
    # generator: KWAS WALPROINOWY / WALPROINIAN to KARTA LEKU, a nie sekcja.
    # Ukosnik nie jest cecha sekcji, tylko cecha zapisu nazwy. Lista musi byc
    # wymieniona, nie zgadywana; nowa sekcja ma byc tu dopisana recznie.
    NAZWY_SEKCJI = {"SSRI", "SNRI", "INNE PRZECIWDEPRESYJNE", "PRZECIWPSYCHOTYCZNE",
                    "TCA / STARSZE", "STABILIZATORY NASTROJU", "GABAPENTYNOIDY",
                    "PRZECIWPADACZKOWE W UZYCIU PSYCHIATRYCZNYM",
                    "BENZODIAZEPINY", "LEKI Z / NASENNE NIEBENZODIAZEPINOWE",
                    "ANKSJOLITYKI I NASENNE NIE-BZD",
                    "PSYCHOSTYMULANTY I ADHD",
                    "UZALEŻNIENIA / LECZENIE SUBSTYTUCYJNE"}
    karty = {}          # nazwa karty -> (plik, linia)
    sekcje = {}         # (plik, linia) -> nazwa sekcji
    for f in KLASOWE:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        for i, h in naglowki(L):
            if h in NAZWY_SEKCJI:
                sekcje[(f, i)] = h
            else:
                karty[h] = (f, i)

    coreL = open(os.path.join(PROJEKT, CORE), encoding="utf-8").read().split("\n")
    indeks, w_ind = {}, False
    for l in coreL:
        if l.strip().startswith("INDEKS KART"):
            w_ind = True; continue
        if l.strip().startswith("SEKCJE KLASOWE"):
            w_ind = False; continue
        if w_ind and l.strip():
            c = l.rsplit(None, 1)
            if len(c) == 2 and c[1].endswith(".txt"):
                indeks[c[0].strip()] = c[1].strip()

    # R1 KARTA -> wpis indeksu
    z = [k for k in karty if k not in indeks]
    zglos("R1 KARTA -> wpis w indeksie", len(karty), z,
          "karta bez wpisu w indeksie jest nieadresowalna (tak zginal walproinian)")

    # R2 WPIS INDEKSU -> istniejaca karta we WSKAZANYM pliku
    z = []
    for k, f in indeks.items():
        if k in NAZWY_SEKCJI:
            continue        # indeks wymienia tez sekcje - celowo, to nie sierota
        if k not in karty:
            z.append("%s: wpis bez karty" % k)
        elif karty[k][0] != f:
            z.append("%s: indeks wskazuje %s, karta w %s" % (k, f, karty[k][0]))
    zglos("R2 INDEKS -> karta w tym pliku", len(indeks), z, "wpis prowadzacy donikad")

    # R3 KARTA -> ma sekcje-wlasciciela (jakis naglowek sekcji WYZEJ w tym pliku)
    z = []
    for k, (f, i) in karty.items():
        if not any(sf == f and si < i for (sf, si) in sekcje):
            z.append("%s (%s): brak sekcji nad karta" % (k, f))
    zglos("R3 KARTA -> sekcja-wlasciciel", len(karty), z,
          "sekcja wiaze lek z BLOKIEM KLASY w 18; karta bez sekcji nie ma klasy")

    # R4 SEKCJA -> ma pod soba karte
    z = []
    for (sf, si), nz in sekcje.items():
        if not any(f == sf and i > si for (f, i) in karty.values()):
            z.append("%s (%s): sekcja bez kart" % (nz, sf))
    zglos("R4 SEKCJA -> ma karty", len(sekcje), z, "naglowek oderwany od swoich kart")

    # R5 KARTA -> ma pole dawki
    z = []
    for k, (f, i) in karty.items():
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        kon = min([j for (ff, j) in list(karty.values()) + list(sekcje) if ff == f and j > i] or [len(L)])
        if not any(re.match(r'^(DAWKA|MAX)', x) for x in L[i:kon]):
            z.append("%s (%s): karta bez pola DAWKA" % (k, f))
    zglos("R5 KARTA -> pole dawki", len(karty), z, "karta bez dawki nie odpowiada na pytanie wizyty")

    # R6 WPIS CACHE (OK) -> punkty>0 + postac + EKSPOZYCJA
    n, z = 0, []
    for fp in sorted(glob.glob(os.path.join(REPO, "chpl", "*.json"))):
        if os.path.basename(fp) == "INDEX.json":
            continue
        for p in json.load(open(fp, encoding="utf-8")).get("produkty", []):
            if p.get("stan") != "OK":
                continue
            n += 1
            e = os.path.basename(fp)[:-5] + "/" + str(p.get("nazwa"))
            if not (p.get("punkty") or {}):
                z.append(e + ": stan OK, zero punktow")
            if not p.get("postac"):
                z.append(e + ": stan OK, brak pola postac")
            elif p.get("EKSPOZYCJA") is None:
                z.append(e + ": stan OK, brak EKSPOZYCJI")
    zglos("R6 WPIS CACHE OK -> tresc + postac + ekspozycja", n, z,
          "wpis udajacy komplet; tak przeszly skany piracetamu")

    # R7 PRODUKT DEPOT -> interwal w tresci
    n, z = 0, []
    for fp in sorted(glob.glob(os.path.join(REPO, "chpl", "*.json"))):
        if os.path.basename(fp) == "INDEX.json":
            continue
        for p in json.load(open(fp, encoding="utf-8")).get("produkty", []):
            e = (p.get("EKSPOZYCJA") or {}).get("ekspozycja")
            if e not in ("DEPOT", "POSREDNIA"):
                continue
            n += 1
            tekst = " ".join((p.get("punkty") or {}).values()).lower()
            # WZORZEC BYL ZA WASKI. Pierwsza wersja szukala wylacznie 'co N
            # tygodni' i zglosila Buvidal jako depot bez interwalu - a jego
            # ChPL pisze 'raz na tydzien' i 'raz na miesiac'. Falszywy alarm
            # uczy ignorowania alarmow, wiec wzorzec obejmuje teraz obie formy.
            if not re.search(r'(co\s+(\d+|dwa|trzy|cztery|kilka)\s*(–|-|do)?\s*\d*\s*'
                             r'(tygodni|tyg|dni|miesi)|raz\s+(na|w)\s+\w*\s*'
                             r'(tydzie|tygodn|miesi|dob)|co\s+(tydzie|tygodn|miesi))', tekst):
                z.append("%s/%s: %s bez interwalu w tresci" % (os.path.basename(fp)[:-5], p.get("nazwa"), e))
    zglos("R7 DEPOT -> interwal podawania", n, z,
          "depot bez interwalu to dawka bez czestosci")

    # R8 MANIFEST -> zbior plikow i hashe
    man = sorted(glob.glob(os.path.join(PROJEKT, "MANIFEST_TRESCI_rev*.txt")))[-1]
    wykaz = {}
    for l in open(man, encoding="utf-8"):
        m = re.match(r'^([0-9a-f]{12})\s+\d+\s+(.+)$', l.rstrip("\n"))
        if m:
            wykaz[m.group(2)] = m.group(1)
    POZA = ("00_CIAGLOSC", "REGULAMIN", "REJESTR", "MANIFEST")
    realne = {f for f in os.listdir(PROJEKT) if not f.startswith(POZA)}
    z = ["%s: w wykazie, nie ma pliku" % f for f in wykaz if f not in realne]
    z += ["%s: plik jest, nie ma w wykazie" % f for f in realne if f not in wykaz]
    z += ["%s: hash rozny od wykazu" % f for f in sorted(realne & set(wykaz))
          if sha(os.path.join(PROJEKT, f))[:12] != wykaz[f]]
    zglos("R8 MANIFEST -> zbior + hashe", len(wykaz), z,
          "zgodna SUMA przy nieaktualnym wykazie (znalezisko 4)")

    # R9 WYDANIE -> identyczne z projekt/
    n, z = 0, []
    if os.path.isdir(WYDANIE):
        for f in sorted(os.listdir(WYDANIE)):
            n += 1
            p1, p2 = os.path.join(WYDANIE, f), os.path.join(PROJEKT, f)
            if not os.path.exists(p2):
                z.append("%s: w wydaniu, nie ma w projekt/" % f)
            elif sha(p1) != sha(p2):
                z.append("%s: wydanie rozni sie od projekt/" % f)
    zglos("R9 WYDANIE (%s) -> zgodne z projekt" % os.path.basename(WYDANIE), n, z,
          "lekarz wgrywa nie to, co przetestowane")

    # R10 SUBSTANCJA W INDEKSIE CACHE -> plik istnieje i deklaruje te substancje
    idx = json.load(open(os.path.join(REPO, "chpl", "INDEX.json"), encoding="utf-8"))["substancje"]
    z, udokumentowane = [], []
    for s, v in idx.items():
        sciezka = v.get("plik")
        if not sciezka:
            # Wpis bez pliku, ale Z JAWNYM, DATOWANYM STANEM to nie jest
            # green-on-empty, tylko udokumentowana nieobecnosc - dokladnie to,
            # czego caly czas wymagam od paczki. Audyt ma lapac brak BEZ opisu.
            if v.get("stan") and v.get("sprawdzono"):
                udokumentowane.append("%s: %s (%s)" % (s, v["stan"], v["sprawdzono"]))
                continue
            z.append("%s: wpis indeksu bez pliku I BEZ opisanego stanu" % s)
            continue
        p = os.path.join(REPO, sciezka)
        if not os.path.exists(p):
            z.append("%s: indeks wskazuje nieistniejacy plik %s" % (s, sciezka))
        elif json.load(open(p, encoding="utf-8")).get("substancja") != s:
            z.append("%s: plik deklaruje inna substancje" % s)
    zglos("R10 INDEKS CACHE -> plik albo opisany brak", len(idx), z,
          "wpis bez pliku i bez opisu stanu; %d nieobecnosci udokumentowanych: %s"
          % (len(udokumentowane), ", ".join(x.split(":")[0] for x in udokumentowane)))

    # ------------------------------------------------- R11: wskazniki z 18
    # 2026-09-24. Sekcja POSTAC DEPOT w 18 mowila "DAWKI DEPOT BRAK W PACZCE"
    # dla arypiprazolu, olanzapiny i rysperydonu, a karty te dawki mialy od
    # trzech rewizji. Twierdzenie o NIEOBECNOSCI zestarzalo sie w ciszy i
    # WYGASZALO liczbe, ktora w paczce jest. Zadna z dziesieciu regul tego nie
    # widziala, bo wszystkie sprawdzaja OBECNOSC danych.
    # Naprawa: 18 nie orzeka o nieobecnosci, tylko WSKAZUJE pole karty
    # (ZRODLO_DAWKI: <plik> / <karta>, pola A, B, C). To przenosi ryzyko ze
    # starzejacego sie twierdzenia na starzejacy sie WSKAZNIK — i wlasnie
    # dlatego wskaznik musi miec swoja regule.
    m18 = os.path.join(PROJEKT, "18_PSYCH_PHARMA_FORMULARY_PL.txt")
    tresc18 = open(m18, encoding="utf-8").read()
    # wskaznik moze byc zawiniety na kilka linii — sklejamy akapit
    akapity = re.split(r"\n(?=\S)", tresc18)
    pary, z = [], []
    for a in akapity:
        for m in re.finditer(r"ŹRÓDŁO_DAWKI:\s*(DRUG_DB_[A-Z_]+)\s*/\s*([^,]+?),\s*pola?\s+(.+?)(?:\.|$)",
                             " ".join(a.split()), re.S):
            plik, karta, pola = m.group(1) + ".txt", m.group(2).strip(), m.group(3)
            for pole in [x.strip() for x in re.split(r",|;", pola) if x.strip()]:
                pary.append((plik, karta, pole))
    for plik, karta, pole in pary:
        sc = os.path.join(PROJEKT, plik)
        if not os.path.exists(sc):
            z.append("18 wskazuje nieistniejacy plik %s" % plik); continue
        L = open(sc, encoding="utf-8").read().split("\n")
        naglowki_pliku = [h for _, h in naglowki(L)]
        if karta not in naglowki_pliku:
            z.append("18 -> %s / %s: karty o tej nazwie w pliku NIE MA" % (plik, karta)); continue
        i = naglowki_pliku.index(karta)
        poz = [k for k, h in naglowki(L)]
        a, b = poz[i], (poz[i + 1] if i + 1 < len(poz) else len(L))
        if not any(l.startswith(pole) for l in L[a:b]):
            z.append("18 -> %s / %s: pola '%s' w karcie NIE MA — wskaznik wisi w prozni"
                     % (plik, karta, pole))
    zglos("R11 WSKAZNIK Z 18 -> istniejace pole karty", len(pary), z,
          "wskaznik prowadzacy donikad; N_WEJSCIE liczy pary (karta, pole)")

    # ------------------------------------------- R12: 18 nie orzeka o braku
    # WYROCZNIA JAWNA, nie green-on-empty: oczekiwana liczba recznych twierdzen
    # o nieobecnosci w tej sekcji wynosi DOKLADNIE 0, a N_WEJSCIE to liczba
    # linii sekcji — wiec zero znalezisk przy niezerowym wejsciu cos znaczy.
    # UCZCIWE OGRANICZENIE: ta regula lapie WYLACZNIE sformulowania z listy
    # ponizej. Jej zielony wynik NIE JEST dowodem, ze w sekcji nie ma innego
    # zdania o nieobecnosci — jest dowodem, ze nie ma TYCH. Nowe sformulowanie
    # trzeba tu dopisac. "Nie znalazlem" nie znaczy "nie ma".
    FRAZY_BRAKU = ["BRAK W PACZCE", "BRAK ChPL", "bez dawki", "NIE MA W PACZCE",
                   "DAWKI NIE MA", "BRAK DANYCH LOKALNYCH"]
    # Granica sekcji jest KOTWICA, wiec ma byc odporna na zmiane nazwy bloku
    # ponizej. 2026-09-24 "PRZELICZNIKI DOUSTNY" zmienilo sie w "PRZELICZNIKI
    # INTRA-LEK" i regula stracila WEJSCIE — audyt zglosil to jako green-on-empty
    # zamiast po cichu przejsc. Dlatego konczymy na PRZELICZNIKI, nie na
    # pelnej nazwie, a brak dopasowania nadal jest znaleziskiem.
    sek = re.search(r"^POSTAĆ DEPOT KONTRA.*?(?=^PRZELICZNIKI )",
                    tresc18, re.S | re.M)
    z2, linie_sek = [], []
    if not sek:
        z2.append("sekcji POSTAĆ DEPOT nie znaleziono — granice sie zmienily, regula slepa")
    else:
        linie_sek = sek.group(0).split("\n")
        for nr, l in enumerate(linie_sek, 1):
            if "ŹRÓDŁO_DAWKI" in l or l.strip().startswith("ZASADA TEJ SEKCJI"):
                continue
            for fr in FRAZY_BRAKU:
                if fr in l:
                    z2.append("linia %d orzeka o nieobecnosci ('%s'): %s" % (nr, fr, l.strip()[:70]))
    zglos("R12 18 NIE ORZEKA O NIEOBECNOSCI (oczekiwane 0)", len(linie_sek), z2,
          "zdanie o braku w sekcji POSTAĆ DEPOT; wyrocznia jawna: oczekiwane 0")

    # ------------------------------------------ R13: slot z 18 -> karta niesie liczbe
    # rev.47. Przeliczniki intra-lek (doustny -> depot tej samej substancji)
    # wyszly z 18 do kart; w 18 zostal SAM SLOT. Ryzyko przeniosla sie na slot:
    # moze wskazywac karte, ktora wcale nie ma przelicznika. Wtedy przy wizycie
    # nie ma liczby NIGDZIE, a 18 wyglada, jakby wiedzialo, gdzie ona jest.
    SLOT = re.compile(r"^\s{2}([a-ząćęłńóśźż]+)\.([a-z_]+)\s*->\s*(DRUG_DB_[A-Z_]+)\s*/\s*([A-ZĄĆĘŁŃÓŚŹŻ]+)\s*$")
    # UWAGA. Pierwsza wersja wymagala tylko "liczba w mg + slowo depot/dekanian".
    # Przeszla na ZEPSUTYM pliku, bo zaliczyla linie POSTAC z nazwa produktu
    # ("Decaldol 50 mg/ml, dekanian"). Identyfikator produktu udawal przelicznik
    # — ta sama pomylka, ktora ta rewizja wycina z 18. Regula wymaga teraz
    # wzorca PRZELICZANIA: krotnosci, strzalki albo slowa "odpowiada".
    # Wzorzec musi opisywac PRZELICZANIE, a nie mowienie o przeliczaniu.
    # Slowo "przelicz" bylo za luzne: zaliczalo linie "patrz 18, TABELA
    # ROWNOWAZNOSCI ... gdzie stoja PRZELICZENIA", czyli samo ODESLANIE.
    # Linie odsylajace sa wprost pomijane nizej.
    PRZELICZNIK_W_KARCIE = re.compile(
        r"(\d+\s*[-–]?\s*\d*\s*razy\s+wi[eę]k|=\s*\d+x|\dx\s*mg|"
        r"mg/d\s*->\s*\d|->\s*\d+\s*mg|odpowiada\s+\d)", re.I)
    sloty, z3 = [], []
    for l in tresc18.split("\n"):
        m = SLOT.match(l)
        if m: sloty.append(m.groups())
    for lek, rel, plik, karta in sloty:
        sc = os.path.join(PROJEKT, plik + ".txt")
        if not os.path.exists(sc):
            z3.append("%s.%s -> nie ma pliku %s.txt" % (lek, rel, plik)); continue
        Lk = open(sc, encoding="utf-8").read().split("\n")
        npl = [(k, h) for k, h in naglowki(Lk)]
        idx = [k for k, h in npl if h == karta]
        if not idx:
            z3.append("%s.%s -> karty %s nie ma w %s" % (lek, rel, karta, plik)); continue
        poz = [k for k, _ in npl]
        a0 = idx[0]; b0 = min([x for x in poz if x > a0] + [len(Lk)])
        # karta MUSI miec linie z liczba w mg i slowem opisujacym postac przedluzona
        ma = any(PRZELICZNIK_W_KARCIE.search(x) and "patrz 18" not in x
                 for x in Lk[a0:b0])
        if not ma:
            z3.append("%s.%s -> karta %s NIE NIESIE przelicznika; 18 wskazuje pustke"
                      % (lek, rel, karta))
    zglos("R13 SLOT Z 18 -> karta niesie liczbe", len(sloty), z3,
          "slot prowadzacy do karty bez przelicznika; N_WEJSCIE = liczba slotow w 18")

    # ------------------------------------------ R14: JEDNA tabela rownowaznosci
    # Przeliczenie MIEDZY roznymi substancjami depot nie nalezy do zadnej karty.
    # Ma byc jednym bytem w 18. Ta regula pilnuje obu stron: tabela w 18 istnieje
    # i ma wiersze, a ZADNA karta nie trzyma jej kopii. Kopia jest grozna nie
    # dlatego, ze sie powtarza, tylko dlatego, ze moze sie rozjechac po cichu.
    DEKANIANY = ("flupentyksol", "flufenazyn", "zuklopentyksol", "haloperidol", "haloperydol")
    tab = re.search(r"^TABELA RÓWNOWAŻNOŚCI DEPOTÓW.*?(?=^[A-ZĄĆĘŁŃÓŚŹŻ]{4}|\Z)",
                    tresc18, re.S | re.M)
    z4, n4 = [], 0
    if not tab:
        z4.append("w 18 NIE MA tabeli rownowaznosci depotow — jedyne zrodlo zniknelo")
    else:
        wiersze = [l for l in tab.group(0).split("\n")
                   if re.match(r"^\s{2}dekano?n?ian[a-z]*\s", l)]
        n4 += len(wiersze)
        if len(wiersze) < 2:
            z4.append("tabela rownowaznosci ma %d wierszy — przelicznik miedzy lekami "
                      "wymaga co najmniej dwoch" % len(wiersze))
    for f in KLASOWE:
        for l in open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n"):
            if "patrz 18" in l or "TABELA RÓWNOWAŻNOŚCI" in l:
                continue
            ile = sum(1 for d in DEKANIANY if d in l.lower())
            if ile >= 2 and re.search(r"\d+\s*mg", l):
                n4 += 1
                z4.append("%s: karta trzyma KOPIE tabeli rownowaznosci — %s" % (f, l.strip()[:70]))
    zglos("R14 JEDNA tabela rownowaznosci depotow", n4, z4,
          "brak tabeli w 18 albo kopia w karcie; N_WEJSCIE = wiersze tabeli + znalezione kopie")

    # ---------------------------------------------------------- raport
    print("=" * 78)
    print("AUDYT KOMPLETNOSCI — predykat GREEN-ON-EMPTY")
    print("=" * 78)
    puste, bledne, ok = 0, 0, 0
    for w in wyniki:
        stan = "BRAK WEJSCIA" if w["n_we"] == 0 else ("ZNALEZISKA" if w["znaleziska"] else "OK")
        if w["n_we"] == 0:
            puste += 1
        elif w["znaleziska"]:
            bledne += 1
        else:
            ok += 1
        print("%-44s N_WE %5d  %-12s %d" % (w["regula"][:44], w["n_we"], stan, len(w["znaleziska"])))
        for x in w["znaleziska"][:8]:
            print("      - %s" % x[:100])
        if len(w["znaleziska"]) > 8:
            print("      ... i %d wiecej" % (len(w["znaleziska"]) - 8))
    print()
    print("REGUL %d = OK %d + ZE ZNALEZISKAMI %d + BEZ WEJSCIA %d -> %s"
          % (len(wyniki), ok, bledne, puste,
             "BILANS OK" if len(wyniki) == ok + bledne + puste else "FAIL"))
    if puste:
        print("UWAGA: %d regul nie ma czego sprawdzac. Zielony kolor takiej reguly"
              " NIC NIE ZNACZY — to jest green-on-empty." % puste)
    return 1 if (bledne or puste) else 0


if __name__ == "__main__":
    sys.exit(main())
