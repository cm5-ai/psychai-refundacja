#!/usr/bin/env python3
"""Budowa CHPL_CACHE: jeden plik JSON na substancje, commitowany do repo.
Runtime czyta pojedynczy plik z raw.githubusercontent.com - nie caly cache.
Uzycie: python3 generator/chpl_cache.py --lista zrodla/chpl_cache_lista.txt [--tylko lek1,lek2] [--punkty 4.1,4.2,4.3,4.4,4.5,4.6,4.8,5.2]"""
import hashlib
import json, re, os, sys, subprocess, tempfile, argparse, unicodedata, hashlib, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import polityka
import dobor

KATALOG = "chpl"
DZIS = datetime.date.today().isoformat()
LIMIT_ZNAKOW = 200000        # praktycznie bez limitu. Przy 6000 ucinalo klozapinie 4.2/4.4/4.5/4.8,
                             # przy 20000 nadal ucinalo klozapinie 4.4 (rozrost 5,2 MB -> ok. 5,4 MB)
                             # i metadonowi 4.2 - czyli progi przerwania i dawkowanie.
# ZAKRES LIMITU, ZAPISANY WPROST [R83, 2026-10-05].
# MAX_PRODUKTOW NIE JEST KWOTA PACZKI. Jest limitem PROBKOWANIA przy budowie
# cache OD ZERA: ile produktow narzedzie samo wybierze, gdy nikt mu nie wskazal
# konkretnych. Dokument DOSTARCZONY i PRZYPISANY (lekarz pobral go przegladarka,
# sha256 policzone, adres z rejestru znany) wchodzi INNYM KANALEM i limitu nie
# dotyczy — bo limit nie mowi "do bazy wolno wziac trzy", tylko "probkujac,
# wez trzy".
# To rozdzielenie istnialo od 2026-09-24 w rekordzie paliperydonu ("Limit 3
# produktow na substancje ich NIE obejmuje - byly poza cache em"), ale nie bylo
# zapisane TUTAJ, wiec za kazdym razem wygladalo na obejscie wlasnej reguly.
# ZAKRES LIMITU rozstrzygnieto zbieznie. GPT: "limit 3 dotyczy probkowania, a
# kazdy poprawnie przypisany dokument dostarczony przez lekarza wchodzi do cache
# z proweniencja". Grok: "MAX_PRODUKTOW = 3 jest limitem probnika glownej
# przebudowy, nie kwota paczki (...) o ile niesie proweniencje i idzie
# przenosnikiem, a nie recznym wrzutem".
#
# MIEJSCE IMPORTU rozstrzygnieto OSOBNO I NIE OD RAZU. Pierwsze odpowiedzi szly
# w rozne strony: GPT "osobny skrypt utrwalalby druga sciezke" (czyli glowna
# sciezka), Grok "C. B do cache" (czyli piaty dolacz_*.py). Przez jeden dzien
# stalo tu zdanie, ze powiedzieli to samo - nie powiedzieli, i to byl moj blad,
# nie ich. Zapytani ponownie, z policzonym faktem, ze skryptow dolacz_*.py jest
# juz cztery i kazdy wola ten sam deterministyczny kanal postacie.py, obaj
# odpowiedzieli GLOWNA. GPT: "dla kolejnych partii dokumentow wybieram jeden
# jawny tryb importu zamiast piatego skryptu". Grok: "--import-lokalny w
# chpl_cache.py nic nie psuje, dopoki nie podnosi MAX_PRODUKTOW i nie wchodzi w
# przebudowe, ktora bierze trzy produkty".
# DLATEGO IMPORT JEST TUTAJ, w glownej sciezce, a nie w nowym dolacz_*.py.
MAX_PRODUKTOW = 3            # probkowanie przy budowie od zera; patrz --import-lokalny


