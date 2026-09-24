# SLOWNIK POSTACI — PSYCH-AI

Po co: zeby depot nigdy wiecej nie wypadl z cache, i zeby dawka doustna nigdy
nie zostala podana jako dawka depotu.

## Trzy przyczyny, dla ktorych depoty wypadly (wszystkie sprawdzone na danych 2026-09-24)

1. **Limit na substancje.** `chpl_cache.py`, `MAX_PRODUKTOW = 3`, kandydaci
   w kolejnosci z rejestru, bez wiedzy o postaci. Trzy generyki doustne
   zjadaly miejsca, depot przepadal. Dotknelo: Zypadhera, Rispolept Consta,
   Xeplion, Trevicta, Haloperidol WZF 5 mg/ml.
2. **Klucz odsiewania = sama nazwa produktu.** 95 nazw w rejestrze kryje
   wiecej niz jedna postac. Bilans: 2493 pozycje, 801 grup po kluczu `nazwa`,
   910 grup po kluczu `(nazwa, postac)` — 109 pozycji scalanych po cichu.
   Abilify ma pod jedna nazwa tabletki, tabletki ulegajace rozpadowi, roztwor
   doustny ORAZ roztwor do wstrzykiwan. Zostawala jedna z czterech.
3. **Pole `postac` nie koduje depotu.** Fluanxol Depot, Clopixol-Depot
   i Decaldol maja w rejestrze `Roztwor do wstrzykiwan`.

## Model: trzy pola, dwa rozne zrodla

| pole | wartosci | zrodlo |
|---|---|---|
| DROGA | DOUSTNA, INIEKCJA, INFUZJA, TRANSDERMALNA, PODJEZYKOWA, OROMUKOZALNA, DOODBYTNICZA, WZIEWNA, DONOSOWA, IMPLANT | pole `postac`, deterministycznie |
| UWALNIANIE | NATYCHMIASTOWE, PRZEDLUZONE, ZMODYFIKOWANE | pole `postac`, deterministycznie |
| EKSPOZYCJA | DEPOT, POSREDNIA, KROTKA | ChPL 4.2 albo tabela wyjatkow — **nigdy** pole `postac` |

Klasa kliniczna = DROGA x UWALNIANIE x EKSPOZYCJA:
DOUSTNA_IR, DOUSTNA_MR, INIEKCJA_KROTKA, INIEKCJA_POSREDNIA, DEPOT,
IMPLANT, TRANSDERMALNY, PODJEZYKOWY, OROMUKOZALNY, DOODBYTNICZY, WZIEWNY, DONOSOWY.

INIEKCJA_POSREDNIA istnieje dla octanu zuklopentyksolu (Clopixol-Acuphase):
dziala 2-3 doby, nie jest podtrzymaniem. Wziety za depot daje dziure
terapeutyczna na dwa tygodnie; depot wziety za niego daje przedawkowanie
z dzialaniem na tygodnie. To nie niuans uwalniania — to inny lek kliniczny
pod tym samym kodem ATC.

INTERWAL nie jest czescia slownika postaci: ma inne zrodlo (ChPL 4.2, nie
rejestr) i nie jest cecha postaci — Fluanxol Depot to ten sam produkt
"co 2 albo 4 tygodnie". Ale JEST czescia klucza doboru produktow do cache,
patrz nizej.

## Czego NIE wolno

Dopasowanie przyblizone jest zakazane (warstwa 40, par. 3B). Klucz to rownosc
napisu po kanonizacji. Cztery reguly, ktore wygladaja rozsadnie i sa BLEDNE —
kazda ma kontrprzyklad w danych:

| regula | kontrprzyklad |
|---|---|
| `acetas` = depot | 9 z 12 trafien to Eslicarbazepini acetas — Zebinix i Eslibon, zwykle tabletki |
| `o przedluzonym uwalnianiu` = depot | 112 pozycji to doustne tabletki XR |
| depot poznam po polu `postac` | Fluanxol Depot, Clopixol-Depot, Decaldol — pole milczy |
| depot poznam po soli | `palmitas` nie wystepuje ANI RAZU: 59 depotow paliperydonu ma nazwe powszechna `Paliperidonum` |

## Dwa rodzaje testu (`test_postacie.py`)

**A. Wartownicy** — 14 produktow o znanej odpowiedzi, w tym trzy
kontrprzyklady (Zebinix, Eslibon, Invega), ktore MUSZA wyjsc jako nie-depot.
Ten test sprawdza moja pamiec.

