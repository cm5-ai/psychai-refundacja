"""Generator leki[] z arkusza A1 wykazu MZ. Kontrakt odtworzony z datasetu 83W (FG-1)."""
import re, json, calendar, datetime as dt, openpyxl
from normtxt import norm_text

MARK = re.compile(r'<(\d+)>')

def split_cell(v):
    """-> (marked:bool, [(markers:tuple, text)])"""
    if v is None: return False, []
    s = str(v).strip()
    if s == '' or s.lower() == 'x': return False, []
    if not MARK.search(s):
        return False, [((), clean(s))]
    parts = re.split(r'((?:<\d+>)+)', s)
    out = []; i = 1
    while i < len(parts):
        ms = tuple(int(m) for m in MARK.findall(parts[i])); txt = clean(parts[i+1] if i+1 < len(parts) else '')
        if txt and txt.lower() != 'x': out.append((ms, txt))
        i += 2
    return True, out

def clean(t):
    t = t.strip()
    while t.endswith(';'): t = t[:-1].rstrip()
    return t

def col_parts(v):
    """F/G -> {'N': str|None, 'O': str|None} or {'*': str}"""
    s = '' if v is None else str(v).strip()
    m = re.match(r'^(.*?)\s+-\s+dla kolumny N,\s*(.*?)\s+-\s+dla kolumny O$', s)
    if m: return {'N': m.group(1).strip(), 'O': m.group(2).strip()}
    m = re.match(r'^(.*?)\s+-\s+dla kolumny ([NO])$', s)
    if m: return {m.group(2): m.group(1).strip()}
    return {'*': s}

def marked_values(s):
    """'<1>a/<2><3>b' -> {1:a,2:b,3:b}; unmarked -> None"""
    if not MARK.search(s): return None
    out = {}
    for grp, val in re.findall(r'((?:<\d+>)+)([^<]*)', s):
        val = val.strip().rstrip('/').strip()
        for m in MARK.findall(grp): out[int(m)] = val
    return out

def add_period(od, okres):
    d = dt.date.fromisoformat(od); y = mo = 0
    for n, u in re.findall(r'(\d+)\s*(lat[a]?|rok|rok[u]?|miesi\w*)', okres):
        n = int(n)
        if u.startswith('miesi'): mo += n
        else: y += n
    if y == 0 and mo == 0: raise ValueError(okres)
    tot = d.month - 1 + mo; yy = d.year + y + tot // 12; mm = tot % 12 + 1
    dd = min(d.day, calendar.monthrange(yy, mm)[1])
    return dt.date(yy, mm, dd).isoformat()

def windows(F, G, col, segs, cell_marked):
    fp, gp = col_parts(F), col_parts(G)
    f = fp.get(col, fp.get('*')); g = gp.get(col, gp.get('*'))
    unk = lambda why: {"status_parsowania": "UNKNOWN", "powod": why, "rule_version": "FG-1"}
    if f is None or g is None or f == '' or g == '':
        return [unk("brak F/G dla kolumny")] * len(segs)
    fm, gm = marked_values(f), marked_values(g)
    cell_marks = set(m for ms, _ in segs for m in ms)
    res = []
    for ms, _ in segs:
        try:
            if fm is None: od = f
            else:
                if not cell_marked or set(fm) != cell_marks: res.append(unk("markery F/G różne od markerów komórki")); continue
                od = fm[ms[0]]
            if gm is None: ok = g
            else:
                if not cell_marked or set(gm) != cell_marks: res.append(unk("markery F/G różne od markerów komórki")); continue
                ok = gm[ms[0]]
            dt.date.fromisoformat(od)
            res.append({"status_parsowania": "PARSED", "decyzja_od": od, "decyzja_okres": ok,
                        "decyzja_do_technical": add_period(od, ok), "rule_version": "FG-1"})
        except Exception as e:
            res.append(unk("nieparsowalne F/G: %s" % e))
    return res

LIT = re.compile(r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b')

def build_leki(xlsx, dataset_id, prefixes, subst_dict, rejestr):
    ws = openpyxl.load_workbook(xlsx, read_only=True)['A1']
    by_src = {}
    for s in subst_dict['substancje']:
        for f in s['formy']:
            for n in f['nazwy_zrodlowe']: by_src[n] = (s['klucz'], f['klucz'])
    reg = {w['norm_text']: w for w in rejestr['wpisy']}
    leki, problems, new_texts = [], [], {}
    rid = 0
    for i, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if i < 3 or row[0] is None: continue
        grp = str(row[7] or '')
        if not any(grp.startswith(p) for p in prefixes): continue
        rid += 1
        src = str(row[1]).strip()
        par, kan = by_src.get(src, (None, None))
        if par is None: problems.append(('NOWA_SUBSTANCJA', i, src))
        wsk = []
        for col, idx, typ in (('N', 13, 'rejestracyjne'), ('O', 14, 'pozarejestracyjne')):
            marked, segs = split_cell(row[idx])
            for (ms, txt), okno in zip(segs, windows(row[5], row[6], col, segs, marked)):
                e = reg.get(norm_text(txt))
                if e is None:
                    new_texts.setdefault(norm_text(txt), txt)
                    ws_, ki, kw = "UNKNOWN", [], []
                else:
                    ws_, ki, kw = e['warunek_status'], e['kody_interpretowane'], e['kody_interpretowane_wspolistniejace']
                wsk.append({"tekst": txt, "typ": typ, "kody_literalne": LIT.findall(txt),
                            "kody_interpretowane": list(ki), "warunek_w_zapisie": ws_ != "NO_CONDITION",
                            "okno_decyzji": okno, "kody_interpretowane_wspolistniejace": list(kw),
                            "warunek_status": ws_})
        leki.append({"version_key": "%s|%d" % (dataset_id, rid), "dataset_id": dataset_id, "rekord_id": rid,
                     "pozycja_zrodlowa": {"arkusz": "A1", "wiersz_xlsx": i, "lp_w_wykazie": str(row[0]).strip()},
                     "substancja_czynna_zrodlo": src, "substancja_parent": par, "substancja_kanoniczna": kan,
                     "nazwa_postac_dawka": str(row[2]).strip(), "zawartosc_opakowania": str(row[3]).strip(),
                     "gtin": str(row[4]).strip(), "grupa_limitowa": grp,
                     "poziom_odplatnosci": str(row[15]).strip(), "doplata_swiadczeniobiorcy": str(row[16]).strip(),
                     "wskazania": wsk,
                     "decyzja_zrodlo": {"termin_wejscia_w_zycie": str(row[5]).strip(), "okres_obowiazywania": str(row[6]).strip()}})
    return leki, problems, new_texts
