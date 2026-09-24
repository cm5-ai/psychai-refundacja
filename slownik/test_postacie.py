"""Testy slownika postaci. Dwa rodzaje:
  A. WARTOWNICY - produkty o znanej, sprawdzonej odpowiedzi. Lapia regresje.
  B. TEST BRAKU - sierota LAI. Lapie produkt, ktorego NIKT recznie nie wpisal.
Test B jest wazniejszy: test A sprawdza moja pamiec, test B sprawdza regule.
"""
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import postacie as PO

K = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = json.load(open(os.path.join(K, "rpl/RPL_PSYCH.json"), encoding="utf-8"))["produkty"]
def _klucz(p):
    """ChPL nalezy do PRODUKTU I POSTACI. Sama nazwa sklejala ChPL tabletek
    z iniekcja o tej samej nazwie (Haloperidol WZF, Clonazepamum TZF) i dawala
    falszywe alarmy kadencji. Klucz = (kanoniczna nazwa, drogi)."""
    try:
        drogi = tuple(PO.postac_klasa(p.get("postac"))["droga"])
    except KeyError:
        drogi = ()
    return (PO.kanon_nazwy(p.get("nazwa")), drogi)


C42 = {}
for f in glob.glob(os.path.join(K, "chpl/*.json")):
    if f.endswith("INDEX.json"):
        continue
    for p in json.load(open(f, encoding="utf-8")).get("produkty", []):
        t = (p.get("punkty") or {}).get("4.2")
        if t:
            C42[_klucz(p)] = t

WARTOWNICY = {
    # depoty, przy ktorych pole postac MILCZY - tu bylo zrodlo bledu
    "Fluanxol Depot":     "DEPOT",
    "Clopixol-Depot":     "DEPOT",
    "Decaldol":           "DEPOT",
    # iniekcja posrednia - ani krotka, ani depot
    "Clopixol-Acuphase":  "POSREDNIA",
    # depoty, przy ktorych pole postac mowi wprost
    "Xeplion":            "DEPOT",
    "Trevicta":           "DEPOT",
    "BYANNLI":            "DEPOT",
    "Zypadhera":          "DEPOT",
    "Rispolept Consta":   "DEPOT",
    "Abilify Maintena":   "DEPOT",
    "Okedi":              "DEPOT",
    # KONTRPRZYKLADY: acetas w nazwie powszechnej, ale postac doustna.
    # Regula "acetas = depot" zrobilaby z nich depoty. Musza wyjsc jako NIE-INIEKCJA.
    "Zebinix":            None,
    "Eslibon":            None,
    # doustny XR - przedluzone uwalnianie to NIE depot
    "Invega":             None,
}

def uruchom():
    bledy = []
    # --- test kompletnosci slownika
    r = PO.test_kompletnosci(P)
    print("KOMPLETNOSC SLOWNIKA: %s (napisow %d, brakujacych %d)"
          % (r["WYNIK"], r["N_WEJSCIE"], r["N_ODRZUCONE"]))
    if r["WYNIK"] != "PASS":
        bledy.append("napisy spoza slownika: %s" % r["BRAKUJACE_NAPISY"])

    # --- test A: wartownicy
    widziane = set()
    for p in P:
        n = p.get("nazwa")
        if n not in WARTOWNICY:
            continue
        widziane.add(n)
        e = PO.ekspozycja(p, chpl_42=C42.get(_klucz(p)))["ekspozycja"]
        ocz = WARTOWNICY[n]
        if e != ocz:
            bledy.append("WARTOWNIK %s (%s): oczekiwano %s, jest %s"
                         % (n, p.get("postac"), ocz, e))
    brak = sorted(set(WARTOWNICY) - widziane)
    print("WARTOWNICY: sprawdzono %d z %d" % (len(widziane), len(WARTOWNICY)))
    if brak:
        bledy.append("wartownikow NIE MA w rejestrze (zmiana nazwy albo wycofanie): %s" % brak)

    # --- test B: sieroty LAI
    sieroty = []
    for p in P:
        syg = PO.kandydat_lai(p, chpl_42=C42.get(_klucz(p)))
        if not syg:
            continue
        e = PO.ekspozycja(p, chpl_42=C42.get(_klucz(p)))
        # Wpis w tabeli wyjatkow = alarm sprawdzony przez czlowieka. Rozstrzyga.
        if e["ekspozycja"] == "KROTKA" and e.get("zrodlo") != "WYJATEK_PRODUKTOWY":
            sieroty.append((p.get("nazwa"), p.get("postac"), syg))
    print("SIEROTY LAI: %d" % len(sieroty))
    for s in sieroty:
        bledy.append("SIEROTA LAI %s (%s): sygnaly %s, a klasa mowi KROTKA. "
                     "Dopisz wyjatek produktowy albo popraw regule." % s)

    print()
    if bledy:
        print("FAIL — %d bledow:" % len(bledy))
        for b in bledy:
            print("  -", b)
        return 1
    print("PASS — bez bledow.")
    return 0

if __name__ == "__main__":
    sys.exit(uruchom())
