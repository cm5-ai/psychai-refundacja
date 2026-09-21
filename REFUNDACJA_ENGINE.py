#!/usr/bin/env python3
"""
REFUNDACJA_ENGINE — deterministyczny serwis CDS refundacji dla PSYCH-AI (tylko biblioteka standardowa).
Źródło: dokładnie jeden plik REFUNDACJA_DATA*.json w katalogu datasetu. Brak odwołań do konkretnego wykazu.

Użycie:
  python3 REFUNDACJA_ENGINE.py --dataset-dir /mnt/project --case case.json [--today RRRR-MM-DD]
  (case: JSON z pliku albo '-' = stdin). Wynik: JSON na stdout.

Wejście (case):
  query: {medication | substance | gtin}
  icd10_confirmed: [kody ICD-10 ustalone przez lekarza]
  hypotheses: [{code, status, positive_clues: [...]}]      (PASS A)
  clinical_facts: {positive: [...], negative: [...]}       (surowe fakty; nie są interpretowane przez silnik)
  condition_answers: {fact_id: "TAK"|"NIE"|"NIE_WIEM"}     (odpowiedzi lekarza na pytania silnika)
  today: RRRR-MM-DD (opcjonalnie; domyślnie data w strefie Europe/Warsaw)

Statusy refundation_status:
  TAK                         — dopasowanie + warunek spełniony/brak + okno IN_FORCE_* + dataset nie zablokowany + klucz
  NIE                         — wyłącznie §12: pozycja usunięta z wykazu (pozycje_usuniete), dataset nie zablokowany
  NIEPOTWIERDZONY             — okno decyzji inne niż IN_FORCE_* albo dataset zablokowany (freshness)
  DO_UZUPELNIENIA             — brakuje faktu klinicznego mogącego zmienić wynik (pytanie w questions[])
  NIE_SPELNIA_WARUNKU         — lekarz odpowiedział NIE na warunek wskazania (to nie jest NIE refundacji)
  NIE_SAMODZIELNA_PODSTAWA    — dopasowanie tylko przez chorobę współistniejącą
  BRAK_DANYCH                 — nazwa poza datasetem / brak rozpoznania / brak dopasowania
  NO_VERDICT                  — brak lub konflikt version_key, dataset nieczytelny lub niejednoznaczny
"""
import argparse, datetime as dt, glob, hashlib, json, os, re, sys, unicodedata, calendar

ENGINE_VERSION = "RE-1.0"
BLOCKING = {"SUPERSEDED", "SUPERSEDED_SUCCESSOR_NOT_DEPLOYED", "SOURCE_CHECK_STALE", "DATASET_NOT_YET_EFFECTIVE"}
IN_FORCE = {"IN_FORCE_BY_DECISION_WINDOW", "IN_FORCE_BY_SUCCESSOR_DOCUMENT"}


# ------------------------------------------------------------------ dataset
class DatasetError(Exception):
    pass


def load_active(dataset_dir):
    files = sorted(set(glob.glob(os.path.join(dataset_dir, "REFUNDACJA_DATA*.json"))))
    if len(files) != 1:
        raise DatasetError("DATASET_NOT_UNIQUE: oczekiwano dokładnie 1 pliku REFUNDACJA_DATA*.json, znaleziono %d" % len(files))
    with open(files[0], encoding="utf-8") as f:
        d = json.load(f)
    m = d.get("metadata") or {}
    for k in ("dataset_id", "valid_from", "schema_version", "freshness_manifest"):
        if not m.get(k):
            raise DatasetError("DATASET_INVALID: brak metadata." + k)
    for k in ("leki", "slownik_substancji", "slownik_interpretacji", "slownik_icd10", "rozstrzygniecia_okien", "pozycje_usuniete"):
        if k not in d:
            raise DatasetError("DATASET_INVALID: brak sekcji " + k)
    return d, files[0]


def today_warsaw():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()
    except Exception:
        return dt.date.today().isoformat()


def add_months(iso, n):
    d = dt.date.fromisoformat(iso)
    idx = d.month - 1 + n
    y, mo = d.year + idx // 12, idx % 12 + 1
    return dt.date(y, mo, min(d.day, calendar.monthrange(y, mo)[1])).isoformat()


