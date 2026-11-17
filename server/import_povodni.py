#!/usr/bin/env python3
"""Načíta pôvodné registrácie (pred novým formulárom) ako odtlačky e-mailov.

Vstup: CSV na štandardnom vstupe s riadkami `sha256_emailu,kraj` (kraj môže byť prázdny alebo
„Mimo Slovenska“). Surové e-maily sa na server neposielajú. Služba podľa odtlačku spozná, že sa
pôvodný člen zaregistroval nanovo, a nezapočíta ho dvakrát.
"""
import csv, os, sqlite3, sys
DB = os.environ.get("QGISSK_DB", "/var/lib/qgis-sk/registracie.db")
con = sqlite3.connect(DB)
con.execute("CREATE TABLE IF NOT EXISTS povodni (email_hash TEXT PRIMARY KEY, kraj TEXT)")
n = 0
for row in csv.reader(sys.stdin):
    if not row or len(row[0]) != 64: continue
    con.execute("INSERT OR REPLACE INTO povodni (email_hash, kraj) VALUES (?, ?)", (row[0], (row[1] if len(row) > 1 else "") or None))
    n += 1
con.commit(); print("načítaných odtlačkov:", n)
