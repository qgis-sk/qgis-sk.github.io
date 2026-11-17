#!/usr/bin/env python3
"""QGIS Slovensko – registračná služba.

Prijíma registrácie jednotlivcov a organizácií z formulárov na qgis.sk a vracia
súhrnné počty pre komunitnú mapu. Čistý Python (stdlib) + SQLite, bez závislostí.

Verejné:
  POST /api/jednotlivec   registrácia človeka (e-mail je kľúč, opakovaná registrácia údaje aktualizuje);
                          ak je nastavené odosielanie pošty, registrácia platí až po potvrdení odkazom z e-mailu
  POST /api/potvrdit      potvrdenie registrácie tokenom z e-mailu
  POST /api/n             anonymné počítanie návštev (bez cookies, bez ukladania IP)
  POST /api/organizacia   registrácia organizácie (kľúčom je IČO); na mapu ide až po ručnom overení
  GET  /api/stat          súhrnné počty ľudí po krajoch (žiadne osobné údaje)
  GET  /api/ico?ico=…     názov a sídlo podľa IČO z Registra právnických osôb (predvyplnenie formulára)
  GET  /api/zdravie       kontrola behu

Osobné údaje sa nikdy nevracajú cez API ani nezapisujú do logu. Export robí správca
na serveri skriptom export.py.
"""
import datetime
import hashlib
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import threading
import time
import urllib.parse
import urllib.request
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8773"))
DB = os.environ.get("QGISSK_DB", "/var/lib/qgis-sk/registracie.db")
ORIGINS = set(o.strip() for o in os.environ.get(
    "QGISSK_ORIGINS", "https://qgis.sk,https://www.qgis.sk").split(",") if o.strip())

SITE = os.environ.get("QGISSK_SITE", "https://qgis.sk").rstrip("/")
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT") or 587)
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
MAIL_FROM = os.environ.get("MAIL_FROM") or SMTP_USER
NOTIFY_TO = os.environ.get("NOTIFY_TO", "")
MAIL_DIR = os.environ.get("QGISSK_MAIL_DIR", "")      # iba testy: e-maily sa zapisujú do priečinka
MAIL_ON = bool(MAIL_DIR or (SMTP_HOST and SMTP_USER and SMTP_PASS))
TOKEN_DNI = 7

KRAJE = ["Bratislavský", "Trnavský", "Trenčiansky", "Nitriansky", "Žilinský",
         "Banskobystrický", "Prešovský", "Košický"]
MIMO = "Mimo Slovenska"
OBLASTI = ["Verejná správa a samospráva", "Súkromný sektor", "Akademická sféra a výskum",
           "Študent/ka", "Občianska spoločnosť", "Voľný čas"]
SKUSENOSTI = ["Začínam", "Bežne ho používam", "Pokročilý používateľ", "Vyvíjam pluginy alebo učím QGIS"]
ZAUJMY = ["Novinky o QGIS", "Stretnutia a konferencie", "Školenia a workshopy",
          "Pomoc pri riešení problémov", "Ponuky spolupráce a práce", "Slovenské dáta a návody"]
PRISPIET = ["Prednáška alebo ukážka", "Návod alebo článok", "Preklad QGIS do slovenčiny",
            "Pomoc s organizáciou podujatia", "Lektorovanie"]
TYPY = ["firma", "institucia", "skola", "samosprava", "komunita"]
PONUKA = ["Školenia", "Služby alebo vývoj", "Stáže a témy záverečných prác",
          "Priestory na stretnutie", "Otvorené dáta", "Prípadová štúdia na web"]

