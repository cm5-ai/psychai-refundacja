#!/usr/bin/env python3
"""MANIFEST DOKUMENTOW POBRANYCH PRZEGLADARKA LEKARZA. [R83, 2026-10-05]

PO CO. Import do cache'u (chpl_cache.py --import-lokalny) nie zgaduje, czyj
jest plik. Dostaje manifest: osiem kolumn, kazda z jawnego zrodla. Ten skrypt
manifest BUDUJE i robi to po kluczu deterministycznym, nie po nazwie.

SKAD CO POCHODZI
  plik           -> katalog _zrodla_lokalne/chpl, nazwa ChPL_<pozwolenie>_RPL<id>.pdf
  id_rpl         -> czlon RPL<id> nazwy pliku; to identyfikator w ADRESIE rejestru
  substancja,
  pozwolenie,
  id_rejestru,
  adres          -> BLOK PLIKU WIZYTY, znaleziony po ROWNOSCI id w adresie
  naglowek       -> nazwa | moc | postac z tego samego bloku (tylko do zapisu
                    proweniencji; pola rekordu cache biora sie z eksportu RPL)
  sha256         -> policzone z BAJTOW pliku, tutaj, przy budowie manifestu

DLACZEGO PO ADRESIE, A NIE PO NAZWIE PLIKU. Czlon <pozwolenie> w nazwie pliku
jest tym, co wpisal pobierajacy. Czlon RPL<id> stoi w adresie, pod ktorym plik
zostal pobrany. Wiazemy po adresie, a pozwolenie z nazwy SPRAWDZAMY wobec bloku
— rozjazd tych dwoch jest bledem i wypada z manifestu z podaniem obu wartosci.
To jest ta sama klasa bledu, ktora 2026-10-04 oblala zasiewy S16 i S19: plik o
zgodnym hashu pod inna nazwa nie podpisuje rejestracji.

BILANS par. 3B: N_WEJSCIE = N_ZACHOWANE + N_ODRZUCONE, odrzucone z powodem.
"""
import hashlib
import os
import re
import sys

NAZWA = re.compile(r"^ChPL_([^_]+)_RPL(\d+)\.pdf$")
PACZKA = os.environ.get("PSYCHAI_PACZKA") or os.path.expanduser("~/mnt/psychai-paczka")
WIZYTA = os.path.join(PACZKA, "projekt", "LEKI_WIZYTA.txt")
DOKUMENTY = os.path.join(PACZKA, "_zrodla_lokalne", "chpl")


def bloki_wizyty(sciezka):
    """Rejestracje z pliku wizyty, zaindeksowane po id z ADRESU_Z_REJESTRU.

    Klucz to liczba miedzy /medicinal-products/ a /characteristic — rownosc
    napisu, zero dopasowania. Blok bez adresu nie trafia do indeksu wcale:
    nie ma czym go zwiazac z plikiem i udawanie, ze jest, byloby zgadywaniem.
    """
    wg_id, biez = {}, {}
    ADRES = re.compile(r"/medicinal-products/(\d+)/characteristic")

    def zamknij(b):
        # DWIE NAZWY TEGO SAMEGO ADRESU [poprawka 2026-10-05]. Blok BEZ dawki
        # niesie ADRES_Z_REJESTRU; blok, ktory dawke JUZ dostal, niesie
        # DOKUMENT. Pierwsza wersja czytala tylko pierwsza z nich, wiec po
        # przebudowie pliku wizyty 292 zaimportowane rejestracje "znikaly" z
        # indeksu i manifest raportowal 726 z 1065 zamiast 1018. Pusty wynik
        # wygladal na brak dokumentu, a dokument lezal. Par. 3B: "nie
        # znalazlem" to nie "nie ma".
        a = (b.get("ADRES_Z_REJESTRU") or b.get("DOKUMENT") or "")
        m = ADRES.search(a)
        if not m:
            return
        i = m.group(1)
        if i in wg_id:
            raise ValueError("PLIK WIZYTY: adres z id %s stoi przy dwoch blokach. "
                             "Klucz przestal byc kluczem - nie scalam." % i)
        wg_id[i] = b

    for linia in open(sciezka, encoding="utf-8"):
        if linia.startswith("### "):
            if biez:
                zamknij(biez)
            biez = {"NAGLOWEK": linia[4:].strip()}
            continue
        if not biez:
            continue
        m = re.match(r"^([A-Z_]+):\s*(.*)$", linia.rstrip("\n"))
        if m:
            biez[m.group(1)] = m.group(2).strip()
    if biez:
        zamknij(biez)
    return wg_id


