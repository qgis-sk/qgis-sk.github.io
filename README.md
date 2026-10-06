# qgis.sk – web Slovenskej skupiny používateľov QGIS

Statická stránka občianskeho združenia **QGIS Slovensko** (IČO 55961746). Beží na GitHub Pages
z vetvy `master`, doména `qgis.sk` (súbor `CNAME`). Žiadny server, žiadny build, žiadny framework:
čisté HTML, CSS a jeden JavaScript pre mapu.

## Ako sa stránka publikuje

| Vetva | Čo je to | Kde to vidno |
|---|---|---|
| `master` | živá stránka | https://qgis.sk |
| `dev` | pracovná verzia | nikde naživo, iba lokálny náhľad |

Postup: zmeny robíme vo vetve `dev`, skontrolujeme lokálne a keď sme spokojní, zlúčime `dev` do
`master` (pull request alebo `git merge`). GitHub Pages stránku nasadí sama do pár minút.

Lokálny náhľad (v priečinku repozitára):

```bash
python3 -m http.server 8765
```

a otvoriť http://localhost:8765. Náhľad cez `file://` nefunguje, lebo mapa načítava dáta cez `fetch`.

## Štruktúra

```
index.html                 domovská stránka (hero, čísla, ciele, prečo QGIS, komunitná mapa,
                           podujatia, zdroje, zapojte sa, kontakt)
o-nas.html                 Kto sme: poslanie, ciele zo stanov, tím, údaje o združení
pravidla.html              Pravidlá komunity: kódex správania, členstvo podľa stanov
blog/index.html            zoznam článkov
blog/<slug>.html           jednotlivé články
feed.xml                   RSS kanál noviniek (odporúčanie QGIS.org pre user groups)
1_qgis_advent.html         starší adventný kalendár 2020 (ponechaný)
styles.css                 všetky štýly (farby QGIS: #589632, #93b023, #ee7913, #f0e64a)
js/komunita.js             mapa organizácií (Leaflet + OpenStreetMap), vyhľadávanie, filtre,
                           mobilné menu
data/organizacie.json      dáta pre mapu – GENEROVANÉ, needitovať ručne
data/stat.json             počty členov – udržiavané ručne
data/organizacie-tabulka.csv  záloha tabuľky z 6. 10. 2026
scripts/sync_organizacie.py   skript, ktorý z tabuľky vyrobí organizacie.json
.github/workflows/sync-organizacie.yml  mesačná automatizácia
dokumenty/                 stanovy a iné dokumenty združenia
images/                    logá a fotky
```

Štruktúra stránok vychádza z oficiálnej šablóny
[QGIS-User-Group-Website](https://github.com/qgis/QGIS-User-Group-Website) (Domov, Kto sme,
Podujatia, Komunita, Pravidlá, Blog), ale na vlastnej doméne a bez Huga.

## Komunitná mapa organizácií

Na mape sú **iba organizácie** (firmy, inštitúcie, školy, samosprávy, komunity), nikdy fyzické osoby.

### Zdroj dát: zdieľaná Google tabuľka

