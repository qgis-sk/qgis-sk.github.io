#!/bin/bash
# Správca QGIS Slovensko – pohľad na registrácie zo svojho počítača (cez SSH na server služby).
#
#   ./server/admin.sh zoznam [N]     posledných N registrácií ľudí s časom (predvolene 30)
#   ./server/admin.sh organizacie    organizácie čakajúce na overenie
#   ./server/admin.sh csv            uloží úplné CSV (ľudia aj organizácie) do server/.private/export/
#   ./server/admin.sh navstevnost    návštevnosť webu a registrácie po dňoch
#   ./server/admin.sh pribehy        príklady použitia QGIS, o ktoré sa ľudia podelili
#   ./server/admin.sh sledovat       každú minútu vypíše nové registrácie (ukončenie Ctrl+C)
#
# Výstupy obsahujú osobné údaje. Priečinok server/.private/ sa do repozitára neposiela.
set -euo pipefail
cd "$(dirname "$0")"
HOST="${QGISSK_HOST:-root@178.104.15.246}"
R() { ssh -o BatchMode=yes "$HOST" "python3 /opt/qgis-sk/export.py $*"; }

tabulka() {   # CSV jednotlivcov zo štandardného vstupu → čitateľná tabuľka, čas v slovenskom pásme
python3 -c '
import csv, sys, datetime
try:
    from zoneinfo import ZoneInfo; TZ = ZoneInfo("Europe/Bratislava")
except Exception:
    TZ = None
n = int(sys.argv[1]); rows = list(csv.DictReader(sys.stdin))
def cas(s):
    d = datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    return (d.astimezone(TZ) if TZ else d).strftime("%d.%m. %H:%M")
print("spolu nových registrácií: %d" % len(rows))
print("%-12s %-28s %-34s %-16s %s" % ("čas", "meno", "e-mail", "kraj", "poznámka"))
for r in rows[-n:]:
    p = []
    if r["upravene"] != r["vytvorene"]: p.append("upravené " + cas(r["upravene"]))
    if r.get("clenstvo") == "1": p.append("chce členstvo v OZ")
    if r.get("novinky") == "1": p.append("novinky")
    if (r.get("pribeh") or r.get("pribeh_odkaz")): p.append("PRÍKLAD POUŽITIA")
    if r.get("organizacia"): p.append(r["organizacia"][:30])
    print("%-12s %-28s %-34s %-16s %s" % (cas(r["vytvorene"]), r["meno"][:28], r["email"][:34], r["kraj"], ", ".join(p)))
' "$1"
}

case "${1:-}" in
  zoznam)      R jednotlivci | tabulka "${2:-30}" ;;
  organizacie) R organizacie nová | python3 -c '
import csv, sys
rows = list(csv.DictReader(sys.stdin))
print("čakajú na overenie: %d" % len(rows))
for r in rows:
    ico = "IČO neuvedené" if r["ico"].startswith("?") else "IČO " + r["ico"]
    print("-" * 70); print(r["nazov"], "|", r.get("obec") or "", "|", ico, "|", r["typ"], "|", r["vytvorene"][:16].replace("T", " "), "UTC")
    print("  register:", r["rpo_nazov"], "|", r["rpo_adresa"]); print("  popis:", r["popis"])
    if r["web"]: print("  web:", r["web"])
    if r["pracovisko"]: print("  pracovisko:", r["pracovisko"])
    print("  kontakt:", r["kontakt_meno"], "|", r["kontakt_email"])
' ;;
  csv)         mkdir -p .private/export; D=$(date +%Y%m%d-%H%M)
               R jednotlivci > ".private/export/jednotlivci-$D.csv"; R organizacie > ".private/export/organizacie-$D.csv"
               echo "Uložené do: $(pwd)/.private/export/"; ls -la .private/export | tail -2 ;;
  navstevnost) R navstevnost "${2:-14}" ;;
  pribehy)     R pribehy ;;
  sledovat)    N=-1
               while true; do
                 C=$(R jednotlivci | python3 -c 'import csv,sys; print(len(list(csv.DictReader(sys.stdin))))')
                 if [ "$C" != "$N" ]; then echo "== $(date +%H:%M) – registrácií: $C =="; R jednotlivci | tabulka 8 | tail -n +3; N=$C; fi
                 sleep 60
               done ;;
  *)           sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//' ;;
esac