def norm(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (("z", "s"), ("qu", "kw"), ("ph", "f"), ("th", "t"), ("x", "ks"), ("v", "w"), ("y", "i"), ("c", "k")):
        s = s.replace(a, b)
    return s


def szkielet(s):
    return re.sub(r'[^bcdfghjklmnpqrstvwxz]', '', norm(s))


def slowa(s):
    return [w for w in re.split(r'[^a-z0-9]+', norm(s)) if w]


def zaczyna_sie(tekst, rdzen):
    """Dopasowanie TYLKO od poczatku slowa. Podciag w srodku dawal
    imipramina -> Clomipramini (Anafranil) i fluoksetyna -> Ginkgo folii."""
    return any(szkielet(w).startswith(rdzen) for w in slowa(tekst))


SYNONIMY = {"walproinian": ["valproicum", "valproas"], "kwas walproinowy": ["valproicum"],
            "lit": ["lithii", "lithium"], "weglan litu": ["lithii carbonas"]}


def dopasuj(zapyt, produkty):
    """Pusta lista = NIE ZNALEZIONO. To nie znaczy, ze produktu nie ma."""
    trafy, widziane = [], set()
    q = szkielet(zapyt)[:5]
    if len(q) >= 4:
        for p in produkty:
            if zaczyna_sie(p.get("substancja", "") + " " + p.get("nazwa", ""), q):
                if id(p) not in widziane:
                    widziane.add(id(p)); trafy.append(p)
    for syn in SYNONIMY.get(zapyt.lower().strip(), []):
        qs = norm(syn)[:6]                 # synonim lacinski: prefiks doslowny, nie szkielet
        for p in produkty:
            if any(w.startswith(qs) for w in slowa(p.get("substancja", "") + " " + p.get("nazwa", ""))):
                if id(p) not in widziane:
                    widziane.add(id(p)); trafy.append(p)
    return trafy


def pdf_tekst(url):
    """Zwraca (tekst, sha256_pdf) albo (None, powod)."""
    if not url:
        return None, "BRAK URL ChPL W SPISIE"
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "a.pdf")
        r = subprocess.run(["curl", "-sSfL", "--retry", "3", "-m", "120", "-o", p, url])
        if r.returncode:
            return None, f"BLAD POBRANIA (curl {r.returncode})"
        if os.path.getsize(p) < 1000:
            return None, "PLIK ZA MALY - to nie jest ChPL"
        sha = hashlib.sha256(open(p, "rb").read()).hexdigest()
        r2 = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True)
        if r2.returncode:
            return None, "BLAD pdftotext"
        return (r2.stdout.decode("utf-8", "replace"), sha)


def punkty(t, chce):
    """Zwraca {punkt: {"tekst":..., "uciety":bool, "dlugosc_zrodla":int}}.
    Uciecie MUSI byc jawne: punkt uciety w polowie wyglada jak kompletny,
    a to w nim siedza progi przerwania leczenia i schematy dawkowania."""
    t = " ".join(t.split())
    ms = list(re.finditer(r'(?<![\d.])([45])\.(\d{1,2})\.?\s+(?=[A-ZŁŚŻŹĆŃÓĘĄ])', t))
    out = {}
    for i, m in enumerate(ms):
        k = f"{m.group(1)}.{m.group(2)}"
        if k not in chce or k in out:
            continue
        pelny = t[m.start(): ms[i + 1].start() if i + 1 < len(ms) else len(t)]
        out[k] = {"tekst": pelny[:LIMIT_ZNAKOW], "uciety": len(pelny) > LIMIT_ZNAKOW,
                  "dlugosc_zrodla": len(pelny)}
    return out


