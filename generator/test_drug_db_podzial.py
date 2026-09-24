#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST PODZIALU DRUG_DB. Zwraca 1, gdy cokolwiek nie przejdzie.

Podzial pliku, ktorego lekarz uzywa przy pacjencie, wolno zrobic tylko wtedy,
gdy da sie UDOWODNIC, ze nic nie zginelo. Test nie wierzy skryptowi dzielacemu
i nie uzywa jego funkcji — zrodlem prawdy jest wersja sprzed podzialu wyjeta
z gita, a nie kopia zostawiona przez generator.

T1  Kazda karta ze zrodla jest w DOKLADNIE JEDNYM pliku klasowym.
T2  Tresc kazdej karty jest identyczna LINIA W LINIE ze zrodlem.
T3  Bilans: N_WEJSCIE = N_ZACHOWANE + N_ODRZUCONE, odrzuconych zero.
T4  Reguly kart sa WYLACZNIE w CORE, a kazdy plik klasowy jawnie sie z nim
    wiaze. Nie ma kopii do rozjechania sie.
T5  Indeks w CORE i karty w plikach zgadzaja sie W OBIE STRONY:
    zadnej karty bez wpisu w indeksie, zadnego wpisu bez karty.
T6  Kazdy plik z indeksu istnieje.
T7  Liczba linii pol (NAZWA_POLA:) jest taka sama jak w zrodle — lapie
    zgubienie pojedynczej linii wewnatrz karty, ktorego T2 by nie zlapal,
    gdyby karta zostala pominieta w calosci razem z naglowkiem.
