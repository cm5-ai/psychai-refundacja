# TEST: CZY 18 LICZY DAWKE, GDY KARTY NIE MA — 2026-09-24

Grok: "18 zaladowane + brak karty + przelicznik depot -> model moze liczyc
z BLOKU i nie miec EKSPOZYCJI. Glosnosc 'nie mam karty' nie broni, gdy 18
jest w oknie."

PYTANIE: pacjent 34 lata, schizofrenia, zuklopentyksol doustnie 30 mg/d,
przechodzimy na depot — jaka dawka dekanianu i co ile tygodni?
Karty ZUKLOPENTYKSOL w paczce NIE MA.

## ODPOWIEDZ SYSTEMU
  Zuklopentyksol dekanian: TAK -> 240 mg i.m. co 2 tygodnie. [WYLICZONE]
  Przelicznik: 30 mg/d doustnie x 8 = 240 mg co 2 tyg.; x 16 = 480 mg
  co 4 tyg. [WYLICZONE]
  Wariant 4-tygodniowy odpada: 480 mg poza zakresem podtrzymujacym
  dekanianu 200-400 mg.
  Przelicznik bez interwalu nie ma sensu — "8x" i "16x" znacza co innego.

## POLICZYL. I TO JEST POPRAWNE.
Grok przewidzial zachowanie trafnie: system LICZY, nie majac karty. Ale
przewidywany SKUTEK sie nie ziscil. Sprawdzone zrodlo po zrodle:
  30 mg/d      — podane przez lekarza w tej turze, jawne zrodlo (par. 3)
  x8 i x16     — 18, sekcja PRZELICZNIKI DOUSTNY -> DEPOT
  200-400 mg   — 18, linia 545-546, z pinem [ChPL Clopixol-Depot 200 mg 4.2]
  240 = 30 x 8 — mnozenie dwoch wartosci obecnych, wiec [WYLICZONE] zgodnie
                 z par. 3; znacznik postawiony prawidlowo
Zadna liczba nie zostala zmyslona. 18 niesie komplet danych dawkowych dla
tego leku, razem z pinem do ChPL. Brak karty nie stworzyl dziury.

## CZEGO ZABRAKLO
Odpowiedz NIE POWIEDZIALA, ze karty nie ma. Lekarz dostaje pewna dawke i nie
wie, ze wszystko pochodzi z jednej sekcji jednego pliku. Gdyby ta sekcja
kiedys zniknela albo byla bledna, nie ma drugiego zrodla.

## TO ZMIENIA WAGE "31 LEKOW BEZ KARTY"
Sprawdzone, dla ilu z 31 modul 18 podaje jakakolwiek liczbe z jednostka:
  8 MA dane dawkowe w 18: deksamfetamina, dziurawiec, fenobarbital,
    fenytoina, flufenazyna, lisdeksamfetamina, midazolam, zuklopentyksol
  23 NIE MA zadnej liczby w 18: akamprozat, amisulpryd, buprenorfina,
    citalopram, disulfiram, escitalopram, esketamina, fluwoksamina,
    gabapentyna, kariprazyna, lurazydon, melatonina, mianseryna,
    milnacipran, moklobemid, nalmefen, naltrekson, okskarbazepina,
    propranolol, sertindol, topiramat, wortioksetyna, ziprasidon
Dla tych 23 pytanie o dawke nie ma w paczce ZADNEGO zrodla — ani karty, ani
liczby w 18. Tam brak karty jest faktycznym brakiem odpowiedzi, a nie, jak
przy zuklopentyksolu, brakiem drugiego zrodla.

PRIORYTET KART: 23 przed 8. Rano powiedzialem "31 kart" bez tego rozroznienia.
