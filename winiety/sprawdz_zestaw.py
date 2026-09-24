#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPRAWDZ ZESTAW BLOKUJACY — czy winiety mowia o paczce, ktora naprawde istnieje.

PO CO. Winieta z bledna wartoscia oczekiwana jest GORSZA NIZ JEJ BRAK: obleje
poprawna paczke i nauczy ignorowania bramki. Ten skrypt nie uruchamia modelu.
Sprawdza jedno: czy to, czego winieta oczekuje, STOI W PLIKACH.

CZEGO NIE SPRAWDZA. Czy oczekiwana wartosc jest MADRA klinicznie. To nalezy
do lekarza. Tu pytamy tylko, czy jest w paczce.

REGULY
  V1  wartosc oczekiwana musi wystepowac w paczce
  V2  kazdy evidence_key musi wystepowac w paczce
  V1b wartosc WYLICZONA musi wymagac znacznika [WYLICZONE]
  V3  kazdy zwrot z 'wymaga_z_paczki' musi wystepowac w paczce
      'wymaga_zachowania' NIE jest sprawdzane wobec paczki — to wlasciwosc
      odpowiedzi, nie tekst pliku
  V4  zakazane_wartosci sa RAPORTOWANE, nie oblewaja: czesc ma istniec
      (siostrzany produkt, liczba z innej tabeli), a czesc MA NIE ISTNIEC
      (zwroty falszywej nieobecnosci). Raport pokazuje, ktore sa ktore.
  V5  bilans: N_WEJSCIE = liczba krotek, nie liczba plikow
"""
import json, os, sys, glob, unicodedata

def _paczka():
    k = os.environ.get("PSYCHAI_PACZKA")
    if k and os.path.isdir(os.path.join(k, "projekt")):
        return k
    for p in (os.path.expanduser("~/mnt/psychai-paczka"),
              os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "..", "psychai-paczka")):
        if os.path.isdir(os.path.join(p, "projekt")):
            return os.path.normpath(p)
    raise SystemExit("FAIL: nie znajduje paczki.")

def kanon(s):
    """Kanonizacja JAWNA (3B): bez ogonkow, bez wielkosci liter, myslniki
    sprowadzone do jednego znaku, biale znaki sciete. Porownujemy po tym
    kluczu, nie po podobienstwie."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    for a, b in (("–", "-"), ("—", "-"), ("−", "-"),
                 ("„", '"'), ("”", '"'), (" ", " ")):
        s = s.replace(a, b)
    return " ".join(s.lower().split())

ROOT = _paczka()
TEKST = ""
for f in sorted(glob.glob(os.path.join(ROOT, "projekt", "*.txt"))):
    if os.path.basename(f).startswith("MANIFEST_"):
        continue
    TEKST += open(f, encoding="utf-8").read() + "\n"
TEKST_K = kanon(TEKST)

def jest(x):
    return kanon(x) in TEKST_K

