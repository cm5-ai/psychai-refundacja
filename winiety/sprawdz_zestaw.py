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
import json, os, re, sys, glob, unicodedata

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
                "wymaga_zachowania", "wymagane_zdarzenia", "zakazane_zdarzenia",
                "warunkowe_z_paczki"}
    OPCJONALNE = {"komentarz", "rola"}
    TYPY_WARTOSCI = {"CYTAT", "WYLICZONA"}

    # LEGENDA JEST DEKLARACJA, NIE OZDOBA [2026-09-25, petla 2 harnessu].
    # Plik opisuje krotke dwa razy: slownikiem JAK_CZYTAC_KROTKE dla
    # czytajacego i zbiorem WYMAGANE dla kodu. Nic nie pilnowalo, zeby oba
    # mowily to samo — harness przemianowal klucz w legendzie i przeszlo,
    # bo kod legendy nie czyta. Dwa opisy jednej rzeczy rozjezdzaja sie
    # zawsze; pilnowany jest tylko ten, ktory oblewa.
    legenda = set(d.get("JAK_CZYTAC_KROTKE") or {})
    if not legenda:
        print("FAIL: brak JAK_CZYTAC_KROTKE. Zestaw bez legendy czyta sie"
              " tylko przez kod, a kod nie tlumaczy, co znaczy slot.")
        return 1
    if legenda != WYMAGANE:
        print("FAIL: legenda rozjechana ze schematem.")
        print("   w legendzie, nie w schemacie: %s" % sorted(legenda - WYMAGANE))
        print("   w schemacie, nie w legendzie: %s" % sorted(WYMAGANE - legenda))
        print("   Czytajacy i kod opisuja inna krotke.")
        return 1

    ZAKAZANE_WYMAGANE = {"wartosc"}
    # "zdarzenie" [R9, Grok]: zakaz nie na NAPIS, tylko na KSZTALT — zakres,
    # liczba z interwalem, wspolwystapienie. Bez tego pola zakaz "200 mg"
    # oblewal odpowiedz poprawna, bo 200 jest gornym krancem WLASNEGO
    # zakresu karty. Nazwy ksztaltow sa DANA, nie domyslem parsera.
    ZAKAZANE_OPCJONALNE = {"chyba_ze", "powod", "zdarzenie"}
    # SLOWNIK ZDARZEN JEST DANA [R10]. Rodzina dawkowa chodzi na gramatyce
    # globalnej (winiety/gramatyka.py); rodzina interwalowa jeszcze nie —
    # i nie dala ani jednego falszywego alarmu, wiec nie ruszam jej bez powodu.
    ZDARZENIA = {"ASSERTED_DOSE", "EXCLUDED_DOSE", "QUOTED_DOCTOR",
                 "ASSERTED_DOSE_BEZ_POSTACI", "ZAKRES", "REFUSAL", "MARKER_OPINIA",
                 "INTERWAL_14_DNI", "INTERWAL_28_DNI"}
    RODZINA_DAWKOWA = {"ASSERTED_DOSE", "ASSERTED_DOSE_BEZ_POSTACI", "EXCLUDED_DOSE", "QUOTED_DOCTOR"}

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
        # WARUNKOWE TEZ MUSI ISTNIEC W PACZCE. Inaczej literowka w
        # zastrzezeniu nigdy nie zapali sie na sprawdzeniu statycznym,
        # a krotka bedzie zadac napisu, ktorego nie da sie oddac.
        for r in k.get("warunkowe_z_paczki") or []:
            m = r.get("wymaga") or ""
            if not jest(m):
                bledy.append("V3 %s: 'warunkowe_z_paczki' -> '%s' NIE WYSTEPUJE w paczce"
                             % (ident, m))
        for m in k.get("wymaga_z_paczki") or []:
            if not jest(m):
                bledy.append("V3 %s: 'wymaga_z_paczki' -> '%s' NIE WYSTEPUJE w paczce" % (ident, m))
        for z in k.get("zakazane_wartosci") or []:
            # Zagniezdzony obiekt tez ma schemat. Bez tego literowka w kluczu
            # dawala pusty napis jako "zakazana wartosc" — zakaz, ktory nigdy
            # nie pasuje, czyli kontrola wylaczona po cichu.
            if isinstance(z, dict):
                brak_z = ZAKAZANE_WYMAGANE - set(z)
                obce_z = set(z) - ZAKAZANE_WYMAGANE - ZAKAZANE_OPCJONALNE
                if brak_z or obce_z:
                    bledy.append("V0 %s: zakazana wartosc ma zly schemat "
                                 "(brak %s, obce %s) — zakaz bez wartosci nigdy "
                                 "nie zapali" % (ident, sorted(brak_z), sorted(obce_z)))
                    continue
                if not str(z.get("wartosc") or "").strip():
                    bledy.append("V0 %s: zakazana wartosc pusta" % ident)
                    continue
                # KROTKA Z WLASNYM WYJATKIEM W RODZINIE DAWKOWEJ JEST
                # OBLANYM PROJEKTEM KROTKI, NIE DZIURA DO ZALATANIA [Grok, R10].
                # Wyjatek per krotka to ta sama choroba, ktora wersja 22
                # wyrzucila z warstwy 40: lista powierzchniowych form.
                if z.get("zdarzenie") in RODZINA_DAWKOWA and z.get("chyba_ze"):
                    bledy.append("V7 %s: zakaz '%s' w rodzinie dawkowej niesie wlasne "
                                 "'chyba_ze'. Ramy sa globalne — wyjatek nalezy do "
                                 "gramatyki, nie do krotki" % (ident, z.get("wartosc")))
                    continue
                if "zdarzenie" in z and z["zdarzenie"] not in ZDARZENIA:
                    bledy.append("V0 %s: zdarzenie '%s' spoza zadeklarowanego zbioru %s"
                                 % (ident, z["zdarzenie"], sorted(ZDARZENIA)))
                    continue
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
    # V6 — GRAMATYKA ZDARZEN I JEJ KANARKI [R10, Grok].
    # Gramatyka jest teraz sedzia dla kazdej liczby dawki. Sedzia bez testu
    # linia-w-linie jest gorszy od braku sedziego, bo wyglada na pomiar.
    try:
        sys.path.insert(0, tu)
        import gramatyka
        bl_g = gramatyka.sprawdz_kanarki(cicho=True)
        print("V6 — GRAMATYKA ZDARZEN: kanarkow %d, ram %d, oblanych %d"
              % (len(gramatyka.KANARKI), len(gramatyka.RAMY_WYKLUCZAJACE), len(bl_g)))
        print("     G2, G5, G10 maja NIE zapalic. Kanarek, ktory tylko potwierdza,")
        print("     ze cos dziala, nie wykrywa zakresu za szerokiego.")
        for b in bl_g:
            bledy.append("V6 " + b)
    except Exception as e:
        bledy.append("V6: gramatyka nie da sie uruchomic (%s) — sedzia rodziny "
                     "dawkowej NIE ISTNIEJE, a krotki na niego wskazuja" % e)
    print()

    st = d.get("STATUS_KLASY") or {}
    if st.get("STAN") == "BLOCKING_DISABLED_FOR_CLASS":
        print("STATUS KLASY: BLOCKING_DISABLED_FOR_CLASS — %s" % st.get("KLASA"))
        print("   Oblanie na ZDARZENIU DAWKI trafia do przegladu, NIE zatrzymuje wydania.")
        # NIE 'w' — 'w' to lista krotek, a przeslonieta nazwa zabijala
        # BILANS dwadziescia linii nizej. Ta sama klasa bledu, ktora ten
        # plik sciga: cicha kolizja, ktora nie krzyczy, tylko psuje wynik.
        for warunek in st.get("WARUNKI_POWROTU") or []:
            print("   " + warunek)
        print()

    # V5 — TABLICA ALIASOW MA WLASNE KANARKI [R9, Grok].
    # Tablica bez testu linia-w-linie jest slownikiem, ktoremu nikt nie
    # patrzy na rece: pierwsza literowka wylacza interwal po cichu, a
    # zestaw dalej mowi "SPOJNY". Kanarek KAN-3 pilnuje jednego konkretnego
    # bledu — dopasowania po podciagu ("co 2 tyg" w "co 24 tygodnie").
    za = d.get("ZDARZENIA_I_ALIASY")
    if not za:
        bledy.append("V5: brak ZDARZENIA_I_ALIASY — zakazy na ksztalt nie maja definicji")
    else:
        tab = za.get("TABLICA_ALIASOW") or {}
        kan = za.get("KANARKI") or []
        if not tab:
            bledy.append("V5: TABLICA_ALIASOW pusta — kazdy interwal przeciekalby")
        if not kan:
            bledy.append("V5: tablica aliasow BEZ KANARKOW — slownik bez testu")
        wsz = [(k, a) for k, lst in tab.items() for a in lst]
        dubel = [a for _, a in wsz if [x for _, x in wsz].count(a) > 1]
        if dubel:
            bledy.append("V5: alias w dwoch klasach interwalu: %s" % sorted(set(dubel)))

        def interwaly(tekst):
            """Dopasowanie PO GRANICY SLOWA, nigdy po podciagu."""
            low = " " + re.sub(r"[^0-9a-ząćęłńóśżź.]+", " ", tekst.lower()) + " "
            out = set()
            for klasa, lista in tab.items():
                for a in lista:
                    wz = " " + re.sub(r"[^0-9a-ząćęłńóśżź.]+", " ", a.lower()).strip() + " "
                    if wz in low:
                        out.add(klasa)
            return out

        oczek = {"KAN-1": {"28_DNI"}, "KAN-2": {"14_DNI"}, "KAN-3": set(),
                 "KAN-4": set(), "KAN-5": {"28_DNI"}, "KAN-6": set()}
        n_kan = 0
        for c in kan:
            ident_k = c.get("id")
            if ident_k not in oczek:
                bledy.append("V5: kanarek %s bez oczekiwania w kodzie — kanarek, "
                             "ktorego nikt nie sprawdza, jest komentarzem" % ident_k)
                continue
            n_kan += 1
            mam = interwaly(c.get("tekst", ""))
            if mam != oczek[ident_k]:
                bledy.append("V5 %s: tekst %r -> interwaly %s, oczekiwano %s"
                             % (ident_k, c.get("tekst"), sorted(mam) or "brak",
                                sorted(oczek[ident_k]) or "brak"))
        brak_kan = set(oczek) - {c.get("id") for c in kan}
        if brak_kan:
            bledy.append("V5: kod oczekuje kanarkow, ktorych w pliku NIE MA: %s"
                         % sorted(brak_kan))
        print("V5 — TABLICA ALIASOW: klas %d, aliasow %d, kanarkow odpalonych %d/%d"
              % (len(tab), len(wsz), n_kan, len(oczek)))
        print("     KAN-3 i KAN-4 maja NIE zapalic. Kanarek, ktory tylko potwierdza,")
        print("     ze cos dziala, nie wykrywa zakresu za szerokiego.")
        print("     KAN-6 przeciek ZNANY I ZADEKLAROWANY: liczebnik slowny.")
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
