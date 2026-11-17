// Konfigurácia webu qgis.sk.
// api: registračná služba QGIS Slovensko (server Geosupport, Norimberg). Pri lokálnom náhľade
// sa používa služba spustená na tomto počítači: PORT=18774 QGISSK_DB=/tmp/q.db
// QGISSK_ORIGINS=http://localhost:8765 python3 server/app.py
window.QGISSK = {
  api: (location.hostname === "localhost" || location.hostname === "127.0.0.1")
    ? "http://localhost:18774"
    : "https://qgis.geosupport.sk"
};
