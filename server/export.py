#!/usr/bin/env python3
"""Nástroje pre správcu (spúšťa sa na serveri ako root).

  python3 export.py jednotlivci > jednotlivci.csv
  python3 export.py organizacie [nová]           všetky alebo iba čakajúce na overenie
  python3 export.py oznac <ICO> overená           po prenesení organizácie na mapu
  python3 export.py pribehy                       príklady použitia QGIS, o ktoré sa ľudia podelili
  python3 export.py navstevnost [dní]             návštevnosť webu a registrácie po dňoch (predvolene 14)
"""
import csv, datetime, os, sqlite3, sys
DB = os.environ.get("QGISSK_DB", "/var/lib/qgis-sk/registracie.db")
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
cmd = sys.argv[1] if len(sys.argv) > 1 else ""

if cmd == "oznac" and len(sys.argv) == 4:
    n = con.execute("UPDATE organizacie SET stav = ? WHERE ico = ?", (sys.argv[3], sys.argv[2])).rowcount
    con.commit(); print("zmenených riadkov:", n); sys.exit(0)

if cmd == "pribehy":
    for tab, kto in (("jednotlivci", "meno"), ("organizacie", "nazov")):
        for r in con.execute("SELECT * FROM " + tab + " WHERE COALESCE(pribeh, '') <> '' OR COALESCE(pribeh_odkaz, '') <> '' ORDER BY upravene"):
            kontakt = r["email"] if tab == "jednotlivci" else r["kontakt_email"]
            print("=" * 70); print(r[kto], "|", kontakt, "|", r["upravene"][:10])
            if r["pribeh"]: print(r["pribeh"])
            if r["pribeh_odkaz"]: print("Odkaz:", r["pribeh_odkaz"])
    sys.exit(0)

if cmd == "navstevnost":
    dni = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    od = (datetime.date.today() - datetime.timedelta(days=dni - 1)).isoformat()
    reg = {r[0]: r[1] for r in con.execute("SELECT substr(vytvorene, 1, 10), COUNT(*) FROM jednotlivci WHERE vytvorene >= ? GROUP BY 1", (od,))}
    org = {r[0]: r[1] for r in con.execute("SELECT substr(vytvorene, 1, 10), COUNT(*) FROM organizacie WHERE vytvorene >= ? GROUP BY 1", (od,))}
    form = {r[0]: r[1] for r in con.execute("SELECT den, SUM(pocet) FROM navstevy WHERE den >= ? AND stranka LIKE '/pridat-sa%' GROUP BY 1", (od,))}
    print("%-11s %12s %11s %10s %12s %12s" % ("deň", "návštevníci", "zobrazenia", "formulár", "registrácie", "organizácie"))
    for r in con.execute("SELECT * FROM dni WHERE den >= ? ORDER BY den", (od,)):
        print("%-11s %12d %11d %10d %12d %12d" % (r["den"], r["navstevnici"], r["zobrazenia"], form.get(r["den"], 0), reg.get(r["den"], 0), org.get(r["den"], 0)))
    print("\nOdkiaľ prišli (zobrazenia):")
    for r in con.execute("SELECT zdroj, SUM(pocet) n FROM navstevy WHERE den >= ? GROUP BY zdroj ORDER BY n DESC LIMIT 12", (od,)):
        print("  %-32s %6d" % (r["zdroj"], r["n"]))
    print("\nNajnavštevovanejšie stránky:")
    for r in con.execute("SELECT stranka, SUM(pocet) n FROM navstevy WHERE den >= ? GROUP BY stranka ORDER BY n DESC LIMIT 12", (od,)):
        print("  %-32s %6d" % (r["stranka"], r["n"]))
    c = con.execute("SELECT COUNT(*) FROM cakajuce").fetchone()[0]
    print("\nRegistrácie čakajúce na potvrdenie e-mailom:", c)
    sys.exit(0)

if cmd not in ("jednotlivci", "organizacie"):
    sys.exit(__doc__)
q = "SELECT * FROM " + cmd
args = ()
if cmd == "organizacie" and len(sys.argv) > 2:
    q += " WHERE stav = ?"; args = (sys.argv[2],)
rows = con.execute(q + " ORDER BY id", args).fetchall()
w = csv.writer(sys.stdout)
if rows:
    w.writerow(rows[0].keys())
    for r in rows: w.writerow(list(r))
