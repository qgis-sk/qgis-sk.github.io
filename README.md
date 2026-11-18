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
js/config.js               adresa registračnej služby
js/formular.js             odosielanie formulárov, dohľadanie IČO
pridat-sa.html             formulár pre jednotlivcov
pridat-organizaciu.html    formulár pre organizácie
server/                    registračná služba (beží na serveri Geosupportu)
js/mapa.js                 komunitná mapa (MapLibre GL): tmavý podklad, reliéf, 3D terén, zhluky, legenda
js/komunita.js             zoznam organizácií, vyhľadávanie, filtre, panel po krajoch,
                           mobilné menu, SVG mapa Slovenska v hlavičke (kraje + body organizácií)
data/organizacie.json      dáta pre mapu – GENEROVANÉ, needitovať ručne
data/stat.json             počty členov – udržiavané ručne
data/sk-kraje.json         zjednodušené hranice 8 krajov (OpenStreetMap/Nominatim) pre mapu v hlavičke
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

Na mape sú **iba organizácie** (firmy, inštitúcie, školy, samosprávy, komunity), nikdy fyzické osoby, a iba
tie so sídlom na Slovensku. Zoznam vznikol z odpovedí registračného formulára skupiny (Google Forms, od novembra
2020): vybrali sme riadky, kde sa registrovala organizácia alebo člen s pracovnou adresou organizácie, a sídla sme
overili v Registri právnických osôb, ORSR a na weboch organizácií.

### Zdroj dát: zdieľaná Google tabuľka

