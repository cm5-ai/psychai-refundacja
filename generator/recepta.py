"""RECEPTA — najtańszy odpowiednik i liczba opakowań. Czyta WYŁĄCZNIE wynik REFUNDACJA_ENGINE (JSON).
Nie tworzy faktów refundacyjnych: poziom, dopłata, status, LP i klucz są przepisane z silnika.
Liczba opakowań i koszt kuracji = WYLICZONE (dzielenie/mnożenie, §3 w. 40).
Użycie: python3 recepta.py wynik_silnika.json --moc "100 mg" [--postac "powl"] [--dni 90 --na-dobe 1.5] [--braki BRAKI.json] [--top 6]"""
import json, re, sys, math, argparse, collections

def norm(s): return re.sub(r"\s+", " ", (s or "").lower().replace(",", ".")).strip()
def liczba(s):
    try: return float(str(s).replace(",", "."))
    except Exception: return None
def zl(x): return ("%.2f" % x).replace(".", ",")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wynik"); ap.add_argument("--moc", required=True); ap.add_argument("--postac", default="")
    ap.add_argument("--dni", type=float); ap.add_argument("--na-dobe", type=float, help="liczba tabletek/jednostek na dobę")
    ap.add_argument("--braki"); ap.add_argument("--top", type=int, default=6)
    a = ap.parse_args()
    o = json.load(open(a.wynik, encoding="utf-8"))
    ds = o.get("dataset_id") or "?"
    braki = set()
    if a.braki:
        try: braki = set(json.load(open(a.braki, encoding="utf-8")).get("gtin", []))
        except Exception: print("BRAKI: nie wczytano listy — ostrzeżenia o brakach NIEDOSTĘPNE")
    moc = norm(a.moc).replace(" ", "")
    pos = []
    for x in o.get("results", []):
        prep = norm(x.get("preparation"))
        if moc not in prep.replace(" ", ""): continue
        if a.postac and norm(a.postac) not in prep: continue
        pos.append(x)
    if not pos:
        print("RECEPTA: brak pozycji silnika dla mocy '%s'%s [DATASET %s]" % (a.moc, (" i postaci '%s'" % a.postac) if a.postac else "", ds)); return
    # postaci rozdzielnie — nie mieszaj IR z o przedłużonym uwalnianiu
    postaci = collections.defaultdict(list)
    for x in pos:
        p = x["preparation"].split(",")[1].strip() if x["preparation"].count(",") >= 2 else "?"
        postaci[p].append(x)
    if len(postaci) > 1 and not a.postac:
        print("UWAGA: %d różne postacie (%s) — każda osobno; nie są zamienne bez decyzji lekarza." % (len(postaci), "; ".join(postaci)))
    for p, xs in postaci.items():
        # jedna linia na GTIN + wskazanie dopasowane do rozpoznania (match), inaczej pierwsze
        best = {}
        for x in xs:
            k = x["GTIN"]
            if k not in best or (x.get("match") and not best[k].get("match")): best[k] = x
        rows = sorted(best.values(), key=lambda x: (x["refundation_status"] != "TAK", liczba(x["copay"]["doplata"]) if liczba(x["copay"]["doplata"]) is not None else 9e9))
        print("\n== %s %s — %d opakowań w wykazie [DATASET %s]" % (a.moc, p, len(rows), ds))
        for x in rows[:a.top]:
            d = liczba(x["copay"]["doplata"]); szt = re.match(r"\s*(\d+)", x.get("package") or "")
            linia = "- %s | %s | %s, dopłata %s zł/op. | STATUS: %s | LP %s | GTIN %s" % (
                x["preparation"], x["package"], x["copay"]["poziom"], x["copay"]["doplata"], x["refundation_status"], x["LP"], x["GTIN"])
            if a.dni and a.na_dobe and szt:
                n = math.ceil(a.dni * a.na_dobe / int(szt.group(1)))
                linia += " | na %g dni × %g/d: %d op.%s (WYLICZONE)" % (a.dni, a.na_dobe, n, (" = %s zł" % zl(n * d)) if d is not None else "")
            if x["GTIN"] in braki: linia += " | ⚠ ZAGROŻONY BRAKIEM (lista MZ)"
            print(linia)
        if len(rows) > a.top: print("  … i %d kolejnych (droższe)" % (len(rows) - a.top))
        st = collections.Counter(x["refundation_status"] for x in rows)
        if "TAK" not in st: print("  STATUS ≠ TAK: najpierw rozstrzygnij warunek/wskazanie wg 39 — kolejność wg dopłaty jest warunkowa.")
    print("\nPIN: [REFUNDACJA_ENGINE | %s] — dopłata wg pozycji A1, bez uprawnień dodatkowych." % ds)

if __name__ == "__main__": main()