def freshness(d, today):
    m = d["metadata"]
    if m.get("superseded_by"):
        return "SUPERSEDED"
    ro = d["rozstrzygniecia_okien"]
    sc = ro.get("successor") if ro.get("stan") == "APPLIED" else None
    if sc and sc.get("state") == "PROMOTED" and sc["valid_from"] <= today and sc["dataset_id"] != m["dataset_id"]:
        return "SUPERSEDED_SUCCESSOR_NOT_DEPLOYED"
    if today < m["valid_from"]:
        return "DATASET_NOT_YET_EFFECTIVE"
    fm = m["freshness_manifest"]
    if fm.get("check_valid_until") and today >= fm["check_valid_until"]:
        return "SOURCE_CHECK_STALE"
    if today >= add_months(m["valid_from"], m.get("freshness_rule", {}).get("cykl_miesiecy", 3)):
        return "EXPECTED_REPLACEMENT_DATE_REACHED"
    return "CURRENT_SOURCE_NOT_EXTERNALLY_CONFIRMED"


def key_ok(d, r):
    dsid = d["metadata"]["dataset_id"]
    return r.get("dataset_id") == dsid and r.get("version_key") == "%s|%s" % (dsid, r.get("rekord_id"))


# ------------------------------------------------------------------ wyszukiwanie leku
def norm(s):
    s = str(s).replace("ł", "l").replace("Ł", "L")
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()
    s = s.replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", s).strip()


def alias_hit(alias, q):
    return alias.startswith(q) or any(w.startswith(q) for w in re.split(r"[\s+()]+", alias) if w)


def resolve(d, query):
    leki = d["leki"]
    if query.get("gtin"):
        g = str(query["gtin"]).strip()
        recs = [r for r in leki if r["gtin"] == g]
        if recs:
            return {"status": "RESOLVED", "via": "gtin", "records": recs}
        rem = [p for p in d["pozycje_usuniete"]["pozycje"] if p["gtin"] == g]
        return {"status": "REMOVED" if rem else "UNRESOLVED", "via": "gtin", "records": [], "removed": rem}
    term = query.get("medication") or query.get("substance") or ""
    q = norm(term)
    if len(q) < 3:
        return {"status": "UNRESOLVED", "via": "name", "records": [], "reason": "nazwa krótsza niż 3 znaki"}
    toks = q.split(" ")
    rest = toks[1:]
    rest_ok = lambda r: all(t in norm(r["nazwa_postac_dawka"] + " " + r["zawartosc_opakowania"]) for t in rest)
    parents, forms = {}, {}
    for s in d["slownik_substancji"]["substancje"]:
        parents[s["klucz"]] = [norm(a) for a in s["aliasy"]]
        for f in s["formy"]:
            if f.get("aliasy"):
                forms[f["klucz"]] = [norm(a) for a in f["aliasy"]]
    hit_parents = {k for k, al in parents.items() if any(alias_hit(a, q) for a in al)}
    if hit_parents:
        return {"status": "RESOLVED", "via": "substancja", "records": [r for r in leki if r["substancja_parent"] in hit_parents]}
    hit_forms = {k for k, al in forms.items() if any(alias_hit(a, q) for a in al)}
    if hit_forms:
        return {"status": "RESOLVED", "via": "forma", "records": [r for r in leki if r["substancja_kanoniczna"] in hit_forms]}
    if rest and len(toks[0]) >= 3:
        hp = {k for k, al in parents.items() if any(alias_hit(a, toks[0]) for a in al)}
        recs = [r for r in leki if r["substancja_parent"] in hp and rest_ok(r)]
        if recs:
            return {"status": "RESOLVED", "via": "substancja+dawka", "records": recs}
    recs = [r for r in leki if len(toks[0]) >= 3 and toks[0] in norm(r["nazwa_postac_dawka"].split(",")[0]) and rest_ok(r)]
    if recs:
        return {"status": "RESOLVED", "via": "preparat", "records": recs}
    rem = [p for p in d["pozycje_usuniete"]["pozycje"]
           if toks[0] in norm(p["nazwa_postac_dawka"].split(",")[0]) and all(t in norm(p["nazwa_postac_dawka"] + " " + p["zawartosc_opakowania"]) for t in rest)]
    if rem:
        return {"status": "REMOVED", "via": "preparat", "records": [], "removed": rem}
    return {"status": "UNRESOLVED", "via": "name", "records": []}


