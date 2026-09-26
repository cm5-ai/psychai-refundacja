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

# SCIEZKA DO PACZKI — trzy proby, w tej kolejnosci, bez zgadywania.
# 1. PSYCHAI_PACZKA z otoczenia (CI podaje ja jawnie),
# 2. ~/mnt/psychai-paczka (ta maszyna),
# 3. katalog siostrzany obok tego repo (uklad checkoutu w CI).
# Powod: zaszyta sciezka tej maszyny sprawiala, ze audyt i testy NIE DALY SIE
# uruchomic nigdzie indziej. Narzedzie, ktorego nie da sie odpalic w CI, jest
# narzedziem, ktore chodzi tylko wtedy, gdy ktos pamieta.
def _paczka():
    k = os.environ.get("PSYCHAI_PACZKA")
    if k and os.path.isdir(k):
        return k
    for p in (os.path.expanduser("~/mnt/psychai-paczka"),
              os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "..", "psychai-paczka")):
        if os.path.isdir(p):
            return os.path.normpath(p)
    raise SystemExit("FAIL: nie znajduje paczki. Ustaw PSYCHAI_PACZKA "
                     "albo umiesc psychai-paczka obok tego repo.")


PACZKA = _paczka()
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


# Rewizja paczki SPRZED podzialu DRUG_DB na pliki klasowe — jedyne zrodlo prawdy
# dla tego testu. Podzial zrobil commit 683d132; 458b5ab to jego rodzic.
# Domyslne "HEAD" bylo pulapka: na dzisiejszym HEAD plik jest juz PO podziale,
# wiec test konczyl sie FAILEM, ktory znaczyl "zle uruchomiles", a wygladal
# jak "paczka zepsuta". Argument nadal nadpisuje stala.
REV_PRZED_PODZIALEM = "458b5ab"