def plik_nazwy(s):
    """Nazwa pliku STABILNA: tylko bez znakow diakrytycznych i malymi literami.
    NIE uzywa norm() - norm() sluzy do dopasowania i jego zmiana (np. z->s)
    przemianowywala pliki, zostawiajac w repo sieroty ze starymi danymi."""
    b = unicodedata.normalize('NFKD', s.lower())
    b = ''.join(c for c in b if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', b).strip('_')


# ---------------------------------------------------------------------------
# IMPORT DOKUMENTOW LOKALNYCH [R83, 2026-10-05].
#
# WEJSCIE: manifest TSV, kolumny
#   substancja, pozwolenie, id_rejestru, id_rpl, naglowek, sha256, plik, adres
# Plik lezy w katalogu dokumentow (domyslnie psychai-paczka/_zrodla_lokalne/chpl).
#
# CO SPRAWDZA, ZANIM COKOLWIEK DOPISZE — kazdy warunek osobno, kazdy z powodem:
#   1. plik istnieje,
#   2. sha256 BAJTOW rowne sha z manifestu (nie przepisane z manifestu — liczone),
#   3. adres z manifestu niesie to samo id_rpl co kolumna id_rpl,
#   4. punkty daja sie odczytac (chpl_z_pdf), a 4.2 nie jest pusty,
#   5. tej pary (sha256, pozwolenie) jeszcze w rekordzie nie ma.
# Warunek niespelniony -> pozycja ODRZUCONA z powodem. Bilans par. 3B.
#
# CZEGO NIE ROBI: nie promuje niczego do pliku wizyty ani do gabinetu. To jest
# osobna decyzja i osobny pomiar — obaj recenzenci powiedzieli to niezaleznie,
# GPT: "import do cache oddzielic od promocji do gabinetu", Grok: "do pliku
# wizyty nie wchodza".
def _spis_wg_id(spis):
    """Eksport RPL zaindeksowany po id rejestracji. Klucz deterministyczny.

    NIE po pozwoleniu: rejestracje centralne EU maja pole 'pozwolenie' PUSTE
    (zmierzone na RPL_PSYCH.json: 2693 produkty, 2161 roznych pozwolen, jedyna
    wartosc powtorzona to pusty napis). Pusty napis jako klucz sklejalby setki
    roznych produktow w jeden. Pole 'id' jest unikalne i to ono jest kluczem.
    """
    d = json.load(open(spis, encoding="utf-8"))["produkty"]
    wg = {}
    for p in d:
        i = str(p.get("id") or "")
        if not i:
            continue
        if i in wg:
            raise ValueError("EKSPORT RPL: id %s wystepuje dwa razy. "
                             "Klucz przestal byc kluczem - nie scalam." % i)
        wg[i] = p
    return wg


def import_lokalny(manifest, katalog_dokumentow, spis, zapisz=False):
    """Dopisanie do cache'u dokumentow JUZ POBRANYCH I PRZYPISANYCH.

    CO TO JEST. Kanal poza probnikiem glownej przebudowy. MAX_PRODUKTOW
    ogranicza, ile produktow narzedzie WYBIERZE SAMO, gdy nikt mu nie wskazal
    konkretnych; dokument wskazany, pobrany i przypisany nie jest probka.
    Rozstrzygniete zbieznie 2026-10-05: obaj recenzenci odpowiedzieli GLOWNA
    (import w tym pliku), nie piaty skrypt dolacz_*.py.

    SKAD BIORA SIE POLA REKORDU — i to jest poprawka bledu z 2026-10-04.
    Pierwsza wersja tej funkcji skladala nazwe, moc i postac z kolumny
    'naglowek' manifestu i nie dawala wcale DROGI, UWALNIANIA, EKSPOZYCJI,
    podmiotu ani klucz_rpl. Audyt R6 zglosil 92 znaleziska: wpis udajacy
    komplet. Teraz:
      nazwa, moc, postac, podmiot, atc, nazwa_powszechna
                       <- EKSPORT RPL, po kluczu id rejestracji (rownosc)
      DROGA, UWALNIANIE <- postacie.postac_klasa(postac): ROWNOSC NAPISU ze
                           slownikiem postaci. Napis spoza slownika rzuca
                           wyjatkiem i pozycja jest ODRZUCONA, nie zgadnieta.
      EKSPOZYCJA        <- postacie.ekspozycja(): ChPL albo tabela wyjatkow.
    Zakaz, ktory to realizuje, obaj recenzenci postawili tak samo. Grok:
    "DROGA, EKSPOZYCJA i UWALNIANIE nie wolno wyprowadzac parserem z postaci -
    to wzorzec, nie klucz". GPT: "sama postac i ATC nie dowodza wszystkich
    trzech; brak wymaganej wartosci oznacza dokument zachowany jako
    zweryfikowane zrodlo, ale poza rekordami cache ze statusem OK".

    TRESC PUNKTOW STOI PRZY PRODUKCIE, W CALOSCI. Rozwazalem scalanie: jedna
    kanoniczna tresc na sha256 kanonu punktu plus odsylacz przy produkcie.
    ZMIERZONE na kwetiapinie, obie wersje z tej samej danej: pelna tresc 5 320 865 B
    surowo i 1 923 105 B jako obiekt gita, scalona 1 934 703 B i 605 609 B; 95
    generykow niesie 21-31 roznych tresci kazdego punktu, nie 95. Zysk realny,
    ekstrapolacja na 1019 dokumentow to +21 MB w .git wobec +6,6 MB.
    ODRZUCONE MIMO TO, zbieznie. Scalanie wymagaloby zmiany kontraktu odczytu
    w 24 miejscach osmiu modulow paczki, a wsrod nich sa chpl_layer.py i
    generator_wizyty.py - droga, ktora dawka idzie do pliku wizyty i dalej do
    lekarza przy pacjencie - oraz kontrola_etykiet.py, ktora z zasady nie
    importuje generatora i musialaby dostac DRUGI resolver. Grok: "liczba podana
    lekarzowi ma stac w TRESCI, ktora czyta droga dawki, a nie w odsylaczu,
    ktorego brak czyta sie jako pustke albo wyjatek; oszczednosc dysku nie jest
    zrodlem i nie zmienia tego kontraktu". GPT: "rozstrzyga wymog dowiedzionego
    zrodla i pinu na drodze dawki: sama oszczednosc dysku, bez wykazanej potrzeby
    operacyjnej, nie uzasadnia dokladania nowego trybu awarii do tej drogi".
    Megabajty nie sa powodem, zeby dolozyc drodze dawki tryb awarii, ktorego
    dzis nie ma.

    CZEGO TA FUNKCJA NIE ROBI. Nie promuje niczego do pliku wizyty ani do
    gabinetu i nie udaje, ze to zrobila. Po imporcie cache wie o dokumencie,
    a plik wizyty jeszcze nie - i bramka 'kontrola etykiet' MA to pokazac na
    czerwono. Grok: "zielen znaczylaby, ze plik wizyty juz widzi dokument".
    """
    _kat = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _kat)
    sys.path.insert(0, os.path.join(_kat, "..", "slownik"))
    import chpl_z_pdf
    import postacie as PO

    rpl = _spis_wg_id(spis)
    we, zach, odrz = 0, [], []
    wg_substancji = {}

    for linia in open(manifest, encoding="utf-8"):
        if not linia.strip() or linia.lstrip().startswith("#"):
            continue
        c = linia.rstrip("\n").split("\t")
        if len(c) < 8:
            odrz.append((linia.strip()[:40], "wiersz ma %d kolumn, potrzeba 8" % len(c)))
            continue
        sub, poz, id_rej, id_rpl, nag, sha_dekl, plik, adres = [x.strip() for x in c[:8]]
        we += 1
        ident = "%s|%s" % (sub, id_rej)

        # 1. bajty sa
        sc = os.path.join(katalog_dokumentow, plik)
        if not os.path.exists(sc):
            odrz.append((ident, "pliku nie ma: %s" % plik)); continue

        # 2. bajty sa TE bajty — sha liczone, nie przepisane z manifestu
        sha = hashlib.sha256(open(sc, "rb").read()).hexdigest()
        if sha != sha_dekl:
            odrz.append((ident, "sha256 bajtow %s != manifest %s"
                         % (sha[:12], sha_dekl[:12]))); continue

        # 3. adres niesie ten sam identyfikator, pod ktorym dokument stoi
        if ("/%s/" % id_rpl) not in adres:
            odrz.append((ident, "adres nie niesie id_rpl %s" % id_rpl)); continue

        # 4. rejestracja stoi w eksporcie RPL — stad przyjda pola rekordu
        prod = rpl.get(id_rej)
        if prod is None:
            odrz.append((ident, "id rejestracji %s nie stoi w eksporcie RPL" % id_rej))
            continue
        if poz and str(prod.get("pozwolenie") or "") != poz:
            odrz.append((ident, "pozwolenie w manifescie %s != RPL %s"
                         % (poz, prod.get("pozwolenie")))); continue

        # 5. postac stoi w slowniku postaci. Napis spoza slownika NIE jest
        #    zgadywany — PO.postac_klasa rzuca, a pozycja wypada z importu.
        try:
            kl = PO.postac_klasa(prod.get("postac"))
        except KeyError as e:
            odrz.append((ident, "postac spoza slownika: %s" % str(e)[:90])); continue

        # 6. punkty daja sie odczytac, a 4.2 nie jest pusty
        try:
            punkty, diag = chpl_z_pdf.punkty(sc)
        except Exception as e:
            odrz.append((ident, "odczyt punktow nie powiodl sie: %s" % e)); continue
        if not (punkty.get("4.2") or "").strip():
            odrz.append((ident, "punkt 4.2 pusty — dokument bez dawkowania")); continue

        wg_substancji.setdefault(sub, []).append(
            dict(pozwolenie=poz, id_rejestru=id_rej, naglowek=nag, sha256=sha,
                 plik=plik, adres=adres, punkty=punkty, diag=diag,
                 prod=prod, kl=kl))
        zach.append(ident)

    dopisane, pominiete, przed_b, po_b = 0, 0, 0, 0
    for sub, lista in sorted(wg_substancji.items()):
        sciezka = os.path.join(KATALOG, "%s.json" % sub)
        if not os.path.exists(sciezka):
            for x in lista:
                i = "%s|%s" % (sub, x["id_rejestru"])
                odrz.append((i, "nie ma rekordu cache %s.json" % sub))
                if i in zach:
                    zach.remove(i)
            continue
        przed_b += os.path.getsize(sciezka)
        rek = json.load(open(sciezka, encoding="utf-8"))
        maja = {(p.get("sha256_pdf"), str(p.get("id_rejestru") or ""))
                for p in rek.get("produkty", [])}
        maja_sha = {p.get("sha256_pdf") for p in rek.get("produkty", [])}
        for x in lista:
            if (x["sha256"], x["id_rejestru"]) in maja or x["sha256"] in maja_sha:
                pominiete += 1
                continue
            prod = x["prod"]
            wpis = {
                "nazwa": prod.get("nazwa"),
                "moc": prod.get("moc"),
                "postac": prod.get("postac"),
                "podmiot": prod.get("podmiot"),
                "pozwolenie": str(prod.get("pozwolenie") or ""),
                "id_rejestru": x["id_rejestru"],
                "zrodlo": x["adres"],
                "zrodlo_pliku": x["plik"],
                "sha256_pdf": x["sha256"],
                "stan": "OK",
                "punkty_nieznalezione": diag_brak(x["diag"]),
                "punkty_uciete": [],
                "klucz_rpl": {
                    "atc": prod.get("atc"),
                    "nazwa_powszechna": [prod.get("nazwa_powszechna")],
                    "postac": [prod.get("postac")],
                    "zrodlo": "RPL_PSYCH.json, rownosc id rejestracji %s" % x["id_rejestru"],
                },
                "DROGA": x["kl"]["droga"],
                "UWALNIANIE": x["kl"]["uwalnianie"],
                "EKSPOZYCJA": PO.ekspozycja(prod, chpl_42=x["punkty"].get("4.2")),
                "naglowek_z_rejestru": x["naglowek"],
                "proweniencja": ("dokument pobrany przegladarka lekarza %s; sha256 "
                                 "bajtow policzone przy imporcie; adres i pola "
                                 "produktu z eksportu RPL po id rejestracji" % DZIS),
            }
            wpis["punkty"] = x["punkty"]
            rek.setdefault("produkty", []).append(wpis)
            dopisane += 1

        rek["uwaga_import_lokalny"] = (
            "Produkty dopisane importem lokalnym %s z dokumentow pobranych "
            "przegladarka lekarza. MAX_PRODUKTOW jest limitem PROBKOWANIA przy "
            "budowie od zera i tego kanalu nie obejmuje. Import do cache NIE "
            "JEST wejsciem do pliku wizyty - do czasu jawnej przebudowy pliku "
            "wizyty warstwy sie roznia i bramka etykiet ma to pokazac." % DZIS)
        tekst = json.dumps(rek, ensure_ascii=False, indent=1, sort_keys=True)
        po_b += len(tekst.encode("utf-8"))
        if zapisz:
            open(sciezka, "w", encoding="utf-8").write(tekst)

    print("IMPORT DOKUMENTOW LOKALNYCH DO CACHE")
    print("  manifest:  %s" % manifest)
    print("  dokumenty: %s" % katalog_dokumentow)
    print("  spis RPL:  %s" % spis)
    print()
    print("  BILANS (par. 3B)")
    print("    N_WEJSCIE   = %d" % we)
    print("    N_ZACHOWANE = %d" % len(zach))
    print("    N_ODRZUCONE = %d" % len(odrz))
    print("    BILANS      = %s" % ("OK" if we == len(zach) + len(odrz) else "FAIL"))
    print()
    print("    dopisane do rekordow:    %d" % dopisane)
    print("    pominiete, bo juz byly:  %d" % pominiete)
    print()
    print("  ROZMIAR — ZMIERZONY PRZED ZAPISEM, NIE PO")
    print("    rekordy przed: %d B" % przed_b)
    print("    rekordy po:    %d B" % po_b)
    if przed_b:
        print("    krotnosc:      x%.1f" % (po_b / przed_b))
    if odrz:
        print()
        print("  ODRZUCONE — identyfikatory i powody:")
        for i, r in odrz[:40]:
            print("    %-28s %s" % (i, r))
        if len(odrz) > 40:
            print("    ... i jeszcze %d" % (len(odrz) - 40))
    print()
    print("  ZAPISANE." if zapisz else
          "  SUCHY PRZEBIEG. Bez --zapisz nic nie zostalo zmienione.")
    return 0 if we == len(zach) + len(odrz) else 1