# ------------------------------------------------------------------ ICD i okna
def norm_code(c):
    c = str(c).strip().upper().replace(" ", "").replace(",", ".")
    m = re.fullmatch(r"([A-Z])(\d{2})(?:\.(\d{1,2}))?", c)
    return (m.group(1) + m.group(2) + ("." + m.group(3) if m.group(3) else "")) if m else None


def covers(tok, q):
    if tok == "F00-F99":
        return "full" if q[0] == "F" else None
    if tok == q or q.startswith(tok + "."):
        return "full"
    if tok.startswith(q + "."):
        return "part"
    return None


def match_indication(w, codes):
    best = None
    rank = {"lit": 3, "int": 2, "com": 1}
    pairs = [(c, "lit") for c in w["kody_literalne"]] + [(c, "int") for c in w["kody_interpretowane"]] + \
            [(c, "com") for c in w.get("kody_interpretowane_wspolistniejace", [])]
    for q in codes:
        for c, src in pairs:
            k = covers(c, q)
            if not k:
                continue
            score = (1 if k == "full" else 0, rank[src])
            if best is None or score > best["score"]:
                best = {"score": score, "code": c, "query_code": q, "source": src, "kind": k}
    return best


def window_status(d, r, w, seg_index, today):
    o = w["okno_decyzji"]
    if not o or o.get("status_parsowania") != "PARSED":
        st = "UNKNOWN"
    elif today < o["decyzja_od"]:
        st = "NOT_YET_EFFECTIVE_TECHNICAL"
    elif today < o["decyzja_do_technical"]:
        st = "IN_FORCE_BY_DECISION_WINDOW"
    else:
        st = "ELAPSED_TECHNICAL"
    notes = []
    ro = d["rozstrzygniecia_okien"]
    if ro.get("stan") == "APPLIED" and st not in IN_FORCE:
        e = next((x for x in ro["wyniki"] if x["rekord_id"] == r["rekord_id"] and x["typ"] == w["typ"] and x["segment"] == seg_index), None)
        sid = ro["successor"]["dataset_id"]
        if e and e["wynik"] == "NEW_DECISION":
            if e["successor_od"] <= today < e["successor_do_technical"]:
                if e["successor_poziom"] == r["poziom_odplatnosci"]:
                    st = "IN_FORCE_BY_SUCCESSOR_DOCUMENT"
                    notes.append("RES-1: " + sid)
                else:
                    notes.append("wykaz następca %s: okno od %s, poziom %s (różny)" % (sid, e["successor_od"], e["successor_poziom"]))
            elif e["successor_od"] > today:
                notes.append("wykaz następca %s deklaruje okno od %s" % (sid, e["successor_od"]))
        elif e and e["wynik"] in ("GTIN_ABSENT", "SEGMENT_NOT_MATCHED", "AMBIGUOUS", "SUCCESSOR_WINDOW_UNKNOWN"):
            notes.append("wykaz następca %s: %s" % (sid, e["wynik"]))
    return st, o, notes


def fact_id_condition(w):
    return "warunek:" + hashlib.sha256(w["tekst"].encode("utf-8")).hexdigest()[:10]