**B. Sierota LAI** — wazniejszy. Produkt jest kandydatem na depot, gdy trafia
w sygnal NIEZALEZNY od slownika i od tabeli wyjatkow: sol LAI przy drodze
iniekcyjnej, kadencja >= 7 dni w ChPL 4.2, nosnik oleisty w 6.1, token w nazwie
produktu. Kandydat, ktory dostal klase INIEKCJA_KROTKA i nie ma wpisu
w tabeli wyjatkow, to FAIL builda — nie cicha akceptacja.
Ten test sprawdza regule, nie pamiec. To on wylapie kolejny Fluanxol Depot.

Stan 2026-09-24: 140 produktow iniekcyjnych, 11 kandydatow LAI, 0 sierot.

**C. Kompletnosc** — kazdy napis w polu `postac` musi byc w slowniku.
Napis spoza slownika = FAIL builda, NIGDY `UNKNOWN` w produkcji.
Stan 2026-09-24: 58 napisow, 0 brakujacych.

## Co zostalo do zrobienia w generatorze

1. Klucz odsiewania `(nazwa, postac)` zamiast `nazwa`. Bez tego iniekcja
   Abilify dalej bedzie ginac razem z tabletkami.
2. Limit nie na substancje, tylko na `(substancja x klasa x kubel interwalu)`.
   Proba na sucho pokazala, ze sam `(substancja x klasa)` NIE wystarcza:
   w koszyku DEPOT paliperydonu siedzi 14 nazw, a trzy miejsca zajmuja
   BYANNLI, Denepra i Egoropal — Xeplion i Trevicta dalej wypadaja.
   Kubelki z ChPL 4.2: P0, P2D_P3D, P2W, P2W_P4W, P4W, P12W, P24W.
   Dobor dwuprzebiegowy: pierwszy przebieg po klasie, drugi po ujawnieniu
   interwalu z pobranej ChPL.

## Proba zlosliwa (`proba_zlosliwa.py`, 2026-09-24)

Nie potwierdza slownika — probuje go zlamac. Siedem grup przypadkow.

| grupa | co sprawdza | wynik |
|---|---|---|
| A | napisy spoza slownika (inna kolejnosc slow, brak lacznika, pusty, None) | wszystkie WYBUCHAJA, zadnego cichego przejscia |
| B | slowo `Depot` w nazwie leku DOUSTNEGO | nie staje sie depotem — warunek drogi trzyma |
| C | `acetas` w iniekcji, ktora nie jest depotem | zglaszany jako sierota, build pyta |
| D | depot bez tokenu, bez soli, bez ChPL | **przechodzi jako KROTKA. Granica metody.** Z ChPL 4.2 lapany od razu |
| E | postac wielodrogowa | jeden produkt, dwie drogi |
| F | kanonizacja klucza (male litery, twarda spacja, mylnik, spacje wokol lacznika) | 4 ZNALEZISKA, poprawione |
| G | nazwa podobna do wyjatku (Fluanxol Depot Forte, Decaldol Mini) | NIE dziedziczy DEPOT |

**Znalezisko F.** Tabela wyjatkow porownywala nazwy zbyt doslownie: `fluanxol depot`,
`Fluanxol\u00a0Depot`, `Clopixol–Depot` (mylnik) i `Clopixol - Depot` nie trafialy we wpis
i schodzily do KROTKA. Wazne: **detektor sierot zlapal wszystkie cztery** — build
stanalby, nie przepuscil. Dwuwarstwowosc zadzialala.
Poprawka: jawna kanonizacja klucza — NFC, mylniki na lacznik, spacje nietypowe na
zwykla, zwezenie bialych znakow, spacje wokol lacznika, bez wielkosci liter.
To rownosc po jawnej kanonizacji, nie dopasowanie przyblizone.
Bilans scalania po kanonizacji nazw: 801 nazw surowych -> 797. Sklejone 4 pary,
wszystkie to ten sam produkt zapisany dwa razy: `ABILIUM`/`Abilium`,
`Frisium  10`/`Frisium 10`, `Remirta ORO`/`Remirta Oro`, `ZolpiGen`/`Zolpigen`.
Zaden inny produkt nie zostal sklejony. Assercja w kodzie pilnuje, zeby kanonizacja
nie skleila dwoch roznych wyjatkow.

