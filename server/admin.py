"""QGIS Slovensko – administrácia registrácií (prehľad v prehliadači).

Prístup: https://<služba>/admin, prihlásenie menom a heslom. Účty spravuje root na serveri
príkazom `qgis-sk-admin` (heslá sú uložené iba ako PBKDF2 odtlačky v /etc/qgis-sk/admin.json).
Sedenia sú len v pamäti (reštart služby odhlási), cookie je HttpOnly + Secure + SameSite=Strict.
"""
import csv
import datetime
import hashlib
import hmac
import io
import json
import os
import secrets
import threading
import time
import urllib.parse

ADMIN_FILE = os.environ.get("QGISSK_ADMIN_FILE", "/etc/qgis-sk/admin.json")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin")
SECURE = os.environ.get("QGISSK_COOKIE_SECURE", "1") != "0"
ITER = 600000
SEDENIE_S = 12 * 3600
STAVY = ("nová", "overená", "zamietnutá")
_sess = {}
_fails = {}
_lock = threading.Lock()
core = {}


def init(**kw):
    core.update(kw)
    with core["db"]() as con:
        con.execute("CREATE TABLE IF NOT EXISTS dennik (cas TEXT, kto TEXT, co TEXT)")


def hash_pw(pw, salt=None, it=ITER):
    salt = salt or secrets.token_hex(16)
    return "pbkdf2_sha256$%d$%s$%s" % (it, salt, hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), it).hex())


def check_pw(pw, stored):
    try:
        _, it, salt, h = stored.split("$")
        return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), int(it)).hex(), h)
    except Exception:
        return False


def accounts():
    try:
        with open(ADMIN_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _blocked(key, add=False):
    """Najviac 8 neúspešných pokusov za 15 minút na adresu aj na účet."""
    t = time.time()
    with _lock:
        lst = [x for x in _fails.get(key, []) if t - x < 900]
        if add:
            lst.append(t)
        _fails[key] = lst
        return len(lst) >= 8


def _user(h):
    for part in (h.headers.get("Cookie") or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == "qsa":
            with _lock:
                s = _sess.get(v)
                if s and s[1] > time.time():
                    _sess[v] = (s[0], time.time() + SEDENIE_S)
                    return s[0], v
    return None, None


def _out(h, code, body, ctype="application/json; charset=utf-8", extra=()):
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False)
    if isinstance(body, str):
        body = body.encode("utf-8")
    h.send_response(code)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(body)))
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("X-Frame-Options", "DENY")
    h.send_header("Referrer-Policy", "no-referrer")
    h.send_header("X-Robots-Tag", "noindex, nofollow")
    h.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    for k, v in extra:
        h.send_header(k, v)
    h.end_headers()
    h.wfile.write(body)


def _log(kto, co):
    with core["db"]() as con:
        con.execute("INSERT INTO dennik (cas, kto, co) VALUES (?, ?, ?)", (core["now"](), kto, co))


def _rows(con, q, args=()):
    return [dict(r) for r in con.execute(q, args).fetchall()]


def prehlad():
    od = (datetime.date.today() - datetime.timedelta(days=29)).isoformat()
    with core["db"]() as con:
        ludia = _rows(con, "SELECT * FROM jednotlivci ORDER BY id DESC")
        org = _rows(con, "SELECT * FROM organizacie ORDER BY id DESC")
        dni = _rows(con, "SELECT * FROM dni WHERE den >= ? ORDER BY den DESC", (od,))
        form = {r["den"]: r["n"] for r in _rows(con, "SELECT den, SUM(pocet) n FROM navstevy WHERE den >= ? AND stranka LIKE '/pridat-sa%' GROUP BY den", (od,))}
        zdroje = _rows(con, "SELECT zdroj, SUM(pocet) n FROM navstevy WHERE den >= ? GROUP BY zdroj ORDER BY n DESC LIMIT 15", (od,))
        stranky = _rows(con, "SELECT stranka, SUM(pocet) n FROM navstevy WHERE den >= ? GROUP BY stranka ORDER BY n DESC LIMIT 15", (od,))
        cakajuce = con.execute("SELECT COUNT(*) FROM cakajuce").fetchone()[0]
    for r in ludia:
        for k in ("oblast", "zaujmy", "prispiet"):
            try:
                r[k] = json.loads(r[k] or "[]")
            except ValueError:
                r[k] = []
    for r in org:
        try:
            r["ponuka"] = json.loads(r["ponuka"] or "[]")
        except ValueError:
            r["ponuka"] = []
        r["ico"] = "" if (r["ico"] or "").startswith("?") else r["ico"]
    reg = {}
    for r in ludia:
        reg[r["vytvorene"][:10]] = reg.get(r["vytvorene"][:10], 0) + 1
    regorg = {}
    for r in org:
        regorg[r["vytvorene"][:10]] = regorg.get(r["vytvorene"][:10], 0) + 1
    for d in dni:
        d["formular"] = form.get(d["den"], 0)
        d["registracie"] = reg.get(d["den"], 0)
        d["organizacie"] = regorg.get(d["den"], 0)
    return {"stat": core["stat"](), "jednotlivci": ludia, "organizacie": org, "dni": dni, "zdroje": zdroje,
            "stranky": stranky, "cakajuce": cakajuce, "cas": core["now"]()}