# ------------------------------------------------------------------ ocena
def evaluate(d, case, today=None):
    today = today or case.get("today") or today_warsaw()
    m = d["metadata"]
    fr = freshness(d, today)
    blocked = fr in BLOCKING
    codes = [c for c in (norm_code(x) for x in case.get("icd10_confirmed", [])) if c]
    answers = case.get("condition_answers", {})
    out = {"engine_version": ENGINE_VERSION, "dataset_id": m["dataset_id"], "today": today, "freshness_status": fr,
           "query": case.get("query", {}), "icd10_confirmed": codes, "results": [], "questions": [],
           "potential_indications": [], "uncoded_indications": [], "notes": []}
    res = resolve(d, case.get("query", {}))
    out["query_resolution"] = {"status": res["status"], "via": res["via"], "records": len(res["records"]),
                               "substances": sorted({r["substancja_parent"] for r in res["records"]})}
    if res["status"] == "UNRESOLVED":
        out["summary"] = {"refundation_status": "BRAK_DANYCH", "reason": "POZA ZAKRESEM / WERYFIKACJA WYMAGANA: nazwa lub GTIN nie występuje w datasecie"}
        return out
    if res["status"] == "REMOVED":
        items = []
        for p in res["removed"]:
            items.append({"dataset_id": m["dataset_id"], "version_key": p["poprzedni_version_key"], "LP": p["poprzedni_lp"],
                          "GTIN": p["gtin"], "preparation": p["nazwa_postac_dawka"], "package": p["zawartosc_opakowania"],
                          "indication_literal": None, "indication_type": None,
                          "refundation_status": "NIEPOTWIERDZONY" if blocked else "NIE",
                          "copay": {"poziom": "100%" if not blocked else None, "doplata": None},
                          "decision_window_status": None, "freshness_status": fr, "missing_clinical_facts": [],
                          "provenance": {"podstawa": "§12 — brak w wykazie od " + p["brak_w_wykazie_od"],
                                         "poprzedni_dataset_id": d["pozycje_usuniete"]["poprzedni_dataset_id"],
                                         "aktywny_dataset_id": m["dataset_id"]}})
            items[-1]["verdict_line"] = ("REFUNDACJA: NIE | ODPŁATNOŚĆ: 100%% | PODSTAWA: brak w wykazie %s od %s (poprzednio %s) | KLUCZ POPRZEDNI: %s"
                                         % (m.get("designation") or m["dataset_id"], p["brak_w_wykazie_od"], d["pozycje_usuniete"]["poprzedni_dataset_id"], p["poprzedni_version_key"])
                                         if not blocked else "STATUS BIEŻĄCY: NIEPOTWIERDZONY | dataset: " + fr)
        out["results"] = items
        out["summary"] = {"refundation_status": items[0]["refundation_status"], "counts": {items[0]["refundation_status"]: len(items)}}
        return out
    if not codes:
        out["questions"].append({"fact_id": "icd10_confirmed", "question": "Jakie rozpoznanie (kod ICD-10) ustalono u pacjenta?",
                                 "why": "ocena wskazania refundacyjnego wymaga rozpoznania"})
    qmap, uncoded = {}, {}
    bad_keys = sum(1 for r in d["leki"] if not key_ok(d, r))
    if bad_keys:
        out["notes"].append("DATASET_KEY_CONFLICT: %d rekordów z brakującym lub niezgodnym version_key — NO_VERDICT dla całego zapytania" % bad_keys)
    for r in res["records"]:
        if bad_keys or not key_ok(d, r):
            out["results"].append(item(d, r, None, None, "NO_VERDICT", fr, None, [], {"blad": "brak lub konflikt version_key"}))
            continue
        seg = {"rejestracyjne": 0, "pozarejestracyjne": 0}
        best = None
        for w in r["wskazania"]:
            k = seg[w["typ"]]; seg[w["typ"]] += 1
            if not w["kody_literalne"] and not w["kody_interpretowane"] and not w.get("kody_interpretowane_wspolistniejace"):
                u = uncoded.setdefault((r["substancja_parent"], w["typ"], w["tekst"]), 0)
                uncoded[(r["substancja_parent"], w["typ"], w["tekst"])] = u + 1
                continue
            mt = match_indication(w, codes) if codes else None
            if not mt:
                continue
            ws, o, notes = window_status(d, r, w, k, today)
            missing, status = [], None
            if mt["source"] == "com":
                status = "NIE_SAMODZIELNA_PODSTAWA"
            elif blocked:
                status = "NIEPOTWIERDZONY"
            elif ws not in IN_FORCE:
                status = "NIEPOTWIERDZONY"
            elif mt["kind"] == "part":
                fid = "icd_podkategoria:" + mt["query_code"]
                missing.append({"fact_id": fid, "question": "Jakie rozpoznanie ze szczegółową podkategorią ICD-10 ustalono (wskazanie obejmuje wyłącznie: %s)?" % ", ".join(
                    w["kody_literalne"] + w["kody_interpretowane"])})
                status = "DO_UZUPELNIENIA"
            elif w["warunek_status"] != "NO_CONDITION":
                fid = fact_id_condition(w)
                ans = answers.get(fid)
                if ans == "TAK":
                    status = "TAK"
                elif ans == "NIE":
                    status = "NIE_SPELNIA_WARUNKU"
                else:
                    missing.append({"fact_id": fid, "question": "Czy pacjent spełnia wszystkie warunki zapisane w treści wskazania: „%s”? (TAK / NIE / NIE WIEM)" % w["tekst"]})
                    status = "DO_UZUPELNIENIA"
            else:
                status = "TAK"
            it = item(d, r, w, mt, status, fr, (ws, o, notes), missing, None)
            order = ["TAK", "DO_UZUPELNIENIA", "NIEPOTWIERDZONY", "NIE_SPELNIA_WARUNKU", "NIE_SAMODZIELNA_PODSTAWA"]
            if best is None or order.index(status) < order.index(best["refundation_status"]):
                best = it
        if best:
            out["results"].append(best)
            for mf in best["missing_clinical_facts"]:
                q = qmap.setdefault(mf["fact_id"], {**mf, "affected": 0})
                q["affected"] += 1
    out["questions"] += sorted(qmap.values(), key=lambda x: x["fact_id"])
    out["uncoded_indications"] = [{"substancja_parent": k[0], "indication_type": k[1], "indication_literal": k[2], "records": v}
                                  for k, v in sorted(uncoded.items())]
    # PASS B — tylko hipotezy z dodatnią przesłanką
    for h in case.get("hypotheses", []):
        hc = norm_code(h.get("code", ""))
        if not hc or hc in codes or h.get("status", "ACTIVE") not in ("ACTIVE",):
            continue
        if not h.get("positive_clues"):
            out["notes"].append("PASS_B: hipoteza %s pominięta — brak dodatniej przesłanki klinicznej" % hc)
            continue
        sub = evaluate(d, {**case, "icd10_confirmed": [hc], "hypotheses": [], "condition_answers": answers}, today)
        found = {}
        have = {(x["indication_literal"], x["indication_type"]) for x in out["results"] if x["refundation_status"] == "TAK"}
        for x in sub["results"]:
            if (x["indication_literal"], x["indication_type"]) in have:
                continue
            key = (x["indication_literal"], x["indication_type"], x["refundation_status"], x["copay"]["poziom"])
            found[key] = found.get(key, 0) + 1
        for (lit, typ, st, lvl), n in sorted(found.items(), key=lambda z: str(z)):
            out["potential_indications"].append({"hypothesis": hc, "status": "HIPOTEZA_DO_WERYFIKACJI", "positive_clues": h["positive_clues"],
                                                 "indication_literal": lit, "indication_type": typ,
                                                 "po_potwierdzeniu": {"refundation_status": st, "poziom": lvl, "records": n}})
    cnt = {}
    for x in out["results"]:
        cnt[x["refundation_status"]] = cnt.get(x["refundation_status"], 0) + 1
    prio = ["TAK", "DO_UZUPELNIENIA", "NIEPOTWIERDZONY", "NIE_SPELNIA_WARUNKU", "NIE_SAMODZIELNA_PODSTAWA"]
    if bad_keys or (cnt and set(cnt) == {"NO_VERDICT"}):
        overall = "NO_VERDICT"
    else:
        overall = next((s for s in prio if cnt.get(s)), "DO_UZUPELNIENIA" if not codes else "BRAK_DANYCH")
    out["summary"] = {"refundation_status": overall, "counts": cnt, "records_evaluated": len(res["records"])}
    if overall == "BRAK_DANYCH":
        out["summary"]["reason"] = ("brak skodowanego wskazania obejmującego rozpoznanie; brak dopasowania nie oznacza braku refundacji"
                                    + ("; wskazania nieskodowane: %d" % len(out["uncoded_indications"]) if out["uncoded_indications"] else ""))
    out["grouped"] = group(out["results"])
    return out