[QGIS SK – organizácie na mape](https://docs.google.com/spreadsheets/d/1Yge6hcfhaaxkVRBLft4XKlQN3ZQrvibsqIzYUWxBB9k/edit)
(zdieľanie: ktokoľvek s odkazom môže zobraziť). Tabuľku upravujete priamo v Google Sheets.

| Stĺpec | Význam |
|---|---|
| `nazov` | názov organizácie, ako sa zobrazí na mape |
| `typ` | `firma`, `institucia`, `skola`, `samosprava` alebo `komunita` (podľa toho sú filtre a farba bodu) |
| `ulica`, `mesto`, `krajina` | sídlo; `krajina` ako kód (`SK`, `CZ`, …), iné než SK sa zobrazí pri názve |
| `lat`, `lon` | súradnice WGS84 s bodkou ako desatinným oddeľovačom; bez nich sa riadok na mape nezobrazí |
| `web` | odkaz (s `https://`) |
| `ico` | IČO ako text (v tabuľke je zadané vzorcom `="00166545"`, aby ostali úvodné nuly) |
| `popis` | jedna veta, zobrazí sa v zozname |
| `zaradenie` | `registrovaná organizácia (formulár)` alebo `člen s pracovnou e-mailovou adresou …`; druhý typ dostane na mape štítok „na potvrdenie“ |
| `stav` | `overené` / `neoverené` (sídlo); zobrazí sa ako štítok |
| `zobrazit_na_mape` | nechať prázdne alebo `áno`; hodnota **`skryť`** riadok z mapy odstráni |
| `zdroj_sidla` | odkiaľ je sídlo overené (RPO, ORSR, ARES, web…) |
| `registrovane` | dátum registrácie vo formulári |
| `poznamka` | interné poznámky, na web nejdú |

Pridanie organizácie = nový riadok. Sídlo overte v Registri právnických osôb
(https://rpo.statistics.sk) alebo ORSR a súradnice doplňte napríklad z OpenStreetMap
(pravý klik na mape → zobrazí sa lat, lon).

### Ako sa dáta dostanú na web

1. `scripts/sync_organizacie.py` stiahne tabuľku ako CSV (adresa je v premennej `SHEET_CSV_URL`),
   vezme riadky so súradnicami, vynechá riadky so `skryť`, pridá počty z `data/stat.json`
   a zapíše `data/organizacie.json`.
2. GitHub Action `sync-organizacie.yml` to spúšťa **1. deň v mesiaci o 06:00 UTC** a zmenu
   commitne do vetvy, v ktorej beží. Dá sa spustiť aj ručne: GitHub → Actions → „Sync organizácií
   zo zdieľanej tabuľky“ → Run workflow. (GitHub ponúka workflow až po zlúčení do `master`.)
3. Adresa tabuľky je uložená ako repository variable `SHEET_CSV_URL`
   (Settings → Secrets and variables → Actions → Variables).

Ručné spustenie na vlastnom počítači:

```bash
SHEET_CSV_URL="https://docs.google.com/spreadsheets/d/1Yge6hcfhaaxkVRBLft4XKlQN3ZQrvibsqIzYUWxBB9k/gviz/tq?tqx=out:csv" python3 scripts/sync_organizacie.py
```

### Počty členov

`data/stat.json` obsahuje počet individuálnych členov a celkový počet registrácií z registračného
formulára. Formulár obsahuje osobné údaje, preto sa nečíta automaticky; počet aktualizujeme ručne
(unikátne e-maily bez riadkov, kde sa registrovala iba organizácia). Číslo sa zobrazuje v páse
s číslami a nad mapou.

## Blog a RSS

Nový článok = nový súbor `blog/<slug>.html` (skopírovať existujúci, upraviť obsah) + riadok v
`blog/index.html` + položka `<item>` vo `feed.xml` (nový článok hore). QGIS.org odporúča novinky
posielať aj na https://feed.qgis.org.

## Podujatia

Časová os je v `index.html` v sekcii `#podujatia`. Nové podujatie sa pridá ako prvý `<li>` v zozname
`.timeline`; položku „Pripravujeme“ ponecháme na vrchu.

## Tím a údaje o združení

Stránka `o-nas.html`: zoznam tímu, ciele zo stanov, IČO, registrácia a odkaz na
`dokumenty/Stanovy_QGIS_Slovensko.pdf`. Pri zmene štatutára alebo stanov upraviť tu a v pätičke
kontaktu na `index.html`.

## Externé závislosti

- Font Cairo z Google Fonts
- Leaflet 1.9.4 z cdnjs
- Dlaždice OpenStreetMap (štandardný server, vhodný pre nízku návštevnosť; pri raste prejsť na
  vlastný alebo platený poskytovateľ)

## Licencia

Obsah CC BY-SA 4.0. Logo QGIS podľa pravidiel ochrannej známky QGIS.org.
