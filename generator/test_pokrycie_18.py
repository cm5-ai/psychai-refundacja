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

PROJEKT = os.path.expanduser("~/mnt/psychai-paczka/projekt")
KLASOWE = ["DRUG_DB_AD.txt", "DRUG_DB_AP.txt", "DRUG_DB_BZD.txt",
           "DRUG_DB_STAB.txt", "DRUG_DB_ADHD_UZAL.txt"]
BAZA = 18          # stan 2026-09-24 po 12 nowych kartach i dwoch synonimach pisowni
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
    print("Wszystkie %d maja ChPL w cache, wiec karty DA SIE zbudowac." % len(bez)
          if all(r in cache for r in bez) else
          "UWAGA: czesc lekow bez karty nie ma tez ChPL w cache.")
    print("TEST POKRYCIA 18: %s" % ("OSTRZEZENIE" if len(bez) > BAZA else "PRZESZEDL"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
