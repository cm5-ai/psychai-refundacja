"""Buduje REFUNDACJA_DATA.json z załącznika MZ (xlsx, arkusz A1).
Słowniki kuratorskie i reguły bierze 1:1 z poprzedniego datasetu.
Użycie:
  python3 generator/build.py --xlsx X.xlsx --poprzedni REFUNDACJA_DATA.json \
     --oznaczenie 84W --valid-from 2026-10-01 --data-aktu 2026-09-16 --poz 70 \
     --check-valid-until 2027-01-01 --url URL --wyjscie out.json --raport raport.md
Kody wyjścia: 0 = OK; 2 = blokada (nowa substancja / nowy tekst / zła struktura)."""
import argparse, json, hashlib, copy, sys, os, datetime, collections, openpyxl
sys.path.insert(0, os.path.dirname(__file__))
from gen_leki import build_leki
from serialize import dumps

MIES = {1: 'stycznia', 4: 'kwietnia', 7: 'lipca', 10: 'października'}
HEAD = ['LP', 'Substancja czynna', 'Nazwa  postać i dawka', 'Zawartość opakowania']

def main():
    a = argparse.ArgumentParser()
    for k in ('xlsx', 'poprzedni', 'oznaczenie', 'valid-from', 'data-aktu', 'poz', 'check-valid-until', 'url', 'wyjscie', 'raport'):
        a.add_argument('--' + k, required=k not in ('url',))
    a.add_argument('--pozwol-nowe-teksty', action='store_true')
    x = a.parse_args()
    ref = json.load(open(x.poprzedni, encoding='utf-8'))
    ws = openpyxl.load_workbook(x.xlsx, read_only=True)['A1']
    hdr = [str(c).strip() if c else '' for c in next(ws.iter_rows(min_row=2, max_row=2, values_only=True))]
    if hdr[:4] != HEAD or len(hdr) != 17 or not hdr[13].startswith('Zakres wskazań objętych') or not hdr[16].startswith('Wysokość dopłaty'):
        print('BLOKADA: zmieniony układ kolumn arkusza A1:', hdr); sys.exit(2)
    d = copy.deepcopy(ref); m = d['metadata']
    SHA = hashlib.sha256(open(x.xlsx, 'rb').read()).hexdigest()
    DID = '%s|%s|%s' % (x.oznaczenie, x.valid_from, SHA[:12])
    leki, prob, new = build_leki(x.xlsx, DID, m['zakres_danych']['grupy_limitowe_prefiksy'], d['slownik_substancji'], d['rejestr_tekstow_wskazan'])
    blok = []
    if prob: blok.append('NOWE SUBSTANCJE bez wpisu w slownik_substancji: %s' % prob)
    if new and not x.pozwol_nowe_teksty: blok.append('NOWE TEKSTY WSKAZAŃ (warunek UNKNOWN, bez kodów interpretowanych): %d' % len(new))
    d['leki'] = leki
    wb = openpyxl.load_workbook(x.xlsx, read_only=True); cells = set()
    for sh in wb.sheetnames:
        for row in wb[sh].iter_rows(values_only=True):
            for c in row:
                if c is not None: cells.add(str(c).strip())
    g_new = {r['gtin'] for r in leki}; seen = set(); rem = []
    for r in ref['leki']:
        g = r['gtin']
        if g in g_new or g in seen or g in cells: continue
        seen.add(g)
        rem.append({"gtin": g, "nazwa_postac_dawka": r['nazwa_postac_dawka'], "zawartosc_opakowania": r['zawartosc_opakowania'],
                    "substancja_parent": r['substancja_parent'], "poprzedni_version_key": r['version_key'],
                    "poprzedni_lp": r['pozycja_zrodlowa']['lp_w_wykazie'], "brak_w_wykazie_od": x.valid_from})
    d['pozycje_usuniete'] = {"poprzedni_dataset_id": ref['metadata']['dataset_id'],
        "semantyka": "GTIN obecny w zakresie poprzedniego wykazu i nieobecny w ŻADNYM arkuszu nowego załącznika. GTIN przeniesiony do innego arkusza lub poza zakres grup NIE jest tu wpisywany.",
        "pozycje": rem}
    d['rozstrzygniecia_okien'] = {"resolver": "RES-1", "stan": "SUCCESSOR_NOT_AVAILABLE", "rule_version": "FG-1", "successor": None, "wyniki": []}
    vf = datetime.date.fromisoformat(x.valid_from); da = datetime.date.fromisoformat(x.data_aktu)
    na = 'na 1 %s %d r.' % (MIES.get(vf.month, str(vf.month)), vf.year)
    dz = '%d %s %d r.' % (da.day, ['stycznia','lutego','marca','kwietnia','maja','czerwca','lipca','sierpnia','września','października','listopada','grudnia'][da.month-1], da.year)
    L = leki
    m.update({"dataset_id": DID,
      "source_document": "Załącznik do obwieszczenia Ministra Zdrowia z dnia %s w sprawie wykazu refundowanych leków, środków spożywczych specjalnego przeznaczenia żywieniowego oraz wyrobów medycznych (Dz. Urz. Min. Zdrow. poz. %s), oznaczenie %s; plik %s, arkusz A1" % (dz, x.poz, x.oznaczenie, os.path.basename(x.xlsx)),
      "source_date": x.data_aktu, "effective_date": x.valid_from, "valid_from": x.valid_from, "valid_until": None, "superseded_by": None,
      "generated_at": datetime.date.today().isoformat(), "record_count": len(L),
      "substancje_count": len({r['substancja_czynna_zrodlo'] for r in L}),
      "preparaty_count": len({(r['nazwa_postac_dawka'], r['zawartosc_opakowania']) for r in L}),
      "gtin_count": len({r['gtin'] for r in L}),
      "substancje_kanoniczne_count": len({r['substancja_kanoniczna'] for r in L}),
      "substancje_parent_count": len({r['substancja_parent'] for r in L}),
      "dataset_id_legacy": "REFUNDACJA_DATA/%s/%s" % (x.oznaczenie, x.valid_from), "designation": x.oznaczenie,
      "designation_source": "Prefiks załączników MZ do obwieszczenia z %s (%s); akt: Dz. Urz. Min. Zdrow. poz. %s." % (x.data_aktu, os.path.basename(x.xlsx), x.poz),
      "base_act": {"tytul": "Obwieszczenie Ministra Zdrowia z dnia %s w sprawie wykazu refundowanych leków, środków spożywczych specjalnego przeznaczenia żywieniowego oraz wyrobów medycznych %s" % (dz, na),
                   "dz_urz": "Dz. Urz. Min. Zdrow. poz. %s" % x.poz, "data": x.data_aktu, "valid_from": x.valid_from, "url": x.url or ""},
      "acts_out_of_scope_A1": [], "acts_verified_at": datetime.date.today().isoformat(),
      "build_note": "generator/build.py (FG-1). Słowniki kuratorskie 1:1 z %s; nowe teksty: %d, nowe substancje: %d." % (ref['metadata']['dataset_id'], len(new), len(prob)),
      "freshness_manifest": {"tryb": "MANUAL_SOURCE_INGESTION", "last_successful_check": datetime.date.today().isoformat(), "check_valid_until": x.check_valid_until}})
    m['source_file'] = dict(m['source_file'], nazwa=os.path.basename(x.xlsx), sha256=SHA)
    m['zakres_danych']['grupy_limitowe_objete'] = sorted({r['grupa_limitowa'] for r in L})
    kc = m['kontrola_choroby_psychiczne']; rr = [r for r in L if any(kc['fraza_literalna'] in w['tekst'] for w in r['wskazania'])]
    kc.update({"liczba_rekordow": len(rr), "substancje_count": len({r['substancja_czynna_zrodlo'] for r in rr}),
               "substancje": sorted({r['substancja_czynna_zrodlo'] for r in rr}),
               "substancje_kanoniczne_count": len({r['substancja_kanoniczna'] for r in rr}),
               "substancje_parent_count": len({r['substancja_parent'] for r in rr})})
    out = dumps(d); open(x.wyjscie, 'w', encoding='utf-8').write(out)
    sha = hashlib.sha256(out.encode()).hexdigest()
    # raport zmian
    A = collections.defaultdict(list); B = collections.defaultdict(list)
    for r in ref['leki']: A[r['gtin']].append(r)
    for r in L: B[r['gtin']].append(r)
    wsk = collections.defaultdict(lambda: [0, set(), set()]); poz = []; dop = 0
    for g in set(A) & set(B):
        if [q['poziom_odplatnosci'] for q in A[g]] != [q['poziom_odplatnosci'] for q in B[g]]: poz.append((A[g][0]['nazwa_postac_dawka'], [q['poziom_odplatnosci'] for q in A[g]], [q['poziom_odplatnosci'] for q in B[g]]))
        if [q['doplata_swiadczeniobiorcy'] for q in A[g]] != [q['doplata_swiadczeniobiorcy'] for q in B[g]]: dop += 1
        ta = {(w['typ'], w['tekst']) for q in A[g] for w in q['wskazania']}; tb = {(w['typ'], w['tekst']) for q in B[g] for w in q['wskazania']}
        if ta != tb:
            s = A[g][0]['substancja_parent']; wsk[s][0] += 1; wsk[s][1] |= ta - tb; wsk[s][2] |= tb - ta
    R = ['# Raport wykazu %s (od %s)' % (x.oznaczenie, x.valid_from), '', 'dataset_id: `%s`  ' % DID, 'sha256 danych: `%s`  ' % sha, 'rekordy: %d (poprzednio %d)' % (len(L), len(ref['leki'])), '']
    if blok: R += ['## BLOKADY', ''] + ['- ' + b for b in blok] + ['']
    if new: R += ['## Nowe teksty wskazań (bez kodów interpretowanych)', ''] + ['- ' + t for t in new.values()] + ['']
    R += ['## Usunięte z wykazu (%d) — silnik: REFUNDACJA: NIE od %s' % (len(rem), x.valid_from), ''] + ['- %s %s %s (LP %s)' % (p['substancja_parent'], p['nazwa_postac_dawka'], p['zawartosc_opakowania'], p['poprzedni_lp']) for p in rem] + ['']
    nowe = [r for r in L if r['gtin'] not in A]
    R += ['## Nowe pozycje (%d)' % len({r['gtin'] for r in nowe}), ''] + sorted({'- %s %s %s — %s' % (r['substancja_parent'], r['nazwa_postac_dawka'], r['zawartosc_opakowania'], r['poziom_odplatnosci']) for r in nowe}) + ['']
    R += ['## Zmiany wskazań', ''] + ['- **%s** (%d poz.): usunięto %s; dodano %s' % (s, v[0], sorted(t for _, t in v[1]), sorted(t for _, t in v[2])) for s, v in wsk.items()] + ['']
    R += ['## Zmiany poziomu odpłatności: %d' % len(poz), ''] + ['- %s: %s -> %s' % p for p in poz] + ['', 'Zmiany dopłat: %d pozycji' % dop, '']
    open(x.raport, 'w', encoding='utf-8').write('\n'.join(R))
    print(DID, sha, 'rekordy', len(L), 'usuniete', len(rem), 'nowe_teksty', len(new), 'blokady', len(blok))
    sys.exit(2 if blok else 0)

if __name__ == '__main__': main()
