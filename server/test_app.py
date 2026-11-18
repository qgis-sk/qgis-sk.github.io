#!/usr/bin/env python3
"""Testy služby na dočasnej databáze: python3 server/test_app.py
Beh 1: bez pošty (registrácia platí hneď). Beh 2: s potvrdením e-mailom (pošta do priečinka)."""
import email, email.policy, glob, hashlib, json, os, re, subprocess, sys, tempfile, time, urllib.request, urllib.error
here = os.path.dirname(os.path.abspath(__file__))
ok = True

def check(name, cond):
    global ok; ok = ok and bool(cond); print(("OK   " if cond else "FAIL ") + name)

def run(port, extra_env, body):
    tmp = tempfile.mkdtemp()
    env = dict(os.environ, PORT=str(port), QGISSK_DB=os.path.join(tmp, "t.db"), QGISSK_ORIGINS="https://qgis.sk", **extra_env(tmp))
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "NOTIFY_TO"):
        env.pop(k, None) if k not in extra_env(tmp) else None
    p = subprocess.Popen([sys.executable, os.path.join(here, "app.py")], env=env)
    base = "http://127.0.0.1:" + str(port)

    def call(path, data=None, origin="https://qgis.sk", ua="Mozilla/5.0 test"):
        req = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json", "Origin": origin, "User-Agent": ua})
        try:
            r = urllib.request.urlopen(req, timeout=15); return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)
    try:
        for _ in range(50):
            try: call("/api/zdravie"); break
            except Exception: time.sleep(0.1)
        body(call, env, tmp)
    finally:
        p.terminate()

good = {"meno": "Test Osoba", "email": "nova@example.org", "kraj": "Prešovský", "suhlas": True, "t": 5, "oblast": ["Súkromný sektor", "vymyslené"]}
org = {"nazov": "Test s.r.o.", "ico": "51287153", "obec": "Klenov", "typ": "firma", "popis": "Geoportály a analýzy.", "kontakt_meno": "A B", "kontakt_email": "a@example.org", "suhlas": True, "t": 5}

