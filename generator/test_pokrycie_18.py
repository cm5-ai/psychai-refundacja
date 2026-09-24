#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""POKRYCIE MODULU 18 KARTAMI — o ilu lekach 18 decyduje, nie majac karty.

Po co. 18 wylania kandydatow, stawia BLOKI i trzyma przeliczniki depot.
DRUG_DB trzyma dawki. Jesli 18 nazywa lek, ktorego karty nie ma, to przy
wizycie kandydat jest wskazany, a dawki nie ma skad wziac. 18 mowi wprost
"brak karty != odmowa", wiec to nie jest awaria - ale jest to DZIURA, ktorej
wielkosc powinna byc znana i nie powinna rosnac po cichu.

METODA. Rdzen osmioznakowy nazwy: pozwala zlapac formy odmienione
(zuklopentyksolu, lisdeksamfetaminie) bez zgadywania koncowek. Za lek uznajemy
slowo z 18, ktorego rdzen wystepuje w indeksie cache ChPL albo wsrod nazw kart
- czyli mamy niezalezne potwierdzenie, ze to nazwa substancji, a nie zwykle
slowo. Krotkie nazwy (ponizej 6 znakow, np. "lit") sa wylaczone z dopasowania
prefiksowego, bo "lit" lapal "literalny" i "literowka".

PROG. Liczba lekow bez karty jest zapisana jako BAZA. Wzrost = OSTRZEZENIE:
ktos dopisal do 18 lek, dla ktorego nie ma dawek. Spadek = zaktualizuj BAZE.
"""
import json, os, re, sys

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


PROJEKT = os.path.join(_paczka(), "projekt")
KLASOWE = ["DRUG_DB_AD.txt", "DRUG_DB_AP.txt", "DRUG_DB_BZD.txt",
           "DRUG_DB_STAB.txt", "DRUG_DB_ADHD_UZAL.txt"]
BAZA = 2           # stan 2026-09-24, rev.45: zostaja tylko flufenazyna i milnacipran,
                   # ktore NIE MAJA ZADNEGO PRODUKTU W REJESTRZE PL (sprawdzone dwukrotnie)
MIN_NAZWA = 6
RDZEN = 8

# PISOWNIA. 18 uzywa nazw miedzynarodowych, karty - polskich. Rdzen osmioznakowy
# ich nie skleja (citalopr / cytalopr), wiec lek Z KARTA wychodzil jako "bez karty".
# Tabela jest JAWNA I DETERMINISTYCZNA (rownosc rdzeni po podstawieniu), nie
# podobienstwo - par przyblizonych tu nie wolno dopisywac. Kazde uzycie jest
# raportowane ponizej, zeby scalenie nie bylo ciche.
SYNONIMY = {"citalopr": "cytalopr", "escitalo": "escytalo"}


def plaski(s):
    return re.sub(r"[^a-z0-9]", "", inn.bez_ogonkow(s or "").lower())


def rdzen(s):
    return plaski(s)[:RDZEN]


def main():
    karty = set()
    for f in KLASOWE:
        for l in open(os.path.join(PROJEKT, f), encoding="utf-8"):
            l = l.rstrip("\n")
            if re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9 _/.\-]{1,}$', l):
                for czesc in l.split("/"):      # KWAS WALPROINOWY / WALPROINIAN -> obie czesci
                    if len(plaski(czesc)) >= MIN_NAZWA:
                        karty.add(rdzen(czesc))
    idx = json.load(open(os.path.join(REPO, "chpl", "INDEX.json"), encoding="utf-8"))["substancje"]
    cache = {rdzen(s): s for s in idx if len(plaski(s)) >= MIN_NAZWA}

    t18 = open(os.path.join(PROJEKT, "18_PSYCH_PHARMA_FORMULARY_PL.txt"), encoding="utf-8").read()
    leki = {}
    uzyte_synonimy = []
    for w in {x for x in re.findall(r'\b[a-ząćęłńóśźż]{7,}\b', t18)}:
        r = rdzen(w)
        if r in SYNONIMY and SYNONIMY[r] in karty:
            uzyte_synonimy.append("%s -> %s (karta)" % (r, SYNONIMY[r]))
            r = SYNONIMY[r]
        if r in cache or r in karty:
            leki.setdefault(r, set()).add(w)

    bez = sorted(r for r in leki if r not in karty)
    maja = len(leki) - len(bez)
    print("N_WEJSCIE %d rdzeni lekowych w 18 = z karta %d + BEZ KARTY %d -> %s"
          % (len(leki), maja, len(bez), "BILANS OK" if len(leki) == maja + len(bez) else "FAIL"))
    if uzyte_synonimy:
        print("SYNONIMY UZYTE (%d): %s" % (len(uzyte_synonimy), "; ".join(sorted(uzyte_synonimy))))
    print()
    for r in bez:
        print("   %-28s %s" % ("/".join(sorted(leki[r]))[:28], "ChPL w cache: " + cache.get(r, "BRAK")))
    print()
    if len(bez) > BAZA:
        print("OSTRZEZENIE: lekow bez karty %d, baza %d. Ktos dopisal do 18 lek,"
              " dla ktorego nie ma dawek." % (len(bez), BAZA))
        return 1
    if len(bez) < BAZA:
        print("Lekow bez karty %d, baza %d — spadlo. Zaktualizuj BAZE w tym pliku." % (len(bez), BAZA))
    # OBECNOSC W INDEKSIE TO NIE TO SAMO CO ZRODLO. Wpis moze istniec, a nie
    # miec pliku ani punktow ChPL — wtedy zdanie "karty DA SIE zbudowac" jest
    # falszywa obietnica. Sprawdzamy, czy pod nazwa naprawde cos lezy.
    ma_zrodlo, bez_zrodla = [], []
    for r in bez:
        s_nazwa = cache.get(r)
        v = idx.get(s_nazwa) if s_nazwa else None
        plik = (v or {}).get("plik")
        ok = False
        if plik and os.path.exists(os.path.join(REPO, plik)):
            d = json.load(open(os.path.join(REPO, plik), encoding="utf-8"))
            ok = any((x.get("punkty") or {}) for x in d.get("produkty", []))
        (ma_zrodlo if ok else bez_zrodla).append(s_nazwa or r)
    print("ZRODLO: z punktami ChPL %d, BEZ ZRODLA %d -> %s"
          % (len(ma_zrodlo), len(bez_zrodla),
             "BILANS OK" if len(ma_zrodlo) + len(bez_zrodla) == len(bez) else "FAIL"))
    if ma_zrodlo:
        print("   DA SIE ZBUDOWAC: %s" % ", ".join(sorted(ma_zrodlo)))
    if bez_zrodla:
        print("   NIE MA Z CZEGO ZBUDOWAC (wpis w indeksie bez pliku albo bez punktow): %s"
              % ", ".join(sorted(bez_zrodla)))
    print("TEST POKRYCIA 18: %s" % ("OSTRZEZENIE" if len(bez) > BAZA else "PRZESZEDL"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
