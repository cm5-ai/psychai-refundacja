"""Klasyfikator postaci leku dla PSYCH-AI.

Trzy pola, DWA ROZNE ZRODLA:
  DROGA, UWALNIANIE  -> deterministycznie z pola postac (slownik_postaci.json)
  EKSPOZYCJA         -> z ChPL albo z jawnej tabeli wyjatkow (wyjatki_produktowe.json)
Pole postac NIE koduje depotu. Fluanxol Depot to dowod.

Zakaz z warstwy 40 par. 3B: dopasowanie przyblizone nie jest dopuszczalnym
zrodlem danych podawanych przy pacjencie. Klucz to rownosc napisu.
"""
import json, os, re, unicodedata

K = os.path.dirname(os.path.abspath(__file__))
SLOWNIK = json.load(open(os.path.join(K, "slownik_postaci.json"), encoding="utf-8"))
WYJATKI = json.load(open(os.path.join(K, "wyjatki_produktowe.json"), encoding="utf-8"))

# Sole i estry, ktore same w sobie oznaczaja postac o przedluzonym dzialaniu,
# ALE WYLACZNIE gdy droga jest iniekcyjna. Bez tego warunku "acetas" zrobiloby
# depot z Zebinixu (Eslicarbazepini acetas, tabletki doustne).
SOLE_LAI = ("decanoas", "palmitas", "pamoas", "embonas", "enanthas", "lauroxil")
SOLE_POSREDNIE = ("acetas",)
# Token w NAZWIE PRODUKTU, nie w polu postac. Sygnal pomocniczy, nie rozstrzygajacy.
TOKENY_LAI = ("depot", "depo", "maintena", "consta", "acuphase", "trevicta", "byannli", "xeplion")
# Porownanie na malych literach: rejestr zapisuje BYANNLI wielkimi, a token "Byannli"
# go nie lapal. Wykryte 2026-09-24 przy pierwszym uruchomieniu detektora.
KADENCJA = re.compile(r"co\s+(dwa|trzy|cztery|sześć|6|2|3|4|12|24)\s+(tygodni|tygodnie|miesiac|miesiące|miesięcy)"
                      r"|raz\s+na\s+(miesiąc|\d+\s*tygodni)|co\s+miesiąc|comiesięczn", re.I)
NOSNIK_OLEISTY = re.compile(r"olej\w*\s+(arachidow|sezamow|rycynow)|triglicerydy|viscoleo", re.I)


def kanon(s):
    return unicodedata.normalize("NFC", (s or "").strip())


def postac_klasa(postac):
    """DROGA + UWALNIANIE z pola postac. Napis spoza slownika = wyjatek, nie UNKNOWN."""
    k = kanon(postac)
    if k not in SLOWNIK["POSTACIE"]:
        raise KeyError("NAPIS SPOZA SLOWNIKA POSTACI: %r. "
                       "Dopisz go do slownik_postaci.json. Nie zgaduj." % k)
    return SLOWNIK["POSTACIE"][k]


def ekspozycja(produkt, chpl_42=None):
    """DEPOT / POSREDNIA / KROTKA / None. Zrodlo jawne w polu 'zrodlo'."""
    nazwa = kanon(produkt.get("nazwa"))
    w = WYJATKI["PRODUKTY"].get(nazwa)
    if w:
        return {"ekspozycja": w["ekspozycja"], "interwal_kubel": w.get("interwal_kubel"),
                "zrodlo": "WYJATEK_PRODUKTOWY", "pin": w.get("pin")}
    kl = postac_klasa(produkt.get("postac"))
    if "INIEKCJA" not in kl["droga"]:
        return {"ekspozycja": None, "zrodlo": "NIE_INIEKCJA"}
    if kl["uwalnianie"] == "PRZEDLUZONE":
        return {"ekspozycja": "DEPOT", "zrodlo": "POLE_POSTAC"}
    if chpl_42 and KADENCJA.search(chpl_42):
        return {"ekspozycja": "DEPOT", "zrodlo": "CHPL_4.2_KADENCJA"}
    return {"ekspozycja": "KROTKA", "zrodlo": "DOMYSLNIE_KROTKA"}


def kandydat_lai(produkt, chpl_42=None, chpl_61=None):
    """TEST BRAKU. Sygnaly NIEZALEZNE od slownika i od tabeli wyjatkow.
    Zwraca liste trafionych sygnalow. Produkt z sygnalem, ktory dostal klase
    KROTKA i nie ma wpisu w tabeli wyjatkow, to SIEROTA LAI - build ma zawolac
    o nowy wyjatek, nie przepuscic go po cichu."""
    syg = []
    try:
        kl = postac_klasa(produkt.get("postac"))
    except KeyError:
        return ["NAPIS_SPOZA_SLOWNIKA"]
    if "INIEKCJA" not in kl["droga"]:
        return syg
    npow = (produkt.get("nazwa_powszechna") or "").lower()
    if any(s in npow for s in SOLE_LAI):
        syg.append("SOL_LAI")
    if any(s in npow for s in SOLE_POSREDNIE):
        syg.append("SOL_POSREDNIA")
    nz = (produkt.get("nazwa") or "").lower()
    if any(t in nz for t in TOKENY_LAI):
        syg.append("TOKEN_W_NAZWIE")
    if chpl_42 and KADENCJA.search(chpl_42):
        syg.append("KADENCJA_CHPL_4.2")
    if chpl_61 and NOSNIK_OLEISTY.search(chpl_61):
        syg.append("NOSNIK_OLEISTY")
    return syg


def test_kompletnosci(produkty):
    """Kazdy napis w polu postac musi byc w slowniku. Bilans par. 3B."""
    napisy = {kanon(p.get("postac")) for p in produkty}
    brak = sorted(napisy - set(SLOWNIK["POSTACIE"]))
    return {"N_WEJSCIE": len(napisy),
            "N_ZACHOWANE": len(napisy) - len(brak),
            "N_ODRZUCONE": len(brak),
            "BRAKUJACE_NAPISY": brak,
            "WYNIK": "PASS" if not brak else "FAIL"}
