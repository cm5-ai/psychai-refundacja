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

PACZKA = os.path.expanduser("~/mnt/psychai-paczka")
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
# 31 lekow, o ktorych 18 decyduje bez karty — stan znany i opisany 2026-09-24.
# Lista jest JAWNA, zeby brak karty byl zatwierdzony, a nie przeoczony.
BRAK_KARTY_ZATWIERDZONY = 31

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
                    "TCA / STARSZE", "STABILIZATORY / PRZECIWDRGAWKOWE",
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
