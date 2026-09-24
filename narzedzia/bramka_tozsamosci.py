#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BRAMKA TOZSAMOSCI — nic, co identyfikuje pacjenta ani otwiera sejf, nie wchodzi
do repozytorium.

DLACZEGO TA JEDNA JEST PIERWSZA [R7, punkt 9]. Nie dlatego, ze najwazniejsza —
GPT i Grok zgodnie to odrzucili i mieli racje: nie poprawia liczby na wizycie.
Dlatego, ze jest PIERWSZA W KOLEJCE NIEODWRACALNYCH. Zielone, ktore powinno
byc czerwone, naprawia sie nazajutrz. Kod PSY wypchniety do historii gita
zostaje tam na zawsze, a `git push` robi lekarz miedzy pacjentami.

TO NIE JEST HIPOTEZA. Skan tej samej rodziny, zbudowany 2026-09-24 do kopii
narzedzi, przy PIERWSZYM uruchomieniu zatrzymal cztery pliki, ktore autor
kopii by wyslal. Lista wykluczen byla zalozeniem; zatrzymal je skan.

CZEGO TA BRAMKA NIE DOWODZI. Ze paczka jest klinicznie poprawna. Ze L1
dziala. Ze dane pacjentow sa bezpieczne gdziekolwiek indziej niz w tym
drzewie. Sprawdza jedna rzecz: czy do REPOZYTORIUM nie wszedl identyfikator
albo material klucza.

DUPLIKACJA JEST ZAMIERZONA. Ten sam plik lezy w obu repozytoriach. Wspolne
zrodlo wymagaloby tokenu miedzy repo — czyli bramka bezpieczenstwa zalezalaby
od sekretu, ktorego brak dzis oblewa pokrycie w drugim repo. Kontrola, ktora
milknie przy braku sekretu, jest gorsza niz skopiowana.