def item(d, r, w, mt, status, fr, win, missing, err):
    m = d["metadata"]
    ws, o, notes = win if win else (None, None, [])
    lbl = m.get("designation") or m["dataset_id"]
    interp = None
    if mt and mt["source"] in ("int", "com"):
        e = next((x for x in d["slownik_interpretacji"] if mt["code"] in x["kody"]), None)
        interp = {"kod": mt["code"], "source_id": e and e.get("source_id"), "verification_status": e and e.get("verification_status"),
                  "zakres_mapowania": e and e.get("zakres_mapowania")}
    it = {"dataset_id": m["dataset_id"], "version_key": r.get("version_key"), "LP": r["pozycja_zrodlowa"]["lp_w_wykazie"],
          "GTIN": r["gtin"], "preparation": r["nazwa_postac_dawka"], "package": r["zawartosc_opakowania"],
          "substance_source": r["substancja_czynna_zrodlo"], "substance_parent": r["substancja_parent"],
          "limit_group": r["grupa_limitowa"],
          "indication_literal": w["tekst"] if w else None, "indication_type": w["typ"] if w else None,
          "refundation_status": status,
          "copay": {"poziom": r["poziom_odplatnosci"] if status != "NO_VERDICT" else None,
                    "doplata": r["doplata_swiadczeniobiorcy"] if status != "NO_VERDICT" else None,
                    "zakres": "pozycja A1, bez uprawnień dodatkowych; cena 100%: BRAK DANYCH"},
          "decision_window_status": ws,
          "decision_window": ({"od": o["decyzja_od"], "do_technical": o["decyzja_do_technical"], "okres": o["decyzja_okres"]}
                              if o and o.get("status_parsowania") == "PARSED" else (o or None)),
          "freshness_status": fr,
          "match": ({"kod_wskazania": mt["code"], "kod_rozpoznania": mt["query_code"], "zrodlo_kodu": {"lit": "literalny", "int": "interpretowany", "com": "wspolistnienie"}[mt["source"]],
                     "zakres": mt["kind"], "interpretacja": interp} if mt else None),
          "condition_status": w["warunek_status"] if w else None,
          "missing_clinical_facts": missing,
          "provenance": {"source_document": m["source_document"], "base_act": m.get("base_act"), "row_xlsx": r["pozycja_zrodlowa"]["wiersz_xlsx"],
                         "rule_versions": {"engine": ENGINE_VERSION, "okno": (o or {}).get("rule_version")}, "notes": notes, **(err or {})}}
    if status == "NO_VERDICT":
        it["verdict_line"] = "NO_VERDICT — brak lub konflikt version_key (rekord %s)" % r.get("rekord_id")
    else:
        okno = ("%s–%s (%s)" % (o["decyzja_od"], o["decyzja_do_technical"], o["decyzja_okres"]) if o and o.get("status_parsowania") == "PARSED"
                else "UNKNOWN" + (" (%s)" % o.get("powod") if o and o.get("powod") else ""))
        head = "REFUNDACJA: TAK" if status == "TAK" else "STATUS: " + status
        it["verdict_line"] = ("%s | ODPŁATNOŚĆ WG %s: %s | DOPŁATA: %s zł | OKNO DECYZJI: %s | STATUS OKNA: %s | DATASET: %s | LP %s | KLUCZ: %s%s"
                              % (head, lbl, r["poziom_odplatnosci"], r["doplata_swiadczeniobiorcy"], okno, ws, fr,
                                 r["pozycja_zrodlowa"]["lp_w_wykazie"], r["version_key"], (" | " + "; ".join(notes)) if notes else ""))
    return it