def main():
    # Sciezka wzgledem TEGO PLIKU, nie wzgledem katalogu wywolania. Hak
    # pre-push startuje z korzenia repozytorium i wersja wzgledna oblewala
    # bez powodu — czyli falszywy alarm, ktory uczy obchodzenia haka.
    tu = os.path.dirname(os.path.abspath(__file__))
    d = json.load(open(os.path.join(tu, "zestaw_blokujacy.json"), encoding="utf-8"))
    w = d["WINIETY"]
    print("=" * 70)
    print("SPRAWDZENIE ZESTAWU BLOKUJACEGO WOBEC PACZKI")
    print("=" * 70)
    print("paczka: %s" % os.path.relpath(ROOT))
    print("N_WEJSCIE (krotek): %d" % len(w))
    print()
    if not w:
        print("FAIL: zestaw pusty. Regula bez wejscia nie jest zielona.")
        return 1

    # SCHEMAT KROTKI JAKO DANA [2026-09-25, harness mutacyjny].
    # Harness przemianowal klucz "wartosc" na "wartosc_ZEPSUTA". Kazde
    # sprawdzenie ponizej pyta o pole przez .get(), wiec pole NIEISTNIEJACE
    # bylo nie do odroznienia od pola PUSTEGO — kontrola V1 po prostu sie
    # nie odpalila, a bramka powiedziala "ZESTAW SPOJNY". Literowka w kluczu
    # wylaczala kontrole po cichu.
    # To ten sam blad, przed ktorym broni cala paczka: BRAK != PUSTE,
    # "nie znalazlem" != "nie ma". Nazwy pol sa tu DANA, nie domyslem.
    WYMAGANE = {"rdzen", "produkt", "slot", "wartosc", "wartosc_typ",
                "evidence_key", "zakazane_wartosci", "wymaga_z_paczki",
                "wymaga_zachowania"}
    OPCJONALNE = {"komentarz", "rola"}
    TYPY_WARTOSCI = {"CYTAT", "WYLICZONA"}

    bledy, uwagi = [], []
    for v in w:
        ident = v.get("id", "<BEZ ID>")
        if "krotka" not in v:
            bledy.append("V0 %s: winieta bez pola 'krotka'" % ident)
            continue
        k = v["krotka"]
        brak = WYMAGANE - set(k)
        obce = set(k) - WYMAGANE - OPCJONALNE
        if brak:
            bledy.append("V0 %s: krotka BEZ POL %s — kontrole, ktore ich "
                         "pilnuja, po prostu sie nie odpala" % (ident, sorted(brak)))
        if obce:
            bledy.append("V0 %s: krotka ma POLA SPOZA SCHEMATU %s — literowka "
                         "w nazwie klucza wyglada jak pole puste" % (ident, sorted(obce)))
        if k.get("wartosc") and k.get("wartosc_typ") not in TYPY_WARTOSCI:
            bledy.append("V0 %s: wartosc_typ '%s' spoza {CYTAT, WYLICZONA} — "
                         "bez typu nie wiadomo, czy to cytat pola, czy arytmetyka"
                         % (ident, k.get("wartosc_typ")))
        if k.get("wartosc") and k.get("wartosc_typ") == "CYTAT" and not jest(k["wartosc"]):
            bledy.append("V1 %s: wartosc CYTAT '%s' NIE WYSTEPUJE w paczce" % (ident, k["wartosc"]))
        if k.get("wartosc") and k.get("wartosc_typ") == "WYLICZONA" and not (k.get("wymaga_zachowania") or []):
            bledy.append("V1b %s: wartosc WYLICZONA bez wymogu znacznika [WYLICZONE]" % ident)
        for e in k.get("evidence_key") or []:
            if not jest(e):
                bledy.append("V2 %s: evidence_key '%s' NIE WYSTEPUJE w paczce" % (ident, e))
        for m in k.get("wymaga_z_paczki") or []:
            if not jest(m):
                bledy.append("V3 %s: 'wymaga_z_paczki' -> '%s' NIE WYSTEPUJE w paczce" % (ident, m))
        for z in k.get("zakazane_wartosci") or []:
            wart = z.get("wartosc", "") if isinstance(z, dict) else z
            wyj = (z.get("chyba_ze") or []) if isinstance(z, dict) else []
            uwagi.append((ident, wart, jest(wart), len(wyj)))

    print("V4 — ZAKAZANE WARTOSCI: czy to realne pomylki, czy wymyslone")
    print("     JEST w paczce = realne ryzyko pomylki (siostrzany produkt, inna tabela)")
    print("     NIE MA        = zwrot falszywej nieobecnosci, ma nigdy nie pasc")
    print("     wyjatkow: N   = dozwolona, gdy zacytowana PO TO, BY JA WYKLUCZYC")
    for ident, z, obecne, n_wyj in uwagi:
        print("   %-16s %-30s %-6s %s" % (ident, z[:30], "JEST" if obecne else "nie ma",
              ("wyjatkow: %d" % n_wyj) if n_wyj else ""))
    print()
    print("BILANS: krotek %d, sprawdzen V1-V3 wykonanych %d, zakazanych %d"
          % (len(w), sum(1 + len(v["krotka"].get("evidence_key") or [])
                         + len(v["krotka"].get("wymaga_z_paczki") or []) for v in w), len(uwagi)))
    print()
    if bledy:
        print("ZESTAW NIE NADAJE SIE DO UZYCIA — %d bledow:" % len(bledy))
        for b in bledy:
            print("   " + b)
        print()
        print("Winieta oczekujaca czegos, czego w paczce nie ma, OBLEJE POPRAWNA")
        print("PACZKE. To gorsze niz brak winiety, bo uczy ignorowania bramki.")
        return 1
    print("ZESTAW SPOJNY Z PACZKA.")
    print("CO TO ZNACZY: kazda oczekiwana wartosc i kazdy pin ISTNIEJA w plikach.")
    print("NIE znaczy, ze model je odda — to mierzy dopiero przebieg.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
