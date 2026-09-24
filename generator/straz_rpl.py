#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STRAZ L4 x RPL — maszynowe sprawdzenie twierdzen paczki o rejestrze PL.

CO TO JEST. Warstwa L4 ramy umie dzis powiedziec tylko "nikt na to nie patrzyl
od N dni". Tutaj zdania paczki o rejestrze sa KONFRONTOWANE z oficjalnym
eksportem RPL, ktory to repozytorium sciaga co poniedzialek.

SZEW [rama, SZWY]. Twierdzenia zyja w paczce (modul 18, karty DRUG_DB) i tam
pilnuje ich narzedzia/straz_czasu.py — po kotwicy i po dacie. Tutaj pilnowana
jest ich TRESC, bo tutaj leza dane. Plik pytan odwoluje sie do wpisow strazy
po ID (R01, R03...). Zadna strona nie zastepuje drugiej: tamta pilnuje, czy
zdanie nadal stoi w pliku, ta — czy jest prawdziwe.

KLUCZ TO ATC, NIE NAZWA. Rejestr mowi po lacinie (Quetiapinum, Acidum
valproicum), paczka po polsku. Dopasowanie po nazwie byloby przyblizone,
a 3B zabrania przyblizonego klucza dla danych podawanych przy pacjencie.

KANARKI SA WARUNKIEM, NIE OZDOBA. Zanim padnie jakikolwiek wniosek o
NIEOBECNOSCI, sprawdzane sa leki, o ktorych paczka wie, ze w rejestrze SA.
Zero przy ktorymkolwiek znaczy: zapytanie albo eksport zepsuty — i wtedy
narzedzie NIE ORZEKA NICZEGO. Powod jest empiryczny: przy pierwszej probie
dwa zapytania zwrocily "0 produktow kwetiapiny", co wygladalo jak odpowiedz,
a bylo bledem pola. Bez kanarka automat zaczalby kasowac prawdziwe
ostrzezenia z kart.

WYNIK JEDNEGO PYTANIA:
  ZGODNE     rejestr potwierdza zdanie paczki
  ROZBIEZNE  rejestr mu przeczy -> zdanie w paczce jest DZIS FALSZYWE
  NIE_WIEM   nie da sie rozstrzygnac (brak produktu w spisie, zly typ)
