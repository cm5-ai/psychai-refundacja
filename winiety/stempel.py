#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STEMPEL WYDANIA — kandydat. NIE DOTYKA projekt/.

Po co. Mutacje z 2026-09-24 pokazaly, ze podmiana pliku o tej samej nazwie
jest wykrywana PRZYPADKOWO: tylko wtedy, gdy ten sam fakt lezy jeszcze
w drugim pliku (karta i 18). Fakt lezacy w jednym miejscu nie ma czym sie
obronic, a uciety plik nie daje sygnalu w ogole.

CZEGO NIE DA SIE ZROBIC. Przy wizycie nie ma jak policzyc sha256 pliku -
model czyta tekst, nie liczy skrotow. Stempel musi opierac sie na tym, co
model UMIE policzyc wiarygodnie: przeczytac wlasna linie naglowka pliku
i policzyc naglowki kart.

MECHANIZM, TRZY ZGODNOSCI:
  1. kazdy plik paczki deklaruje w naglowku: WYDANIE: <rev> | <suma>
  2. CORE trzyma SKLAD WYDANIA: dla kazdego pliku - wydanie i LISTA NAZW KART
  3. przed pierwsza odpowiedzia system porownuje jedno z drugim ORAZ liczy
     karty, ktore faktycznie widzi
Niezgodnosc ktoregokolwiek = jedna linia ostrzezenia przed odpowiedzia.

CO TO LAPIE:
  - wgranie wczorajszej wersji pliku (inne WYDANIE w naglowku)
  - plik uciety tak, ze przepadly karty (liczba kart < deklarowana)
  - brak pliku z SKLADU
CZEGO NIE LAPIE, i to ma byc napisane wprost, a nie przemilczane:
  - podmiane POJEDYNCZEJ KARTY wewnatrz pliku o poprawnym naglowku
  - wyciecie jednej linii z karty (liczba kart sie zgadza)
Przy recznym wgrywaniu plikow to sa przypadki nierealistyczne - lekarz
podmienia CALE pliki, nie sklada ich z kawalkow. Gdyby kiedys pliki byly
generowane albo edytowane recznie, ta granica przestaje wystarczac.
"""
import os, re, subprocess, sys, hashlib

KAT = os.path.dirname(os.path.abspath(__file__))
PACZKA = os.path.expanduser("~/mnt/psychai-paczka")
PROJEKT = os.path.join(PACZKA, "projekt")
WYJSCIE = os.path.join(KAT, "stempel")

WYDANIE = "rev33"
SUMA = "2bbb4fa74d490526"
PELNY = ["00_CIAGLOSC_PSYCH-AI_CZYTAJ_NAJPIERW.txt", "MASTER_v20_2026-09-20.txt",
         "02_INDEX_PRECEDENCE.txt", "18_PSYCH_PHARMA_FORMULARY_PL.txt",
         "DRUG_DB_PSYCHIATRIA_CORE.txt", "DRUG_DB_AD.txt", "DRUG_DB_AP.txt",
         "DRUG_DB_BZD.txt", "DRUG_DB_STAB.txt", "DRUG_DB_ADHD_UZAL.txt"]
KLASOWE = [f for f in PELNY if f.startswith("DRUG_DB_") and f != "DRUG_DB_PSYCHIATRIA_CORE.txt"]
# Naglowki sekcji klasowych - to nie sa karty lekow.
SEKCJE = {"SSRI", "SNRI", "INNE PRZECIWDEPRESYJNE", "PRZECIWPSYCHOTYCZNE"}


def karty(tekst):
    return [l for l in tekst.split("\n")
            if re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9 _\-]{1,}$', l)]


def naglowek(nazwa, wydanie=WYDANIE, suma=SUMA):
    return "WYDANIE: %s | %s | PLIK: %s" % (wydanie, suma, nazwa)


REGULA = """
=====================================================================
KONTROLA WYDANIA — PRZED PIERWSZA ODPOWIEDZIA MERYTORYCZNA
=====================================================================
Kazdy plik paczki ma w drugiej linii: WYDANIE: <rev> | <suma> | PLIK: <nazwa>.
SKLAD WYDANIA ponizej mowi, ile kart ma miec kazdy plik klasowy.