def _csv(co):
    with core["db"]() as con:
        rows = con.execute("SELECT * FROM " + co + " ORDER BY id").fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    if rows:
        w.writerow(rows[0].keys())
        for r in rows:
            w.writerow(list(r))
    return "﻿" + out.getvalue()      # BOM, aby Excel správne zobrazil diakritiku


def handle(h, method, u, body=None):
    """Obslúži /admin…; vráti True, ak bola požiadavka vybavená."""
    path = u.path.rstrip("/") or "/admin"
    if not path.startswith("/admin"):
        return False
    if method == "GET":
        static = {"/admin": ("index.html", "text/html; charset=utf-8"), "/admin/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/admin/app.css": ("app.css", "text/css; charset=utf-8")}
        if path in static:
            name, ctype = static[path]
            with open(os.path.join(STATIC, name), "rb") as f:
                _out(h, 200, f.read(), ctype)
            return True
        kto, _ = _user(h)
        if path == "/admin/api/ja":
            _out(h, 200, {"meno": kto, "nastavene": bool(accounts())})
        elif not kto:
            _out(h, 401, {"chyba": "Prihláste sa."})
        elif path == "/admin/api/prehlad":
            _out(h, 200, prehlad())
        elif path == "/admin/api/csv":
            co = (urllib.parse.parse_qs(u.query).get("co") or [""])[0]
            if co not in ("jednotlivci", "organizacie"):
                _out(h, 400, {"chyba": "Neznámy export."})
            else:
                _log(kto, "export " + co)
                _out(h, 200, _csv(co), "text/csv; charset=utf-8",
                     [("Content-Disposition", 'attachment; filename="qgis-sk-%s-%s.csv"' % (co, datetime.date.today().isoformat()))])
        else:
            _out(h, 404, {"chyba": "Nenájdené."})
        return True
    # POST: iba z vlastnej stránky administrácie
    origin = h.headers.get("Origin") or ""
    host = h.headers.get("Host") or ""
    if h.headers.get("X-Admin") != "1" or urllib.parse.urlparse(origin).netloc != host:
        _out(h, 403, {"chyba": "Zakázané."})
        return True
    d = body if isinstance(body, dict) else {}
    ip = h.ip()
    if path == "/admin/api/login":
        meno = str(d.get("meno") or "").strip().lower()[:60]
        if _blocked("ip:" + ip) or _blocked("u:" + meno):
            _out(h, 429, {"chyba": "Príliš veľa neúspešných pokusov. Skúste to o 15 minút."})
            return True
        acc = accounts()
        if not acc:
            _out(h, 503, {"chyba": "Administrácia ešte nemá žiadny účet. Vytvorte ho na serveri príkazom qgis-sk-admin."})
            return True
        stored = acc.get(meno)
        ok = check_pw(str(d.get("heslo") or ""), stored) if stored else (check_pw("x", hash_pw("y", it=1000)) and False)
        if not ok:
            _blocked("ip:" + ip, add=True)
            _blocked("u:" + meno, add=True)
            time.sleep(0.4)
            _out(h, 401, {"chyba": "Nesprávne meno alebo heslo."})
            return True
        token = secrets.token_urlsafe(32)
        with _lock:
            for k in [k for k, v in _sess.items() if v[1] < time.time()]:
                _sess.pop(k, None)
            _sess[token] = (meno, time.time() + SEDENIE_S)
        _log(meno, "prihlásenie")
        _out(h, 200, {"meno": meno}, extra=[("Set-Cookie", "qsa=%s; Path=/admin; HttpOnly; SameSite=Strict; Max-Age=%d%s" % (token, SEDENIE_S, "; Secure" if SECURE else ""))])
        return True
    kto, token = _user(h)
    if path == "/admin/api/logout":
        with _lock:
            _sess.pop(token, None)
        _out(h, 200, {"ok": True}, extra=[("Set-Cookie", "qsa=; Path=/admin; HttpOnly; SameSite=Strict; Max-Age=0" + ("; Secure" if SECURE else ""))])
        return True
    if not kto:
        _out(h, 401, {"chyba": "Prihláste sa."})
        return True
    try:
        rid = int(d.get("id"))
    except (TypeError, ValueError):
        _out(h, 400, {"chyba": "Chýba záznam."})
        return True
    if path == "/admin/api/organizacia":
        if d.get("stav") not in STAVY:
            _out(h, 400, {"chyba": "Neznámy stav."})
            return True
        with core["db"]() as con:
            n = con.execute("UPDATE organizacie SET stav = ? WHERE id = ?", (d["stav"], rid)).rowcount
        _log(kto, "organizácia %d → %s" % (rid, d["stav"]))
    elif path == "/admin/api/zmazat":
        co = d.get("co")
        if co not in ("jednotlivci", "organizacie"):
            _out(h, 400, {"chyba": "Neznámy typ záznamu."})
            return True
        with core["db"]() as con:
            if co == "jednotlivci":
                row = con.execute("SELECT email FROM jednotlivci WHERE id = ?", (rid,)).fetchone()
                if row:
                    con.execute("DELETE FROM cakajuce WHERE email = ?", (row["email"],))
            n = con.execute("DELETE FROM " + co + " WHERE id = ?", (rid,)).rowcount
        _log(kto, "zmazaný záznam %s %d" % (co, rid))
    else:
        _out(h, 404, {"chyba": "Nenájdené."})
        return True
    core["cache"]["v"] = None
    _out(h, 200, {"ok": True, "zmenene": n})
    return True