def main():
    if not os.path.exists(WIZYTA):
        print("NIE MA PLIKU WIZYTY: %s" % WIZYTA)
        return 2
    wg_id = bloki_wizyty(WIZYTA)
    pliki = sorted(f for f in os.listdir(DOKUMENTY) if f.lower().endswith(".pdf"))

    we, wiersze, odrz = 0, [], []
    for f in pliki:
        we += 1
        m = NAZWA.match(f)
        if not m:
            odrz.append((f, "nazwa nie ma postaci ChPL_<pozwolenie>_RPL<id>.pdf"))
            continue
        poz_z_nazwy, id_rpl = m.group(1), m.group(2)
        b = wg_id.get(id_rpl)
        if b is None:
            odrz.append((f, "adresu z id %s nie ma w pliku wizyty" % id_rpl))
            continue
        ident = (b.get("IDENTYFIKATOR") or "").split()[0] if b.get("IDENTYFIKATOR") else ""
        if poz_z_nazwy != ident:
            odrz.append((f, "pozwolenie z nazwy %s != identyfikator bloku %s"
                         % (poz_z_nazwy, ident)))
            continue
        idr = (b.get("ID_REJESTRU") or "").split()[0]
        if not idr:
            odrz.append((f, "blok nie niesie ID_REJESTRU"))
            continue
        sub = b.get("SUBSTANCJA") or ""
        if not sub:
            odrz.append((f, "blok nie niesie SUBSTANCJI"))
            continue
        sha = hashlib.sha256(open(os.path.join(DOKUMENTY, f), "rb").read()).hexdigest()
        adres = (b.get("ADRES_Z_REJESTRU") or b.get("DOKUMENT") or "")
        if not adres:
            odrz.append((f, "blok nie niesie adresu dokumentu"))
            continue
        wiersze.append("\t".join([sub, ident, idr, id_rpl,
                                  b.get("NAGLOWEK", ""), sha, f, adres]))

    wyj = sys.argv[1] if len(sys.argv) > 1 else "zrodla/manifest_lokalny.tsv"
    os.makedirs(os.path.dirname(wyj) or ".", exist_ok=True)
    with open(wyj, "w", encoding="utf-8") as fh:
        fh.write("# substancja\tpozwolenie\tid_rejestru\tid_rpl\tnaglowek\tsha256\tplik\tadres\n")
        for w in wiersze:
            fh.write(w + "\n")

    print("MANIFEST DOKUMENTOW LOKALNYCH")
    print("  dokumenty: %s" % DOKUMENTY)
    print("  wizyta:    %s" % WIZYTA)
    print("  wyjscie:   %s" % wyj)
    print()
    print("  BILANS (par. 3B)")
    print("    N_WEJSCIE   = %d" % we)
    print("    N_ZACHOWANE = %d" % len(wiersze))
    print("    N_ODRZUCONE = %d" % len(odrz))
    print("    BILANS      = %s" % ("OK" if we == len(wiersze) + len(odrz) else "FAIL"))
    if odrz:
        print()
        print("  ODRZUCONE:")
        for f, r in odrz[:40]:
            print("    %-34s %s" % (f, r))
        if len(odrz) > 40:
            print("    ... i jeszcze %d" % (len(odrz) - 40))
    return 0 if we == len(wiersze) + len(odrz) else 1


if __name__ == "__main__":
    raise SystemExit(main())
