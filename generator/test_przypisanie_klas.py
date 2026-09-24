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
    "PROPRANOLOL": ("DRUG_DB_BZD.txt",
                    "C07AA05 to beta-adrenolityk, ale ChPL wymienia wprost zmniejszenie leku "
                    "sytuacyjnego i uogolnionego oraz drzenie samoistne; 18 uzywa go przy objawach "
                    "autonomicznych, wiec karta lezy w sekcji anksjolitykow nie-BZD."),
    "LIT": ("DRUG_DB_STAB.txt",
            "N05AN01 stoi w grupie przeciwpsychotycznej ATC, ale lit jest stabilizatorem "
            "nastroju: 18 prowadzi go przez profilaktyke nawrotow i litemie, nie przez klase AP."),
    "KLONAZEPAM": ("DRUG_DB_BZD.txt",
                   "N03AE01 to kod przeciwpadaczkowy, ale to benzodiazepina: BLOK BZD "
                   "(SUD, opioid, OSAS, wiek z upadkami) obowiazuje ja tak samo jak reszte klasy."),
}
# Karty, dla ktorych ATC nie da sie ustalic — brak mostu do rejestru.
# To NIE jest zgoda na dowolne przypisanie; to jawny stan "nie sprawdzone".
BEZ_ATC_ZNANE = {"IMIPRAMINA"}
# SEKCJE WYMIENIONE, NIE ZGADYWANE PO UKOSNIKU. Poprzednia wersja uznawala za
# sekcje kazdy naglowek z ukosnikiem, wiec KWAS WALPROINOWY / WALPROINIAN —
# karta leku — nigdy nie byl sprawdzany pod katem przypisania do pliku.
# Nowa sekcja musi byc dopisana tutaj recznie.
SEKCJE = {"SSRI", "SNRI", "INNE PRZECIWDEPRESYJNE", "TCA / STARSZE",
          "PSYCHOSTYMULANTY I ADHD",
          "PRZECIWPSYCHOTYCZNE", "BENZODIAZEPINY", "LEKI Z / NASENNE NIEBENZODIAZEPINOWE",
          "ANKSJOLITYKI I NASENNE NIE-BZD", "STABILIZATORY NASTROJU",
          "GABAPENTYNOIDY", "PRZECIWPADACZKOWE W UZYCIU PSYCHIATRYCZNYM",
          "UZALEŻNIENIA / LECZENIE SUBSTYTUCYJNE"}
ALIAS_CACHE = {"escytalopram": "escitalopram", "flupentyksol": "flupentiksol",
               "cytalopram": "citalopram",
               "zuklopentyksol": "zuklopentiksol"}

bledy, uwagi = [], []


def plaski(s):
    return re.sub(r"[^a-z0-9]", "", inn.bez_ogonkow(s or "").lower())


def naglowki(tekst):
    return [l for l in tekst.split("\n")
            if re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9 _/.\-]{1,}$', l)]


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
        # 1. KOLEJNOSC: naglowek sekcji musi miec pod soba karte
        for i, h in enumerate(H):
            if h not in SEKCJE:
                continue
            if not [x for x in H[i + 1:] if x not in SEKCJE]:
                bledy.append("KOLEJNOSC %s: sekcja '%s' nie ma pod soba zadnej karty" % (f, h))
        # 2. PRZYPISANIE
        for h in H:
            if h in SEKCJE:
                continue
            n_we += 1
            # Nazwa karty moze niesc dwa synonimy (KWAS WALPROINOWY / WALPROINIAN).
            # Probujemy kazdej czesci: wystarczy, ze jedna ma most do rejestru.
            atc = set()
            for czesc in [h] + h.split("/"):
                czesc = czesc.strip()
                if not czesc:
                    continue
                klucz = ALIAS_CACHE.get(plaski(czesc), plaski(czesc))
                meta = cache.get(plaski(klucz))
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