def bez_posty(call, env, tmp):
    print("-- bez pošty --")
    h = hashlib.sha256(b"stary@example.org").hexdigest()
    subprocess.run([sys.executable, os.path.join(here, "import_povodni.py")], input=(h + ",Bratislavský\n" + "a" * 64 + ",\n").encode(), env=env, check=True, stdout=subprocess.DEVNULL)
    c, st = call("/api/stat"); check("štatistika s pôvodnými", c == 200 and st["ludia_spolu"] == 2 and st["kraje"]["Bratislavský"] == 1 and st["kraj_neznamy"] == 1 and st["povodni_nacitani"])
    c, r = call("/api/jednotlivec", dict(good, pribeh="Mapujeme studne v teréne.\n\n\n\nCez QField.", pribeh_odkaz="https://example.org/mapa")); check("registrácia človeka", c == 200 and r["ok"] and r["poradie_v_kraji"] == 1 and r["ludia_spolu"] == 3 and "potvrdit" not in r)
    c, r = call("/api/jednotlivec", dict(good, kraj="Košický")); check("opakovaná registrácia aktualizuje", c == 200 and r["aktualizacia"] and r["ludia_spolu"] == 3)
    c, r = call("/api/jednotlivec", dict(good, email="STARY@example.org", kraj="Košický")); check("pôvodný člen sa nezapočíta dvakrát", c == 200 and r["povodna_registracia"] and r["ludia_spolu"] == 3)
    c, st = call("/api/stat"); check("presun pôvodného do nového kraja", st["kraje"]["Bratislavský"] == 0 and st["kraje"]["Košický"] == 2)
    c, r = call("/api/jednotlivec", dict(good, email="zly")); check("zlý e-mail odmietnutý", c == 400 and r["pole"] == "email")
    c, r = call("/api/jednotlivec", dict(good, email="x@example.org", suhlas=False)); check("bez súhlasu odmietnuté", c == 400)
    c, r = call("/api/jednotlivec", dict(good, email="bot@example.org", web_stranka="http://spam")); c2, st = call("/api/stat")
    check("robot sa neuloží", c == 200 and st["ludia_spolu"] == 3)
    c, r = call("/api/jednotlivec", dict(good, email="y@example.org"), origin="https://zly.example"); check("cudzí pôvod odmietnutý", c == 403)
    c, r = call("/api/organizacia", dict(org, pribeh="Pasport zelene v QGIS.")); check("registrácia organizácie", c == 200 and r["ok"])
    c, r = call("/api/organizacia", dict(org, ico="123")); check("zlé IČO odmietnuté", c == 400 and r["pole"] == "ico")
    bez = dict(org, ico="", nazov="Základná škola Test", obec="Prešov")
    c, r = call("/api/organizacia", bez); c2, st = call("/api/stat"); check("organizácia bez IČO", c == 200 and r["ok"] and not r["aktualizacia"] and st["organizacie_cakaju_na_overenie"] == 2)
    c, r = call("/api/organizacia", dict(bez, nazov="základná škola test", popis="Iný popis školy.")); check("rovnaký názov a obec sa aktualizuje", c == 200 and r["aktualizacia"])
    c, r = call("/api/organizacia", dict(bez, obec="")); check("bez obce odmietnuté", c == 400 and r["pole"] == "obec")
    c, st = call("/api/stat"); check("organizácie čakajú na overenie", st["organizacie_cakaju_na_overenie"] == 2)
    check("štatistika neobsahuje osobné údaje", "example.org" not in json.dumps(st))
    exp = lambda *a: subprocess.run([sys.executable, os.path.join(here, "export.py")] + list(a), env=env, capture_output=True, text=True).stdout
    check("export jednotlivcov", "nova@example.org" in exp("jednotlivci"))
    out = exp("pribehy"); check("export príbehov", "Mapujeme studne" in out and "Pasport zelene" in out and "example.org/mapa" in out and "\n\n\n" not in out.split("Mapujeme")[1][:60])
    # prenos pôvodných členov ako úplných záznamov
    full = ("email,meno,kraj,kraj_odhad,vytvorene,oblast,novinky,poznamka\n"
            "stary@example.org,Stará Osoba,Bratislavský,1,2020-11-18T10:00:00Z,[],1,Pôvodná registrácia\n"
            "dalsi@example.org,Ďalší Člen,,0,2021-02-01T10:00:00Z,[],0,Pôvodná registrácia\n"
            "tretia@example.org,Tretia Osoba,Nitriansky,1,2021-03-01T10:00:00Z,[],1,Pôvodná registrácia\n")
    out = subprocess.run([sys.executable, os.path.join(here, "import_povodni.py")], input=full.encode(), env=env, capture_output=True, text=False).stdout.decode()
    time.sleep(0.1); call("/api/jednotlivec", dict(good, email="vynuluj-cache@example.org", web_stranka="x"))
    subprocess.run([sys.executable, "-c", "import sqlite3,os; c=sqlite3.connect(os.environ['QGISSK_DB']); c.execute(\"UPDATE jednotlivci SET upravene=upravene\"); c.commit()"], env=env)
    c, r = call("/api/jednotlivec", dict(good, email="x-cache@example.org", kraj="Trnavský")); c, st = call("/api/stat")
    check("prenos pôvodných: 2 noví + 2 prenesení + 1 už bol, odtlačky zmazané", "prenesených pôvodných členov: 2" in out and "už boli v databáze: 1" in out and st["ludia_spolu"] == 5 and st["kraj_neznamy"] == 1 and st["kraje"]["Nitriansky"] == 1 and st["povodne_bez_obnovy"] == 2 and st["nove_registracie"] == 2)
    c, r = call("/api/jednotlivec", dict(good, email="dalsi@example.org", kraj="Žilinský")); c2, st = call("/api/stat")
    check("pôvodný člen si doplní kraj", r["povodna_registracia"] and not r["aktualizacia"] and st["ludia_spolu"] == 5 and st["kraj_neznamy"] == 0 and st["kraje"]["Žilinský"] == 1 and st["povodne_bez_obnovy"] == 1)
    # návštevnosť
    call("/api/n", {"p": "/", "r": "l.facebook.com"}); call("/api/n", {"p": "/pridat-sa.html", "s": "Facebook"}); call("/api/n", {"p": "/", "r": "qgis.sk"})
    call("/api/n", {"p": "/<script>", "r": "x"}); call("/api/n", {"p": "/"}, ua="Googlebot/2.1")
    out = exp("navstevnost")
    den = [l for l in out.splitlines() if re.match(r"\d{4}-\d\d-\d\d", l)]
    check("návštevnosť: 1 návštevník, 3 zobrazenia, 1× formulár", den and den[0].split()[1:4] == ["1", "3", "1"])
    check("návštevnosť: zdroje", re.search(r"facebook\.com\s+1", out) and re.search(r"facebook\s+1", out) and re.search(r"priamo\s+1", out) and "script" not in out and "Googlebot" not in out)