OBLEWA TAKZE PRZY WLASNYM BLEDZIE [warunek GPT]. Kazdy wyjatek konczy sie
kodem 1. Skaner, ktory pada po cichu, jest gorszy niz jego brak, bo zostawia
zielone pole.
"""
import os, re, sys, subprocess

WYJATKI = ".github/bramka_wyjatki.tsv"

PSY = re.compile(r"PSY-([A-Z0-9?*]{4})-([A-Z0-9?*]{4})-([A-Z0-9?*]{4})")
KLUCZ_TRESC = [
    ("klucz prywatny age",      re.compile(rb"AGE-SECRET-KEY-1[A-Z0-9]{10,}")),
    ("klucz prywatny OpenSSH",  re.compile(rb"BEGIN (OPENSSH|RSA|EC|DSA|PGP) PRIVATE KEY")),
    ("token GitHub",            re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}")),
]
KLUCZ_NAZWA = re.compile(r"(_KLUCZ_|op_identity|\.key$|\.pem$|id_rsa|id_ed25519)", re.I)
# Granice musza odcinac FRAGMENTY HASZY. Pierwsze 11 znakow sumy
# "79122422579d957..." to cyfry i trafily w sume kontrolna PESEL — falszywy
# alarm w maszynowym JSON-ie. Falszywe alarmy ucza ignorowania alarmow,
# wiec zawezamy klucz, zamiast wykluczac plik.
PESEL = re.compile(rb"(?<![0-9A-Za-z_-])([0-9]{11})(?![0-9A-Za-z_-])")
# Miesiac w PESEL koduje stulecie; nieistniejacy miesiac albo dzien znaczy,
# ze to nie jest PESEL, tylko liczba.
PESEL_WIEK = set(range(1, 13)) | set(range(21, 33)) | set(range(81, 93))
BIN = (".png",".jpg",".jpeg",".gif",".pdf",".zip",".gz",".tar",".age",".b64",".ico",".woff",".woff2")

def zaslepka(grupy):
    return all(set(g) <= set("X?*") for g in grupy)

def pesel_poprawny(s):
    """Dwa warunki naraz: suma kontrolna ORAZ sensowna data w srodku.
    Sama suma daje trafienie co dziesiata losowa liczba 11-cyfrowa."""
    if int(s[2:4]) not in PESEL_WIEK or not 1 <= int(s[4:6]) <= 31:
        return False
    w = (1,3,7,9,1,3,7,9,1,3)
    c = sum(int(s[i]) * w[i] for i in range(10))
    return (10 - c % 10) % 10 == int(s[10])

def wczytaj_wyjatki():
    if not os.path.isfile(WYJATKI):
        return []
    out = []
    for nr, l in enumerate(open(WYJATKI, encoding="utf-8"), 1):
        if l.startswith("#") or not l.strip():
            continue
        p = l.rstrip("\n").split("\t")
        if len(p) != 3:
            raise ValueError("%s wiersz %d: %d kolumn zamiast 3" % (WYJATKI, nr, len(p)))
        out.append(p)
    return out

def pliki_drzewa():
    r = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("git ls-files nieudane: " + r.stderr.strip())
    return [x for x in r.stdout.split("\n") if x]

def dodane_linie(baza, head):
    """Tresc DODAWANA w tym pchnieciu. Stan drzewa nie wystarcza: plik moze
    zostac dodany i usuniety w dwoch commitach jednego pchniecia, a w historii
    zostaje na zawsze."""
    if not baza or not head or set(baza) == {"0"}:
        return []
    r = subprocess.run(["git", "diff", "--unified=0", baza, head],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        raise RuntimeError("git diff %s %s nieudane: %s" % (baza[:8], head[:8], r.stderr.strip()))
    plik, out = "?", []
    for l in r.stdout.split("\n"):
        if l.startswith("+++ b/"):
            plik = l[6:]
        elif l.startswith("+") and not l.startswith("+++"):
            out.append((plik, l[1:]))
    return out

def main():
    wyjatki = wczytaj_wyjatki()
    wyj_sciezki = set(w[0] for w in wyjatki)
    znaleziska = []

    print("=" * 68)
    print("BRAMKA TOZSAMOSCI")
    print("=" * 68)
    print("WYJATKOW (wersjonowanych, z powodem): %d" % len(wyjatki))
    for s, co, powod in wyjatki:
        print("   %-44s %s" % (s[:44], powod[:60]))
    print()

    pliki = pliki_drzewa()
    n_plik = n_pom = n_usuniete = 0
    for f in pliki:
        if f in wyj_sciezki:
            n_pom += 1
            continue
        if not os.path.exists(f):
            # Plik sledzony przez gita, ale nieobecny na dysku (skasowany,
            # jeszcze niezacommitowany). Nie ma czego skanowac i nie ma jak
            # niczego wyciec. Alarm tutaj bylby falszywy, a falszywe alarmy
            # ucza ignorowania alarmow.
            n_usuniete += 1
            continue
        n_plik += 1
        if KLUCZ_NAZWA.search(os.path.basename(f)):
            znaleziska.append(("NAZWA PLIKU wyglada na material klucza", f, os.path.basename(f)))
        m = PSY.search(f)
        if m and not zaslepka(m.groups()):
            znaleziska.append(("KOD PACJENTA W NAZWIE PLIKU", f, m.group(0)))
        if f.lower().endswith(BIN):
            continue
        try:
            dane = open(f, "rb").read()
        except Exception as e:
            znaleziska.append(("NIE DA SIE ODCZYTAC — nie ryzykuje", f, str(e)[:50]))
            continue
        for opis, rx in KLUCZ_TRESC:
            if rx.search(dane):
                znaleziska.append((opis.upper(), f, "(tresci nie pokazuje)"))
        try:
            tekst = dane.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for m in PSY.finditer(tekst):
            if not zaslepka(m.groups()):
                znaleziska.append(("KOD PACJENTA W TRESCI", f, m.group(0)))
                break
        for m in PESEL.finditer(dane):
            s = m.group(1).decode()
            if pesel_poprawny(s):
                znaleziska.append(("LICZBA O POPRAWNEJ SUMIE KONTROLNEJ PESEL", f, s[:4] + "*******"))
                break

    baza, head = os.environ.get("BRAMKA_BAZA", ""), os.environ.get("BRAMKA_HEAD", "")
    dodane = dodane_linie(baza, head)
    for plik, linia in dodane:
        if plik in wyj_sciezki:
            continue
        for m in PSY.finditer(linia):
            if not zaslepka(m.groups()):
                znaleziska.append(("KOD PACJENTA W DODAWANEJ LINII", plik, m.group(0)))
        for opis, rx in KLUCZ_TRESC:
            if rx.search(linia.encode("utf-8", "replace")):
                znaleziska.append((opis.upper() + " W DODAWANEJ LINII", plik, "(tresci nie pokazuje)"))

    print("BILANS: plikow w drzewie %d = sprawdzonych %d + wyjatkow %d + skasowanych %d"
          % (len(pliki), n_plik, n_pom, n_usuniete))
    print("        linii dodawanych w tym pchnieciu: %d%s"
          % (len(dodane), "" if dodane else "  (brak zakresu — sprawdzone samo drzewo)"))
    if len(pliki) != n_plik + n_pom + n_usuniete:
        print("FAIL: bilans sie nie zgadza."); return 1
    if n_plik == 0:
        print("FAIL: ZERO PLIKOW DO SPRAWDZENIA. Regula bez wejscia nie jest zielona.")
        return 1
    print()
    if not znaleziska:
        print("CZYSTO.")
        print()
        print("CZEGO TO NIE DOWODZI: ani tego, ze paczka jest klinicznie poprawna,")
        print("ani ze L1 dziala, ani ze dane pacjentow sa bezpieczne gdziekolwiek")
        print("indziej niz w tym drzewie. Tylko tyle, ze tutaj ich nie ma.")
        return 0
    print("ZNALEZISK: %d — NIC NIE WOLNO WYPCHNAC" % len(znaleziska))
    print()
    for co, gdzie, dowod in znaleziska:
        print("  %s" % co)
        print("     plik:  %s" % gdzie)
        print("     dowod: %s" % dowod)
        print()
    print("Kod pacjenta w historii gita zostaje tam na zawsze. Usuniecie pliku")
    print("nastepnym commitem NIE USUWA go z historii.")
    return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Warunek GPT: bramka oblewa takze przy wlasnym bledzie. Skaner, ktory
        # pada po cichu, zostawia zielone pole.
        print("FAIL: bramka tozsamosci sama sie wywrocila: %s: %s" % (type(e).__name__, e))
        sys.exit(1)
