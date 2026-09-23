#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLITYKA ARTEFAKTOW - dwie bramy przed zapisem pliku klinicznego.

PO CO TO ISTNIEJE. 2026-09-23 ten sam blad wyszedl w czterech miejscach naraz:
generator nadpisal 88 dobrych plikow pustka, bo nie bylo sieci; generator kasowal
plik przy braku trafienia; dopasowanie po szkielecie mieszalo leki; wycofanie
legacy decydowalo po NAZWIE POLA zamiast po tresci claimu i wycofalo wpisy
o ciazy mowiace "nie odstawiac automatycznie".

Reguly zakazujace tego wszystkiego byly w instrukcji projektu OD DAWNA. Problem
nie polegal na ich braku, tylko na tym, ze KAZDY SKRYPT IMPLEMENTOWAL JE SOBIE
OD NOWA - i w kazdym dalo sie je zaimplementowac zle. Reguly bezpieczenstwa byly
wlasnoscia skryptow zamiast wlasnoscia architektury zapisu.

DWIE BRAMY, W TEJ KOLEJNOSCI. Jedna nie wystarcza, i to jest tu rzecz
najwazniejsza. Brama zapisu zatrzymuje blad 1, 2 i 3, ale blad 4 PRZEZ NIA
PRZECHODZI: zapis byl formalnie legalny, bledna byla KLASYFIKACJA.
  1. sprawdz_semantyke  - czy wolno tak sklasyfikowac i przeksztalcic?
  2. sprawdz_publikacje - czy wolno TYM nadpisac stan produkcyjny?

FAIL-CLOSED. Nieznany typ artefaktu, nieznany stan, niezadeklarowany klucz =
BRAK ZAPISU. Nigdy domyslna zgoda.

