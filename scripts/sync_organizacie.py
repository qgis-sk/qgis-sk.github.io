#!/usr/bin/env python3
"""Stiahne tabuľku organizácií (Google Sheet publikovaný ako CSV) a zapíše data/organizacie.json.

Použitie:
  SHEET_CSV_URL="https://docs.google.com/spreadsheets/d/1Yge6hcfhaaxkVRBLft4XKlQN3ZQrvibsqIzYUWxBB9k/gviz/tq?tqx=out:csv" \
  python3 scripts/sync_organizacie.py

Do JSON idú všetky slovenské riadky (krajina = SK) s platnými súradnicami. Riadok sa skryje iba hodnotou "skryť"
v stĺpci zobrazit_na_mape. Stĺpec zaradenie rozlišuje organizácie registrované cez formulár
od organizácií odvodených z pracovnej adresy člena (tie sú na mape označené "na potvrdenie").
Počty členov (data/stat.json) sa udržiavajú ručne.
Osobné údaje (e-maily, mená osôb) sa do JSON nikdy nezapisujú.
"""
import csv, io, json, os, sys, urllib.request, datetime, pathlib

URL = os.environ.get("SHEET_CSV_URL") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not URL:
    sys.exit("Chýba SHEET_CSV_URL")

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "organizacie.json"
TYPY = {"firma", "institucia", "skola", "samosprava", "komunita"}
KEEP = ["nazov", "typ", "mesto", "krajina", "lat", "lon", "web", "popis", "stav"]

KRAJE = json.loads((pathlib.Path(__file__).resolve().parent.parent / "data" / "sk-kraje.json").read_text(encoding="utf-8"))

def _in_ring(lon, lat, ring):
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i]; x2, y2 = ring[i - 1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside

def kraj_of(lon, lat):
    """Kraj podľa súradníc (bod v polygóne nad zjednodušenými hranicami krajov)."""
    for f in KRAJE["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            if _in_ring(lon, lat, poly[0]) and not any(_in_ring(lon, lat, h) for h in poly[1:]):
                return f["properties"]["nazov"]
    return ""

def norm(s): return (s or "").strip()
def hidden(s): return norm(s).lower() in ("skryť", "skryt", "hide", "nezobrazovať")

raw = urllib.request.urlopen(URL, timeout=60).read().decode("utf-8-sig")
rows = list(csv.DictReader(io.StringIO(raw)))
out = []
for r in rows:
    r = {k.strip().lower(): v for k, v in r.items() if k}
    if hidden(r.get("zobrazit_na_mape")): continue
    if (norm(r.get("krajina")) or "SK").upper() != "SK":
        print("preskakujem (zahraničná organizácia):", r.get("nazov"), file=sys.stderr); continue
    try:
        lat = float(norm(r.get("lat")).replace(",", ".")); lon = float(norm(r.get("lon")).replace(",", "."))
    except ValueError:
        print("preskakujem (bez súradníc):", r.get("nazov"), file=sys.stderr); continue
    typ = norm(r.get("typ")).lower()
    if typ not in TYPY: typ = "institucia"
    out.append({
        "nazov": norm(r.get("nazov")), "typ": typ, "mesto": norm(r.get("mesto")),
        "krajina": norm(r.get("krajina")) or "SK", "lat": round(lat, 5), "lon": round(lon, 5),
        "web": norm(r.get("web")), "popis": norm(r.get("popis")),
        "stav": "overené" if norm(r.get("stav")).lower().startswith("over") else "neoverené",
        "registracia": "člen" if norm(r.get("zaradenie")).lower().startswith("člen") else "organizácia",
        "kraj": kraj_of(lon, lat),
    })
out.sort(key=lambda o: o["nazov"].lower())
stat = {}
sp = OUT.parent / "stat.json"
if sp.exists():
    stat = {k: v for k, v in json.loads(sp.read_text(encoding="utf-8")).items() if not k.startswith("_")}
OUT.write_text(json.dumps({
    "_poznamka": "Generované automaticky zo zdieľanej tabuľky organizácií; needitovať ručne.",
    "aktualizovane": datetime.date.today().isoformat(),
    "stat": stat,
    "organizacie": out,
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"zapísaných organizácií: {len(out)} -> {OUT}")