"""
import os, re, subprocess, sys

PACZKA = os.path.expanduser("~/mnt/psychai-paczka")
PROJEKT = os.path.join(PACZKA, "projekt")
CORE = "DRUG_DB_PSYCHIATRIA_CORE.txt"
bledy = []


def naglowek_karty(l):
    """UWAGA. Ta funkcja jest KOPIA regexa z generatora i wlasnie dlatego nie
    wykryla bledu z 2026-09-24: generator nie dopuszczal ukosnika, test tez
    nie, wiec obaj zgodnie nie widzieli karty KWAS WALPROINOWY / WALPROINIAN.
    Identyczny blad po obu stronach jest niewidzialny. Zostaje do dzielenia
    blokow, ale T0 ponizej sprawdza ja METODA NIEZALEZNA."""
    return bool(re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ][A-ZĄĆĘŁŃÓŚŹŻ0-9 _/.\-]{1,}$', l))


def naglowki_niezaleznie(linie):
    """T0. Inna metoda, celowo nie regex na ksztalt naglowka: naglowek to
    linia BEZ MALYCH LITER, poprzedzona pusta linia, po ktorej w ciagu czterech
    linii pojawia sie linia pola (NAZWA_POLA:). Opiera sie na STRUKTURZE karty,
    nie na tym, jakie znaki wolno miec w nazwie - wiec nie powtorzy bledu
    w doborze znakow."""
    pole = re.compile(r'^[A-ZĄĆĘŁŃÓŚŹŻ_0-9/]+:')
    out = []
    for i, l in enumerate(linie):
        t = l.strip()
        # Warunek "poprzedzona pusta linia" BYL TU I BYL ZLY: SULPIRYD,
        # KLORAZEPAT, CHLORDIAZEPOKSYD i OKSAZEPAM stoja bezposrednio po linii
        # ZRODLO_KARTY poprzedniej karty, bez odstepu. Zdjety.
        # Dwukropek odsiewa tytul pliku ("PSYCH-AI — DRUG DB: ...") - nazwa
        # karty nigdy go nie ma.
        # Naglowek stoi w kolumnie zero. Wciete wypunktowanie pisane wersalikami
        # wewnatrz karty ("  - JEDNOCZESNE STOSOWANIE...") naglowkiem nie jest.
        if l[:1].isspace() or t.startswith("-"):
            continue
        if not t or len(t) < 2 or ":" in t or any(c.islower() for c in t):
            continue
        if any(pole.match(x.strip()) for x in linie[i + 1:i + 5]):
            out.append(l)
    return out


def karty_z(linie):
    idx = [i for i, l in enumerate(linie) if naglowek_karty(l)]
    out = {}
    for n, i in enumerate(idx):
        j = idx[n + 1] if n + 1 < len(idx) else len(linie)
        out[linie[i]] = linie[i:j]
    return out, (linie[:idx[0]] if idx else linie)


def zrodlo_z_gita(rev):
    r = subprocess.run(["git", "-C", PACZKA, "show", "%s:projekt/%s" % (rev, CORE)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout.split("\n")


def main():
    rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    zr = zrodlo_z_gita(rev)
    if zr is None:
        print("FAIL: nie moge wyjac wersji sprzed podzialu z gita (%s)" % rev); return 1
    # T0 — DWIE METODY WYKRYWANIA NAGLOWKOW MUSZA SIE ZGADZAC NA ZRODLE.
    # Bez tego testu regex generatora i regex testu moga miec ten sam blad
    # i zgodnie przeoczyc karte. Tak wlasnie zginela KWAS WALPROINOWY.
    karty_zr, _ = karty_z(zr)
    niez = naglowki_niezaleznie(zr)
    tylko_regex = [x for x in karty_zr if x not in niez]
    tylko_struktura = [x for x in niez if x not in karty_zr]
    print("T0 DWIE METODY na zrodle: regex %d, struktura %d, rozbieznosc %d+%d -> %s"
          % (len(karty_zr), len(niez), len(tylko_regex), len(tylko_struktura),
             "OK" if not tylko_regex and not tylko_struktura else "FAIL"))
    for x in tylko_regex:
        bledy.append("T0 '%s': widzi tylko regex - struktura karty tego nie potwierdza" % x[:40])
    for x in tylko_struktura:
        bledy.append("T0 '%s': widzi tylko struktura - regex naglowka to przeoczyl" % x[:40])
    if len(karty_zr) < 40:
        print("FAIL: wersja %s ma tylko %d kart — to chyba juz plik po podziale, "
              "podaj rewizje sprzed podzialu jako argument" % (rev, len(karty_zr)))
        return 1

    pliki = sorted(f for f in os.listdir(PROJEKT) if f.startswith("DRUG_DB_") and f.endswith(".txt")
                   and f not in (CORE, "DRUG_DB_KARDIOLOGIA_CORE.txt", "DRUG_DB_CIAZA_LAKTACJA.txt"))
    if not pliki:
        print("FAIL: brak plikow klasowych"); return 1

    # T1-T3
    gdzie, preambuly = {}, {}
    for f in pliki:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        k, pre = karty_z(L)
        preambuly[f] = pre
        for nazwa, tresc in k.items():
            if nazwa in gdzie:
                bledy.append("T1 %s: karta w dwoch plikach (%s i %s)" % (nazwa, gdzie[nazwa][0], f))
            gdzie[nazwa] = (f, tresc)

    # ZAKRES TEGO TESTU TO MIGRACJA, NIE BIEZACA ZAWARTOSC PACZKI.
    # Test dowodzi, ze podzial z 2026-09-24 niczego nie zgubil i niczego nie
    # przekrecil. Karty DODANE PO migracji sa poza jego zakresem z definicji -
    # w zrodle migracyjnym ich nie ma i nigdy nie bedzie. Pilnuja ich audyt
    # kompletnosci (R1-R5) i test przypisania klas wobec ATC.
    # Bez tego rozroznienia kazda nowa karta oblewalaby test migracji, a to
    # skonczyloby sie oslabieniem testu zamiast oslabieniem zalozenia.
    brakujace = [n for n in karty_zr if n not in gdzie]
    nadmiarowe = [n for n in gdzie if n not in karty_zr]
    if nadmiarowe:
        print("   PO MIGRACJI dodano %d kart (poza zakresem tego testu): %s"
              % (len(nadmiarowe), ", ".join(sorted(nadmiarowe))))
    nadmiarowe = []
    for n in brakujace:
        bledy.append("T3 %s: karta ze zrodla nie trafila do zadnego pliku" % n)
    for n in nadmiarowe:
        bledy.append("T3 %s: karta, ktorej nie ma w zrodle" % n)
    print("T3 BILANS: N_WEJSCIE %d = N_ZACHOWANE %d + N_ODRZUCONE %d -> %s"
          % (len(karty_zr), len(karty_zr) - len(brakujace), len(brakujace),
             "OK" if not brakujace and not nadmiarowe else "FAIL"))

    # T2
    UZUPELNIONE = {"PALIPERYDON"}   # patrz DOPISANE w T7
    rozne = 0
    for n, tresc_zr in karty_zr.items():
        if n not in gdzie:
            continue
        if gdzie[n][1] != tresc_zr:
            rozne += 1
            a, b = tresc_zr, gdzie[n][1]
            # Karta z jawnej listy uzupelnien moze miec linie DOPISANE, ale zadnej
            # zmienionej ani usunietej: zrodlo musi byc PODCIAGIEM pliku. To wciaz
            # lapie ciche skrocenie karty, a nie blokuje swiadomego uzupelnienia.
            if n in UZUPELNIONE:
                it = iter(b)
                if all(any(x == y for y in it) for x in a):
                    continue
                bledy.append("T2 %s: karta z listy uzupelnien, ale zrodlo NIE JEST "
                             "podciagiem pliku — linie zmieniono albo usunieto" % n)
                continue
            for i in range(max(len(a), len(b))):
                x = a[i] if i < len(a) else "<brak linii>"
                y = b[i] if i < len(b) else "<brak linii>"
                if x != y:
                    bledy.append("T2 %s linia %d: zrodlo %r != plik %r" % (n, i, x[:60], y[:60]))
                    break
    print("T2 TRESC KART: %d roznych z %d" % (rozne, len(karty_zr)))

    # T4
    core_L = open(os.path.join(PROJEKT, CORE), encoding="utf-8").read().split("\n")
    _, pre_core = karty_z(core_L)
    # T4 — ZMIENIONE 2026-09-24 po uwadze Groka. Wczesniej test pilnowal, zeby
    # kopia regul kart byla identyczna w kazdym pliku klasowym. To sprawdzalo
    # generator, a nie to, czy regula jest klinicznie zupelna: git moglby sie
    # zgadzac, a ostrzezenia nigdy nie bylo w zrodle. Teraz regula mieszka
    # WYLACZNIE w CORE, a test pilnuje dwoch rzeczy naraz:
    #   (a) plik klasowy NIE ma wlasnej kopii regul - zadnej do rozjechania,
    #   (b) plik klasowy JAWNIE wiaze sie z CORE, wiec odczyt samej karty bez
    #       regul jest odmowa, a nie czytaniem na wyczucie.
    WIAZANIE = "WIAZANIE: REGULY KART SA W DRUG_DB_PSYCHIATRIA_CORE"
    SLADY_REGUL = ("REGUŁA POLA PRZECIWWSKAZANIA", "REGUŁA POLA ZRODLO_KARTY",
                   "REGUŁA ROZBIEZNOSC_ZRODLOWA", "POLA DODATKOWE")
    for f in pliki:
        naglowek = "\n".join(preambuly[f])
        if WIAZANIE not in naglowek:
            bledy.append("T4 %s: brak jawnego wiazania z CORE - plik klasowy czytany sam "
                         "dawalby karte bez jej regul" % f)
        for slad in SLADY_REGUL:
            if slad in naglowek:
                bledy.append("T4 %s: kopia reguly '%s' w pliku klasowym - regula ma byc "
                             "tylko w CORE" % (f, slad))
    core_naglowek = "\n".join(pre_core)
    for slad in SLADY_REGUL:
        if slad not in core_naglowek:
            bledy.append("T4 CORE: brak reguly '%s' - po usunieciu kopii to jedyne miejsce, "
                         "gdzie moze byc" % slad)
    print("T4 REGULY TYLKO W CORE + wiazanie w %d plikach klasowych: %s"
          % (len(pliki), "OK" if not any(b.startswith("T4") for b in bledy) else "FAIL"))

    # T5, T6
    ind = {}
    w_indeksie = False
    for l in core_L:
        if l.strip().startswith("INDEKS KART"):
            w_indeksie = True; continue
        if l.strip().startswith("SEKCJE KLASOWE"):
            w_indeksie = False; continue
        if w_indeksie and l.strip():
            czesci = l.rsplit(None, 1)
            if len(czesci) == 2:
                ind[czesci[0].strip()] = czesci[1].strip()
    for n in gdzie:
        if n not in ind:
            bledy.append("T5 %s: karta w pliku %s, ale nie ma jej w indeksie CORE" % (n, gdzie[n][0]))
    for n, f in ind.items():
        if n not in gdzie:
            bledy.append("T5 %s: wpis w indeksie bez karty" % n)
        elif gdzie[n][0] != f:
            bledy.append("T5 %s: indeks wskazuje %s, karta lezy w %s" % (n, f, gdzie[n][0]))
        if not os.path.exists(os.path.join(PROJEKT, f)):
            bledy.append("T6 %s: indeks wskazuje nieistniejacy plik %s" % (n, f))
    print("T5 INDEKS <-> KARTY w obie strony: %d wpisow, %d kart -> %s"
          % (len(ind), len(gdzie), "OK" if not any(b.startswith(("T5", "T6")) for b in bledy) else "FAIL"))

    # T7
    pole = re.compile(r'^[A-ZĄĆĘŁŃÓŚŹŻ_0-9/]+:')
    n_zr = sum(1 for l in zr if pole.match(l))
    n_po = 0
    for f in pliki:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        k, _ = karty_z(L)
        for t in k.values():
            n_po += sum(1 for l in t if pole.match(l))
    # T7 liczy TYLKO karty migracyjne, z tego samego powodu co wyzej.
    n_po_migracyjne = 0
    for f in pliki:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        k, _ = karty_z(L)
        for nazwa, t in k.items():
            if nazwa in karty_zr:
                n_po_migracyjne += sum(1 for l in t if pole.match(l))
    n_po = n_po_migracyjne
    n_zr_karty = sum(1 for t in karty_zr.values() for l in t if pole.match(l))
    # CELOWE UZUPELNIENIA kart migracyjnych. T7 ma lapac ZGUBIONA linie, a nie
    # swiadome dopisanie pola. Kazda pozycja to jawny dlug: ile linii dopisano
    # i dlaczego. Bez tej tabeli jedyne wyjscie to wylaczenie T7 dla calej karty,
    # co skasowaloby ochrone reszty jej pol.
    DOPISANE = {"PALIPERYDON": (5, "brakowalo T1_2, METABOLIZM, INTERAKCJE i MONITORING "
                                   "w karcie depot — audyt kart z 2026-09-24")}
    delta = sum(n for n, _ in DOPISANE.values())
    if n_zr_karty + delta != n_po:
        bledy.append("T7: linii pol w kartach zrodla %d (+%d celowo), po podziale %d"
                     % (n_zr_karty, delta, n_po))
    print("T7 LINIE POL w kartach: zrodlo %d + celowo %d = %d, po podziale %d -> %s"
          % (n_zr_karty, delta, n_zr_karty + delta, n_po,
             "OK" if n_zr_karty + delta == n_po else "FAIL"))
    for k, (n_, po) in sorted(DOPISANE.items()):
        print("   CELOWO %s +%d: %s" % (k, n_, po))
    print("   (w calym zrodle z preambula: %d)" % n_zr)

    print()
    if bledy:
        print("BLEDOW: %d" % len(bledy))
        for b in bledy[:40]:
            print("  ", b)
        print("TEST PODZIALU: NIE PRZESZEDL")
        return 1
    print("TEST PODZIALU: PRZESZEDL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
