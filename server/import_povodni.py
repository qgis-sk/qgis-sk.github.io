#!/usr/bin/env python3
"""Načíta pôvodné registrácie (spred nového formulára) do databázy služby.

Vstup na štandardnom vstupe, jeden z dvoch tvarov:

1. Úplné záznamy – CSV s hlavičkou `email,meno,kraj,kraj_odhad,vytvorene,oblast,novinky,poznamka`
   (pripraví ho `scripts/povodni_z_formulara.py`). Ľudia sa zapíšu ako riadky s príznakom
   `povodny`; kto sa medzitým zaregistroval nanovo, ostáva so svojimi novými údajmi a iba dostane
   príznak. Odtlačky z kroku 2 sa potom zmažú, lebo už nie sú potrebné.
2. Odtlačky – riadky `sha256_emailu,kraj` bez hlavičky (pôvodný spôsob, bez osobných údajov).
"""
import csv, json, os, sqlite3, sys
DB = os.environ.get("QGISSK_DB", "/var/lib/qgis-sk/registracie.db")
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
rows = list(csv.reader(sys.stdin))
if rows and rows[0] and rows[0][0] == "email":
    hdr = rows[0]; nove = existuju = 0; mena = []
    uz = {r["meno"].strip().lower(): r["email"] for r in con.execute("SELECT meno, email FROM jednotlivci WHERE povodny = 0")}
    for raw in rows[1:]:
        r = dict(zip(hdr, raw))
        if "@" not in r.get("email", ""): continue
        row = con.execute("SELECT id, povodny FROM jednotlivci WHERE email = ?", (r["email"],)).fetchone()
        if row:
            if not row["povodny"]:
                con.execute("UPDATE jednotlivci SET povodny = 1, obnovil = 1 WHERE id = ?", (row["id"],))
            existuju += 1
            continue
        if r["meno"].strip().lower() in uz:
            mena.append(r["meno"])
        con.execute("INSERT INTO jednotlivci (vytvorene, upravene, suhlas, meno, email, kraj, kraj_odhad, oblast, novinky, poznamka, povodny, obnovil, clenstvo, zaujmy, prispiet)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, '[]', '[]')",
                    (r["vytvorene"], r["vytvorene"], r["vytvorene"], r["meno"], r["email"], r["kraj"], int(r["kraj_odhad"] or 0),
                     r["oblast"] or "[]", int(r["novinky"] or 0), r["poznamka"]))
        nove += 1
    n = con.execute("DELETE FROM povodni").rowcount
    con.commit()
    print("prenesených pôvodných členov: %d | už boli v databáze: %d | zmazaných odtlačkov: %d" % (nove, existuju, n))
    if mena:
        print("POZOR, rovnaké meno má pôvodný aj nový záznam s iným e-mailom (možná duplicita):", ", ".join(mena))
else:
    con.execute("CREATE TABLE IF NOT EXISTS povodni (email_hash TEXT PRIMARY KEY, kraj TEXT)")
    n = 0
    for row in rows:
        if not row or len(row[0]) != 64: continue
        con.execute("INSERT OR REPLACE INTO povodni (email_hash, kraj) VALUES (?, ?)", (row[0], (row[1] if len(row) > 1 else "") or None))
        n += 1
    con.commit(); print("načítaných odtlačkov:", n)