"""
import datetime, json, os, re, sys

KORZEN  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPIS    = os.environ.get("RPL_SPIS",    os.path.join(KORZEN, "rpl", "RPL_PSYCH.json"))
PYTANIA = os.environ.get("RPL_PYTANIA", os.path.join(KORZEN, ".github", "straz_rpl_pytania.tsv"))
KANARKI = os.environ.get("RPL_KANARKI", os.path.join(KORZEN, ".github", "straz_rpl_kanarki.tsv"))

# Spis jest sciagany co poniedzialek. Dwa tygodnie to dwa nieudane przebiegi
# z rzedu — wtedy problem jest po stronie pobierania, nie rejestru.
MAX_WIEK_SPISU = int(os.environ.get("RPL_MAX_WIEK", "14"))

def wczytaj_tsv(sciezka, kolumn):
    if not os.path.isfile(sciezka):
        raise SystemExit("FAIL: brak pliku %s" % sciezka)
    out, zle = [], []
    for nr, linia in enumerate(open(sciezka, encoding="utf-8"), 1):
        if linia.startswith("#") or not linia.strip():
            continue
        pola = linia.rstrip("\n").split("\t")
        if len(pola) != kolumn:
            zle.append("  wiersz %d: %d kolumn zamiast %d" % (nr, len(pola), kolumn))
            continue
        out.append(pola)
    if zle:
        print("FAIL: zly format %s" % os.path.basename(sciezka))
        print("\n".join(zle)); sys.exit(1)
    return out

def granica():
    """Drukowane przy KAZDYM wyniku, zielonym i czerwonym.
    [Grok, runda R6] Granica tego narzedzia: wolno mu pytac, czy NOSNIK
    w swiecie nadal istnieje i czy tekst zrodla sie ruszyl. Nie wolno mu
    pytac, czy ZDANIE KLINICZNE na karcie jest prawdziwe. Drugie pytanie,
    obsluzone pierwszym zrodlem, produkuje falszywa pewnosc: zielone
    zlaczenie wyglada jak walidacja dawki."""
    print()
    print("-" * 70)
    print("CZEGO TO SPRAWDZENIE NIE DOWODZI — czytaj, zanim uznasz to za zgode.")
    print("-" * 70)
    print("Rejestr NIE NIESIE EKSPOZYCJI. Zweryfikowane na eksporcie 2026-09-23:")
    print("   Clopixol-Acuphase   50 mg   Roztwor do wstrzykiwan")
    print("   Clopixol-Depot     200 mg   Roztwor do wstrzykiwan")
    print("Krotko dzialajacy i depot maja IDENTYCZNY napis w polu postac.")
    print("Tak samo Okedi (28 dni) i Rispolept Consta (2 tygodnie).")
    print()
    print("Dlatego ta straz NIGDY nie mowi 'dawka potwierdzona rejestrem' ani")
    print("'mozna podac'. Mowi wylacznie, czy pozycja w rejestrze jest albo")
    print("jej nie ma. Para dawka-interwal, rownowaznosc depotow i zasadnosc")
    print("zamiany zostaja po stronie karty, modulu 18 i lekarza.")
    print()
    print("Z TEGO POWODU NIE MA TU PYTANIA TYPU 'OBECNOSC_POSTACI'. Pytanie")
    print("'czy iniekcja tej substancji jest w RPL' wyglada na uzyteczne,")
    print("a rozpina falszywy parasol rejestru nad zla para dawka-interwal.")
    print("Jego brak jest decyzja, nie przeoczeniem.")
    print()
    print("Pole waznosc_pozwolenia nie jest tu uzywane jako sygnal wycofania.")
    print("Na 2696 pozycji 519 ma je puste, 1110 to 'Bezterminowe', a 124 nosi")
    print("daty z przeszlosci — pole zostaje po wygasnieciu, wiec 'wygaslo'")
    print("z tego eksportu bylby wnioskiem z danej, ktora milczy.")


def main():
    if not os.path.isfile(SPIS):
        print("FAIL: brak spisu RPL (%s). Bez niego nie orzekam niczego." % SPIS)
        sys.exit(1)
    d = json.load(open(SPIS, encoding="utf-8"))
    produkty = d.get("produkty") or []
    stan = (d.get("metadata") or {}).get("stan_na_dzien", "NIEZNANY")

    def atc_listy(r): return [str(a) for a in (r.get("atc") or [])]
    def po_atc(kod):  return [r for r in produkty if any(a.startswith(kod) for a in atc_listy(r))]

    print("=" * 70)
    print("STRAZ L4 x RPL")
    print("=" * 70)
    print("SPIS: %s" % os.path.relpath(SPIS, KORZEN))
    print("STAN REJESTRU NA DZIEN: %s      produktow w spisie: %d" % (stan, len(produkty)))
    print()
    if not produkty:
        print("FAIL: spis pusty. Pusty wynik NIE JEST informacja, ze czegos nie ma.")
        sys.exit(1)

    # WIEK SPISU. Ta straz czyta plik z repozytorium, nie rejestr na zywo.
    # Gdyby spis-rpl przestal dzialac — zmieniony URL eksportu, padniete API,
    # wygasly workflow — straz dostawalaby w kolko ten sam stary plik i byla
    # ZIELONA OD NIESWIEZYCH DANYCH. To jest dokladnie to, przed czym warstwa
    # L4 ma bronic, wiec musi pilnowac rowniez wieku wlasnego wejscia.
    dzis = datetime.date.today()
    if os.environ.get("RPL_DZIS"):
        dzis = datetime.date.fromisoformat(os.environ["RPL_DZIS"])
    try:
        d_spisu = datetime.date.fromisoformat(stan)
    except ValueError:
        print("FAIL: spis nie podaje daty w formacie RRRR-MM-DD (stan_na_dzien=%s)." % stan)
        print("Bez daty wejscia nie wiem, czy odpowiadam o dzisiaj, czy o zeszlym roku.")
        sys.exit(1)
    wiek = (dzis - d_spisu).days
    print("WIEK SPISU: %d dni (limit %d)" % (wiek, MAX_WIEK_SPISU))
    if wiek > MAX_WIEK_SPISU:
        print()
        print("FAIL: SPIS SIE ZESTARZAL — nie orzekam niczego.")
        print("Spis jest sciagany co poniedzialek; %d dni znaczy, ze pobieranie" % wiek)
        print("przestalo dzialac. Odpowiedzi z tego pliku opisywalyby rejestr")
        print("sprzed %d dni, a wygladalyby jak odpowiedzi o dzisiaj." % wiek)
        print("Sprawdz workflow 'Spis RPL (leki psychiatryczne)'.")
        sys.exit(1)
    print()

    kanarki = wczytaj_tsv(KANARKI, 3)
    if not kanarki:
        print("FAIL: brak kanarkow. Bez nich zaden wniosek o nieobecnosci nie jest wazny.")
        sys.exit(1)
    print("KANARKI (leki, o ktorych paczka wie, ze SA):")
    padl = []
    for kod, minimum, opis in kanarki:
        n = len(po_atc(kod))
        ok = n >= int(minimum)
        print("   %-9s %-24s %4d produktow  (min %s)  %s"
              % (kod, opis[:24], n, minimum, "ok" if ok else "PADL"))
        if not ok:
            padl.append("%s (%s): %d < %s" % (kod, opis, n, minimum))
    print()
    if padl:
        print("KANARKI PADLY — NIE ORZEKAM NICZEGO:")
        for x in padl: print("   " + x)
        print()
        print("To NIE znaczy, ze tych lekow nie ma w rejestrze. Znaczy, ze zepsute")
        print("jest zapytanie albo eksport. Wniosek o nieobecnosci bylby tu")
        print("najgorszym mozliwym bledem: skasowalby prawdziwe ostrzezenie z karty.")
        sys.exit(1)

    pytania = wczytaj_tsv(PYTANIA, 6)
    if not pytania:
        print("FAIL: zero pytan. Regula bez wejscia nie jest zielona.")
        sys.exit(1)

    n_zgodne = n_rozbiezne = n_niewiem = 0
    rozbiezne = []
    print("PYTANIA (%d):" % len(pytania))
    print("-" * 70)
    for ident, kod, typ, param, zrodlo, skutek in pytania:
        trafienia = po_atc(kod) if kod != "-" else produkty
        dowod = []
        if typ == "BRAK_PRODUKTU":
            n = len(trafienia)
            wynik = "ZGODNE" if n == 0 else "ROZBIEZNE"
            szczegol = "%d produktow" % n
            dowod = ["%s | %s | %s" % (r.get("nazwa"), r.get("moc"), r.get("postac"))
                     for r in trafienia[:4]]
        elif typ == "BRAK_POSTACI":
            rx = re.compile(param, re.I)
            maj = [r for r in trafienia if rx.search(r.get("postac") or "")]
            wynik = "ZGODNE" if not maj else "ROZBIEZNE"
            szczegol = "%d produktow, %d roznych postaci, pasujacych: %d" % (
                len(trafienia), len(set((r.get("postac") or "") for r in trafienia)), len(maj))
            dowod = ["%s | %s" % (r.get("nazwa"), r.get("postac")) for r in maj[:4]]
        elif typ == "NAZWA_POWSZECHNA":
            # PARAMETR: "Nazwa=Oczekiwana" albo "Nazwa|moc=Oczekiwana".
            # Moc jest czescia klucza, bo pulapka nazewnicza potrafi dotyczyc
            # JEDNEJ mocy: Invega 3/6/9 mg ma Paliperidonum, a 12 mg
            # Paraperidonum. Pytanie bez mocy przechodziloby na sasiednim
            # wpisie i milczalo, gdy rejestr poprawi akurat ten jeden.
            nazwa_prod, oczek = param.split("=", 1)
            moc_f = None
            if "|" in nazwa_prod:
                nazwa_prod, moc_f = nazwa_prod.split("|", 1)
            maj = [r for r in trafienia if (r.get("nazwa") or "").lower() == nazwa_prod.lower()]
            if moc_f is not None:
                maj = [r for r in maj if (r.get("moc") or "").strip() == moc_f.strip()]
            if not maj:
                wynik = "NIE_WIEM"
                szczegol = "produktu '%s'%s nie ma dzis w spisie" % (nazwa_prod, " " + moc_f if moc_f else "")
            else:
                zgodne = [r for r in maj if (r.get("nazwa_powszechna") or "") == oczek]
                wynik = "ZGODNE" if zgodne else "ROZBIEZNE"
                szczegol = "%d wpisow, nazwa_powszechna: %s" % (
                    len(maj), sorted(set((r.get("nazwa_powszechna") or "") for r in maj)))
        else:
            wynik, szczegol = "NIE_WIEM", "nieznany typ pytania: %s" % typ

        if wynik == "ZGODNE":
            n_zgodne += 1
        elif wynik == "ROZBIEZNE":
            n_rozbiezne += 1
            rozbiezne.append((ident, zrodlo, skutek, szczegol, dowod))
        else:
            n_niewiem += 1
        print("  %-5s %-9s %-17s %-10s %s" % (ident, kod, typ, wynik, szczegol))
    print("-" * 70)
    print("BILANS: N_PYTAN %d = ZGODNE %d + ROZBIEZNE %d + NIE_WIEM %d"
          % (len(pytania), n_zgodne, n_rozbiezne, n_niewiem))
    if len(pytania) != n_zgodne + n_rozbiezne + n_niewiem:
        print("FAIL: bilans sie nie zgadza."); sys.exit(1)
    print()

    if not rozbiezne:
        print("ZGODNE ZE STANEM REJESTRU NA %s." % stan)
        print()
        print("CO TO ZNACZY: te zdania paczki sa na ten dzien PRAWDZIWE — nie")
        print("tylko 'nikt nie sprawdzal'. Ta data jest data sprawdzenia")
        print("MASZYNOWEGO i moze zastapic reczna date w rejestrze strazy.")
        granica()
        return 0

    print("ROZBIEZNOSCI — PACZKA MOWI CO INNEGO NIZ REJESTR:")
    print()
    for ident, zrodlo, skutek, szczegol, dowod in rozbiezne:
        print("  %s  ->  %s" % (ident, zrodlo))
        print("     rejestr: %s" % szczegol)
        for x in dowod: print("       %s" % x)
        print("     skutek:  %s" % skutek)
        print()
    print("Te zdania sa DZIS FALSZYWE. Zmiana tresci karty nalezy do lekarza —")
    print("narzedzie nie dotyka kart.")
    granica()
    return 1

if __name__ == "__main__":
    sys.exit(main())