MAX_BODY = 16 * 1024
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s.]{2,}$")
ICO_RE = re.compile(r"^\d{8}$")
_lock = threading.Lock()
_hits = {}            # ip -> [časové pečiatky]  (len v pamäti, neukladá sa)
_stat_cache = {"t": 0, "v": None}
_dnes = {"den": "", "sol": b"", "videni": set()}      # dnešní návštevníci (len v pamäti, denne sa maže)


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS jednotlivci (
            id INTEGER PRIMARY KEY, vytvorene TEXT, upravene TEXT,
            meno TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE, kraj TEXT NOT NULL,
            oblast TEXT, skusenost TEXT, organizacia TEXT, zaujmy TEXT, prispiet TEXT,
            novinky INTEGER DEFAULT 0, clenstvo INTEGER DEFAULT 0, suhlas TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS organizacie (
            id INTEGER PRIMARY KEY, vytvorene TEXT, upravene TEXT,
            nazov TEXT NOT NULL, ico TEXT NOT NULL UNIQUE, typ TEXT NOT NULL,
            pracovisko TEXT, web TEXT, popis TEXT NOT NULL, ponuka TEXT,
            kontakt_meno TEXT NOT NULL, kontakt_email TEXT NOT NULL,
            rpo_nazov TEXT, rpo_adresa TEXT, stav TEXT DEFAULT 'nová', suhlas TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS povodni (
            email_hash TEXT PRIMARY KEY, kraj TEXT);
        CREATE TABLE IF NOT EXISTS cakajuce (
            token_hash TEXT PRIMARY KEY, email TEXT NOT NULL COLLATE NOCASE, udaje TEXT NOT NULL, vytvorene TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS navstevy (
            den TEXT, stranka TEXT, zdroj TEXT, pocet INTEGER DEFAULT 0, PRIMARY KEY (den, stranka, zdroj));
        CREATE TABLE IF NOT EXISTS dni (
            den TEXT PRIMARY KEY, navstevnici INTEGER DEFAULT 0, zobrazenia INTEGER DEFAULT 0);
        """)
        for tab in ("jednotlivci", "organizacie"):
            cols = [r[1] for r in con.execute("PRAGMA table_info(" + tab + ")")]
            for col in ("pribeh", "pribeh_odkaz"):
                if col not in cols:
                    con.execute("ALTER TABLE " + tab + " ADD COLUMN " + col + " TEXT")


def email_hash(email):
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def limited(ip, bucket, n, per=3600):
    """True, ak adresa prekročila n požiadaviek za `per` sekúnd."""
    key = bucket + ":" + ip
    t = time.time()
    with _lock:
        lst = [x for x in _hits.get(key, []) if t - x < per]
        if len(lst) >= n:
            _hits[key] = lst
            return True
        lst.append(t)
        _hits[key] = lst
        if len(_hits) > 5000:
            for k in list(_hits)[:1000]:
                _hits.pop(k, None)
    return False


def s(v, n):
    """Orezaný jednoriadkový text najviac n znakov."""
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def text(v, n):
    """Viacriadkový text najviac n znakov (zachová riadky, odstráni riadiace znaky)."""
    v = re.sub(r"[\x00-\x08\x0b-\x1f]", "", str(v or "")).replace("\r", "")
    return re.sub(r"\n{3,}", "\n\n", v).strip()[:n]


def url(v, n=300):
    v = s(v, n)
    return v if re.match(r"^https?://[^\s]+\.[^\s]+$", v) else ""


def posli(komu, predmet, telo):
    """Odošle e-mail. Vyhodí výnimku pri chybe."""
    m = EmailMessage()
    m["Subject"] = predmet
    m["From"] = "QGIS Slovensko <" + MAIL_FROM + ">"
    m["To"] = komu
    m.set_content(telo)
    if MAIL_DIR:
        os.makedirs(MAIL_DIR, exist_ok=True)
        with open(os.path.join(MAIL_DIR, str(time.time_ns()) + ".eml"), "w", encoding="utf-8") as f:
            f.write(m.as_string())
        return
    if SMTP_PORT == 465:
        srv = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20, context=ssl.create_default_context())
    else:
        srv = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        srv.starttls(context=ssl.create_default_context())
    try:
        srv.login(SMTP_USER, SMTP_PASS)
        srv.send_message(m)
    finally:
        try:
            srv.quit()
        except Exception:
            pass


def oznam_timu(predmet, telo):
    """Upozornenie tímu (ak je nastavené NOTIFY_TO); nikdy neblokuje odpoveď používateľovi."""
    if not (MAIL_ON and NOTIFY_TO):
        return

    def run():
        try:
            posli(NOTIFY_TO, predmet, telo)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()


def bez_prazdneho_pribehu(vals):
    """Pri aktualizácii neprepisuj skôr poslaný príklad použitia prázdnou hodnotou."""
    return {k: v for k, v in vals.items() if not (k in ("pribeh", "pribeh_odkaz") and not v)}


def uloz_jednotlivca(vals):
    """Zapíše alebo aktualizuje človeka; vráti odpoveď pre formulár."""
    email = vals["email"]
    t = now()
    with db() as con:
        row = con.execute("SELECT id FROM jednotlivci WHERE email = ?", (email,)).fetchone()
        if row:
            zmeny = bez_prazdneho_pribehu(vals)
            con.execute("UPDATE jednotlivci SET upravene=?, " + ", ".join(k + "=?" for k in zmeny) + " WHERE id=?",
                        [t] + list(zmeny.values()) + [row["id"]])
        else:
            cols = ["vytvorene", "upravene", "suhlas"] + list(vals)
            con.execute("INSERT INTO jednotlivci (" + ", ".join(cols) + ") VALUES (" + ", ".join("?" * len(cols)) + ")",
                        [t, t, t] + list(vals.values()))
        bol_povodny = con.execute("SELECT 1 FROM povodni WHERE email_hash = ?", (email_hash(email),)).fetchone()
        con.execute("DELETE FROM cakajuce WHERE email = ?", (email,))
    _stat_cache["v"] = None
    st = stat()
    kraj = vals["kraj"]
    if vals.get("pribeh"):
        oznam_timu("QGIS SK – nový príklad použitia od člena komunity",
                   "Člen komunity sa pri registrácii podelil o príklad použitia QGIS.\n"
                   "Pozrite si ho exportom na serveri: python3 /opt/qgis-sk/export.py pribehy\n")
    return {"ok": True, "aktualizacia": bool(row), "povodna_registracia": bool(bol_povodny),
            "kraj": kraj, "poradie_v_kraji": st["kraje"].get(kraj, st["mimo_sr"]),
            "ludia_spolu": st["ludia_spolu"]}


def navsteva(ip, ua, d):
    """Anonymné počítanie: denné súčty podľa stránky a zdroja. IP sa neukladá,
    slúži len na denný odtlačok v pamäti, aby sa návštevník počítal raz za deň."""
    stranka = str(d.get("p") or "/")[:80]
    if not re.match(r"^/[A-Za-z0-9/._-]*$", stranka):
        return
    zdroj = re.sub(r"[^a-z0-9._-]", "", str(d.get("s") or "").lower())[:30]
    if not zdroj:
        zdroj = re.sub(r"[^a-z0-9.-]", "", str(d.get("r") or "").lower())[:60]
        zdroj = re.sub(r"^(www|m|l|lm)\.", "", zdroj)
        if zdroj in ("qgis.sk", "localhost"):
            zdroj = ""
    den = datetime.date.today().isoformat()
    with _lock:
        if _dnes["den"] != den:
            _dnes.update(den=den, sol=secrets.token_bytes(16), videni=set())
        h = hashlib.sha256(_dnes["sol"] + ip.encode() + ua.encode()).digest()[:8]
        novy = h not in _dnes["videni"]
        if novy and len(_dnes["videni"]) < 200000:
            _dnes["videni"].add(h)
    with db() as con:
        con.execute("INSERT INTO navstevy (den, stranka, zdroj, pocet) VALUES (?, ?, ?, 1) "
                    "ON CONFLICT(den, stranka, zdroj) DO UPDATE SET pocet = pocet + 1", (den, stranka, zdroj or "priamo"))
        con.execute("INSERT INTO dni (den, navstevnici, zobrazenia) VALUES (?, ?, 1) "
                    "ON CONFLICT(den) DO UPDATE SET navstevnici = navstevnici + ?, zobrazenia = zobrazenia + 1",
                    (den, 1 if novy else 0, 1 if novy else 0))


def pick(values, allowed):
    if not isinstance(values, list):
        return []
    return [v for v in values if v in allowed]


def stat():
    t = time.time()
    if _stat_cache["v"] and t - _stat_cache["t"] < 20:
        return _stat_cache["v"]
    with db() as con:
        novi = con.execute("SELECT email, kraj FROM jednotlivci").fetchall()
        povodni = con.execute("SELECT email_hash, kraj FROM povodni").fetchall()
        org_cakaju = con.execute("SELECT COUNT(*) FROM organizacie WHERE stav = 'nová'").fetchone()[0]
    kraje = {k: 0 for k in KRAJE}
    mimo = 0
    nove_hash = set()
    for r in novi:
        nove_hash.add(email_hash(r["email"]))
        if r["kraj"] in kraje:
            kraje[r["kraj"]] += 1
        else:
            mimo += 1
    neznamy = 0
    zostava = 0
    for r in povodni:
        if r["email_hash"] in nove_hash:
            continue
        zostava += 1
        if r["kraj"] in kraje:
            kraje[r["kraj"]] += 1
        elif r["kraj"] == MIMO:
            mimo += 1
        else:
            neznamy += 1
    v = {
        "ludia_spolu": len(novi) + zostava,
        "nove_registracie": len(novi),
        "povodne_bez_obnovy": zostava,
        "povodni_nacitani": len(povodni) > 0,
        "kraje": kraje,
        "mimo_sr": mimo,
        "kraj_neznamy": neznamy,
        "organizacie_cakaju_na_overenie": org_cakaju,
        "aktualizovane": now(),
    }
    _stat_cache.update(t=t, v=v)
    return v


def rpo(ico):
    url = "https://api.statistics.sk/rpo/v1/search?" + urllib.parse.urlencode({"identifier": ico})
    req = urllib.request.Request(url, headers={"User-Agent": "qgis.sk registracia"})
    d = json.load(urllib.request.urlopen(req, timeout=8))
    res = d.get("results") or []
    if not res:
        return None
    e = res[0]

    def current(items):
        items = items or []
        live = [i for i in items if not i.get("validTo")]
        return (live or items)[-1] if items else {}

    name = current(e.get("fullNames")).get("value", "")
    a = current(e.get("addresses"))
    street = a.get("street") or ""
    if isinstance(street, dict):
        street = street.get("value", "")
    num = a.get("buildingNumber") or (a.get("regNumber") or "")
    mun = (a.get("municipality") or {}).get("value", "")
    psc = (a.get("postalCodes") or [""])[0]
    line = (" ".join(x for x in [street or mun.split(" - ")[0], str(num)] if x)).strip()
    adresa = ", ".join(x for x in [line, (psc + " " + mun).strip()] if x)
    return {"nazov": name, "adresa": adresa, "obec": mun, "zaniknuta": bool(e.get("termination"))}


class H(BaseHTTPRequestHandler):
    server_version = "qgis-sk"
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):   # žiadne logy s adresami ani obsahom
        pass

    def ip(self):
        return (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        origin = self.headers.get("Origin")
        if origin in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/zdravie":
            return self.send_json(200, {"ok": True})
        if u.path == "/api/stat":
            return self.send_json(200, stat())
        if u.path == "/api/ico":
            ico = (urllib.parse.parse_qs(u.query).get("ico") or [""])[0].strip()
            if not ICO_RE.match(ico):
                return self.send_json(400, {"chyba": "IČO má 8 číslic."})
            if limited(self.ip(), "ico", 40):
                return self.send_json(429, {"chyba": "Príliš veľa požiadaviek, skúste neskôr."})
            try:
                r = rpo(ico)
            except Exception:
                return self.send_json(502, {"chyba": "Register je momentálne nedostupný. Pokračujte, sídlo overíme neskôr."})
            if not r:
                return self.send_json(404, {"chyba": "Organizáciu s týmto IČO sme v registri nenašli."})
            return self.send_json(200, r)
        self.send_json(404, {"chyba": "Nenájdené."})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if u.path not in ("/api/jednotlivec", "/api/organizacia", "/api/potvrdit", "/api/n"):
            return self.send_json(404, {"chyba": "Nenájdené."})
        origin = self.headers.get("Origin")
        if origin not in ORIGINS:
            return self.send_json(403, {"chyba": "Formulár odošlite zo stránky qgis.sk."})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_BODY:
            return self.send_json(413, {"chyba": "Neplatná veľkosť požiadavky."})
        try:
            d = json.loads(self.rfile.read(n).decode("utf-8"))
            assert isinstance(d, dict)
        except Exception:
            return self.send_json(400, {"chyba": "Neplatné údaje."})
        if u.path == "/api/n":
            ua = self.headers.get("User-Agent") or ""
            if not limited(self.ip(), "n", 300) and not re.search(r"bot|crawl|spider|preview|monitor", ua, re.I):
                try:
                    navsteva(self.ip(), ua, d)
                except sqlite3.Error:
                    pass
            return self.send_json(200, {"ok": True})
        if u.path == "/api/potvrdit":
            if limited(self.ip(), "potvrdit", 60):
                return self.send_json(429, {"chyba": "Príliš veľa pokusov, skúste neskôr."})
            return self.potvrdit(d)
        if limited(self.ip(), "post", 40):
            return self.send_json(429, {"chyba": "Príliš veľa registrácií z jednej adresy. Skúste to o hodinu."})
        # ochrana pred robotmi: skryté pole musí ostať prázdne a formulár otvorený aspoň 2 s
        bot = bool(s(d.get("web_stranka"), 50)) or float(d.get("t") or 0) < 2
        try:
            if u.path == "/api/jednotlivec":
                return self.jednotlivec(d, bot)
            return self.organizacia(d, bot)
        except sqlite3.Error:
            return self.send_json(500, {"chyba": "Uloženie zlyhalo, skúste to prosím znova."})

    def jednotlivec(self, d, bot):
        meno = s(d.get("meno"), 120)
        email = s(d.get("email"), 254).lower()
        kraj = d.get("kraj")
        if len(meno) < 2:
            return self.send_json(400, {"chyba": "Uveďte meno.", "pole": "meno"})
        if not EMAIL_RE.match(email):
            return self.send_json(400, {"chyba": "E-mail nevyzerá správne.", "pole": "email"})
        if kraj not in KRAJE and kraj != MIMO:
            return self.send_json(400, {"chyba": "Vyberte kraj.", "pole": "kraj"})
        if d.get("suhlas") is not True:
            return self.send_json(400, {"chyba": "Bez súhlasu so spracúvaním údajov vás nevieme zapísať.", "pole": "suhlas"})
        if bot:
            return self.send_json(200, {"ok": True, "kraj": kraj, "poradie_v_kraji": 1, "ludia_spolu": stat()["ludia_spolu"]})
        vals = dict(
            meno=meno, email=email, kraj=kraj,
            oblast=json.dumps(pick(d.get("oblast"), OBLASTI), ensure_ascii=False),
            skusenost=d.get("skusenost") if d.get("skusenost") in SKUSENOSTI else "",
            organizacia=s(d.get("organizacia"), 160),
            zaujmy=json.dumps(pick(d.get("zaujmy"), ZAUJMY), ensure_ascii=False),
            prispiet=json.dumps(pick(d.get("prispiet"), PRISPIET), ensure_ascii=False),
            novinky=1 if d.get("novinky") is True else 0,
            clenstvo=1 if d.get("clenstvo") is True else 0,
            pribeh=text(d.get("pribeh"), 1200), pribeh_odkaz=url(d.get("pribeh_odkaz")))
        if not MAIL_ON:
            return self.send_json(200, uloz_jednotlivca(vals))
        # potvrdenie e-mailom: údaje čakajú, kým človek neklikne na odkaz
        den = now()[:10]
        with db() as con:
            con.execute("DELETE FROM cakajuce WHERE vytvorene < ?",
                        ((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=TOKEN_DNI)).strftime("%Y-%m-%dT%H:%M:%SZ"),))
            na_adresu = con.execute("SELECT COUNT(*) FROM cakajuce WHERE email = ? AND vytvorene >= ?", (email, den)).fetchone()[0]
            dnes_spolu = con.execute("SELECT COUNT(*) FROM cakajuce WHERE vytvorene >= ?", (den,)).fetchone()[0]
        if na_adresu >= 3:
            return self.send_json(429, {"chyba": "Na túto adresu sme dnes potvrdzovací e-mail už poslali. Pozrite si aj priečinok s nevyžiadanou poštou."})
        if dnes_spolu >= 600:
            return self.send_json(503, {"chyba": "Dnes je veľký záujem, skúste to prosím zajtra."})
        token = secrets.token_urlsafe(32)
        th = hashlib.sha256(token.encode()).hexdigest()
        with db() as con:
            con.execute("INSERT INTO cakajuce (token_hash, email, udaje, vytvorene) VALUES (?, ?, ?, ?)",
                        (th, email, json.dumps(vals, ensure_ascii=False), now()))
        odkaz = SITE + "/potvrdenie.html?t=" + token
        try:
            posli(email, "Potvrďte registráciu v slovenskej QGIS komunite",
                  "Dobrý deň,\n\n"
                  "ďakujeme za registráciu do slovenskej QGIS komunity. Potvrďte ju prosím kliknutím na odkaz:\n\n"
                  + odkaz + "\n\n"
                  "Odkaz platí " + str(TOKEN_DNI) + " dní. Po potvrdení vás pripočítame do komunity vo vašom kraji"
                  " (na mape sa nezobrazíte menovite).\n\n"
                  "Ak ste sa neregistrovali vy, tento e-mail ignorujte, nič sa neuloží.\n\n"
                  "QGIS Slovensko, o. z.\n" + SITE + "\n")
        except Exception:
            with db() as con:
                con.execute("DELETE FROM cakajuce WHERE token_hash = ?", (th,))
            return self.send_json(502, {"chyba": "Potvrdzovací e-mail sa nepodarilo odoslať. Skontrolujte adresu alebo to skúste neskôr.", "pole": "email"})
        self.send_json(200, {"ok": True, "potvrdit": True})

    def potvrdit(self, d):
        token = str(d.get("t") or "")
        if not re.match(r"^[A-Za-z0-9_-]{20,80}$", token):
            return self.send_json(400, {"chyba": "Neplatný odkaz."})
        th = hashlib.sha256(token.encode()).hexdigest()
        hranica = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=TOKEN_DNI)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with db() as con:
            row = con.execute("SELECT udaje FROM cakajuce WHERE token_hash = ? AND vytvorene >= ?", (th, hranica)).fetchone()
        if not row:
            return self.send_json(410, {"chyba": "Odkaz už bol použitý alebo vypršal. Ak ste registráciu potvrdili, je všetko v poriadku. Inak sa prosím zaregistrujte znova."})
        self.send_json(200, uloz_jednotlivca(json.loads(row["udaje"])))

    def organizacia(self, d, bot):
        nazov = s(d.get("nazov"), 200)
        ico = s(d.get("ico"), 20).replace(" ", "")
        typ = d.get("typ")
        popis = s(d.get("popis"), 150)
        k_meno = s(d.get("kontakt_meno"), 120)
        k_email = s(d.get("kontakt_email"), 254).lower()
        web = s(d.get("web"), 200)
        if len(nazov) < 2:
            return self.send_json(400, {"chyba": "Uveďte názov organizácie.", "pole": "nazov"})
        if not ICO_RE.match(ico):
            return self.send_json(400, {"chyba": "IČO má 8 číslic.", "pole": "ico"})
        if typ not in TYPY:
            return self.send_json(400, {"chyba": "Vyberte typ organizácie.", "pole": "typ"})
        if len(popis) < 5:
            return self.send_json(400, {"chyba": "Napíšte jednou vetou, ako QGIS používate.", "pole": "popis"})
        if web and not re.match(r"^https?://[^\s]+\.[^\s]+$", web):
            return self.send_json(400, {"chyba": "Web uveďte v tvare https://…", "pole": "web"})
        if len(k_meno) < 2:
            return self.send_json(400, {"chyba": "Uveďte kontaktnú osobu.", "pole": "kontakt_meno"})
        if not EMAIL_RE.match(k_email):
            return self.send_json(400, {"chyba": "E-mail kontaktnej osoby nevyzerá správne.", "pole": "kontakt_email"})
        if d.get("suhlas") is not True:
            return self.send_json(400, {"chyba": "Potvrďte prosím oprávnenie a súhlas so zverejnením.", "pole": "suhlas"})
        if bot:
            return self.send_json(200, {"ok": True})
        try:
            r = rpo(ico) or {}
        except Exception:
            r = {}
        vals = dict(nazov=nazov, ico=ico, typ=typ, pracovisko=s(d.get("pracovisko"), 200), web=web, popis=popis,
                    ponuka=json.dumps(pick(d.get("ponuka"), PONUKA), ensure_ascii=False),
                    kontakt_meno=k_meno, kontakt_email=k_email,
                    rpo_nazov=r.get("nazov", ""), rpo_adresa=r.get("adresa", ""),
                    pribeh=text(d.get("pribeh"), 1200), pribeh_odkaz=url(d.get("pribeh_odkaz")))
        t = now()
        with db() as con:
            row = con.execute("SELECT id FROM organizacie WHERE ico = ?", (ico,)).fetchone()
            if row:
                zmeny = bez_prazdneho_pribehu(vals)
                con.execute("UPDATE organizacie SET upravene=?, stav='nová', " + ", ".join(k + "=?" for k in zmeny) + " WHERE id=?",
                            [t] + list(zmeny.values()) + [row["id"]])
            else:
                cols = ["vytvorene", "upravene", "suhlas"] + list(vals)
                con.execute("INSERT INTO organizacie (" + ", ".join(cols) + ") VALUES (" + ", ".join("?" * len(cols)) + ")",
                            [t, t, t] + list(vals.values()))
        _stat_cache["v"] = None
        oznam_timu("QGIS SK – organizácia čaká na overenie: " + nazov,
                   "Nová registrácia organizácie na komunitnú mapu.\n\nNázov: " + nazov + "\nIČO: " + ico +
                   "\nRegister: " + (r.get("nazov", "") + ", " + r.get("adresa", "") if r.get("nazov") else "nenájdené") +
                   ("\nPridali aj príklad použitia." if vals["pribeh"] else "") +
                   "\n\nČakajúce: python3 /opt/qgis-sk/export.py organizacie nová\n")
        self.send_json(200, {"ok": True, "aktualizacia": bool(row), "overene_v_registri": bool(r.get("nazov"))})


if __name__ == "__main__":
    init_db()
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