def zrodlo_z_gita(rev):
    r = subprocess.run(["git", "-C", PACZKA, "show", "%s:projekt/%s" % (rev, CORE)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return r.stdout.split("\n")


def main():
    rev = sys.argv[1] if len(sys.argv) > 1 else REV_PRZED_PODZIALEM
    zr = zrodlo_z_gita(rev)
    if zr is None:
        print("FAIL: nie moge wyjac wersji sprzed podzialu z gita (%s)" % rev); return 1
    # Bez T0 regex generatora i regex testu moga miec ten sam blad i zgodnie
    # przeoczyc karte. Tak wlasnie zginela KWAS WALPROINOWY.
    karty_zr, _ = karty_z(zr)
    niez = naglowki_niezaleznie(zr)
    # BRAMKA WEJSCIA PRZED T0. Zgodnie z 3B regula bez wejscia jest znaleziskiem,
    # a nie wynikiem OK: na pliku PO podziale obie metody widza zero naglowkow,
    # zgadzaja sie ze soba i T0 drukowal "OK" na pustym zbiorze. Dlatego liczbe
    # kart sprawdzamy PRZED T0, a nie po nim.
    if len(karty_zr) < 40 or len(niez) < 40:
        print("FAIL: wersja %s ma %d kart (regex) i %d naglowkow (struktura) — to nie jest "
              "wersja sprzed podzialu; T0 nie zostal uruchomiony na pustym wejsciu"
              % (rev, len(karty_zr), len(niez)))
        return 1
    # T0 — DWIE METODY WYKRYWANIA NAGLOWKOW MUSZA SIE ZGADZAC NA ZRODLE.
    tylko_regex = [x for x in karty_zr if x not in niez]
    tylko_struktura = [x for x in niez if x not in karty_zr]
    print("T0 DWIE METODY na zrodle: N_WEJSCIE regex %d, struktura %d, rozbieznosc %d+%d -> %s"
          % (len(karty_zr), len(niez), len(tylko_regex), len(tylko_struktura),
             "OK" if not tylko_regex and not tylko_struktura else "FAIL"))
    for x in tylko_regex:
        bledy.append("T0 '%s': widzi tylko regex - struktura karty tego nie potwierdza" % x[:40])
    for x in tylko_struktura:
        bledy.append("T0 '%s': widzi tylko struktura - regex naglowka to przeoczyl" % x[:40])

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
    # NAGLOWKI SEKCJI PRZEMIANOWANE PO MIGRACJI. Zmiana nazwy sekcji nie jest
    # zgubieniem karty, ale T3 nie ma jak tego odroznic — lista jest jawna
    # i podaje, na co sekcja zostala rozbita, zeby nie dalo sie tu ukryc
    # zniknietej karty leku.
    PRZEMIANOWANE = {"BENZODIAZEPINY / NASENNE":
                     ["BENZODIAZEPINY", "LEKI Z / NASENNE NIEBENZODIAZEPINOWE",
                      "ANKSJOLITYKI I NASENNE NIE-BZD"],
                     "STABILIZATORY / PRZECIWDRGAWKOWE":
                     ["STABILIZATORY NASTROJU", "GABAPENTYNOIDY",
                      "PRZECIWPADACZKOWE W UZYCIU PSYCHIATRYCZNYM"]}
    for stara, nowe in PRZEMIANOWANE.items():
        brak_nowych = [x for x in nowe if x not in gdzie]
        if brak_nowych:
            bledy.append("T3 %s: przemianowana na %s, ale w plikach nie ma: %s"
                         % (stara, ", ".join(nowe), ", ".join(brak_nowych)))
        else:
            print("   PRZEMIANOWANO sekcje %s -> %s" % (stara, ", ".join(nowe)))
    brakujace = [n for n in karty_zr if n not in gdzie and n not in PRZEMIANOWANE]
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
    # LINIE PRZEPISANE, nie dopisane. Dopisanie jest bezpieczne, przepisanie nie:
    # stara linia POSTAC w tych trzech kartach mowila "dawek postaci iniekcyjnych
    # NIE MA w paczce", co po dodaniu dawek depot bylo juz nieprawda i karta
    # przeczylaby sama sobie. Kazda pozycja = ile linii zrodla znika i dlaczego.
    PRZEPISANE = {"ARYPIPRAZOL": (1, "POSTAC: 'dawek NIE MA' -> wskazanie na dawke depot w karcie"),
                  "OLANZAPINA": (1, "POSTAC: jw., plus odeslanie do NIEPEWNY_ODCZYT_ZRODLA"),
                  "RISPERIDON": (1, "POSTAC: jw., dla obu postaci depot"),
                  # rev.47: przeliczniki intra-lek przeniesione z 18 do kart,
                  # tabela rownowaznosci depotow zostawiona w 18 jako JEDEN byt
                  "FLUPENTYKSOL": (1, "'PRZELICZNIK ... patrz 18' -> wlasciwy przelicznik w karcie plus odeslanie do tabeli rownowaznosci"),
                  "ZUKLOPENTYKSOL": (1, "DAWKA_ROWNOWAZNA: kopia tabeli rownowaznosci usunieta, zostaje odeslanie i czesc wlasna zuklopentyksolu")}
    UZUPELNIONE = set(["PALIPERYDON", "FLUPENTYKSOL", "TIAPRYD", "METADON",
                       "ESTAZOLAM", "BROMAZEPAM", "ARYPIPRAZOL", "OLANZAPINA",
                       "RISPERIDON", "HALOPERIDOL", "ZUKLOPENTYKSOL"])   # patrz DOPISANE w T7
    # NORMALIZACJE PISOWNI POLA — DANA, NIE DOMYSL PARSERA [2026-09-25].
    # rev48 ("jedno pole przestaje miec dwie pisownie") celowo ujednolicila
    # nazwy pol w plikach klasowych. Zrodlo T2 jest ZAMROZONE na commicie
    # sprzed podzialu, wiec od tamtej pory rozni sie od plikow w kazdej
    # karcie, ktora te pisownie niosla — i T2 oblewal w CI przez 52 commity
    # na tych samych czterech kartach. Kontrola czerwona od 52 commitow nie
    # jest kontrola: uczy kasowania maila.
    # NIE ROZLUZNIAM T2. Podstawiam WYLACZNIE te pary, ktore rev48 zmieniala,
    # i licze, ile razy kazda byla potrzebna. Para nieuzyta ani razu jest
    # martwym wylaczeniem i ma to byc widac.
    NORMALIZACJE = [("CIAZA:", "CIĄŻA:")]
    uzyte = dict((a, 0) for a, _ in NORMALIZACJE)

    def znormalizuj(linia):
        for a, b in NORMALIZACJE:
            if linia.startswith(a):
                uzyte[a] += 1
                return b + linia[len(a):]
        return linia

    # ---------------------------------------------------------------------
    # LINIE POSTAWIONE PRZEZ NARZEDZIE, NIE RECZNIE [R16, 2026-09-26].
    #
    # Do dzis kazde swiadome uzupelnienie karty bylo wpisywane RECZNIE do
    # UZUPELNIONE i DOPISANE. To dzialalo, dopoki uzupelnien bylo
    # kilkanascie. narzedzia/przenies_pola_chpl.py dopisal 78 pol i wypelnil
    # 33 — enumeracja kart urosla by do setek pozycji i przestalaby byc
    # czytana, czyli przestalaby cokolwiek chronic.
    #
    # Dlatego linia narzedziowa jest rozpoznawana PO KSZTALCIE, nie po
    # nazwie karty. Kazda taka linia niesie stempel [ChPL <punkt> ...,
    # <data>] postawiony przez przenosnik i nazwe pola z jawnej listy.
    # CO TO NADAL LAPIE: ciche usuniecie albo skrocenie linii zrodlowej —
    # zrodlo musi byc PODCIAGIEM pliku po odjeciu linii narzedziowych,
    # a linia zrodlowa z BRAK DANYCH LOKALNYCH moze zniknac WYLACZNIE
    # wtedy, gdy w jej miejscu stoi to samo pole ze stemplem ChPL.
    # CZEGO NIE LAPIE: czy tresc ze stempla jest wlasciwa. To jest zadanie
    # przenios_pola_chpl.py i jego samotestu, nie tego testu.
    import re as _re
    STEMPEL = _re.compile(r"\[ChPL [^\]]*\d{4}-\d{2}-\d{2}\]\s*$")
    POLE_NAR = _re.compile(r"^([A-ZĄĆĘŁŃÓŚŹŻ_0-9]+):\s")

    def _narzedziowa(linia):
        return bool(STEMPEL.search(linia) and POLE_NAR.match(linia))

    def _pole(linia):
        m = POLE_NAR.match(linia)
        return m.group(1) if m else None

    n_dopisanych = n_wypelnionych = 0

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
            # --- SCIEZKA NARZEDZIOWA
            b_bez = [x for x in b if not _narzedziowa(x)]
            dopisane_tu = len(b) - len(b_bez)
            pola_ze_stemplem = {_pole(x) for x in b if _narzedziowa(x)}
            # linie zrodla, ktore zniknely, a ich pole stoi teraz ze stemplem
            # I mowily BRAK DANYCH LOKALNYCH — czyli wypelnione, nie usuniete
            # NORMALIZACJA REV48 OBOWIAZUJE TAKZE TUTAJ. Pierwsza wersja tej
            # sciezki jej nie uzyla i AGOMELATYNA oblewala przez jedna linie
            # "CIAZA:" kontra "CIĄŻA:" — ta sama para, ktora 52 commity temu
            # trzymala CI na czerwono. Jedna normalizacja, wszystkie sciezki.
            zniklo_zr = [x for x in tresc_zr
                         if x not in b_bez and znormalizuj(x) not in b_bez]
            wypelnione = [x for x in zniklo_zr
                          if "BRAK DANYCH LOKALNYCH" in x and _pole(x) in pola_ze_stemplem]
            reszta = [x for x in zniklo_zr if x not in wypelnione]
            if (dopisane_tu or wypelnione) and not reszta:
                it = iter(b_bez)
                a_bez = [x for x in tresc_zr if x not in wypelnione]
                if all(any(x == y or znormalizuj(x) == y for y in it) for x in a_bez):
                    n_dopisanych += dopisane_tu
                    n_wypelnionych += len(wypelnione)
                    continue
            if n in UZUPELNIONE:
                it = iter(b)
                if all(any(x == y for y in it) for x in a):
                    continue
                # Karta z listy PRZEPISANE ma jawnie zadeklarowana liczbe linii
                # ZMIENIONYCH. Sprawdzamy, ile linii zrodla zniknelo z pliku:
                # wiecej niz zadeklarowano = ciche usuniecie, i to jest blad.
                # LINIE WYPELNIONE PRZEZ NARZEDZIE NIE SA "ZNIKNIETE".
                # ARYPIPRAZOL i RISPERIDON maja zadeklarowana JEDNA linie
                # przepisana recznie (POSTAC). Po wypelnieniu ich
                # PRZECIWWSKAZANIA przez przenosnik licznik pokazywal 2
                # i test oblewal — czyli liczyl razem zmiane reczna
                # i narzedziowa, ktore maja rozne dowody.
                zniklo = [x for x in a if x not in b and znormalizuj(x) not in b
                          and not ("BRAK DANYCH LOKALNYCH" in x
                                   and _pole(x) in {_pole(y) for y in b if _narzedziowa(y)})]
                ile, powod = PRZEPISANE.get(n, (0, ""))
                if len(zniklo) == ile:
                    continue
                bledy.append("T2 %s: zrodlo nie jest podciagiem pliku; zniklo %d linii, "
                             "zadeklarowano %d (%s)" % (n, len(zniklo), ile, powod))
                for x in zniklo[:3]:
                    bledy.append("      ZNIKLO: %s" % x[:90])
                continue
            for i in range(max(len(a), len(b))):
                x = a[i] if i < len(a) else "<brak linii>"
                y = b[i] if i < len(b) else "<brak linii>"
                if x != y and znormalizuj(x) != y:
                    bledy.append("T2 %s linia %d: zrodlo %r != plik %r" % (n, i, x[:60], y[:60]))
                    break
    print("T2 TRESC KART: %d roznych z %d" % (rozne, len(karty_zr)))
    print("   T2 linie narzedziowe ze stemplem ChPL: %d dopisanych, %d wypelnionych "
          "z BRAK DANYCH LOKALNYCH" % (n_dopisanych, n_wypelnionych))
    if not (n_dopisanych or n_wypelnionych):
        bledy.append("T2: regula linii narzedziowej nie objela ANI JEDNEJ linii — "
                     "martwa regula wycisza cos, czego juz nie ma, albo stempel "
                     "przestal pasowac; w obu przypadkach nie chroni")
    for a, b in NORMALIZACJE:
        if uzyte[a]:
            print("   T2 normalizacja %r -> %r uzyta %d razy [rev48]" % (a, b, uzyte[a]))
        else:
            bledy.append("T2 normalizacja %r -> %r NIE BYLA POTRZEBNA ani razu — "
                         "martwe wylaczenie, zapis o swiecie sprzed poprawki" % (a, b))

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
    # LINIE NARZEDZIOWE ODEJMUJEMY OD BILANSU T7 I RAPORTUJEMY OSOBNO.
    # DOPISANE zostaje dla uzupelnien RECZNYCH — kazde z wlasnym powodem.
    # Zlanie obu w jeden licznik znaczyloby, ze zgubiona linia moze sie
    # schowac za dopisana przez narzedzie.
    n_narzedziowych = 0
    for f in pliki:
        L = open(os.path.join(PROJEKT, f), encoding="utf-8").read().split("\n")
        k, _ = karty_z(L)
        for nazwa, t in k.items():
            if nazwa not in karty_zr:
                continue
            # ODEJMUJEMY WYLACZNIE POLA DOPISANE, NIE PRZEPISANE.
            # Linia PRZECIWWSKAZANIA istniala w zrodle jako BRAK DANYCH
            # LOKALNYCH; przenosnik zmienil jej TRESC, nie dolozyl pola.
            # Pierwsza wersja odejmowala ja tez i bilans spadl o 33 —
            # test zglaszal ubytek tam, gdzie nic nie ubylo.
            pola_zr = {_pole(l) for l in karty_zr[nazwa] if pole.match(l)}
            n_narzedziowych += sum(1 for l in t
                                   if _narzedziowa(l) and _pole(l) not in pola_zr)
    n_po = n_po_migracyjne - n_narzedziowych
    print("T7 linie narzedziowe (stempel ChPL) odjete od bilansu: %d" % n_narzedziowych)
    n_zr_karty = sum(1 for t in karty_zr.values() for l in t if pole.match(l))
    # CELOWE UZUPELNIENIA kart migracyjnych. T7 ma lapac ZGUBIONA linie, a nie
    # swiadome dopisanie pola. Kazda pozycja to jawny dlug: ile linii dopisano
    # i dlaczego. Bez tej tabeli jedyne wyjscie to wylaczenie T7 dla calej karty,
    # co skasowaloby ochrone reszty jej pol.
    DOPISANE = {"PALIPERYDON": (8, "brakowalo T1_2, METABOLIZM, INTERAKCJE i MONITORING "
                                   "w karcie depot, oraz CIĄŻA i KP — audyt kart z 2026-09-24. "
                                   "+1 od 2026-09-26: NIEPEWNY_ODCZYT_ZRODLA dla Denepry — szesc "
                                   "dokumentow ChPL (25/50/75/100/150 mg) pod jedna nazwa, "
                                   "wycofane DAWKA_STARSI i DAWKA_DZIECI wg R20-2"),
                "FLUPENTYKSOL": (2, "CIĄŻA i KP — nie bylo ich ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "TIAPRYD": (1, "KP — nie bylo go ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "METADON": (2, "CIĄŻA i KP — nie bylo ich ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "ESTAZOLAM": (1, "KP — nie bylo go ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "BROMAZEPAM": (1, "KP — nie bylo go ani w karcie, ani w DRUG_DB_CIAZA_LAKTACJA"),
                "ARYPIPRAZOL": (1, "dawki depot Abilify Maintena miesieczne i dwumiesieczne; ROZBIEZNOSC_ZRODLOWA: wpis w cache jest starsza wersja dokumentu"),
                "OLANZAPINA": (3, "dawka depot Zypadhera z zespolem poiniekcyjnym, dawka iniekcji doraznej; NIEPEWNY_ODCZYT_ZRODLA dla Tabeli 1 i ROZBIEZNOSC_ZRODLOWA dla wpisow Zyprexy. +1 od 2026-09-26: pola DAWKA_DEPOT i DAWKA_INIEKCJA_DORAZNA wpisane po POTWIERDZENIU PRZEZ LEKARZA wobec nazwanych dokumentow (.github/potwierdzenia_lekarza.tsv); to sa dopisania RECZNE, nie narzedziowe — nie niosa stempla [ChPL ...] i maja byc liczone tutaj"),
                "BUPRENORFINA": (1, "DAWKA_DEPOT Buvidal: cztery wiersze Tabeli 1 potwierdzone przez lekarza 2026-09-26 wobec annexu z 2018; wiersz 26-32 mg pozostaje zablokowany"),
                "RISPERIDON": (0, "dawki depot Rispolept Consta i Okedi — linie bez naglowka pola"),
                "PALIPERYDON_LAI": (1, "Trevicta i BYANNLI: ODSTEPY_ZMIANA_LECZENIA; liczone w pozycji PALIPERYDON"),
                "HALOPERIDOL": (2, "DAWKA_ROWNOWAZNA: odeslanie do tabeli rownowaznosci w 18; DAWKA depot przeniesiona z 18 nie jest linia pola. +1 od 2026-09-26: NIEPEWNY_ODCZYT_ZRODLA dla Haloperidolu WZF — pod ta nazwa leza dwa dokumenty ChPL (tabletka 1 mg i iniekcja 5 mg/ml), galaz PRZECIWWSKAZANIA wycofana wg R20-2"),
                "LORAZEPAM": (1, "NIEPEWNY_ODCZYT_ZRODLA dla Lorabexu — trzy dokumenty pod jedna nazwa (0,5 mg tabl., 2 mg/ml i 4 mg/ml inj.); wycofane DAWKA_STARSI, DAWKA_DZIECI, PRZECIWWSKAZANIA wg R20-2"),
                "KLONAZEPAM": (1, "NIEPEWNY_ODCZYT_ZRODLA dla Clonazepamum TZF — tabletka 0,5 mg i iniekcja 1 mg/ml pod jedna nazwa; wycofane DAWKA_STARSI i PRZECIWWSKAZANIA wg R20-2"),
                "DIAZEPAM": (1, "NIEPEWNY_ODCZYT_ZRODLA dla Neorelium — tabletka 5 mg i iniekcja 5 mg/ml pod jedna nazwa; to ten przypadek, ktory ujawnil cala klase (R20)"),
                "FLUPENTYKSOL_ROWNOWAZNA": (1, "DAWKA_ROWNOWAZNA: odeslanie do tabeli rownowaznosci w 18; liczone osobno od CIĄŻA i KP")}
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