def diag_brak(diag):
    """Punkty, ktorych w dokumencie nie znaleziono. Pusta lista to NIE to samo
    co brak pola - pole musi byc, bo T6 testu odbioru oblewa rekord bez niego."""
    return list((diag or {}).get("brak") or [])


ap = argparse.ArgumentParser()
ap.add_argument("--lista", default="zrodla/chpl_cache_lista.txt")
ap.add_argument("--tylko", default="")
ap.add_argument("--punkty", default="4.1,4.2,4.3,4.4,4.5,4.6,4.8,5.2")
ap.add_argument("--spis", default="rpl/RPL_PSYCH.json")
# IMPORT DOKUMENTOW LOKALNYCH — osobne wejscie tej samej sciezki [R83].
# Nie przebudowuje cache i nie probkuje: bierze dokumenty JUZ DOSTARCZONE
# i przypisane, liczy ich sha256 z bajtow i dopisuje do rekordow z proweniencja.
ap.add_argument("--import-lokalny", default="",
                help="manifest TSV dokumentow lokalnych (8 kolumn)")
ap.add_argument("--dokumenty", default="../psychai-paczka/_zrodla_lokalne/chpl",
                help="katalog z plikami PDF wymienionymi w manifescie")
ap.add_argument("--zapisz", action="store_true",
                help="bez tego import jest sucha proba i nic nie zapisuje")