[QGIS SK – organizácie na mape](https://docs.google.com/spreadsheets/d/1Yge6hcfhaaxkVRBLft4XKlQN3ZQrvibsqIzYUWxBB9k/edit)
(zdieľanie: ktokoľvek s odkazom môže zobraziť). Tabuľku upravujete priamo v Google Sheets.

| Stĺpec | Význam |
|---|---|
| `nazov` | názov organizácie, ako sa zobrazí na mape |
| `typ` | `firma`, `institucia`, `skola`, `samosprava` alebo `komunita` (podľa toho sú filtre a farba bodu) |
| `ulica`, `mesto`, `krajina` | sídlo; `krajina` ako kód (`SK`, `CZ`, …). Na mape sú iba slovenské organizácie, ostatné ostávajú v tabuľke ako evidencia |
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

## Registračné formuláre a komunitná výzva

Dva vlastné formuláre na webe, bez Google:

- `pridat-sa.html` – jednotlivec (meno, e-mail, kraj, súhlas; ostatné nepovinné),
- `pridat-organizaciu.html` – organizácia (názov, obec, typ, popis, kontakt; IČO a ulica nepovinné).
  Sídlo overujeme ručne pred zápisom na mapu; ak je uvedené IČO, služba si pri registrácii uloží
  názov a adresu z Registra právnických osôb.

Odosielajú sa do **registračnej služby** v priečinku `server/` (čistý Python + SQLite, bez závislostí),
ktorá beží na serveri Geosupportu (Hetzner, Norimberg) na adrese z `js/config.js` (`api`).

| Súbor | Účel |
|---|---|
| `server/app.py` | služba: `POST /api/jednotlivec`, `POST /api/organizacia`, `GET /api/stat`, `GET /api/ico` |
| `server/test_app.py` | testy na dočasnej databáze (`python3 server/test_app.py`) |
| `server/deploy.sh` | nasadenie: testy → kód do `/opt/qgis-sk` → systemd `qgis-sk` (používateľ `qgissk`) → nginx `qgis.geosupport.sk` → kontrola |
| `server/admin.py`, `server/admin/` | administrácia v prehliadači na `/admin`: registrácie s časom, organizácie a ich stav, príklady použitia, návštevnosť, CSV, mazanie záznamov; obnovuje sa každých 30 s |
| `server/export.py` | export pre správcu (na serveri): `jednotlivci`, `organizacie [nová]`, `oznac <IČO> overená` |
| `server/admin.sh` | to isté zo svojho počítača cez SSH: `zoznam`, `organizacie`, `csv`, `navstevnost`, `pribehy`, `sledovat` |
| `server/import_povodni.py` | prenesie pôvodných členov do databázy (úplné záznamy z `scripts/povodni_z_formulara.py`, uložené v `server/.private/povodni-plne.csv`); starší spôsob cez odtlačky e-mailov ostáva podporovaný |
| `server/backup.py` | denná záloha databázy do `/var/backups/qgis-sk` (30 dní) |

Zásady: API nikdy nevracia osobné údaje, iba súčty. Služba nezapisuje IP adresy ani obsah do logov.
Databáza je na serveri v `/var/lib/qgis-sk/registracie.db`, čitateľná len pre používateľa služby.
Ochrana pred robotmi: skryté pole, minimálny čas vyplnenia, limit požiadaviek, kontrola pôvodu.

**Jednotlivci** sa na mape nezobrazujú. Dashboard „Komunita podľa krajov“ berie živé súčty z `/api/stat`
(nové registrácie + pôvodní členovia, ktorí sa ešte neregistrovali nanovo). Ak služba nie je dostupná,
použijú sa záložné čísla z `data/stat.json`.

**Organizácie** z formulára idú do stavu „nová“. Na mapu sa dostanú po overení: export čakajúcich
(`export.py organizacie nová`), kontrola sídla, doplnenie riadku do zdieľanej tabuľky pre mapu
(súradnice), potom `export.py oznac <IČO> overená`. Kraj organizácie sa určí zo súradníc pri synchronizácii.

**Administrácia.** `https://<služba>/admin`, prihlásenie menom a heslom. Zobrazuje všetkých ľudí vrátane prenesených z pôvodného formulára (príznak „pôvodný člen“, kraj môže byť odhad alebo prázdny), záznamy sa dajú upraviť, doplniť internou poznámkou alebo zmazať. Účty vytvára root na serveri:
`ssh -t root@server qgis-sk-admin pridat <meno>` (heslo sa zadáva skryto, min. 12 znakov; `zoznam`,
`odobrat <meno>`). Heslá sú uložené len ako PBKDF2 odtlačky. Po 8 neúspešných pokusoch je prihlásenie
na 15 minút zablokované, sedenie trvá 12 hodín, každý zásah (stav, zmazanie, export) sa zapisuje do denníka.

**Potvrdenie e-mailom.** Keď je na serveri nastavená schránka (`ssh -t root@server qgis-sk-set-smtp
<schránka> [adresa pre upozornenia tímu]`, heslo sa zadáva skryto), registrácia jednotlivca platí až po
kliknutí na odkaz z e-mailu (`potvrdenie.html?t=…`, platnosť 7 dní). Bez nastavenej schránky platí
registrácia hneď. Na rovnakú adresu chodia tímu upozornenia na novú organizáciu a nový príklad použitia.
Vypnutie: `qgis-sk-set-smtp --vypnut`.

**Príklady použitia.** Oba formuláre majú nepovinný blok „Riešite s QGIS niečo zaujímavé?“. Výpis:
`python3 /opt/qgis-sk/export.py pribehy`. Zverejňujeme ich len po dohode s autorom.

**Návštevnosť.** `js/meranie.js` posiela pri načítaní stránky anonymný záznam (cesta, doména odkazujúcej
stránky alebo `?utm_source=`). Služba ukladá iba denné súčty; žiadne cookies, žiadne IP adresy,
rešpektuje „Do Not Track“. Prehľad: `python3 /opt/qgis-sk/export.py navstevnost [dní]` ukáže po dňoch
návštevníkov, zobrazenia, otvorenia formulára, registrácie a zdroje. Do odkazov v kampaniach pridávajte
napr. `?utm_source=facebook`.

**Náhľad pri zdieľaní.** `images/og-vyzva.jpg` (1200×630) generuje `scripts/og_image.py` z dát mapy;
po väčšej zmene počtu organizácií ho stačí pregenerovať.

Lokálny test formulárov: spustiť službu
`PORT=18774 QGISSK_DB=/tmp/q.db QGISSK_ORIGINS=http://localhost:8765 python3 server/app.py`
a web cez `python3 -m http.server 8765`.

## Blog a RSS

Nový článok = nový súbor `blog/<slug>.html` (skopírovať existujúci, upraviť obsah) + riadok v
`blog/index.html` + položka `<item>` vo `feed.xml` (nový článok hore).

**Každý článok má autora.** Pod nadpisom je riadok `<p class="byline">` s menom autora (a zdrojom, ak
článok vychádza z cudzieho textu), v zozname blogu meno pod anotáciou a vo `feed.xml` prvok
`<dc:creator>`. Prevzaté texty vždy s odkazom na originál a menom pôvodného autora. QGIS.org odporúča novinky
posielať aj na https://feed.qgis.org.

## Podujatia

Časová os je v `index.html` v sekcii `#podujatia`. Poradie je: zvýraznená novinka (karta `.featured` nad zoznamom), potom položka „Pripravujeme“ ako
prvý `<li>` v zozname `.timeline`, pod ňou podujatia od najnovšieho. Nové podujatie sa vkladá hneď pod „Pripravujeme“.

## Tím a údaje o združení

Stránka `o-nas.html`: zoznam tímu, ciele zo stanov, IČO, registrácia a odkaz na
`dokumenty/Stanovy_QGIS_Slovensko.pdf`. Pri zmene štatutára alebo stanov upraviť tu a v pätičke
kontaktu na `index.html`.

## Externé závislosti

- Font Cairo z Google Fonts
- MapLibre GL JS 4.7.1 z cdnjs (načíta sa až vtedy, keď sa mapa blíži do zorného poľa)
- Vektorové dlaždice a písma máp: [OpenFreeMap](https://openfreemap.org) (dáta © prispievatelia OpenStreetMap, schéma OpenMapTiles), bez kľúča
- Výškový model pre tieňovaný reliéf a 3D terén: AWS Terrain Tiles (Mapzen), bez kľúča
- Hranice krajov (`data/sk-kraje.json`): © prispievatelia OpenStreetMap (ODbL), stiahnuté cez Nominatim

Štýl mapy je vlastný a je celý v `js/mapa.js` (funkcia `styl()`): farby, vrstvy, popisy. Kraje sú
vyfarbené podľa počtu ľudí v komunite, organizácie sú body (oranžová = firmy, zelená = ostatné),
blízke body sa zlučujú do prstenca s číslom, ktorého farby ukazujú podiel firiem a ostatných organizácií. Kartogram krajov je žltý, aby sa neplietol s bodmi. Legenda je priamo v mape.

## Licencia

Obsah CC BY-SA 4.0. Logo QGIS podľa pravidiel ochrannej známky QGIS.org.
