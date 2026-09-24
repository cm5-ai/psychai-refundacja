#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PODZIAL DRUG_DB NA PLIKI KLASOWE — 2026-09-24.

POWOD, ZMIERZONY NIE ZGADNIETY. Przy wizycie plik wchodzi do kontekstu CALY;
nie ma odczytu fragmentu dokumentu projektu. Pytanie klasy 3A ("jaka dawka
kwetiapiny u starszych") ma czytac WYLACZNIE karte tego leku - a ciagnie
86 158 znakow calego DRUG_DB, zeby dostac 15 linii.

CO ROBI. Rozdziela 45 kart na piec plikow klasowych i zostawia w CORE
preambule (reguly kart) plus INDEKS lek -> plik. Adres [CORE/<LEK>/<POLE>]
nadal sie rozwiazuje: CORE mowi, gdzie lezy karta.

CZEGO NIE ROBI. Nie zmienia ANI JEDNEGO ZNAKU tresci karty. Podzial jest
przenosinami, nie redakcja. Test to sprawdza bajt w bajt.

DLACZEGO PREAMBULA JEST W KAZDYM PLIKU. Reguly "PRZECIWWSKAZANIA obowiazkowe",
"ZRODLO_KARTY", "ROZBIEZNOSC_ZRODLOWA" rozstrzygaja o czytaniu karty. Gdyby
zostaly tylko w CORE, odczyt samego pliku klasowego czytalby karty bez ich
regul. Cena: ta sama tresc w szesciu miejscach - wiec test wymaga, zeby byla
IDENTYCZNA co do bajtu we wszystkich. Rozjazd = FAIL, nie cicha rozbieznosc.
"""
import os, re, sys, json, hashlib

PROJEKT = os.path.expanduser("~/mnt/psychai-paczka/projekt")
ZRODLO = os.path.join(PROJEKT, "DRUG_DB_PSYCHIATRIA_CORE.txt")
WERSJA = "v3.6"
DATA = "2026-09-24"

# Przypisanie kart do plikow. JAWNA TABELA, nie heurystyka po nazwie:
# przynaleznosc do klasy jest tym, co wiaze lek z BLOKIEM klasy w 18,
# wiec nie moze zalezec od zgadywania po koncowce nazwy.
PLAN = [
    ("DRUG_DB_AD.txt", "PRZECIWDEPRESYJNE", [
        "SSRI", "SERTRALINA", "ESCYTALOPRAM", "FLUOKSETYNA", "PAROKSETYNA",
        "SNRI", "WENLAFAKSYNA", "DULOKSETYNA",
        "INNE PRZECIWDEPRESYJNE", "MIRTAZAPINA", "TRAZODON", "BUPROPION",
        "AGOMELATYNA", "AMITRYPTYLINA", "KLOMIPRAMINA", "DOKSEPINA", "IMIPRAMINA"]),
    ("DRUG_DB_AP.txt", "PRZECIWPSYCHOTYCZNE", [
        "PRZECIWPSYCHOTYCZNE", "KWETIAPINA", "OLANZAPINA", "ARYPIPRAZOL",
        "RISPERIDON", "HALOPERIDOL", "KLOZAPINA", "TIAPRYD", "SULPIRYD",
        "FLUPENTYKSOL", "PALIPERYDON", "PROMETAZYNA"]),
    ("DRUG_DB_BZD.txt", "BENZODIAZEPINY, Z-LEKI I POZOSTALE NASENNE/ANKSJOLITYCZNE", [
        "ALPRAZOLAM", "LORAZEPAM", "KLONAZEPAM", "TEMAZEPAM", "BROMAZEPAM",
        "DIAZEPAM", "ESTAZOLAM", "NITRAZEPAM", "KLORAZEPAT", "CHLORDIAZEPOKSYD",
        "OKSAZEPAM", "ZOPIKLON", "ZOLPIDEM", "HYDROKSYZYNA", "BUSPIRON"]),
    ("DRUG_DB_STAB.txt", "STABILIZATORY I PRZECIWPADACZKOWE", [
        "KARBAMAZEPINA", "LAMOTRYGINA", "PREGABALINA"]),
    ("DRUG_DB_ADHD_UZAL.txt", "ADHD I UZALEZNIENIA", [
        "ATOMOKSETYNA", "METYLOFENIDAT", "METADON"]),
]
# PROMETAZYNA stoi w AP swiadomie: to fenotiazyna, ma wspolne z klasa DN
# (antycholinergia, sedacja, QT) i 18 traktuje ja przez klase, nie przez
# wskazanie nasenne. Gdyby miala byc w BZD, trzeba to zmienic TU, w jednym
# miejscu, a nie zgadywac przy wizycie.


def naglowek_karty(l):
    return bool(re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9 _\-]{3,}$', l))


def czytaj():
    L = open(ZRODLO, encoding="utf-8").read().split("\n")
    idx = [i for i, l in enumerate(L) if naglowek_karty(l)]
    preambula = L[:idx[0]]
    karty = {}
    for n, i in enumerate(idx):
        j = idx[n + 1] if n + 1 < len(idx) else len(L)
        karty[L[i]] = L[i:j]
    return L, preambula, karty


def naglowek_pliku(klasa, ile):
    return [
        "PSYCH-AI — DRUG DB: %s" % klasa,
        "VERSION: %s" % WERSJA,
        "DATE: %s" % DATA,
        "CZESC PACZKI DRUG_DB. Indeks wszystkich kart i przypisanie lek -> plik:",
        "DRUG_DB_PSYCHIATRIA_CORE. Adres [CORE/<LEK>/<POLE>] rozwiazuje sie przez",
        "ten indeks. Kart w tym pliku: %d." % ile,
        "REGULY KART PONIZEJ SA IDENTYCZNE WE WSZYSTKICH PLIKACH DRUG_DB.",
        "Rozjazd miedzy plikami jest bledem paczki — sprawdza go test.",
        "",
    ]


def main():
    sucho = "--zapisz" not in sys.argv
    L, preambula, karty = czytaj()
    print("ZRODLO: %d linii, %d znakow, kart/sekcji: %d" % (len(L), sum(len(x)+1 for x in L), len(karty)))

    rozdane, wynik = set(), {}
    for plik, klasa, lista in PLAN:
        brak = [x for x in lista if x not in karty]
        if brak:
            print("FAIL: w zrodle nie ma naglowkow %s" % brak); return 1
        dubel = [x for x in lista if x in rozdane]
        if dubel:
            print("FAIL: karta przypisana dwa razy: %s" % dubel); return 1
        rozdane |= set(lista)
        tresc = naglowek_pliku(klasa, sum(1 for x in lista if x not in
                                          ("SSRI", "SNRI", "INNE PRZECIWDEPRESYJNE", "PRZECIWPSYCHOTYCZNE")))
        tresc = tresc + preambula
        for x in lista:
            tresc += karty[x]
        wynik[plik] = tresc

    sieroty = [x for x in karty if x not in rozdane]
    print("BILANS KART: N_WEJSCIE %d = N_ZACHOWANE %d + N_ODRZUCONE %d -> %s"
          % (len(karty), len(rozdane), len(sieroty), "OK" if not sieroty else "FAIL " + str(sieroty)))
    if sieroty:
        return 1

    # CORE: preambula + indeks
    gdzie = {}
    for plik, klasa, lista in PLAN:
        for x in lista:
            gdzie[x] = plik
    core = ["PSYCH-AI — DRUG DB: PSYCHIATRIA CORE", "VERSION: %s" % WERSJA, "DATE: %s" % DATA,
            "ZMIANA %s: karty rozdzielone na piec plikow klasowych. Tresc kart bez" % WERSJA,
            "zmian co do bajtu — podzial jest przenosinami, nie redakcja. Powod: przy",
            "wizycie plik wchodzi CALY, a odczyt jednego pola ciagnal 86 KB, zeby dac",
            "15 linii. Ten plik trzyma reguly kart i INDEKS; karta lezy w pliku klasy.",
            "REGULY KART PONIZEJ SA IDENTYCZNE WE WSZYSTKICH PLIKACH DRUG_DB.", ""]
    core += preambula
    core += ["", "INDEKS KART — LEK -> PLIK", ""]
    for x in sorted(k for k in karty if k in gdzie):
        core.append("%-18s %s" % (x, gdzie[x]))
    core += ["", "SEKCJE KLASOWE:", ""]
    for plik, klasa, lista in PLAN:
        core.append("%-24s %s" % (plik, klasa))
    core.append("")
    wynik["DRUG_DB_PSYCHIATRIA_CORE.txt"] = core

    print()
    print("WYNIK PODZIALU:")
    for plik in ["DRUG_DB_PSYCHIATRIA_CORE.txt"] + [p for p, _, _ in PLAN]:
        t = "\n".join(wynik[plik])
        print("   %-32s %6d zn" % (plik, len(t)))
    print("   %-32s %6d zn (bylo 86158 w jednym pliku)"
          % ("RAZEM", sum(len("\n".join(v)) for v in wynik.values())))
    print()
    naj = max(len("\n".join(wynik[p])) for p, _, _ in PLAN)
    print("ODCZYT POLA (klasa 3A) = CORE + plik klasy: %d..%d zn zamiast 86158"
          % (len("\n".join(core)) + min(len("\n".join(wynik[p])) for p, _, _ in PLAN),
             len("\n".join(core)) + naj))

    if sucho:
        print("\nTRYB SUCHY. Dopisz --zapisz, zeby zapisac do projekt/.")
        return 0
    for plik, tresc in wynik.items():
        open(os.path.join(PROJEKT, plik), "w", encoding="utf-8").write("\n".join(tresc))
    print("\nZAPISANO %d plikow." % len(wynik))
    return 0


if __name__ == "__main__":
    sys.exit(main())