KOSZT, KTORY PRZYJMUJEMY SWIADOMIE. Jeden blad w bramie staje sie bledem
systemowym dla wszystkich artefaktow. Dlatego brama ma byc MALA, ma miec testy
kontraktowe na kazdy typ i tryb dry-run. Nie dokladaj tu logiki dziedzinowej.
"""

# --- slowniki zamkniete -------------------------------------------------------

KLUCZE = ("DETERMINISTYCZNY", "HEURYSTYCZNY")
# HEURYSTYCZNY wolno uzyc TYLKO do wskazywania. Podobienstwo, prog i dopasowanie
# przyblizone nie sa dopuszczalnym zrodlem danych podawanych przy pacjencie (3B).

OWNERSHIP = ("POZIOM_CLAIMU", "POZIOM_POLA")

DZIALANIA = ("ZAPIS", "WSKAZANIE")

# Jedyne powody, dla ktorych zbior moze sie ZMNIEJSZYC. Kazdy musi byc
# stwierdzony w ZRODLE, nie wywnioskowany z tego, ze czegos nie znalezlismy.
POWODY_UBYTKU = ("BRAK_W_BIEZACYM_ZRODLE", "WYCOFANY_PRZEZ_ZRODLO",
                 "ZATWIERDZONA_KOREKTA_MAPOWANIA")

# Stany, ktore NIGDY nie sa informacja o nieistnieniu. To sedno bledu 1 i 2.
STANY_NIEWIEDZY = ("BLAD_POBRANIA", "BRAK_DOPASOWANIA", "BRAK_SIECI",
                   "ZRODLO_NIEDOSTEPNE")


class Odmowa(Exception):
    """Brama odmowila. Tresc mowi, ktora regula i dlaczego."""


# --- polityka per typ artefaktu ----------------------------------------------
# Tablica JAWNA. Typ spoza tablicy = odmowa (fail-closed).

POLITYKA = {
    "CHPL_LAYER": {
        "opis": "Doslowna tresc etykiety ChPL. Nalezy do PRODUKTU.",
        "klucz_wymagany": "DETERMINISTYCZNY",
        "ownership": "POZIOM_CLAIMU",
        "wolno_kasowac": False,
        "wolno_zmniejszyc": True,      # ale tylko z POWODEM_UBYTKU ze zrodla
        "wymagana_proweniencja": ("zrodlo", "sha256_pdf"),
    },
    "LEGACY_LAYER": {
        "opis": "Stare karty pisane recznie. Jedyny zapis - nic nie ginie.",
        "klucz_wymagany": "DETERMINISTYCZNY",
        "ownership": "POZIOM_CLAIMU",
        "wolno_kasowac": False,
        "wolno_zmniejszyc": False,     # liczba wpisow nie ma prawa spasc NIGDY
        "wymagana_proweniencja": ("pochodzenie",),
    },
    "AUTHOR_LAYER": {
        "opis": "To, czego ChPL nie niesie. Claim autorski.",
        "klucz_wymagany": "DETERMINISTYCZNY",
        "ownership": "POZIOM_CLAIMU",
        "wolno_kasowac": False,
        "wolno_zmniejszyc": False,
        "wymagana_proweniencja": ("zrodlo",),
    },
    "KARTY_GEN": {
        "opis": "Karta zbudowana z warstw. Nigdy nie pisana recznie.",
        "klucz_wymagany": "DETERMINISTYCZNY",
        "ownership": "POZIOM_CLAIMU",
        "wolno_kasowac": False,
        "wolno_zmniejszyc": True,
        "wymagana_proweniencja": (),
    },
}


# --- BRAMA 1: SEMANTYKA -------------------------------------------------------

def sprawdz_semantyke(typ, dzialanie, klucz, podstawa_decyzji):
    """Czy wolno tak sklasyfikowac i przeksztalcic?

    podstawa_decyzji: krotka nazw pol rekordu, na ktorych OPARTA BYLA DECYZJA.
    To nie jest ozdoba. Tu wlasnie przechodzil blad 4: decyzja opierala sie
    wylacznie na nazwie pola, choc regula ownership dziala na poziomie claimu.
    """
    p = POLITYKA.get(typ)
    if p is None:
        raise Odmowa("nieznany typ artefaktu %r - fail-closed, brak domyslnej zgody" % typ)
    if dzialanie not in DZIALANIA:
        raise Odmowa("nieznane dzialanie %r" % dzialanie)
    if klucz not in KLUCZE:
        raise Odmowa("klucz musi byc zadeklarowany jako jeden z %r, jest %r" % (KLUCZE, klucz))

    # Heurystyka wolno WSKAZYWAC, nigdy zapisywac.
    if klucz == "HEURYSTYCZNY" and dzialanie == "ZAPIS":
        raise Odmowa(
            "klucz HEURYSTYCZNY nie moze zapisywac - wolno mu tylko WSKAZYWAC. "
            "Dopasowanie przyblizone nie jest zrodlem danych podawanych przy pacjencie.")

    if not podstawa_decyzji:
        raise Odmowa("nie zadeklarowano PODSTAWY DECYZJI - nie wiadomo, na czym "
                     "oparto klasyfikacje, wiec nie da sie sprawdzic, czy wolno")

    # Ownership na poziomie claimu: decyzja NIE MOZE opierac sie wylacznie na
    # metadanych rekordu. Musi siegnac do tresci claimu.
    if p["ownership"] == "POZIOM_CLAIMU":
        METADANE = {"pole_karty", "nazwa_pola", "typ_pola", "lek", "nazwa_pliku"}
        if set(podstawa_decyzji) <= METADANE:
            raise Odmowa(
                "ownership dla %s jest na POZIOMIE CLAIMU, a decyzja opiera sie "
                "wylacznie na metadanych %r. Nazwa pola nie rozstrzyga, do kogo "
                "nalezy fakt - rozstrzyga tresc claimu." % (typ, tuple(podstawa_decyzji)))
    return True


# --- BRAMA 2: PRAWO DO PUBLIKACJI --------------------------------------------

def sprawdz_publikacje(typ, stare_id, nowe_id, stan_zrodla="OK", powody_ubytku=None):
    """Czy wolno TYM nadpisac stan produkcyjny?

    stare_id / nowe_id: ZBIORY identyfikatorow, nie licznosci. Porownanie
    licznosci przepuszcza podmiane: 3 produkty przed, 3 po, dwa inne.
    """
    p = POLITYKA.get(typ)
    if p is None:
        raise Odmowa("nieznany typ artefaktu %r - fail-closed" % typ)

    # Blad pobrania NIGDY nie jest informacja o nieistnieniu.
    if stan_zrodla in STANY_NIEWIEDZY:
        raise Odmowa(
            "stan zrodla %r nalezy do stanow NIEWIEDZY. Nie znalazlem != nie ma. "
            "Zachowuje poprzednia poprawna wersje, nie zapisuje." % stan_zrodla)
    if stan_zrodla != "OK":
        raise Odmowa("nieznany stan zrodla %r - fail-closed" % stan_zrodla)

    stare_id, nowe_id = set(stare_id or ()), set(nowe_id or ())
    znikly = sorted(stare_id - nowe_id)

    if znikly and not p["wolno_kasowac"] and not p["wolno_zmniejszyc"]:
        raise Odmowa("z %s nie ma prawa zniknac nic; znikly: %r" % (typ, znikly[:5]))

    if znikly:
        powody = powody_ubytku or {}
        bez = [i for i in znikly if powody.get(i) not in POWODY_UBYTKU]
        if bez:
            raise Odmowa(
                "kazde zniknięcie wymaga jawnej przyczyny ZE ZRODLA (%r). "
                "Bez przyczyny: %r. Wycofanie bez wskazania nastepcy jest "
                "cichym skasowaniem." % (POWODY_UBYTKU, bez[:5]))

    return {"N_STARE": len(stare_id), "N_NOWE": len(nowe_id),
            "ZNIKLY": znikly, "DOSZLY": sorted(nowe_id - stare_id),
            "BILANS_OK": len(stare_id) - len(znikly) + len(nowe_id - stare_id) == len(nowe_id)}