**Znalezisko D — granica metody, nazwana wprost.** Depot zarejestrowany jako
`Roztwor do wstrzykiwan`, bez soli LAI w nazwie powszechnej, bez tokenu w nazwie
produktu i bez pobranej ChPL nie zostawia zadnego sygnalu. Przechodzi jako
INIEKCJA_KROTKA i nic go nie lapie. Jedyne zabezpieczenie to ChPL 4.2 — z nia
produkt wpada od razu przez kadencje. Wniosek operacyjny: **dla kazdej substancji
z choc jednym produktem iniekcyjnym ChPL musi byc pobrana**, inaczej detektor
sierot dziala z jedna reka za plecami.

## Druga tura prob (2026-09-24, po uwagach GPT)

**Kadencja z ChPL 4.2 to ALARM, nie werdykt — udowodnione na tekscie.**
ChPL Clopixol-Acuphase pasuje do wzorca kadencji ("co dwa tygodnie"), bo punkt 4.2
opisuje PRZEJSCIE NA DEKANIAN. Zdanie o kadencji dotyczy tam innego produktu.
Gdyby kadencja klasyfikowala, Acuphase zostalby depotem — czyli dokladnie ten blad,
przed ktorym cala ta robota ma chronic. Kod zwraca teraz przy trafieniu kadencji
klase KROTKA z polem `alarm`, a rozstrzyga tabela wyjatkow albo pole postac.

**Wzorzec kadencji byl za waski.** Lapal "co 4 tygodnie", ale nie "w odstepie
4 tygodni" ani "raz na 4 tygodnie" — obie frazy wystepuja w ChPL Decaldolu.
Rozszerzony; przy okazji odrzuca "raz na dobe", "dwa razy na dobe", "przez 14 dni"
i "co 24 godziny", ktore kadencja depotu nie sa.

**ChPL nalezy do PRODUKTU I POSTACI, nie do nazwy.** Klucz po samej nazwie doklejal
ChPL tabletek do iniekcji o tej samej nazwie i dawal falszywe alarmy przy
Haloperidolu WZF i Clonazepamum TZF. Klucz to teraz `(kanoniczna nazwa, drogi)`.

**Alarm sprawdzony i odrzucony ma wlasny wpis.** Clonazepamum TZF: fraza "co 3 dni"
w 4.2 to tempo zwiekszania dawki, nie odstep wstrzykniec. Wpisany do tabeli wyjatkow
jako KROTKA z powodem i pinem — inaczej ten sam alarm wracalby przy kazdym buildzie.

**POKRYCIE INIEKCJI — najwazniejsza liczba tej tury.**
Na 140 produktow iniekcyjnych w rejestrze **134 nie ma wlasnej ChPL w cache'u**.
Cache trzyma ChPL doustne tych substancji, nie iniekcyjne. Najwieksze dziury:
paliperydon 59, midazolam 18, buprenorfina 9, rysperydon 8, walproinian 7,
arypiprazol 5, lorazepam 4, olanzapina 4, diazepam 3.
Dla tych produktow detektor sierot dziala wylacznie na nazwie i soli — kadencji
nie ma z czego przeczytac. To jest zadanie numer jeden dla generatora, przed
dokladaniem kolejnych substancji.

**Czego NIE da sie tu sprawdzic: tozsamosci produktu.**
GPT zaproponowal assercje "kolizja nazwy kanonicznej przy wiecej niz jednym
produkcie logicznym = FAIL". Sprawdzilem i nie ma na czym jej oprzec:
`pozwolenie` jest na MOC, wiec jeden produkt ma ich kilka (Xanax ma cztery);
`podmiot` bywa rozny dla tego samego produktu (Frisium 10 ma trzy, Remirta ORO trzy,
ZolpiGen cztery) — prawdopodobnie przez zmiany podmiotu w czasie.
W tym eksporcie nie ma pola bedacego stabilna tozsamoscia produktu.
Dlatego kanonizacja nazwy sluzy WYLACZNIE do lookupu w tabeli wyjatkow i do niczego
innego. Pilnuje tego assercja w kodzie: kanonizacja nie moze skleic dwoch roznych
wpisow tabeli wyjatkow.

## Zrodla decyzji
Konsultacja GPT i Grok, 2026-09-24. Od GPT: rozdzielenie `release_form`
(z rejestru) od `exposure` (z ChPL), napis spoza slownika jako twardy FAIL,
produkt wielodrogowy zostaje jednym produktem w dwoch koszykach.
Od Groka: klucz doboru musi zawierac interwal, bo inaczej ten sam blad wraca
pietro nizej; Acuphase jako osobna klasa; test ma wykrywac BRAK, nie
sprawdzac liste wyjatkow ("to test pamieci, nie reguly").
