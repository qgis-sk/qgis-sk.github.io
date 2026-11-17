#!/usr/bin/env python3
"""Denná záloha databázy registrácií (SQLite backup API), ponecháva posledných 30."""
import datetime, glob, os, sqlite3
DB = "/var/lib/qgis-sk/registracie.db"
OUT = "/var/backups/qgis-sk"
os.makedirs(OUT, mode=0o700, exist_ok=True)
dst = os.path.join(OUT, "registracie-" + datetime.date.today().isoformat() + ".db")
src = sqlite3.connect(DB); bak = sqlite3.connect(dst)
with bak: src.backup(bak)
bak.close(); src.close(); os.chmod(dst, 0o600)
for old in sorted(glob.glob(os.path.join(OUT, "registracie-*.db")))[:-30]:
    os.remove(old)
print("záloha:", dst)
