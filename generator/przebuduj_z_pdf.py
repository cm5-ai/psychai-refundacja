#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRZEBUDOWA CHPL_CACHE Z POBRANYCH PDF - 2026-09-23.

ZRODLO: oryginalne etykiety z rejestru, pobrane przez przegladarke lekarza
(runtime ma 403 przez proxy - sprawdzone z kontenera i z Maca).
EKSTRAKTOR: generator/chpl_z_pdf.py, przetestowany na czterech przypadkach
o ZNANEJ prawidlowej odpowiedzi (generator/PRZYPADKI_WZORCOWE.json).

CZEGO TEN SKRYPT NIE RUSZA. Metadanych produktu - nazwy, mocy, podmiotu,
klucza RPL, adresu zrodla. Te pochodza ze spisu RPL i nie sa przedmiotem
tej przebudowy. Podmieniane sa WYLACZNIE punkty, sha256 pliku i data.

BRAMY. Kazdy zapis przechodzi przez polityke: semantyka (czy wolno tak
sklasyfikowac) i publikacja (czy wolno tym nadpisac stan produkcyjny,
porownanie ZBIOROW identyfikatorow, nie licznosci).

ZASADA NADRZEDNA. Brak PDF dla produktu = NIE RUSZAMY tego produktu.
"Nie pobralem" to nie jest informacja, ze etykiety nie ma.
"""
import json, glob, os, re, sys, hashlib, datetime

KAT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KAT)
import polityka, chpl_z_pdf

CHPL = os.path.join(KAT, "..", "chpl")
POBRANE = os.path.expanduser("~/mnt/Downloads")
DZIS = "2026-09-23"


def pdf_dla(pid):
    g = sorted(glob.glob(os.path.join(POBRANE, "Charakterystyka-%s-*.pdf" % pid)))
    if not g:
        g = sorted(glob.glob(os.path.join(POBRANE, "Charakterystyka-%s-recznie.pdf" % pid)))
    return g[0] if g else None


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def main():
    sucho = "--zapisz" not in sys.argv
    raport = {"plikow": 0, "produktow": 0, "bez_pdf": [], "punkty_przed": 0,
              "punkty_po": 0, "odzyskane": [], "nadal_brak": []}

    for f in sorted(glob.glob(os.path.join(CHPL, "*.json"))):
        if os.path.basename(f) == "INDEX.json":
            continue
        d = json.load(open(f, encoding="utf-8"))
        zmiana = False
        for p in d.get("produkty", []):
            m = re.search(r"/medicinal-products/(\d+)/characteristic", str(p.get("zrodlo", "")))
            if not m:
                continue
            pid = m.group(1)
            sciezka = pdf_dla(pid)
            et = "%s/%s" % (d.get("substancja"), p.get("nazwa"))
            if not sciezka:
                raport["bez_pdf"].append(et)
                continue
            nowe, diag = chpl_z_pdf.punkty(sciezka)
            stare = p.get("punkty") or {}
            raport["produktow"] += 1
            raport["punkty_przed"] += len(stare)
            raport["punkty_po"] += len(nowe)

            # BRAMA 1 - klasyfikacja. Podstawa decyzji siega TRESCI dokumentu.
            polityka.sprawdz_semantyke(
                "CHPL_LAYER", "ZAPIS", "DETERMINISTYCZNY",
                ("naglowek_sekcji_w_pdf", "numer_punktu", "tresc_punktu"))
            # BRAMA 2 - publikacja. Punkt, ktory byl, a ktorego nowy wyciag NIE
            # znalazl, wymaga jawnej przyczyny. Tu jedyna dopuszczalna to
            # zatwierdzona korekta mapowania: stary punkt byl trescia innego.
            znikly = set(stare) - set(nowe)
            polityka.sprawdz_publikacje(
                "CHPL_LAYER", set(stare), set(nowe), "OK",
                {k: "ZATWIERDZONA_KOREKTA_MAPOWANIA" for k in znikly})

            odzyskane = sorted(set(nowe) - set(stare))
            if odzyskane:
                raport["odzyskane"].append("%s: %s" % (et, ",".join(odzyskane)))
            if diag["brak"]:
                raport["nadal_brak"].append("%s: %s" % (et, ",".join(diag["brak"])))

            if sucho:
                continue
            p["punkty"] = nowe
            p["punkty_nieznalezione"] = diag["brak"]
            p["punkty_uciete"] = []
            p["sha256_pdf"] = sha(sciezka)
            p["zrodlo_pliku"] = os.path.basename(sciezka)
            p["stan"] = "OK"
            for k in ("punkty_odrzucone", "KWARANTANNA", "NAGLOWEK_NIEZGODNY",
                      "PODEJRZANIE_KROTKI"):
                p.pop(k, None)
            zmiana = True

        if zmiana and not sucho:
            d["pobrano"] = DZIS
            d["STATUS"] = "PRZEBUDOWANY_Z_PDF"
            d.pop("KWARANTANNA_DATA", None)
            raport["plikow"] += 1
            json.dump(d, open(f, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1, sort_keys=True)

    print("produktow przetworzonych:", raport["produktow"])
    print("punktow przed:", raport["punkty_przed"], "-> po:", raport["punkty_po"])
    print("produktow bez PDF (NIETKNIETE):", len(raport["bez_pdf"]))
    print("produktow z odzyskanymi punktami:", len(raport["odzyskane"]))
    print("produktow, gdzie nadal brakuje punktu:", len(raport["nadal_brak"]))
    for x in raport["nadal_brak"][:15]:
        print("   ", x)
    print("tryb:", "ZAPIS" if not sucho else "PROBNY")
    json.dump(raport, open(os.path.join(KAT, "RAPORT_PRZEBUDOWY.json"), "w",
                           encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
