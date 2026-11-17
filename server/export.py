#!/usr/bin/env python3
"""Export registrácií pre správcu (spúšťa sa na serveri ako root alebo používateľ qgissk).

  python3 export.py jednotlivci > jednotlivci.csv
  python3 export.py organizacie > organizacie.csv      # všetky
  python3 export.py organizacie nová                   # iba čakajúce na overenie
  python3 export.py oznac <ICO> overená                # po prenesení na mapu
"""
import csv, os, sqlite3, sys
DB = os.environ.get("QGISSK_DB", "/var/lib/qgis-sk/registracie.db")
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "oznac" and len(sys.argv) == 4:
    n = con.execute("UPDATE organizacie SET stav = ? WHERE ico = ?", (sys.argv[3], sys.argv[2])).rowcount
    con.commit(); print("zmenených riadkov:", n); sys.exit(0)
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
