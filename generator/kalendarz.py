"""KALENDARZ DLA PACJENTA — wydruk HTML schematu dawkowania (titracja / odstawienie / zamiana).
Wejście: JSON (stdin albo plik). Liczby WYŁĄCZNIE z decyzji lekarza lub źródła zamiany (19 SWITCH_GATEWAY).
Bez danych identyfikujących pacjenta. Wyjście: plik HTML do druku (A4).
JSON: {"tytul": "...", "start": "RRRR-MM-DD", "kroki": [{"dni": 7, "leki": [{"nazwa": "Trittico CR 75 mg", "rano": "", "poludnie": "", "wieczor": "1/3"}]}],
       "uwagi": ["..."], "kontakt": "..."}"""
import json, sys, datetime, html

FR = {"1/4": "¼", "1/3": "⅓", "1/2": "½", "2/3": "⅔", "3/4": "¾"}
def tabl_svg(u):
    u = (u or "").strip()
    if not u: return ""
    cz = {"1/4": (1, 4), "1/3": (1, 3), "1/2": (1, 2), "2/3": (2, 3), "3/4": (3, 4)}.get(u)
    if not cz:
        try: n = float(u.replace(",", ".")); cz = (int(n), 1) if n == int(n) else None
        except Exception: cz = None
    if not cz or cz[1] == 1:
        return '<span class="d">%s</span>' % html.escape(u) + (" tabl." if cz else "")
    a, b = cz; w = 36; seg = w / b; s = ['<svg width="%d" height="18" viewBox="0 0 %d 18"><rect x="0.5" y="0.5" rx="8" width="%d" height="17" fill="#fff" stroke="#333"/>' % (w + 2, w + 2, w)]
    for i in range(a): s.append('<rect x="%.1f" y="1" width="%.1f" height="16" fill="#4a7" %s/>' % (1 + i * seg, seg, 'rx="7"' if i == 0 else ""))
    for i in range(1, b): s.append('<line x1="%.1f" y1="1" x2="%.1f" y2="17" stroke="#333" stroke-dasharray="2,1"/>' % (1 + i * seg, 1 + i * seg))
    s.append("</svg>")
    return "".join(s) + ' <span class="d">%s tabl.</span>' % FR.get(u, u)

def main():
    src = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    k = json.load(open(src, encoding="utf-8")) if src else json.load(sys.stdin)
    out = sys.argv[2] if len(sys.argv) > 2 else "kalendarz.html"
    d0 = datetime.date.fromisoformat(k["start"]); DNI = ["pon", "wt", "śr", "czw", "pt", "sob", "nd"]
    rows, d = [], d0
    for n, kr in enumerate(k["kroki"], 1):
        kon = d + datetime.timedelta(days=kr["dni"] - 1)
        leki = "".join('<tr><td class="lek">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (html.escape(l["nazwa"]), tabl_svg(l.get("rano")), tabl_svg(l.get("poludnie")), tabl_svg(l.get("wieczor"))) for l in kr["leki"])
        dni = "".join('<span class="box">%s<br>%s.%s</span>' % (DNI[(d + datetime.timedelta(i)).weekday()], (d + datetime.timedelta(i)).day, (d + datetime.timedelta(i)).month) for i in range(kr["dni"]))
        rows.append('<section><h2>Etap %d: %s – %s <small>(%d dni)</small></h2><table><tr><th>Lek</th><th>Rano</th><th>Południe</th><th>Wieczór</th></tr>%s</table><div class="dni">%s</div></section>'
                    % (n, d.strftime("%d.%m.%Y"), kon.strftime("%d.%m.%Y"), kr["dni"], leki, dni))
        d = kon + datetime.timedelta(days=1)
    uw = "".join("<li>%s</li>" % html.escape(u) for u in k.get("uwagi", []))
    doc = """<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>%s</title><style>
body{font-family:Arial,sans-serif;max-width:190mm;margin:10mm auto;color:#111;font-size:12pt}h1{font-size:18pt;margin:0 0 4mm}
h2{font-size:13pt;margin:6mm 0 2mm}small{color:#555;font-weight:normal}table{border-collapse:collapse;width:100%%}
th,td{border:1px solid #999;padding:2mm;text-align:center}td.lek{text-align:left;font-weight:bold}.dni{margin-top:2mm}
.box{display:inline-block;border:1px solid #999;width:13mm;height:13mm;margin:0.5mm;font-size:8pt;text-align:center;vertical-align:top;padding-top:1mm}
.d{font-size:13pt;font-weight:bold}section{page-break-inside:avoid}ul{margin-top:2mm}@media print{body{margin:8mm}}
</style></head><body><h1>%s</h1><p>Po przyjęciu dawki danego dnia zaznacz kratkę.</p>%s%s%s</body></html>""" % (
        html.escape(k.get("tytul", "Plan przyjmowania leków")), html.escape(k.get("tytul", "Plan przyjmowania leków")), "".join(rows),
        ("<h2>Ważne</h2><ul>%s</ul>" % uw) if uw else "", ("<p><b>Kontakt:</b> %s</p>" % html.escape(k["kontakt"])) if k.get("kontakt") else "")
    open(out, "w", encoding="utf-8").write(doc); print("KALENDARZ:", out, "| etapy:", len(k["kroki"]), "| od", d0, "do", d - datetime.timedelta(days=1))

if __name__ == "__main__": main()