x = ap.parse_args()
if x.import_lokalny:
    # WCZESNE WYJSCIE. Import nie przebudowuje cache i nie probkuje rejestru —
    # reszta tego pliku jest sciezka budowy od zera i nie ma tu czego robic.
    raise SystemExit(import_lokalny(x.import_lokalny, x.dokumenty, x.spis, x.zapisz))
chce = set(x.punkty.split(","))
dzis = datetime.date.today().isoformat()

d = json.load(open(x.spis, encoding="utf-8"))
substancje = [l.strip() for l in open(x.lista, encoding="utf-8") if l.strip() and not l.startswith("#")]
if x.tylko:
    chciane = {q.strip().lower() for q in x.tylko.split(",") if q.strip()}
    substancje = [s for s in substancje if s.lower() in chciane]

os.makedirs(KATALOG, exist_ok=True)
indeks = {}
if os.path.exists(f"{KATALOG}/INDEX.json"):
    indeks = json.load(open(f"{KATALOG}/INDEX.json", encoding="utf-8")).get("substancje", {})

# BRAMA SEMANTYKI. dopasuj() jest dzis kluczem HEURYSTYCZNYM (szkielet
# spolgloskowy), a heurystyce wolno tylko WSKAZYWAC. Deklaracja jest tu po to,
# zeby to bylo WIDOCZNE i zeby przepiecie na klucz deterministyczny bylo
# zmiana jednej linii, a nie archeologia.
# KLUCZ DETERMINISTYCZNY. Szkielet spolgloskowy mieszal leki - prometazyna
# trafiala na Escitalopramum, perazyna na Valerianae extractum. Teraz dobor
# idzie przez rownosc nazwy powszechnej i kodu ATC5 wobec tabeli kluczy.
# Sprawdzone wobec istniejacego cache: 0 z 208 produktow zgubionych,
# 388 nowych kandydatow, ktorych stare dopasowanie nie znajdowalo.
KLUCZ_DOPASOWANIA = "DETERMINISTYCZNY"
polityka.sprawdz_semantyke("CHPL_LAYER", "WSKAZANIE", KLUCZ_DOPASOWANIA,
                           ("nazwa_powszechna", "atc"))
