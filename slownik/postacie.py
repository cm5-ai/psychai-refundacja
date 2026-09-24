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
# UWAGA. Kadencja w punkcie 4.2 bywa zdaniem o INNYM produkcie: ChPL
# Clopixol-Acuphase opisuje przejscie na dekanian "co dwa tygodnie", wiec wzorzec
# trafia, choc Acuphase depotem NIE JEST. Dlatego kadencja jest WYLACZNIE ALARMEM
# kierujacym do przegladu, nigdy regula klasyfikujaca. Rozstrzyga tabela wyjatkow
# albo pole postac. Sprawdzone 2026-09-24 na tekscie ChPL.
KADENCJA = re.compile(
    r"co\s+(dwa|trzy|cztery|sześć|osiem|dwanaście|\d{1,2})\s*(tygodni\w*|miesi\w+)"
    r"|w\s+odstęp\w+\s+(\d{1,2}|dwóch|trzech|czterech)\s*(tygodni\w*|miesi\w+)"
    r"|raz\s+na\s+(\d{1,2}\s*)?(tygodni\w*|miesi\w+)"
    r"|co\s+miesi\w+|comiesi\w+", re.I)
# Wzorzec "co N dni" USUNIETY 2026-09-24. Trafil dwa razy i dwa razy falszywie:
# ChPL Clonazepamum TZF ("zwiekszac o 0,5 mg co 3 dni") i ChPL Nivalin
# ("Co 3-4 dni dawke stopniowo zwieksza sie") - oba razy to TEMPO ZWIEKSZANIA
# DAWKI, nie odstep miedzy wstrzyknieciami. Zero trafien prawdziwych.
# Jedyny lek o realnym interwale dobowym, Clopixol-Acuphase (co 2-3 dni),
# jest rozstrzygniety wpisem w tabeli wyjatkow, nie tym sygnalem.
# Alarm, ktory myli sie zawsze, uczy ignorowania alarmow.
NOSNIK_OLEISTY = re.compile(r"olej\w*\s+(arachidow|sezamow|rycynow)|triglicerydy|viscoleo", re.I)


# Kanonizacja klucza. Par. 3B dopuszcza rownosc PO JAWNEJ KANONIZACJI i tylko
# taka. Ponizsze przeksztalcenia sa cala kanonizacja - nie ma zadnego dopasowania
# przyblizonego, progu ani podobienstwa.
MYSLNIKI = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"   # dywiz, mylniki, minus
SPACJE = "\u00a0\u2007\u202f\u2009\u200a"                   # twarda spacja i cienkie


def kanon(s):
    """NFC, mylniki na lacznik, spacje nietypowe na zwykla, zwezenie bialych znakow."""
    s = unicodedata.normalize("NFC", s or "")
    for z in MYSLNIKI:
        s = s.replace(z, "-")
    for z in SPACJE:
        s = s.replace(z, " ")
    s = " ".join(s.split())
    s = re.sub(r"\s*-\s*", "-", s)     # "Clopixol - Depot" == "Clopixol-Depot"
    return s


def kanon_nazwy(s):
    """Jak kanon, dodatkowo bez wielkosci liter. Tylko do nazw produktow:
    rejestr zapisuje ten sam produkt raz jako Abilium, raz jako ABILIUM."""
    return kanon(s).casefold()


_WYJATKI_KANON = {kanon_nazwy(k): v for k, v in WYJATKI["PRODUKTY"].items()}
# Bilans scalania (par. 3B): kanonizacja NIE MOZE skleic dwoch roznych wyjatkow.
assert len(_WYJATKI_KANON) == len(WYJATKI["PRODUKTY"]), (
    "Kanonizacja nazw skleila dwa rozne wyjatki produktowe: %d -> %d"
    % (len(WYJATKI["PRODUKTY"]), len(_WYJATKI_KANON)))


def postac_klasa(postac):
    """DROGA + UWALNIANIE z pola postac. Napis spoza slownika = wyjatek, nie UNKNOWN."""
    k = kanon(postac)
    if k not in SLOWNIK["POSTACIE"]:
        raise KeyError("NAPIS SPOZA SLOWNIKA POSTACI: %r. "
                       "Dopisz go do slownik_postaci.json. Nie zgaduj." % k)
    return SLOWNIK["POSTACIE"][k]


# Kadencja MONITOROWANIA to nie kadencja PODAWANIA. Fraza "monitorowac co miesiac",
# "co szesc miesiecy podejmowac probe zmniejszenia dawki" albo "oznaczac stezenie
# co 3 miesiace" trafiala we wzorzec i dawala falszywe alarmy przy Phenytoin Hikma
# i Memotropil. Odrzucamy trafienie, gdy w jego otoczeniu stoi slowo o kontroli,
# a nie o podaniu. Sprawdzone na tekscie 2026-09-24.
KONTEKST_KONTROLI = re.compile(
    r"monitorow|kontrolow|kontroli|oznacza|stęż|badani|wizyt|ocen[iy]|"
    r"prób\w*\s+zmniejsz|zmniejsz\w*\s+dawk|odstawi", re.I)


def kadencja_podania(tekst, okno=90):
    """Trafienie wzorca kadencji, ktore NIE stoi w zdaniu o monitorowaniu."""
    for m in KADENCJA.finditer(tekst or ""):
        otocz = tekst[max(0, m.start() - okno): m.end() + okno]
        if KONTEKST_KONTROLI.search(otocz):
            continue
        return m
    return None


def ekspozycja(produkt, chpl_42=None):
    """DEPOT / POSREDNIA / KROTKA / None. Zrodlo jawne w polu 'zrodlo'."""
    nazwa = kanon_nazwy(produkt.get("nazwa"))
    w = _WYJATKI_KANON.get(nazwa)
    if w:
        return {"ekspozycja": w["ekspozycja"], "interwal_kubel": w.get("interwal_kubel"),
                "zrodlo": "WYJATEK_PRODUKTOWY", "pin": w.get("pin")}
    kl = postac_klasa(produkt.get("postac"))
    if "INIEKCJA" not in kl["droga"]:
        return {"ekspozycja": None, "zrodlo": "NIE_INIEKCJA"}
    if kl["uwalnianie"] == "PRZEDLUZONE":
        return {"ekspozycja": "DEPOT", "zrodlo": "POLE_POSTAC"}
    if chpl_42 and kadencja_podania(chpl_42):
        # ALARM, nie werdykt: zdanie o kadencji moze dotyczyc innego produktu.
        # Klasa zostaje KROTKA, ale produkt trafia na liste do przegladu przez
        # kandydat_lai(); build ma zazadac wpisu do tabeli wyjatkow.
        return {"ekspozycja": "KROTKA", "zrodlo": "DOMYSLNIE_KROTKA_ALARM_KADENCJA",
                "alarm": "KADENCJA_CHPL_4.2"}
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
    if chpl_42 and kadencja_podania(chpl_42):
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
