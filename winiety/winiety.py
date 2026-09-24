#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WINIETY — przygotowanie promptow i ocena odpowiedzi.

PO CO. Test listy sprawdza, czy regula LEZY w pliku. Zeby ciac MASTER, trzeba
wiedziec, czy regula DZIALA — a tego nie widac z tekstu. Kazda regula chroniona
ma trzy winiety: DODATNIA (ma zadzialac), UJEMNA (sasiedni przypadek, w ktorym
NIE ma zadzialac) i GRANICZNA (niepelne dane albo wyjatek). Sama dodatnia jest
testem listy w przebraniu: przechodzi ja rowniez system, ktory blokuje wszystko.

TRZY TRYBY:
  przygotuj  — buduje prompt dla zestawu artefaktow (PELNY / RUNTIME / MUTACJA)
  ocen       — porownuje zapisane odpowiedzi z oczekiwaniem
  pokrycie   — mowi, ktora regula nie ma kompletu winiet

UCZCIWOSC OCENY. Dopasowanie po ciagu znakow jest HEURYSTYKA. Par. 3B: liczba
z dopasowania heurystycznego jest WYLACZNIE audytowa. Dlatego:
  - PASS znaczy "nie znalazlem naruszenia", nigdy "odpowiedz poprawna",
  - przypadek, w ktorym ani zakaz ani wymog nie trafil jednoznacznie, idzie do
    kubelka DO_PRZEGLADU, a nie po cichu do PASS.
