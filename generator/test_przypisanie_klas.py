#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST PRZYPISANIA KLAS — czy karta wjechala do WLASCIWEGO pliku.

Po co osobny test. Test podzialu dowodzi, ze tresc kart nie zmienila sie co do
bajtu i ze kazda karta jest w dokladnie jednym pliku. NIE dowodzi, ze jest
w DOBRYM pliku. Przypisanie do pliku klasowego nie jest kosmetyka: naleznosc
do klasy jest tym, co wiaze lek z BLOKIEM KLASY w module 18. Karta pod zlym
naglowkiem to lek, ktory moze nie dostac swojego BLOKU.

ZRODLO PRAWDY JEST ZEWNETRZNE. Nie sprawdzamy paczki paczka. Nazwa karty idzie
przez indeks cache do produktow, produkty do rejestru, rejestr daje KOD ATC.
ATC jest niezalezny od naszych decyzji redakcyjnych, wiec nie potwierdzi
bledu, ktory sami popelnilismy w podziale.

WYJATKI SA JAWNE. Dwa leki stoja poza swoim kodem ATC i obie decyzje sa
kliniczne, nie pomylkowe. Lista jest tutaj, nie w glowie - i jesli kiedys ma
sie zmienic, zmienia sie w jednym miejscu.

KOLEJNOSC TEZ JEST SPRAWDZANA. Naglowek sekcji wiaze karty, ktore po nim ida.
Naglowek oderwany od swoich kart (2026-09-24: TCA / STARSZE stalo na poczatku
pliku, nad kartami SSRI) jest bledem, ktorego zaden bilans nie widzi.
"""
import json, os, re, sys

KAT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(KAT)
sys.path.insert(0, os.path.join(REPO, "slownik"))
import inn

PROJEKT = os.path.expanduser("~/mnt/psychai-paczka/projekt")
PLIKI = ["DRUG_DB_AD.txt", "DRUG_DB_AP.txt", "DRUG_DB_BZD.txt",
         "DRUG_DB_STAB.txt", "DRUG_DB_ADHD_UZAL.txt"]

# Jakie prefiksy ATC naleza do ktorego pliku.
OCZEKIWANE = {
    "DRUG_DB_AD.txt": ("N06A",),                      # przeciwdepresyjne z TLPD
    "DRUG_DB_AP.txt": ("N05A",),                      # przeciwpsychotyczne
    "DRUG_DB_BZD.txt": ("N05B", "N05C"),              # BZD, Z-leki, anksjolityki
    "DRUG_DB_STAB.txt": ("N03A",),                    # stabilizatory/przeciwpadaczkowe
    "DRUG_DB_ADHD_UZAL.txt": ("N06B", "N07B"),        # psychostymulanty, uzaleznienia
}
# Lek stojacy poza swoim kodem ATC — decyzja kliniczna, z powodem.
WYJATKI = {
    "PROMETAZYNA": ("DRUG_DB_AP.txt",
                    "R06AD02 to lek przeciwhistaminowy, ale to fenotiazyna: dzieli z klasa "
                    "antycholinergie, sedacje i wydluzenie QT, a 18 traktuje ja przez klase, "
                    "nie przez wskazanie nasenne."),
    "KLONAZEPAM": ("DRUG_DB_BZD.txt",
                   "N03AE01 to kod przeciwpadaczkowy, ale to benzodiazepina: BLOK BZD "
                   "(SUD, opioid, OSAS, wiek z upadkami) obowiazuje ja tak samo jak reszte klasy."),
}
# Karty, dla ktorych ATC nie da sie ustalic — brak mostu do rejestru.
# To NIE jest zgoda na dowolne przypisanie; to jawny stan "nie sprawdzone".
BEZ_ATC_ZNANE = {"IMIPRAMINA"}
ALIAS_CACHE = {"escytalopram": "escitalopram", "flupentyksol": "flupentiksol",
               "cytalopram": "citalopram"}

bledy, uwagi = [], []


def plaski(s):
    return re.sub(r"[^a-z0-9]", "", inn.bez_ogonkow(s or "").lower())


def naglowki(tekst):
    return [l for l in tekst.split("\n")
            if re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9 _/.\-]{3,}$', l)]


def main():
    idx = json.load(open(os.path.join(REPO, "chpl", "INDEX.json"), encoding="utf-8"))["substancje"]
    rpl = json.load(open(os.path.join(REPO, "rpl", "RPL_PSYCH.json"), encoding="utf-8"))["produkty"]
    prod2atc = {}
    for p in rpl:
        prod2atc.setdefault(plaski(p["nazwa"]), set()).update(p.get("atc") or [])
    cache = {plaski(s): v for s, v in idx.items()}

    n_we = n_ok = n_wyj = n_bez = 0
    for f in PLIKI:
        t = open(os.path.join(PROJEKT, f), encoding="utf-8").read()
        H = naglowki(t)
        # 1. KOLEJNOSC: naglowek sekcji (z ukosnikiem) musi miec pod soba karte
        for i, h in enumerate(H):
            if "/" not in h:
                continue
            dalsze = [x for x in H[i + 1:] if "/" not in x]
            if not dalsze:
                bledy.append("KOLEJNOSC %s: sekcja '%s' nie ma pod soba zadnej karty" % (f, h))
        # 2. PRZYPISANIE
        for h in H:
            if "/" in h or h in ("SSRI", "SNRI", "INNE PRZECIWDEPRESYJNE", "PRZECIWPSYCHOTYCZNE"):
                continue
            n_we += 1
            klucz = ALIAS_CACHE.get(plaski(h), plaski(h))
            meta = cache.get(plaski(klucz))
            atc = set()
            if meta:
                for nz in meta.get("produkty") or []:
                    atc |= prod2atc.get(plaski(nz), set())
            if not atc:
                n_bez += 1
                (uwagi if h in BEZ_ATC_ZNANE else bledy).append(
                    "BEZ ATC %s/%s: nie ma mostu do rejestru, przypisania NIE SPRAWDZONO" % (f, h))
                continue
            if h in WYJATKI:
                plik, powod = WYJATKI[h]
                if plik != f:
                    bledy.append("WYJATEK %s: opisany dla %s, a karta lezy w %s" % (h, plik, f))
                else:
                    n_wyj += 1
                    uwagi.append("WYJATEK %-14s %s — %s" % (h, ",".join(sorted(a[:7] for a in atc)), powod[:70]))
                continue
            if any(a.startswith(OCZEKIWANE[f]) for a in atc):
                n_ok += 1
            else:
                bledy.append("PRZYPISANIE %s/%s: ATC %s nie pasuje do %s"
                             % (f, h, ",".join(sorted(a[:7] for a in atc)), OCZEKIWANE[f]))

    print("N_WEJSCIE %d = zgodne z ATC %d + jawny wyjatek %d + bez ATC %d + bledne %d -> %s"
          % (n_we, n_ok, n_wyj, n_bez,
             n_we - n_ok - n_wyj - n_bez,
             "BILANS OK" if n_we == n_ok + n_wyj + n_bez + (n_we - n_ok - n_wyj - n_bez) else "FAIL"))
    for u in uwagi:
        print("   UWAGA: %s" % u)
    for b in bledy:
        print("   BLAD:  %s" % b)
    print()
    print("TEST PRZYPISANIA KLAS: %s" % ("NIE PRZESZEDL" if bledy else "PRZESZEDL"))
    return 1 if bledy else 0


if __name__ == "__main__":
    sys.exit(main())