def group(results):
    g = {}
    for x in results:
        k = (x["substance_parent"], x["limit_group"], x["indication_type"], x["indication_literal"], x["refundation_status"],
             x["copay"]["poziom"], x["decision_window_status"])
        e = g.setdefault(k, {"substance_parent": k[0], "limit_group": k[1], "indication_type": k[2], "indication_literal": k[3],
                             "refundation_status": k[4], "poziom": k[5], "decision_window_status": k[6], "records": 0,
                             "doplata_min": None, "doplata_max": None, "przyklady": []})
        e["records"] += 1
        if x["copay"]["doplata"] is not None:
            v = float(x["copay"]["doplata"].replace(",", "."))
            e["doplata_min"] = v if e["doplata_min"] is None else min(e["doplata_min"], v)
            e["doplata_max"] = v if e["doplata_max"] is None else max(e["doplata_max"], v)
        if len(e["przyklady"]) < 3:
            e["przyklady"].append({"LP": x["LP"], "version_key": x["version_key"], "preparation": x["preparation"], "package": x["package"]})
    return list(g.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--today", default=None)
    a = ap.parse_args()
    case = json.load(sys.stdin) if a.case == "-" else json.load(open(a.case, encoding="utf-8"))
    try:
        d, path = load_active(a.dataset_dir)
    except DatasetError as e:
        json.dump({"engine_version": ENGINE_VERSION, "summary": {"refundation_status": "NO_VERDICT", "reason": str(e)}, "results": []},
                  sys.stdout, ensure_ascii=False, indent=1)
        return 3
    out = evaluate(d, case, a.today)
    out["dataset_file"] = os.path.basename(path)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
