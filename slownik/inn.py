#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SLOWNIK INN — jedna substancja, trzy sposoby zapisu.

Po co: rejestr pisze "Lithii carbonas", ksiazka pisze "lithium", nasz plik
nazywa sie "lit". Trzy razy pod rzad moje dorazne obcinanie koncowek
uznalo lit, metadon, ketamine i memantyne za braki, bo nie trafilo miedzy
dopelniacz a mianownik. Kazdy blad szedl w te sama strone: ZAWYZAL braki.

ZASADA. Klucz substancji powstaje DETERMINISTYCZNIE z nazwy lacinskiej:
  1. usuniecie czlonu soli i uwodnienia (jawna lista, nie heurystyka),
  2. sprowadzenie koncowki przypadka do tematu (jawna tabela, najdluzsze
     dopasowanie, minimalna dlugosc tematu),
  3. kanonizacja pisowni na potrzeby SZUKANIA W TEKSCIE (ph->f, th->t,
     y->i, c->k) - tylko do porownania, nigdy do zapisu.
SCALANIE. Dwie rozne nazwy rejestrowe moga dac ten sam klucz TYLKO wtedy,
gdy roznia sie sola albo przypadkiem. Kazde inne zderzenie jest zglaszane
do przegladu, nie scalane po cichu (warstwa 40, par. 3B).
"""
import re, unicodedata

# Czlony, ktore NIE naleza do nazwy substancji: sole, estry, uwodnienia, formy.
SOLE = {
    "hydrochloridum","hydrochloridi","hydrobromidum","hydrobromidi","sulfas","sulfatis",
    "mesylas","mesilas","maleas","maleatis","tartras","tartratis","citras","citratis",
    "succinas","fumaras","hydrogenofumaras","hydrogenotartras","dimaleas","besilas",
    "acetas","decanoas","palmitas","embonas","pamoas","enantas","lauroxil","phosphas",
    "nitras","lactas","stearas","oxalas","bromidum","iodidum","chloridum","carbonas",
    "natricum","natrii","kalicum","kalii","calcicum","calcii","magnesii","argenti",
    "monohydricum","dihydricum","trihydricum","hemihydricum","anhydricum","siccum",
    "micronisatum","purificatum","hydricum","sesquihydricum","monohydrate",
    "acidum","acidi","acid",   # kwalifikator, nie substancja: "Acidum valproicum"
    # Przymiotnikowe formy anionu. "Lithium carbonicum" to ten sam lek co
    # "Lithii carbonas" - roznica jest w zapisie soli, nie w substancji.
    "carbonicum","carbonici","chloricum","sulfuricum","phosphoricum","nitricum","boricum",
}
# Koncowki przypadkow lacinskich. Kolejnosc = od najdluzszej.
KONCOWKI = ("icum","icus","ica","orum","arum","ibus","ium","um","us","is","ae","as","os","i","o","a","e")
# "icum" przed "um": "valproicum" -> "valpro", zeby spotkalo sie z "valproas".
MIN_TEMAT = 5


def bez_ogonkow(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def temat(slowo):
    """Nazwa lacinska jednego wyrazu -> temat. Deterministycznie."""
    w = bez_ogonkow(slowo).lower()
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return ""
    for k in KONCOWKI:
        if w.endswith(k) and len(w) - len(k) >= MIN_TEMAT:
            return w[: -len(k)]
    return w


def klucz(nazwa_lacinska, diag=None):
    """Pelna nazwa rejestrowa -> klucz substancji (moze byc zlozony).

    Dwa zabezpieczenia przed CICHYM SCALENIEM (warstwa 40, par. 3B):
      1. Gdy po odsianiu soli nie zostaje nic, klucz NIE jest pusty - wraca
         cala nazwa po kanonizacji. Bez tego 19 roznych substancji zlozonych
         wylacznie z czlonow soli (Calcii carbonas, Kalii chloridum, 13C-urea)
         dostawalo jeden wspolny pusty klucz.
      2. Gdy jakis czlon NIE jest sola, a wypadl przez minimalna dlugosc
         tematu, klucz dostaje przyrostek "|ZUBOZONY". Bez tego
         "Bifonazolum + Urea" scalalo sie z samym "Bifonazolum", bo "Urea"
         ma cztery litery.
    """
    czesci, odrzucone = [], []
    for w in re.split(r"[^A-Za-zÀ-ž0-9]+", nazwa_lacinska or ""):
        if not w:
            continue
        if bez_ogonkow(w).lower() in SOLE:
            continue
        t = temat(w)
        if len(t) >= MIN_TEMAT:
            czesci.append(t)
        elif t:
            odrzucone.append(t)
    if diag is not None:
        diag["odrzucone"] = odrzucone
    if not czesci:
        pelna = re.sub(r"[^a-z0-9]", "", bez_ogonkow(nazwa_lacinska or "").lower())
        return "CALA:" + pelna
    k = "+".join(sorted(set(czesci)))
    if odrzucone:
        k += "|ZUBOZONY:" + "+".join(sorted(set(odrzucone)))
    return k


def warianty(t):
    """Warianty pisowni DO SZUKANIA W TEKSCIE. Nigdy do zapisu."""
    v = {t}
    v.add(t.replace("ph", "f"))
    v.add(t.replace("th", "t"))
    v.add(t.replace("y", "i"))
    v.add(t.replace("c", "k"))
    v.add(t.replace("ph", "f").replace("th", "t").replace("y", "i").replace("c", "k"))
    v.add(t.replace("ph", "f").replace("y", "i"))
    return {x for x in v if len(x) >= MIN_TEMAT}


def w_tekscie(t, tekst):
    """Czy temat wystepuje w tekscie (po kanonizacji pisowni)."""
    return any(x in tekst for x in warianty(t))
