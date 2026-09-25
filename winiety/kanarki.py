#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KANARKI SEDZIEGO — specyfikacja z kanarki.tsv puszczona na gramatyke.

PO CO OSOBNY PLIK, SKORO gramatyka.py UMIE TO SAMA.
Zeby mutacja miala STRAZNIKA Z NAZWY. Do R14 katalog 62 mutacji nie mial
ANI JEDNEJ pozycji przeciwko sedziemu — a sedzia rozstrzyga o tym, czy
odpowiedz modelu przy pacjencie liczy sie jako podanie dawki, czy jako
jej wykluczenie. Zmierzone 2026-09-25: usuniecie ramy SKALA_POMYLKI
razem z kanarkiem, ktory jej pilnuje, przeszlo przez wszystkie 25 bramek
obu repozytoriow na zielono. Sedzia na tekscie G6 odwracal werdykt —
EXCLUDED_DOSE stawalo sie ASSERTED_DOSE, czyli wzorowa odmowa modelu
zaczynala OBLEWAC.

ROZDZIAL, KTORY TO NAPRAWIA [Grok, R13 pkt 3]:
  kanarki.tsv   SPECYFIKACJA — czego oczekujemy. Mutacja sedziego jej nie rusza.
  gramatyka.py  IMPLEMENTACJA — jak to liczymy. To ja mutujemy.
Kanarek w pliku, ktory psujesz, dowodzi najwyzej tego, ze plik sie laduje.

CZEGO NIE DOWODZI. Ze gramatyka jest MADRA. Dowodzi, ze na dwudziestu
trzech nazwanych tekstach daje werdykty zapisane w tablicy — i ze gdy
przestanie, ktos sie o tym dowie przed pchnieciem.
"""
import os, sys

KAT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KAT)
import gramatyka


def main():
    print("=" * 66)
    print("KANARKI SEDZIEGO — specyfikacja kontra implementacja")
    print("=" * 66)
    bledy = gramatyka.sprawdz_kanarki(cicho=True)
    n = len(gramatyka.KANARKI)
    print("N_WEJSCIE: %d kanarkow z kanarki.tsv, %d ram wykluczajacych"
          % (n, len(gramatyka.RAMY_WYKLUCZAJACE)))
    if not n:
        print("FAIL: ZERO KANARKOW. Zero specyfikacji to zero wiedzy.")
        return 1
    print("BILANS: %d = zgodnych %d + rozjazdow %d" % (n, n - len(bledy), len(bledy)))
    print()
    for b in bledy:
        print("  ROZJAZD " + b)
    if bledy:
        print()
        print("FAIL: sedzia nie zgadza sie z wlasna specyfikacja.")
        print("Werdykt o odpowiedzi modelu zmienil sie, a tablica nie.")
        return 1
    print("SEDZIA ZGODNY ZE SPECYFIKACJA.")
    print("CZEGO TO NIE DOWODZI: ze gramatyka jest madra. Tylko tyle, ze")
    print("na tych tekstach daje werdykty, ktore ktos kiedys zapisal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