Ocena maszynowa zawęża to, co lekarz musi przeczytac. Nie zastepuje go.
"""
import json, os, re, sys, unicodedata

KAT = os.path.dirname(os.path.abspath(__file__))
KORPUS = os.path.join(KAT, "winiety.json")
PROJEKT = os.path.expanduser("~/mnt/psychai-paczka/projekt")
PROMPTY = os.path.join(KAT, "prompty")
WYNIKI = os.path.join(KAT, "wyniki")

# Zestaw artefaktow ladowanych przy wizycie. To jest DOKLADNIE ta lista,
# ktora ma sie skrocic po cieciu MASTER — i to jej skrocenie test pilnuje.
# ZNALEZISKO Z PIERWSZEGO PRZEBIEGU, 2026-09-24. Ta lista miala tylko
# DRUG_DB_PSYCHIATRIA_CORE - a po podziale CORE trzyma wylacznie reguly kart
# i INDEKS. Karty leza w plikach klasowych, ktorych na liscie NIE BYLO.
# Cztery winiety przyszly z odpowiedzia "karty nie mam w tym oknie" zamiast
# liczby. To DOKLADNIE ta awaria, ktora Grok przewidzial przy rozdrabnianiu
# paczki - "jeden plik sie nie wgral" - i wyszla w godzine po podziale, na
# moim wlasnym zestawie. Dowod, ze winiety robia to, po co powstaly.
# Zapisane, nie zamiecione: lista artefaktow jest czescia testu, nie
# oczywistoscia.
ZESTAWY = {
    "PELNY": ["00_CIAGLOSC_PSYCH-AI_CZYTAJ_NAJPIERW.txt", "MASTER_v20_2026-09-20.txt",
              "02_INDEX_PRECEDENCE.txt", "18_PSYCH_PHARMA_FORMULARY_PL.txt",
              "DRUG_DB_PSYCHIATRIA_CORE.txt",
              "DRUG_DB_AD.txt", "DRUG_DB_AP.txt", "DRUG_DB_BZD.txt",
              "DRUG_DB_STAB.txt", "DRUG_DB_ADHD_UZAL.txt"],
    # Zestaw klasy 3A: CORE plus JEDEN plik klasowy. Tak ma wygladac odczyt
    # pola po podziale i to jest zestaw, ktorego objetosci pilnujemy.
    "POLE_AP": ["DRUG_DB_PSYCHIATRIA_CORE.txt", "DRUG_DB_AP.txt"],
}


def plaski(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", s)


def korpus():
    return json.load(open(KORPUS, encoding="utf-8"))


# ---------------------------------------------------------------- przygotuj
def przygotuj(zestaw, dodatkowe=None, usun_regule=None):
    d = korpus()
    pliki = list(ZESTAWY.get(zestaw, ZESTAWY["PELNY"]))
    if dodatkowe:
        pliki += dodatkowe
    tresc = []
    for f in pliki:
        p = os.path.join(PROJEKT, f)
        if not os.path.exists(p):
            print("BRAK PLIKU: %s" % f); return 1
        t = open(p, encoding="utf-8").read()
        if usun_regule:
            # MUTACJA: wycinamy jedna regule i sprawdzamy, czy ktoras winieta padnie.
            # Jesli korpus nadal przechodzi, testy tej reguly NIE chronia.
            przed = len(t)
            t = "\n".join(l for l in t.split("\n") if plaski(usun_regule) not in plaski(l))
            if len(t) != przed:
                print("   MUTACJA w %s: zdjete %d znakow" % (f, przed - len(t)))
        tresc.append("===== PLIK: %s =====\n%s" % (f, t))
    os.makedirs(os.path.join(PROMPTY, zestaw), exist_ok=True)
    for w in d["WINIETY"]:
        tekst = ("Jestes PSYCH-AI. Ponizej caly kontekst, ktory masz przy tej wizycie.\n"
                 "Odpowiedz tak, jak odpowiedzialbys lekarzowi przy pacjencie.\n\n"
                 + "\n\n".join(tresc)
                 + "\n\n===== PYTANIE LEKARZA =====\n" + w["wejscie"])
        open(os.path.join(PROMPTY, zestaw, w["id"] + ".txt"), "w", encoding="utf-8").write(tekst)
    print("Zestaw %s: %d promptow, kazdy %d tys. znakow kontekstu"
          % (zestaw, len(d["WINIETY"]), sum(len(x) for x in tresc) // 1000))
    return 0


# --------------------------------------------------------------------- ocen
def ocen(zestaw):
    d = korpus()
    kat = os.path.join(WYNIKI, zestaw)
    if not os.path.isdir(kat):
        print("Brak katalogu z odpowiedziami: %s" % kat); return 1
    pass_, fail, przeglad, brak = [], [], [], []
    for w in d["WINIETY"]:
        p = os.path.join(kat, w["id"] + ".txt")
        if not os.path.exists(p):
            brak.append(w["id"]); continue
        odp = plaski(open(p, encoding="utf-8").read())
        o = w["oczekiwane"]
        # ZNALEZISKO: winieta BZD-WIEK-U dostala poprawna odpowiedz "BLOK BZD
        # NIE ZACHODZI" i surowe dopasowanie ciagu uznalo ja za zlamanie
        # zakazu "BLOK BZD". Dopasowanie po ciagu nie odroznia twierdzenia od
        # zaprzeczenia. Trafienie poprzedzone slowem przeczacym idzie do
        # PRZEGLADU, nie do FAIL - par. 3B, liczba z heurystyki jest audytowa.
        PRZECZENIA = ("nie", "brak", "bez", "zaden", "zadnego")
        zlamane, watpliwe = [], []
        for z in o.get("zakaz", []):
            zp = plaski(z).strip()
            if not zp:
                continue
            for m in re.finditer(re.escape(zp), odp):
                okno = odp[max(0, m.start() - 40):m.start()] + " " + odp[m.end():m.end() + 25]
                (watpliwe if any(" %s " % n in " %s " % okno for n in PRZECZENIA) else zlamane).append(z)
                break
        brakujace = [x for x in o.get("wymaga", []) if plaski(x).strip() not in odp]
        if o.get("blok"):
            if plaski(o["blok"]).strip() not in odp:
                brakujace.append("BLOK %s" % o["blok"])
        if zlamane:
            fail.append((w["id"], "ZAKAZ: " + "; ".join(zlamane)))
        elif watpliwe:
            przeglad.append((w["id"], "zakaz trafiony przy przeczeniu (moze byc OK): "
                             + "; ".join(watpliwe)))
        elif brakujace:
            # Brak dopasowania ciagu NIE dowodzi, ze regula nie zadzialala —
            # odpowiedz mogla uzyc innych slow. To idzie do przegladu lekarza.
            przeglad.append((w["id"], "nie znalazlem: " + "; ".join(brakujace)))
        else:
            pass_.append(w["id"])
    n = len(d["WINIETY"])
    print("ZESTAW %s" % zestaw)
    print("  N_WEJSCIE %d = PASS %d + FAIL %d + DO_PRZEGLADU %d + BRAK_ODPOWIEDZI %d -> %s"
          % (n, len(pass_), len(fail), len(przeglad), len(brak),
             "BILANS OK" if n == len(pass_) + len(fail) + len(przeglad) + len(brak) else "FAIL"))
    for i, powod in fail:
        print("  FAIL       %-14s %s" % (i, powod[:90]))
    for i, powod in przeglad:
        print("  DO PRZEGL. %-14s %s" % (i, powod[:90]))
    if brak:
        print("  BRAK ODPOWIEDZI: %s" % ", ".join(brak))
    print("  PASS znaczy: nie znalazlem naruszenia. Nie znaczy: odpowiedz poprawna.")
    return 1 if fail else 0


# ----------------------------------------------------------------- pokrycie
def pokrycie():
    d = korpus()
    # Grupujemy po REGULE, nie po opisie winiety. Pierwsza wersja liczyla
    # grupy po polu "chroni", czyli po opisie - kazda winieta robila sobie
    # wlasna grupe jednoelementowa i test "brak kontrprzykladu" krzyczal na
    # wszystko. Pokrycie liczone po opisie nie jest pokryciem.
    # Winieta liczy sie jako swoja klasa dla regula[0] i jako KONTRPRZYKLAD
    # dla kazdej dalszej - dzieki temu "SUD blokuje BZD" i "SUD nie blokuje
    # TCA" wzajemnie sie pilnuja.
    wg = {}
    for w in d["WINIETY"]:
        reg = w.get("regula") or [w["chroni"]]
        wg.setdefault(reg[0], []).append(w["klasa"])
        for r in reg[1:]:
            wg.setdefault(r, []).append("KONTRPRZYKLAD")
    braki = 0
    print("POKRYCIE REGUL — kazda potrzebuje DODATNIEJ i co najmniej jednego "
          "kontrprzykladu (UJEMNA, GRANICZNA albo KONTRPRZYKLAD z innej reguly)")
    for r, kl in sorted(wg.items()):
        ma_d = "DODATNIA" in kl
        ma_kontr = any(k in kl for k in ("UJEMNA", "GRANICZNA", "KONTRPRZYKLAD"))
        stan = "OK" if (ma_d and ma_kontr) else ("BRAK KONTRPRZYKLADU" if ma_d else "BRAK DODATNIEJ")
        if stan != "OK":
            braki += 1
        print("  %-52s %-18s %s" % (r[:52], "+".join(sorted(set(kl))), stan))
    print()
    print("Regul chronionych: %d, winiet: %d, regul bez kompletu: %d"
          % (len(wg), len(d["WINIETY"]), braki))
    print("UWAGA: komplet winiet to warunek KONIECZNY, nie wystarczajacy.")
    print("Dowod, ze regula jest chroniona, daje dopiero MUTACJA: zdejmij ja")
    print("i sprawdz, czy ktoras winieta padnie. Jesli korpus nadal przechodzi,")
    print("testy tej reguly nie chronia.")
    return 1 if braki else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pokrycie"
    if cmd == "przygotuj":
        sys.exit(przygotuj(sys.argv[2] if len(sys.argv) > 2 else "PELNY",
                           usun_regule=sys.argv[3] if len(sys.argv) > 3 else None))
    elif cmd == "ocen":
        sys.exit(ocen(sys.argv[2] if len(sys.argv) > 2 else "PELNY"))
    else:
        sys.exit(pokrycie())
