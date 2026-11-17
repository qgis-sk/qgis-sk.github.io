#!/usr/bin/env python3
"""Rýchly test služby na dočasnej databáze: python3 server/test_app.py"""
import json, os, subprocess, sys, tempfile, time, urllib.request, urllib.error, hashlib
tmp = tempfile.mkdtemp(); port = "18773"
env = dict(os.environ, PORT=port, QGISSK_DB=os.path.join(tmp, "t.db"), QGISSK_ORIGINS="https://qgis.sk")
here = os.path.dirname(os.path.abspath(__file__))
p = subprocess.Popen([sys.executable, os.path.join(here, "app.py")], env=env)
base = "http://127.0.0.1:" + port

def call(path, data=None, origin="https://qgis.sk"):
    req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json", "Origin": origin})
    try:
        r = urllib.request.urlopen(req, timeout=15); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)

ok = True
def check(name, cond):
    global ok; ok = ok and cond; print(("OK   " if cond else "FAIL ") + name)
try:
    for _ in range(50):
        try: call("/api/zdravie"); break
        except Exception: time.sleep(0.1)
    # pôvodný člen s odhadom kraja
    h = hashlib.sha256(b"stary@example.org").hexdigest()
    subprocess.run([sys.executable, os.path.join(here, "import_povodni.py")], input=(h + ",Bratislavský\n" + "a" * 64 + ",\n").encode(), env=env, check=True)
    c, st = call("/api/stat"); check("štatistika s pôvodnými", c == 200 and st["ludia_spolu"] == 2 and st["kraje"]["Bratislavský"] == 1 and st["kraj_neznamy"] == 1 and st["povodni_nacitani"])
    good = {"meno": "Test Osoba", "email": "nova@example.org", "kraj": "Prešovský", "suhlas": True, "t": 5, "oblast": ["Súkromný sektor", "vymyslené"]}
    c, r = call("/api/jednotlivec", good); check("registrácia človeka", c == 200 and r["ok"] and r["poradie_v_kraji"] == 1 and r["ludia_spolu"] == 3)
    c, r = call("/api/jednotlivec", dict(good, kraj="Košický")); check("opakovaná registrácia aktualizuje", c == 200 and r["aktualizacia"] and r["ludia_spolu"] == 3)
    c, r = call("/api/jednotlivec", dict(good, email="STARY@example.org", kraj="Košický")); check("pôvodný člen sa nezapočíta dvakrát", c == 200 and r["povodna_registracia"] and r["ludia_spolu"] == 3)
    c, st = call("/api/stat"); check("presun pôvodného do nového kraja", st["kraje"]["Bratislavský"] == 0 and st["kraje"]["Košický"] == 2)
    c, r = call("/api/jednotlivec", dict(good, email="zly")); check("zlý e-mail odmietnutý", c == 400 and r["pole"] == "email")
    c, r = call("/api/jednotlivec", dict(good, email="x@example.org", suhlas=False)); check("bez súhlasu odmietnuté", c == 400)
    c, r = call("/api/jednotlivec", dict(good, email="bot@example.org", web_stranka="http://spam")); c2, st = call("/api/stat")
    check("robot sa neuloží", c == 200 and st["ludia_spolu"] == 3)
    c, r = call("/api/jednotlivec", dict(good, email="y@example.org"), origin="https://zly.example"); check("cudzí pôvod odmietnutý", c == 403)
    org = {"nazov": "Test s.r.o.", "ico": "51287153", "typ": "firma", "popis": "Geoportály a analýzy.", "kontakt_meno": "A B", "kontakt_email": "a@example.org", "suhlas": True, "t": 5}
    c, r = call("/api/organizacia", org); check("registrácia organizácie", c == 200 and r["ok"])
    c, r = call("/api/organizacia", dict(org, ico="123")); check("zlé IČO odmietnuté", c == 400 and r["pole"] == "ico")
    c, st = call("/api/stat"); check("organizácia čaká na overenie", st["organizacie_cakaju_na_overenie"] == 1)
    out = subprocess.run([sys.executable, os.path.join(here, "export.py"), "jednotlivci"], env=env, capture_output=True, text=True).stdout
    check("export jednotlivcov", "nova@example.org" in out and "stary@example.org" in out)
    check("štatistika neobsahuje osobné údaje", "example.org" not in json.dumps(st))
finally:
    p.terminate()
sys.exit(0 if ok else 1)
