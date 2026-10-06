# Dáta organizácií

- `organizacie.json` – generované skriptom `scripts/sync_organizacie.py` zo zdieľanej tabuľky
  [QGIS SK – organizácie na mape](https://docs.google.com/spreadsheets/d/1JVPnrBTYYyEG4s7gUkXeO6AQWHwmCWVqL-4V0hoUTV8/edit).
  Needitovať ručne; GitHub Action ho prepíše 1. deň v mesiaci (alebo ručne cez „Run workflow“).
- `organizacie-tabulka.csv` – snímka tabuľky z 6.10.2026 (záloha, zdroj pre prvé naplnenie).
- Na mape sú iba riadky so `zobrazit_na_mape = áno` a so súradnicami. Nikdy fyzické osoby.
- Sídla overené cez RPO (api.statistics.sk), ORSR, ARES (CZ), Companies House (UK) a weby organizácií; zdroj je v stĺpci `zdroj_sidla`.
