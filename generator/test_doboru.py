#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEST DOBORU WOBEC ISTNIEJACEGO CACHE. Bez pobierania czegokolwiek.

Pytanie, na ktore odpowiada: czy nowy, deterministyczny klucz wskazuje te same
produkty, ktore juz leza w kartach - a ktorych jednorodnosc sprawdzono
2026-09-23 (84 z 86 kart jeden ATC5, dwie to ta sama substancja w dwoch
wskazaniach, zadnej obcej etykiety).

PRODUKT Z CACHE, KTOREGO NOWY KLUCZ NIE WSKAZUJE, JEST BLEDEM TABELI. Nowy
kandydat, ktorego w cache nie ma, bledem nie jest - to etykieta, ktorej stare
dopasowanie nie znalazlo, i pobierze sie, gdy bedzie siec.
"""
import json, glob, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dobor

Z = C = 0
def ok(w, opis):
    global Z, C
    if w: Z += 1
    else:
        C += 1; print("  CZERWONE: %s" % opis)

rpl = json.load(open("rpl/RPL_PSYCH.json", encoding="utf-8"))["produkty"]
tab = dobor.wczytaj_tabele()

zgubione, nowi, bilanse = [], collections.Counter(), 0
for f in sorted(glob.glob("chpl/*.json")):
    if f.endswith("INDEX.json"):
        continue
    lek = os.path.basename(f)[:-5]
    d = json.load(open(f, encoding="utf-8"))
    w_cache = {(p.get("nazwa") or "").strip() for p in d.get("produkty", [])}
    if not w_cache:
        continue
    wybrane, rap = dobor.dobierz(lek, rpl, tab)
    bilanse += 1
    ok(rap["N_WEJSCIE"] == rap["N_ZACHOWANE"] + rap["N_ODRZUCONE"],
       "%s: bilans doboru" % lek)
    nazwy = {(p.get("nazwa") or "").strip() for p in wybrane}
    brak = sorted(w_cache - nazwy)
    if brak:
        zgubione.append((lek, brak))
    nowi[lek] = len(nazwy - w_cache)

ok(not zgubione, "zaden produkt z cache nie wypada z nowego doboru: %r" % zgubione[:5])
print("\nSUBSTANCJI SPRAWDZONYCH: %d" % bilanse)
print("PRODUKTOW Z CACHE ZGUBIONYCH PRZEZ NOWY KLUCZ: %d" % len(zgubione))
for lek, b in zgubione[:10]:
    print("   %-18s %s" % (lek, b))
suma_nowych = sum(nowi.values())
print("\nNOWYCH KANDYDATOW (etykiety, ktorych stare dopasowanie nie znalazlo): %d"
      % suma_nowych)
for lek, n in nowi.most_common(8):
    if n: print("   %-18s +%d" % (lek, n))

# LEKI, KTORE STARE DOPASOWANIE MIESZALO. Kazdy z nich to konkretny wypadek
# z 2026-09-23, nie przypadek wymyslony: prometazyna trafiala na Pramatis
# (Escitalopramum), perazyna na Persen Noc (Valerianae extractum),
# chlorpromazyna zbierala Chlorprothixeni i Prochlorperazini.
OBCE = {"prometazyna": ["Pramatis"], "perazyna": ["Persen"],
        "chlorpromazyna": ["Chlorprothixen", "Prochlorperaz"],
        "chlorprotiksen": ["Chlorpromaz", "Prochlorperaz"],
        "chlordiazepoksyd": ["Convulex", "Absenor", "Depakine", "Convival"]}
for _lek, _zak in OBCE.items():
    _w, _r = dobor.dobierz(_lek, rpl, tab)
    _n = [p.get("nazwa") for p in _w]
    _t = [x for x in _n if any(z.lower() in (x or "").lower() for z in _zak)]
    ok(not _t, "%s: obcy produkt w wyniku: %r" % (_lek, _t))
    _s = {(p.get("nazwa_powszechna") or "?") for p in _w}
    ok(len(_s) == 1, "%s: dobor daje jedna substancje, daje %r" % (_lek, sorted(_s)))

print("\nZIELONE %d, CZERWONE %d" % (Z, C))
raise SystemExit(1 if C else 0)
