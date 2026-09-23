#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROPOZYCJA TABELI substancja -> klucz. NARZEDZIE WSKAZUJACE, NIE ZAPISUJACE.

Klucz jest HEURYSTYCZNY (podobienstwo nazwy polskiej do lacinskiej), wiec wg
polityki wolno mu wylacznie WSKAZYWAC. Wynik jest materialem do recznego
autoryzowania tabeli, nie tabela. Zadna liczba stad nie idzie do karty.

Dlaczego nie uzywam istniejacego dopasuj(): odziedziczylbym jego slepe plamy
(10 substancji z zerem trafien). To jest DRUGA, niezalezna droga - i rozjazd
miedzy nimi sam jest informacja.
"""
import json, re, sys, unicodedata, collections
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import polityka

polityka.sprawdz_semantyke("CHPL_LAYER", "WSKAZANIE", "HEURYSTYCZNY",
                           ("nazwa_powszechna", "atc"))

def kanon(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s)

# Polska nazwa -> rdzen lacinski. Przeksztalcenia jawne, nie zgadywane.
def rdzenie(pl):
    k = kanon(pl)
    w = {k}
    for a, b in (("y", "i"), ("ks", "x"), ("k", "c"), ("f", "ph"), ("z", "s"),
                 ("w", "v"), ("ty", "thy"), ("oksy", "oxy"), ("cy", "ci")):
        w |= {x.replace(a, b) for x in list(w)}
    return {x[:7] for x in w if len(x) >= 5}

produkty = json.load(open(sys.argv[1], encoding="utf-8"))["produkty"]
lista = [l.strip() for l in open(sys.argv[2], encoding="utf-8")
         if l.strip() and not l.startswith("#")]

print("SUBSTANCJI: %d   PRODUKTOW: %d" % (len(lista), len(produkty)))
print()
jedno, wiele, zero = [], [], []
for s in lista:
    rdz = rdzenie(s)
    grupy = collections.defaultdict(lambda: [0, set()])
    for p in produkty:
        npow = (p.get("nazwa_powszechna") or "").strip()
        if any(kanon(npow).startswith(r) for r in rdz):
            for a in (p.get("atc") or ["?"]):
                grupy[(npow, a)][0] += 1
                grupy[(npow, a)][1].add((p.get("postac") or "?")[:28])
    if not grupy:
        zero.append(s); continue
    atc5 = {a for (_, a) in grupy}
    (wiele if len(grupy) > 1 else jedno).append((s, sorted(grupy.items()), atc5))

print("=== JEDNOZNACZNE (%d) - jedna nazwa powszechna, jeden kod ===" % len(jedno))
for s, g, _ in jedno:
    (npow, a), (n, post) = g[0]
    print("  %-18s %-34s %-9s n=%d" % (s, npow, a, n))
print()
print("=== DO ROZSTRZYGNIECIA RECZNEGO (%d) ===" % len(wiele))
for s, g, atc5 in wiele:
    print("  %s   [%s]" % (s, "ten sam ATC5" if len(atc5) == 1 else "ROZNE ATC5"))
    for (npow, a), (n, post) in g:
        print("        %-40s %-9s n=%-3d  %s" % (npow, a, n, " | ".join(sorted(post))[:60]))
print()
print("=== ZERO TRAFIEN (%d) - brak nie znaczy, ze produktu nie ma ===" % len(zero))
print("   " + ", ".join(zero))
print()
print("BILANS: %d + %d + %d = %d (lista %d)" % (len(jedno), len(wiele), len(zero),
      len(jedno)+len(wiele)+len(zero), len(lista)))