def s_postou(call, env, tmp):
    print("-- s potvrdením e-mailom --")
    mails = lambda: sorted(glob.glob(os.path.join(tmp, "mail", "*.eml")))
    c, r = call("/api/jednotlivec", good); c2, st = call("/api/stat")
    check("registrácia čaká na potvrdenie", c == 200 and r.get("potvrdit") is True and st["ludia_spolu"] == 0 and len(mails()) == 1)
    msg = email.message_from_file(open(mails()[0], encoding="utf-8"), policy=email.policy.default)
    m = msg.get_content()
    tok = re.search(r"potvrdenie\.html\?t=([A-Za-z0-9_-]+)", m)
    check("e-mail má odkaz, adresáta a adresu pre odpovede", tok and msg["To"] == "nova@example.org" and "Potvr" in msg["Subject"] and "QGIS Slovensko" in msg["From"] and msg["Reply-To"] == "kontakt@example.org")
    c, r = call("/api/potvrdit", {"t": "x" * 30}); check("zlý token odmietnutý", c == 410)
    c, r = call("/api/potvrdit", {"t": tok.group(1)}); c2, st = call("/api/stat")
    check("potvrdenie zapíše človeka", c == 200 and r["ok"] and r["poradie_v_kraji"] == 1 and st["ludia_spolu"] == 1)
    c, r = call("/api/potvrdit", {"t": tok.group(1)}); check("token sa dá použiť raz", c == 410)
    c, r = call("/api/jednotlivec", dict(good, kraj="Košický")); c2, st = call("/api/stat")
    check("zmena údajov bez potvrdenia sa neprejaví", r.get("potvrdit") and st["kraje"]["Prešovský"] == 1 and st["kraje"]["Košický"] == 0)
    for _ in range(2): call("/api/jednotlivec", dict(good, kraj="Košický"))
    c, r = call("/api/jednotlivec", dict(good, kraj="Košický")); check("najviac 3 e-maily denne na adresu", c == 429)
    n = len(mails()); c, r = call("/api/organizacia", org); time.sleep(0.5)
    check("upozornenie tímu na novú organizáciu", c == 200 and len(mails()) == n + 1 and email.message_from_file(open(mails()[-1], encoding="utf-8"), policy=email.policy.default)["To"] == "tim@example.org")

