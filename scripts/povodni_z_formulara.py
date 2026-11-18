#!/usr/bin/env python3
"""Pripraví pôvodné registrácie (export odpovedí starého Google formulára) na prenos do služby.

  python3 scripts/povodni_z_formulara.py <odpovede.csv> > server/.private/povodni-plne.csv

Výstup obsahuje osobné údaje a patrí iba do `server/.private/` (neposiela sa do repozitára).
Vynecháva riadky, kde sa registrovala organizácia bez mena osoby. Kraj odhaduje podľa sídla
zamestnávateľa (pracovná e-mailová doména alebo organizácia pri mene); inak ostáva prázdny.
"""
import csv, datetime, json, re, sys
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Bratislava")
except Exception:
    TZ = datetime.timezone(datetime.timedelta(hours=1))
BA, TT, TN, NR, ZA, BB, PO, KE = "Bratislavský", "Trnavský", "Trenčiansky", "Nitriansky", "Žilinský", "Banskobystrický", "Prešovský", "Košický"
MIMO = "Mimo Slovenska"
DOM = {"savba.sk": BA, "stuba.sk": BA, "uniba.sk": BA, "euba.sk": BA, "enviro.gov.sk": BA, "mindop.sk": BA, "reland.sk": BA, "akuson.sk": BA,
       "nsat.sk": BA, "geology.sk": BA, "videomanual.eu": BA, "amavet962.org": BA, "fri.uniza.sk": ZA, "fpedas.uniza.sk": ZA, "uniag.sk": NR,
       "unipo.sk": PO, "geosupport.sk": PO, "spravaciest.sk": TT, "kanet.sk": TN, "banovce.sk": TN, "sopsr.sk": BB, "banskabystrica.sk": BB, "nekonecno.org": KE}
ZAHRANICIE = {"cnrs.fr", "natur.cuni.cz", "amigonet.cz", "vitezslavfiala.cz", "stutenhof.eu", "seznam.cz"}
MENO = [("lutra", BA), ("kajo", ZA), ("prešovská univerzita", PO), ("ustav manazmentu stu", BA), ("ttsk", TT), ("dopravný úrad", BA)]
IBA_ORGANIZACIA = {"Geografický ústav SAV", "videomanual.eu", "Geosupport, s.r.o.", "Solargis", "Ministerstvo životného prostredia Slovenskej republiky",
                   "MO SR", "Mindop", "Real Forest, s.r.o., Technická Univerzita vo Zvolene", "KCMD, UNIZA", "NEKONEČNO | architekti", "Landgeo s.r.o.",
                   "GT data", "Univerzita Karlova", "STU FEI", "Prírodovedecká Fakulta Univerzity Komenského v Bratislave", "Landmann s.r.o."}
OBLAST = [("akademick", "Akademická sféra a výskum"), ("verejn", "Verejná správa a samospráva"), ("štát", "Verejná správa a samospráva"),
          ("súkromn", "Súkromný sektor"), ("občians", "Občianska spoločnosť"), ("študent", "Študent/ka"), ("student", "Študent/ka"), ("hobby", "Voľný čas")]

def cas(s):
    d = datetime.datetime.strptime(s.strip(), "%m/%d/%Y %H:%M:%S").replace(tzinfo=TZ)
    return d.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

rows = [r for r in list(csv.reader(open(sys.argv[1], encoding="utf-8")))[1:] if len(r) >= 4]
ludia, podla_mena = {}, {}
for r in rows:
    meno, email = r[1].strip(), r[3].strip().lower()
    if meno in IBA_ORGANIZACIA or meno.isdigit() or "@" not in email:
        continue
    dom = email.split("@")[-1]
    kraj = MIMO if dom in ZAHRANICIE else DOM.get(dom) or next((k for kluc, k in MENO if kluc in meno.lower()), "")
    obl = []
    for kluc, nova in OBLAST:
        if kluc in r[2].lower() and nova not in obl:
            obl.append(nova)
    ocak = re.sub(r"\s+", " ", r[5]).strip() if len(r) > 5 else ""
    pozn = "Pôvodná registrácia (formulár 2020–2026)." + (" Očakávania: " + ocak if ocak else "")
    kluc_mena = " ".join(re.sub(r"[^a-záäčďéíĺľňóôŕšťúýž ]", "", re.split(r"\s+-\s+|,|\(", meno.lower().replace("ing.", ""))[0]).split())
    z = {"email": email, "meno": re.split(r",|\(|\s+-\s+", meno)[0].replace("Ing. ", "").strip() or meno, "kraj": kraj, "kraj_odhad": 1 if kraj else 0,
         "vytvorene": cas(r[0]), "oblast": json.dumps(obl, ensure_ascii=False), "novinky": 1 if r[4].strip().lower().startswith("á") else 0, "poznamka": pozn}
    if email in ludia:                                   # ten istý e-mail viackrát: ponechaj prvý dátum
        ludia[email]["kraj"] = ludia[email]["kraj"] or kraj
        continue
    if len(kluc_mena.split()) >= 2 and kluc_mena in podla_mena:   # tá istá osoba pod iným e-mailom: jeden záznam
        ludia[podla_mena[kluc_mena]]["poznamka"] += " Ďalší e-mail: " + email + "."
        continue
    podla_mena[kluc_mena] = email
    ludia[email] = z
w = csv.DictWriter(sys.stdout, fieldnames=["email", "meno", "kraj", "kraj_odhad", "vytvorene", "oblast", "novinky", "poznamka"])
w.writeheader()
for z in ludia.values():
    w.writerow(z)
print("ľudí: %d" % len(ludia), file=sys.stderr)
