// Anonymné počítanie návštev pre QGIS Slovensko: bez cookies, bez ukladania IP adries,
// iba denné súčty podľa stránky a zdroja. Rešpektuje nastavenie „Do Not Track“.
(function () {
  if (location.hostname !== "qgis.sk" && location.hostname !== "www.qgis.sk") return;
  if (navigator.doNotTrack === "1" || window.doNotTrack === "1") return;
  var api = (window.QGISSK || {}).api || "https://qgis.geosupport.sk";
  var q = new URLSearchParams(location.search), ref = "";
  try { ref = document.referrer ? new URL(document.referrer).hostname : ""; } catch (e) {}
  try {
    fetch(api + "/api/n", {
      method: "POST", keepalive: true, headers: { "Content-Type": "text/plain" },
      body: JSON.stringify({ p: location.pathname, r: ref, s: q.get("utm_source") || q.get("z") || "" })
    }).catch(function () {});
  } catch (e) {}
})();