def administracia(call, env, tmp):
    print("-- administrácia --")
    sys.path.insert(0, here); import admin as A
    base = "http://127.0.0.1:" + env["PORT"]
    def req(path, data=None, cookie="", headers=None):
        h = {"Content-Type": "application/json", "Origin": base, "X-Admin": "1"}
        if headers is not None: h = headers
        if cookie: h["Cookie"] = cookie
        r = urllib.request.Request(base + path, data=json.dumps(data).encode() if data is not None else None, headers=h)
        try:
            o = urllib.request.urlopen(r, timeout=15); body = o.read(); return o.status, body, o.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers
    c, b, h = req("/admin"); check("stránka administrácie", c == 200 and b"spr" in b and "default-src 'self'" in h["Content-Security-Policy"])
    c, b, h = req("/admin/api/prehlad"); check("bez prihlásenia žiadne údaje", c == 401 and b"example" not in b)
    c, b, h = req("/admin/api/login", {"meno": "miki", "heslo": "x"}); check("bez účtov sa nedá prihlásiť", c == 503)
    json.dump({"miki": A.hash_pw("spravne-heslo-123", it=1000)}, open(env["QGISSK_ADMIN_FILE"], "w"))
    call("/api/jednotlivec", dict(good, pribeh="Mapa studní."))
    call("/api/organizacia", dict(org, ico="", nazov="Škola <script>", obec="Prešov"))
    c, b, h = req("/admin/api/login", {"meno": "miki", "heslo": "zle"}); check("zlé heslo odmietnuté", c == 401)
    c, b, h = req("/admin/api/login", {"meno": "miki", "heslo": "spravne-heslo-123"}, headers={"Content-Type": "application/json", "Origin": "https://zly.example", "X-Admin": "1"}); check("prihlásenie z cudzej stránky odmietnuté", c == 403)
    c, b, h = req("/admin/api/login", {"meno": "Miki", "heslo": "spravne-heslo-123"})
    ck = (h["Set-Cookie"] or "").split(";")[0]
    check("prihlásenie", c == 200 and ck.startswith("qsa=") and "HttpOnly" in h["Set-Cookie"] and "SameSite=Strict" in h["Set-Cookie"])
    c, b, h = req("/admin/api/prehlad", cookie=ck); d = json.loads(b)
    check("prehľad s údajmi", c == 200 and d["jednotlivci"][0]["email"] == "nova@example.org" and d["organizacie"][0]["ico"] == "" and d["stat"]["ludia_spolu"] == 1 and "dni" in d)
    oid = d["organizacie"][0]["id"]; pid = d["jednotlivci"][0]["id"]
    c, b, h = req("/admin/api/organizacia", {"id": oid, "stav": "overená"}, cookie=ck, headers={"Content-Type": "application/json", "Origin": base}); check("zmena bez hlavičky X-Admin odmietnutá", c == 403)
    c, b, h = req("/admin/api/organizacia", {"id": oid, "stav": "overená"}, cookie=ck); c2, st = call("/api/stat"); check("zmena stavu organizácie", c == 200 and st["organizacie_cakaju_na_overenie"] == 0)
    c, b, h = req("/admin/api/upravit", {"co": "jednotlivci", "id": pid, "zmeny": {"meno": "Nové Meno", "email": "nova@example.org", "kraj": "Košický", "poznamka": "volal, oprava kraja", "novinky": True}}, cookie=ck)
    c2, b2, h2 = req("/admin/api/prehlad", cookie=ck); dd = json.loads(b2)["jednotlivci"][0]; c3, st = call("/api/stat")
    check("úprava človeka", c == 200 and dd["meno"] == "Nové Meno" and dd["kraj"] == "Košický" and dd["poznamka"].startswith("volal") and dd["novinky"] == 1 and st["kraje"]["Košický"] == 1 and st["kraje"]["Prešovský"] == 0)
    c, b, h = req("/admin/api/upravit", {"co": "jednotlivci", "id": pid, "zmeny": {"meno": "X Y", "email": "zly", "kraj": "Košický"}}, cookie=ck); check("úprava so zlým e-mailom odmietnutá", c == 400)
    c, b, h = req("/admin/api/upravit", {"co": "jednotlivci", "id": pid, "zmeny": {"meno": "X Y", "email": "nova@example.org", "kraj": "Atlantída"}}, cookie=ck); check("úprava s neznámym krajom odmietnutá", c == 400)
    c, b, h = req("/admin/api/upravit", {"co": "organizacie", "id": oid, "zmeny": {"nazov": "Škola opravená", "obec": "Sabinov", "typ": "skola", "popis": "Opravený popis.", "ico": "51287153", "kontakt_meno": "A B", "kontakt_email": "a@example.org"}}, cookie=ck)
    c2, b2, h2 = req("/admin/api/prehlad", cookie=ck); oo = json.loads(b2)["organizacie"][0]
    check("úprava organizácie", c == 200 and oo["nazov"] == "Škola opravená" and oo["obec"] == "Sabinov" and oo["ico"] == "51287153")
    c, b, h = req("/admin/api/csv?co=jednotlivci", cookie=ck); check("export CSV", c == 200 and b"nova@example.org" in b and "attachment" in h["Content-Disposition"])
    c, b, h = req("/admin/api/csv?co=povodni", cookie=ck); check("export inej tabuľky odmietnutý", c == 400)
    c, b, h = req("/admin/api/zmazat", {"co": "jednotlivci", "id": pid}, cookie=ck); c2, st = call("/api/stat"); check("zmazanie registrácie", c == 200 and st["ludia_spolu"] == 0)
    c, b, h = req("/admin/api/logout", {}, cookie=ck); c2, b2, h2 = req("/admin/api/prehlad", cookie=ck); check("odhlásenie", c == 200 and c2 == 401)
    for _ in range(8): req("/admin/api/login", {"meno": "miki", "heslo": "zle"})
    c, b, h = req("/admin/api/login", {"meno": "miki", "heslo": "spravne-heslo-123"}); check("zablokovanie po opakovaných pokusoch", c == 429)

run(18773, lambda tmp: {}, bez_posty)
run(18777, lambda tmp: {"QGISSK_ADMIN_FILE": os.path.join(tmp, "admin.json"), "QGISSK_COOKIE_SECURE": "0"}, administracia)
run(18775, lambda tmp: {"QGISSK_MAIL_DIR": os.path.join(tmp, "mail"), "NOTIFY_TO": "tim@example.org", "MAIL_FROM": "registracia@example.org", "MAIL_REPLY_TO": "kontakt@example.org"}, s_postou)
sys.exit(0 if ok else 1)