_TABELA = dobor.wczytaj_tabele()

for s in substancje:
    pr, _rap = dobor.dobierz(s, d["produkty"], _TABELA)
    if _rap.get("STAN") != "OK":
        # BRAK WPISU W TABELI TO NIE BRAK LEKU. Nie wracamy po cichu do
        # szkieletu - to on byl bledem. Mowimy, czego brakuje.
        print(f"{s:22} {_rap['STAN']} - klucza dla tej substancji nikt jeszcze nie zapisal")
    else:
        print(f"{s:22} dobor: wejscie={_rap['N_WEJSCIE']} zachowane={_rap['N_ZACHOWANE']} odrzucone={_rap['N_ODRZUCONE']}")
    plik = plik_nazwy(s)
    if not pr:
        print(f"{s:22} NIE ZNALEZIONO w spisie RPL (nie znaczy, ze produktu nie ma)")
        # BRAK DOPASOWANIA NIE KASUJE PLIKU. "Nie znalazlem" to nie "nie ma":
        # regresja w dopasowaniu niszczylaby dane zamiast je zostawic. Wczesniej
        # stalo tu os.remove i wystarczyla jedna zmiana wzorca, zeby substancja
        # stracila etykiete. Poprzedni plik zostaje; indeks mowi, co sie stalo.
        stary_plik = f"{KATALOG}/{plik}.json"
        zachowany = os.path.exists(stary_plik)
        if zachowany:
            print(f"{s:22} poprzedni {stary_plik} ZACHOWANY (brak dopasowania to nie brak leku)")
        indeks[s] = {"plik": stary_plik if zachowany else None,
                     "stan": "NIE_ZNALEZIONO_W_SPISIE", "sprawdzono": dzis,
                     "uwaga": ("Dopasowanie nie trafilo. To NIE jest stwierdzenie, ze "
                               "produktu nie ma. Poprzednia tresc zachowana.")}
        continue
    widz = {}
    for p in pr:
        widz.setdefault(p.get("nazwa", "?"), p)
    kandydaci = list(widz.values())          # NIE ucinamy jeszcze do MAX:
                                             # dobor rozstrzyga sie po pobraniu
    rekord = {"substancja": s, "pobrano": dzis, "punkty_zadane": sorted(chce),
              "uwaga": "ChPL nalezy do PRODUKTU. Rozne produkty tej samej substancji moga sie roznic. Brak punktu != brak tresci.",
              "produkty": []}
    odciski, pominiete_jako_duplikat, nieudane = {}, [], []
    # Limit prob. Nieudane pobranie NIE zajmuje miejsca na etykiete - inaczej
    # jeden niedostepny PDF odbiera substancji jedna z trzech etykiet, a tak
    # wlasnie powstalo osiem pustych pozycji w poprzednim cache. Limit chroni
    # przed przechodzeniem calej listy produktow, gdy serwer nie odpowiada.
    limit_prob = MAX_PRODUKTOW + 3
    prob = 0
    for p in kandydaci:
        if len(rekord["produkty"]) >= MAX_PRODUKTOW or prob >= limit_prob:
            break
        prob += 1
        t, info = pdf_tekst(p.get("chpl"))
        if t is None:
            nieudane.append({"nazwa": p.get("nazwa"), "moc": p.get("moc"),
                             "zrodlo": p.get("chpl") or "", "stan": info})
            print(f"{s:22} {p.get('nazwa'):22} {info} (nie zajmuje miejsca)")
            continue
        got = punkty(t, chce)
        # KLUCZ DETERMINISTYCZNY: tresc pobranych punktow po zwezeniu bialych
        # znakow. Rowność tresci, nie podobienstwo nazwy ani mocy.
        odcisk = hashlib.sha256(
            "\u0000".join(" ".join((got[k]["tekst"] or "").split())
                          for k in sorted(got)).encode("utf-8")).hexdigest()
        if odcisk in odciski:
            pominiete_jako_duplikat.append(
                {"nazwa": p.get("nazwa"), "moc": p.get("moc"),
                 "ta_sama_etykieta_co": odciski[odcisk],
                 "zrodlo": p.get("chpl") or ""})
            print(f"{s:22} {p.get('nazwa'):22} POMINIETY: ta sama tresc co {odciski[odcisk]}")
            continue
        odciski[odcisk] = p.get("nazwa")
        rekord["produkty"].append({"nazwa": p.get("nazwa"), "moc": p.get("moc"),
                                   "podmiot": p.get("podmiot"), "zrodlo": p.get("chpl"),
                                   "sha256_pdf": info, "stan": "OK",
                                   "punkty": {k: got[k]["tekst"] for k in sorted(got)},
                                   "punkty_uciete": sorted(k for k in got if got[k]["uciety"]),
                                   "punkty_nieznalezione": sorted(chce - set(got))})
        uc = sorted(k for k in got if got[k]["uciety"])
        print(f"{s:22} {p.get('nazwa'):22} OK  punkty: {','.join(sorted(got)) or 'brak'}" + (f"  UCIETE: {','.join(uc)}" if uc else ""))
    # BILANS DOBORU. Filtr, ktory cokolwiek odrzuca, musi sie rozliczyc.
    rekord["DOBOR_PRODUKTOW"] = {
        "N_KANDYDATOW": len(kandydaci),
        "N_WYBRANYCH": len(rekord["produkty"]),
        "N_POMINIETYCH_JAKO_DUPLIKAT": len(pominiete_jako_duplikat),
        "N_NIEUDANYCH_POBRAN": len(nieudane),
        "N_PROB": prob,
        "LIMIT_PROB": limit_prob,
        "POMINIETE": pominiete_jako_duplikat or None,
        "NIEUDANE_POBRANIA": nieudane or None,
        "uwaga": ("Produkt o tresci punktow identycznej z juz wybranym NIE zajmuje "
                  "miejsca - rozne moce tego samego opakowania to jedna etykieta. "
                  "Klucz: rownosc tresci po kanonizacji bialych znakow. "
                  "Nieudane pobranie takze nie zajmuje miejsca, ale jest "
                  "wypisane - brak etykiety to fakt, nie cisza. Gdy N_PROB "
                  "rowna sie LIMIT_PROB, lista kandydatow NIE zostala "
                  "przejrzana do konca.")}
    # BRAMA PUBLIKACJI. 2026-09-23 przypadkowy przebieg bez sieci przepisal 88
    # plikow pusta lista produktow: blok bilansowy zapisal N_WYBRANYCH 0, a plik
    # i tak poszedl na dysk. Miara byla, nic nie zatrzymywala.
    sciezka = f"{KATALOG}/{plik}.json"
    stare_id = set()
    if os.path.exists(sciezka):
        try:
            stare_id = {q.get("nazwa") for q in json.load(
                open(sciezka, encoding="utf-8")).get("produkty", [])}
        except Exception:
            stare_id = set()
    nowe_id = {q["nazwa"] for q in rekord["produkty"]}
    # Kazde pobranie nieudane -> to stan NIEWIEDZY, nie wynik.
    stan = "BLAD_POBRANIA" if (nieudane and not rekord["produkty"]) else "OK"
    try:
        polityka.sprawdz_publikacje("CHPL_LAYER", stare_id, nowe_id, stan_zrodla=stan)
    except polityka.Odmowa as e:
        print(f"{s:22} NIE ZAPISANO: {e}")
        indeks[s] = {"plik": sciezka if stare_id else None, "stan": "ZACHOWANO_POPRZEDNI",
                     "sprawdzono": dzis, "powod": str(e),
                     "produkty": sorted(stare_id)}
        continue
    json.dump(rekord, open(sciezka, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    indeks[s] = {"plik": f"{KATALOG}/{plik}.json", "stan": "OK", "pobrano": dzis,
                 "produkty": [p["nazwa"] for p in rekord["produkty"]]}

# Sprzatanie sierot: plik, ktorego INDEX nie wskazuje, nie ma prawa zostac
# w repo - runtime moze go trafic zgadujac nazwe i przeczytac stare dane.
# ZABEZPIECZENIE: kasowanie wylacznie po PELNYM przebiegu generujacym kompletny
# INDEX; tryb --tylko nie usuwa zadnych plikow spoza aktualizowanego zakresu.
if x.tylko:
    print("tryb --tylko: sprzatanie sierot POMINIETE (niepelny przebieg)")
else:
    uzywane = {os.path.basename(v["plik"]) for v in indeks.values() if v.get("plik")}
    for f in sorted(os.listdir(KATALOG)):
        if f.endswith(".json") and f != "INDEX.json" and f not in uzywane:
            os.remove(os.path.join(KATALOG, f))
            print(f"sierota usunieta: {KATALOG}/{f}")

json.dump({"opis": "Indeks CHPL_CACHE. Wlascicielem pinu jest sekcja CHPL_WYCIAG w module 19.",
           "zbudowano": dzis, "punkty": sorted(chce), "substancje": indeks},
          open(f"{KATALOG}/INDEX.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nGOTOWE: {len([v for v in indeks.values() if v.get('stan') == 'OK'])} substancji w cache, indeks: {KATALOG}/INDEX.json")
