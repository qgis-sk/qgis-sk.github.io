#!/usr/bin/env python3
"""Záloha databázy registrácií (SQLite backup API), ponecháva posledných 40 súborov.

  python3 backup.py                 denná záloha (spúšťa systemd timer): registracie-RRRR-MM-DD.db
  python3 backup.py pred-nasadenim  mimoriadna záloha s časom v názve (spúšťa deploy.sh pred reštartom)
"""
import datetime, glob, os, sqlite3, sys
DB = "/var/lib/qgis-sk/registracie.db"
OUT = "/var/backups/qgis-sk"
os.makedirs(OUT, mode=0o700, exist_ok=True)
if not os.path.exists(DB):
    print("databáza ešte neexistuje, nie je čo zálohovať"); sys.exit(0)
znacka = datetime.date.today().isoformat()
if len(sys.argv) > 1:
    znacka = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S") + "-" + "".join(c for c in sys.argv[1] if c.isalnum() or c == "-")[:30]
dst = os.path.join(OUT, "registracie-" + znacka + ".db")
src = sqlite3.connect(DB); bak = sqlite3.connect(dst)
with bak: src.backup(bak)
n = bak.execute("SELECT (SELECT COUNT(*) FROM jednotlivci), (SELECT COUNT(*) FROM organizacie)").fetchone()
bak.close(); src.close(); os.chmod(dst, 0o600)
for old in sorted(glob.glob(os.path.join(OUT, "registracie-*.db")), key=os.path.getmtime)[:-40]:
    os.remove(old)
print("záloha:", dst, "| ľudí:", n[0], "| organizácií:", n[1])
