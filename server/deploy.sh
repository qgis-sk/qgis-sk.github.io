#!/bin/bash
# Nasadenie registračnej služby QGIS Slovensko na server Geosupportu (Hetzner).
# Použitie: ./server/deploy.sh      (z koreňa repozitára; vyžaduje SSH prístup root kľúčom)
set -euo pipefail
HOST="${QGISSK_HOST:-root@178.104.15.246}"
cd "$(dirname "$0")"

echo "== testy =="
python3 test_app.py

echo "== kód =="
ssh "$HOST" 'install -d -m 755 /opt/qgis-sk'
rsync -a --delete --exclude deploy --exclude .private --exclude '__pycache__' --exclude 'deploy.sh' --exclude 'admin.sh' --exclude 'test_app.py' ./ "$HOST:/opt/qgis-sk/"
scp -q deploy/qgis-sk.service deploy/qgis-sk-backup.service deploy/qgis-sk-backup.timer "$HOST:/etc/systemd/system/"
scp -q deploy/qgis.geosupport.sk.nginx "$HOST:/etc/nginx/sites-available/qgis.geosupport.sk"
scp -q deploy/qgis-sk-limit.conf "$HOST:/etc/nginx/conf.d/qgis-sk-limit.conf"
scp -q deploy/qgis-sk-set-smtp deploy/qgis-sk-admin "$HOST:/usr/local/sbin/"
ssh "$HOST" 'chmod 700 /usr/local/sbin/qgis-sk-set-smtp /usr/local/sbin/qgis-sk-admin'


echo "== záloha databázy pred reštartom =="
ssh "$HOST" 'python3 /opt/qgis-sk/backup.py pred-nasadenim'

echo "== služba =="
ssh "$HOST" '
set -e
id qgissk >/dev/null 2>&1 || useradd --system --home-dir /var/lib/qgis-sk --shell /usr/sbin/nologin qgissk
install -d -o qgissk -g qgissk -m 700 /var/lib/qgis-sk
chown -R root:root /opt/qgis-sk && chmod -R go-w /opt/qgis-sk
ln -sfn /etc/nginx/sites-available/qgis.geosupport.sk /etc/nginx/sites-enabled/qgis.geosupport.sk
systemctl daemon-reload
systemctl enable -q qgis-sk qgis-sk-backup.timer
systemctl restart qgis-sk
systemctl start qgis-sk-backup.timer
nginx -t 2>&1 | tail -2
systemctl reload nginx
sleep 1
systemctl is-active qgis-sk
'

if [ -f .private/povodni-plne.csv ]; then
  echo "== pôvodní členovia (úplné záznamy do databázy) =="
  ssh "$HOST" 'runuser -u qgissk -- env QGISSK_DB=/var/lib/qgis-sk/registracie.db python3 /opt/qgis-sk/import_povodni.py' < .private/povodni-plne.csv
  sleep 21
elif [ -f .private/povodni.csv ]; then
  echo "== pôvodné registrácie (odtlačky e-mailov) =="
  ssh "$HOST" 'runuser -u qgissk -- env QGISSK_DB=/var/lib/qgis-sk/registracie.db python3 /opt/qgis-sk/import_povodni.py' < .private/povodni.csv
  sleep 21
fi

echo "== kontrola živej služby =="
curl -fsS https://qgis.geosupport.sk/api/zdravie && echo
curl -fsS https://qgis.geosupport.sk/api/stat | head -c 300 && echo
curl -fsS -o /dev/null -w "administrácia: %{http_code}\n" https://qgis.geosupport.sk/admin
echo "Hotovo."
