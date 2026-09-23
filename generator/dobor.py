#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DOBOR PRODUKTU DO SUBSTANCJI - KLUCZ DETERMINISTYCZNY.

Zastepuje dopasowanie po szkielecie spolgloskowym, ktore mieszalo leki:
prometazyna (szkielet prmts) trafiala na Pramatis czyli Escitalopramum,
chlorpromazyna (khlrp) zbierala Chlorprothixeni i Prochlorperazini,
perazyna (prsn) lapala Persen Noc czyli Valerianae extractum.
Dziesiec substancji nie dawalo zadnego trafienia.

ROZSTRZYGNIECIE RECENZJI 2026-09-23. Sam ATC5 NIE WYSTARCZA - zastapilby
jedna slaba tozsamosc druga. Haloperidol i dekanian haloperidolu maja ten sam
kod N05AD01, a dawki i odstepy nie sa porownywalne. Klucz jest WIELOPOLOWY:
  nazwa_powszechna (lacinska INN, po kanonizacji) ORAZ atc5
Dopasowanie WYLACZNIE przez rownosc. Zero podobienstwa, zero progow.

TABELA JEST DANYMI, NIE KODEM. tabela_kluczy.json - kazdy wpis niesie DOWOD
w postaci produktow, ktore go uzasadniaja, i status WYMAGA_ZATWIERDZENIA
dopoki lekarz nie potwierdzi.

CO Z POSTACIA. Klucz zbiera etykiety; ROZDZIELENIE postaci (doustna, octan,
dekanian) nalezy do KARTY, nie do doboru - karta pokazuje postac przy kazdym
produkcie i ostrzega, gdy stoja obok siebie dawki nieporownywalne.
"""
import json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polityka

TABELA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tabela_kluczy.json")


def kanon(s):
    """Kanonizacja JAWNA: bez znakow diakrytycznych, tylko litery, male."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s)


def wczytaj_tabele(sciezka=TABELA):
    return json.load(open(sciezka, encoding="utf-8"))["substancje"]


def dobierz(substancja, produkty, tabela=None):
    """Zwraca (wybrane, raport). Raport rozlicza KAZDY produkt wejsciowy."""
    polityka.sprawdz_semantyke("CHPL_LAYER", "WSKAZANIE", "DETERMINISTYCZNY",
                               ("nazwa_powszechna", "atc"))
    tab = (tabela if tabela is not None else wczytaj_tabele()).get(substancja)
    if tab is None:
        return [], {"STAN": "BRAK WPISU W TABELI KLUCZY",
                    "uwaga": "Brak wpisu NIE znaczy, ze leku nie ma. Znaczy, ze "
                             "nikt jeszcze nie zapisal dla niego klucza.",
                    "N_WEJSCIE": len(produkty), "N_ZACHOWANE": 0,
                    "N_ODRZUCONE": len(produkty),
                    "ODRZUCONE": [p.get("id") or p.get("nazwa") for p in produkty]}
    npow = {kanon(x) for x in tab["nazwa_powszechna"]}
    atc5 = {a[:5] for a in tab["atc"]}
    wybrane, odrzucone = [], []
    for p in produkty:
        zgodna_nazwa = kanon(p.get("nazwa_powszechna")) in npow
        zgodny_atc = any(a[:5] in atc5 for a in (p.get("atc") or []))
        (wybrane if (zgodna_nazwa and zgodny_atc) else odrzucone).append(p)
    raport = {"STAN": "OK", "N_WEJSCIE": len(produkty), "N_ZACHOWANE": len(wybrane),
              "N_ODRZUCONE": len(odrzucone),
              "ODRZUCONE": [{"nazwa": p.get("nazwa"),
                             "nazwa_powszechna": p.get("nazwa_powszechna"),
                             "atc": p.get("atc")} for p in odrzucone][:200],
              "klucz": {"nazwa_powszechna": sorted(tab["nazwa_powszechna"]),
                        "atc5": sorted(atc5)},
              "status_wpisu": tab.get("status")}
    assert raport["N_WEJSCIE"] == raport["N_ZACHOWANE"] + raport["N_ODRZUCONE"], \
        "BILANS DOBORU dla %s" % substancja
    return wybrane, raport
