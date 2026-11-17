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
org = {"nazov": "Test s.r.o.", "ico": "51287153", "typ": "firma", "popis": "Geoportály a analýzy.", "kontakt_meno": "A B", "kontakt_email": "a@example.org", "suhlas": True, "t": 5}

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
    c, st = call("/api/stat"); check("organizácia čaká na overenie", st["organizacie_cakaju_na_overenie"] == 1)
    check("štatistika neobsahuje osobné údaje", "example.org" not in json.dumps(st))
    exp = lambda *a: subprocess.run([sys.executable, os.path.join(here, "export.py")] + list(a), env=env, capture_output=True, text=True).stdout
    check("export jednotlivcov", "nova@example.org" in exp("jednotlivci"))
    out = exp("pribehy"); check("export príbehov", "Mapujeme studne" in out and "Pasport zelene" in out and "example.org/mapa" in out and "\n\n\n" not in out.split("Mapujeme")[1][:60])
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
    check("e-mail má odkaz a adresáta", tok and msg["To"] == "nova@example.org" and "Potvr" in msg["Subject"] and "QGIS Slovensko" in msg["From"])
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

run(18773, lambda tmp: {}, bez_posty)
run(18775, lambda tmp: {"QGISSK_MAIL_DIR": os.path.join(tmp, "mail"), "NOTIFY_TO": "tim@example.org", "MAIL_FROM": "registracia@example.org"}, s_postou)
sys.exit(0 if ok else 1)