ZANIM odpowiesz merytorycznie PIERWSZY RAZ w rozmowie, sprawdz trzy rzeczy:
  1. czy kazdy wczytany plik paczki ma linie WYDANIE i czy wszystkie podaja
     TO SAMO wydanie i te sama sume,
  2. czy nie brakuje pliku ze SKLADU WYDANIA,
  3. czy liczba kart, ktore WIDZISZ w kazdym pliku klasowym, zgadza sie
     z liczba ze SKLADU.
Niezgodnosc ktorejkolwiek: PIERWSZA LINIA odpowiedzi to
  ⚠ WYDANIE: <co sie nie zgadza>
i dopiero potem odpowiadasz — albo odmawiasz, jesli niezgodnosc dotyczy
pliku potrzebnego do tej odpowiedzi.
Zgodnosc: NIE PISZ NIC. Stempel milczy, gdy wszystko sie zgadza; inaczej
lekarz nauczy sie go pomijac.

To NIE jest suma kontrolna. Nie liczysz skrotow ani kart. Czytasz
zadeklarowane wydanie i sprawdzasz, czy wymienione karty sa na miejscu.
SKLAD podaje NAZWY, nie liczby, bo liczba wymaga zgody co do tego, co jest
karta: naglowek sekcji SSRI kartą nie jest, a przy liczeniu wpadal do puli
i dawal falszywy alarm w paczce, ktora byla w porzadku. Falszywy alarm uczy
ignorowania alarmow, wiec jest gorszy niz brak alarmu. Granica metody: podmiana JEDNEJ
KARTY w pliku z poprawnym naglowkiem nie zostanie wykryta.

SKLAD WYDANIA %s (%s)
""" % (WYDANIE, SUMA)


def main():
    os.makedirs(WYJSCIE, exist_ok=True)
    liczby = {}
    tresci = {}
    for f in PELNY:
        t = open(os.path.join(PROJEKT, f), encoding="utf-8").read()
        tresci[f] = t
        if f in KLASOWE:
            # SEKCJE KLASOWE NIE SA KARTAMI. Pierwsza wersja liczyla je razem
            # z lekami i deklarowala 17 tam, gdzie lekarz i model widza 14 -
            # falszywy alarm w paczce bez usterki.
            liczby[f] = [k for k in karty(t) if k not in SEKCJE]

    sklad = [REGULA]
    for f in PELNY:
        if f in liczby:
            sklad.append("  %-30s %s  karty: %s" % (f, WYDANIE, ", ".join(liczby[f])))
        else:
            sklad.append("  %-30s %s" % (f, WYDANIE))
    sklad.append("")
    blok = "\n".join(sklad)

    for f in PELNY:
        L = tresci[f].split("\n")
        L.insert(1, naglowek(f))
        t = "\n".join(L)
        if f == "DRUG_DB_PSYCHIATRIA_CORE.txt":
            t = t.replace("\nINDEKS KART — LEK -> PLIK\n", blok + "\nINDEKS KART — LEK -> PLIK\n", 1)
        open(os.path.join(WYJSCIE, f), "w", encoding="utf-8").write(t)

    print("STEMPEL zbudowany w %s" % WYJSCIE)
    print("Naglowek dopisany do %d plikow. SKLAD WYDANIA wstawiony do CORE." % len(PELNY))
    for f, n in sorted(liczby.items()):
        print("   %-24s %2d kart: %s" % (f, len(n), ", ".join(n)[:60]))
    dod = sum(len(open(os.path.join(WYJSCIE, f), encoding="utf-8").read()) for f in PELNY) - \
          sum(len(tresci[f]) for f in PELNY)
    print("KOSZT: +%d znakow w calej paczce (~%d tokenow)." % (dod, dod / 3.5))
    print("projekt/ NIETKNIETY.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
