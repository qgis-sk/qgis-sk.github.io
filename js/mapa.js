// Komunitná mapa QGIS Slovensko – MapLibre GL: tmavý podklad, reliéf a 3D terén, kraje vyfarbené
// podľa počtu ľudí, organizácie ako žiariace body so zhlukovaním, legenda priamo v mape.
// Otvorené zdroje bez kľúča: vektorové dlaždice OpenFreeMap (dáta OpenStreetMap), výškový model
// AWS Terrain Tiles (Mapzen). Knižnica sa načíta až vtedy, keď sa mapa blíži do zorného poľa.
window.QgisMapa = (function () {
  const VER = "4.7.1";
  const CDN = "https://cdnjs.cloudflare.com/ajax/libs/maplibre-gl/" + VER + "/maplibre-gl.min.";
  const DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
  const C = { bg: "#1b2a20", zelena: "#b4e36a", oranzova: "#ff9433", kraj: "#f0e64a", krajObrys: "#e3da55", text: "#dde7d8", panel: "#101a13" };
  const SK = [[16.75, 47.68], [22.62, 49.66]];
  const maly = () => window.matchMedia("(max-width: 720px)").matches;
  const pokoj = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const TYPY = { firma: "Firma", institucia: "Inštitúcia", skola: "Škola / univerzita", samosprava: "Samospráva", komunita: "Komunita" };

  let el, map, hotovo = false, popup, vybrane = null, naVyber = null, info, pulz = null, videna = false;
  let orgData = { type: "FeatureCollection", features: [] }, krajeGeo = null, krajePocty = {};

  function styl() {
    const noc = (z1, v1, z2, v2) => ["interpolate", ["linear"], ["zoom"], z1, v1, z2, v2];
    return {
      version: 8,
      glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
      sources: {
        osm: { type: "vector", url: "https://tiles.openfreemap.org/planet" },
        relief: { type: "raster-dem", tiles: [DEM], tileSize: 256, maxzoom: 12, encoding: "terrarium",
          attribution: 'reliéf <a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">AWS Terrain Tiles</a>' },
        teren: { type: "raster-dem", tiles: [DEM], tileSize: 256, maxzoom: 12, encoding: "terrarium" }
      },
      layers: [
        { id: "pozadie", type: "background", paint: { "background-color": C.bg } },
        { id: "tienovanie", type: "hillshade", source: "relief",
          paint: { "hillshade-shadow-color": "#0a1710", "hillshade-highlight-color": "#cfe6b4", "hillshade-accent-color": "#25402a",
            "hillshade-exaggeration": 0.72, "hillshade-illumination-direction": 315 } },
        { id: "lesy", type: "fill", source: "osm", "source-layer": "landcover", filter: ["==", ["get", "class"], "wood"], maxzoom: 12,
          paint: { "fill-color": "#2c5a31", "fill-opacity": 0.22 } },
        { id: "voda", type: "fill", source: "osm", "source-layer": "water", paint: { "fill-color": "#174652" } },
        { id: "rieky", type: "line", source: "osm", "source-layer": "waterway", filter: ["==", ["get", "class"], "river"],
          paint: { "line-color": "#2c7d8f", "line-width": noc(6, 0.6, 12, 2.2), "line-opacity": 0.9 } },
        { id: "cesty", type: "line", source: "osm", "source-layer": "transportation", minzoom: 7,
          filter: ["in", ["get", "class"], ["literal", ["motorway", "trunk", "primary"]]],
          paint: { "line-color": "#6b7c64", "line-width": noc(7, 0.4, 13, 1.8), "line-opacity": 0.55 } },
        { id: "ulice", type: "line", source: "osm", "source-layer": "transportation", minzoom: 11,
          filter: ["in", ["get", "class"], ["literal", ["secondary", "tertiary", "minor"]]],
          paint: { "line-color": "#4a5a45", "line-width": noc(11, 0.3, 15, 1.4), "line-opacity": 0.45 } },
        { id: "budovy", type: "fill", source: "osm", "source-layer": "building", minzoom: 13, paint: { "fill-color": "#33402f", "fill-opacity": 0.6 } },
        { id: "hranica", type: "line", source: "osm", "source-layer": "boundary", filter: ["==", ["get", "admin_level"], 2],
          paint: { "line-color": "#a9c4a2", "line-width": 1.1, "line-dasharray": [3, 2], "line-opacity": 0.6 } },
        { id: "sidla", type: "symbol", source: "osm", "source-layer": "place",
          filter: ["any",
            ["all", ["in", ["get", "class"], ["literal", ["city", "town"]]],
              ["<=", ["coalesce", ["get", "rank"], 20], ["step", ["zoom"], 5, 7, 7, 8, 9, 9, 12, 10, 30]]],
            ["all", [">=", ["zoom"], 10.5], ["in", ["get", "class"], ["literal", ["village", "suburb"]]]]],
          layout: { "text-field": ["coalesce", ["get", "name:sk"], ["get", "name"]], "text-font": ["Noto Sans Regular"],
            "text-size": noc(6, 10.5, 11, 14), "text-max-width": 8, "text-letter-spacing": 0.04 },
          paint: { "text-color": C.text, "text-halo-color": C.bg, "text-halo-width": 1.4, "text-opacity": 0.8 } }
      ]
    };
  }

  function nacitaj(cb) {
    if (window.maplibregl) return cb();
    const css = document.createElement("link"); css.rel = "stylesheet"; css.href = CDN + "css"; document.head.appendChild(css);
    const js = document.createElement("script"); js.src = CDN + "js"; js.onload = cb;
    js.onerror = () => chyba("Mapu sa nepodarilo načítať. Zoznam organizácií je vedľa.");
    document.head.appendChild(js);
  }

  function chyba(text) {
    el.classList.add("mapa-chyba"); el.textContent = text;
  }

  function vytvor() {
    try {
      map = new maplibregl.Map({
        container: el, style: styl(), bounds: SK, fitBoundsOptions: { padding: maly() ? 16 : 40 },
        minZoom: 5, maxZoom: 15, maxPitch: 62, attributionControl: false, cooperativeGestures: true,
        locale: {
          "CooperativeGesturesHandler.WindowsHelpText": "Mapu priblížite kolieskom so stlačeným Ctrl",
          "CooperativeGesturesHandler.MacHelpText": "Mapu priblížite kolieskom so stlačeným ⌘",
          "CooperativeGesturesHandler.MobileHelpText": "Mapu posuniete dvoma prstami",
          "NavigationControl.ZoomIn": "Priblížiť", "NavigationControl.ZoomOut": "Oddialiť", "NavigationControl.ResetBearing": "Otočiť na sever"
        }
      });
    } catch (e) { return chyba("Váš prehliadač nepodporuje zobrazenie tejto mapy. Zoznam organizácií je vedľa."); }
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");
    map.addControl({ onAdd: () => { const d = document.createElement("div"); d.className = "maplibregl-ctrl maplibregl-ctrl-group";
      const b = document.createElement("button"); b.type = "button"; b.title = "Celé Slovensko"; b.textContent = "SK"; b.className = "mapa-domov";
      b.onclick = domov; d.appendChild(b); return d; }, onRemove: () => {} }, "top-right");
    popup = new maplibregl.Popup({ closeButton: false, offset: 14, maxWidth: "280px", className: "mapa-popup" });
    map.on("load", poNacitani);
  }

  // základný záber: na mobile kolmo zhora, inak naklonený pohľad od juhu; pri náklone treba ísť bližšie
  function pohlad() {
    const c = map.cameraForBounds(SK, { padding: maly() ? 16 : 30 });
    if (maly()) return { center: c.center, zoom: c.zoom, pitch: 0, bearing: 0 };
    return { center: [19.5, 48.74], zoom: c.zoom + 0.08, pitch: 42, bearing: -6 };
  }
  function domov() {
    vyber(null); popup.remove();
    map.easeTo(Object.assign({ duration: pokoj ? 0 : 1400 }, pohlad()));
  }

  function poNacitani() {
    if (!maly()) map.setTerrain({ source: "teren", exaggeration: 1.6 });
    // kraje: výplň podľa počtu ľudí, obrys, zvýraznenie pod kurzorom
    map.addSource("kraje", { type: "geojson", data: krajeGeo || { type: "FeatureCollection", features: [] }, generateId: true });
    map.addLayer({ id: "kraje-vypln", type: "fill", source: "kraje", paint: { "fill-color": C.kraj,
      "fill-opacity": ["step", ["coalesce", ["get", "ludia"], 0], 0.07, 1, 0.17, 3, 0.26, 6, 0.35, 11, 0.44, 21, 0.53, 41, 0.62] } }, "voda");
    map.addLayer({ id: "kraje-obrys", type: "line", source: "kraje", paint: { "line-color": C.krajObrys,
      "line-width": ["case", ["boolean", ["feature-state", "nad"], false], 2.8, 1.2],
      "line-opacity": ["case", ["boolean", ["feature-state", "nad"], false], 1, 0.7] } }, "sidla");
    // organizácie: zhluky + body so žiarou
    map.addSource("org", { type: "geojson", data: orgData, cluster: true, clusterRadius: 34, clusterMaxZoom: 9,
      clusterProperties: { firmy: ["+", ["case", ["==", ["get", "typ"], "firma"], 1, 0]] } });
    const farba = ["case", ["==", ["get", "typ"], "firma"], C.oranzova, C.zelena];
    map.addLayer({ id: "bod-ziara", type: "circle", source: "org", filter: ["!", ["has", "point_count"]],
      paint: { "circle-color": farba, "circle-radius": 17, "circle-blur": 1, "circle-opacity": 0.5 } });
    map.addLayer({ id: "bod", type: "circle", source: "org", filter: ["!", ["has", "point_count"]],
      paint: { "circle-color": farba, "circle-radius": ["case", ["==", ["get", "id"], ["literal", ""]], 9, 6.5],
        "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.6 } });
    map.addLayer({ id: "bod-vyber", type: "circle", source: "org", filter: ["==", ["get", "id"], ""],
      paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": 15, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5 } });

    map.on("data", (e) => { if (e.sourceId === "org" && e.isSourceLoaded) zhluky(); });
    map.on("move", zhluky); map.on("moveend", zhluky);
    map.on("click", "bod", (e) => { const p = e.features[0].properties; ukaz(p, e.features[0].geometry.coordinates); vyber(p.id); naVyber && naVyber(p.id); });
    ["bod"].forEach((l) => { map.on("mouseenter", l, () => { map.getCanvas().style.cursor = "pointer"; }); map.on("mouseleave", l, () => { map.getCanvas().style.cursor = ""; }); });
    let nad = null;
    const krajInfo = (f) => {
      if (nad !== null) map.setFeatureState({ source: "kraje", id: nad }, { nad: false });
      nad = f ? f.id : null;
      if (f) { map.setFeatureState({ source: "kraje", id: nad }, { nad: true });
        const p = f.properties; info.textContent = p.nazov + ": " + sklon(p.ludia || 0, "človek", "ľudia", "ľudí") + " · " + sklon(p.org || 0, "organizácia", "organizácie", "organizácií"); info.classList.add("aktivne"); }
      else { info.textContent = maly() ? "Ťuknite na kraj alebo bod" : "Prejdite myšou ponad kraj"; info.classList.remove("aktivne"); }
    };
    map.on("mousemove", "kraje-vypln", (e) => { if (e.features[0].id !== nad) krajInfo(e.features[0]); });
    map.on("mouseleave", "kraje-vypln", () => krajInfo(null));
    map.on("click", "kraje-vypln", (e) => krajInfo(e.features[0]));
    prekrytia(); krajInfo(null);
    const atr = el.querySelector(".maplibregl-ctrl-attrib"); atr && atr.classList.remove("maplibregl-compact-show"); atr && atr.removeAttribute("open");
    hotovo = true; map.getSource("org").setData(orgData);
    // úvodný nájazd kamery, keď sa mapa prvýkrát objaví na obrazovke
    const io = new IntersectionObserver((z) => {
      const vidno = z[0].isIntersecting; if (vidno && !videna) { videna = true; if (!pokoj && !maly()) map.easeTo(Object.assign({ duration: 2400 }, pohlad())); else map.jumpTo(pohlad()); }
      vidno ? pulzuj() : stoj();
    }, { threshold: 0.35 });
    io.observe(el);
  }

  // Zhluk = prstenec zložený z farieb bodov, ktoré obsahuje (oranžová časť = firmy), s počtom v strede
  let znacky = {}, naMape = {};
  function prstenec(p) {
    const n = p.point_count, f = p.firmy || 0, r = n >= 12 ? 25 : n >= 5 ? 21 : 18, w = 6, R = r - w / 2, o = 2 * Math.PI * R;
    const NS = "http://www.w3.org/2000/svg", svg = document.createElementNS(NS, "svg");
    svg.setAttribute("width", 2 * r); svg.setAttribute("height", 2 * r); svg.setAttribute("viewBox", "0 0 " + 2 * r + " " + 2 * r); svg.setAttribute("class", "mapa-zhluk");
    const kruh = (farba, dlzka, posun) => { const c = document.createElementNS(NS, "circle"); c.setAttribute("cx", r); c.setAttribute("cy", r); c.setAttribute("r", R);
      c.setAttribute("fill", "none"); c.setAttribute("stroke", farba); c.setAttribute("stroke-width", w); c.setAttribute("stroke-dasharray", dlzka + " " + (o - dlzka));
      c.setAttribute("stroke-dashoffset", -posun); c.setAttribute("transform", "rotate(-90 " + r + " " + r + ")"); return c; };
    const stred = document.createElementNS(NS, "circle"); stred.setAttribute("cx", r); stred.setAttribute("cy", r); stred.setAttribute("r", r - w + 0.5); stred.setAttribute("fill", C.panel); stred.setAttribute("fill-opacity", "0.92");
    const t = document.createElementNS(NS, "text"); t.setAttribute("x", r); t.setAttribute("y", r); t.setAttribute("text-anchor", "middle"); t.setAttribute("dominant-baseline", "central"); t.textContent = n;
    svg.append(stred, kruh(C.zelena, o * (n - f) / n, 0), kruh(C.oranzova, o * f / n, o * (n - f) / n), t);
    return svg;
  }
  function zhluky() {
    if (!map.getSource("org") || !map.isSourceLoaded("org")) return;
    const nove = {};
    map.querySourceFeatures("org").forEach((f) => {
      const p = f.properties; if (!p.cluster || nove[p.cluster_id]) return;
      let m = znacky[p.cluster_id];
      if (!m) {
        const e = prstenec(p); e.title = sklon(p.point_count, "organizácia", "organizácie", "organizácií") + ", z toho " + sklon(p.firmy || 0, "firma", "firmy", "firiem") + ". Kliknutím priblížite.";
        e.addEventListener("click", (ev) => { ev.stopPropagation();
          map.getSource("org").getClusterExpansionZoom(p.cluster_id).then((z) => map.easeTo({ center: f.geometry.coordinates, zoom: z + 0.4, duration: 700 })); });
        m = znacky[p.cluster_id] = new maplibregl.Marker({ element: e }).setLngLat(f.geometry.coordinates);
      }
      nove[p.cluster_id] = m; if (!naMape[p.cluster_id]) m.addTo(map);
    });
    Object.keys(naMape).forEach((id) => { if (!nove[id]) naMape[id].remove(); });
    naMape = nove;
  }
  function zmazZhluky() { Object.values(naMape).forEach((m) => m.remove()); znacky = {}; naMape = {}; }

  function sklon(n, a, b, c) { return n + " " + (n === 1 ? a : n >= 2 && n <= 4 ? b : c); }

  function prekrytia() {
    info = document.createElement("div"); info.className = "mapa-info"; el.appendChild(info);
    const l = document.createElement("div"); l.className = "mapa-legenda";
    const riadok = (cls, text) => { const r = document.createElement("div"); const i = document.createElement("i"); i.className = cls; r.append(i, text); return r; };
    l.append(riadok("b zel", "inštitúcie, školy, samosprávy, komunity"), riadok("b ora", "firmy"), riadok("zhl", "viac organizácií, prstenec ukazuje ich zloženie"),
      riadok("k", "žltý odtieň kraja: počet ľudí v komunite"));
    el.appendChild(l);
  }

  function pulzuj() {
    if (pokoj || pulz || !hotovo) return;
    const t0 = performance.now();
    pulz = setInterval(() => {
      const s = (Math.sin((performance.now() - t0) / 700) + 1) / 2;
      if (map.getLayer("bod-ziara")) { map.setPaintProperty("bod-ziara", "circle-radius", 14 + 7 * s); map.setPaintProperty("bod-ziara", "circle-opacity", 0.55 - 0.25 * s); }
    }, 60);
  }
  function stoj() { clearInterval(pulz); pulz = null; }

  function ukaz(p, lngLat) {
    const d = document.createElement("div");
    const t = document.createElement("span"); t.className = "typ"; t.textContent = TYPY[p.typ] || p.typ;
    const h = document.createElement("strong"); h.textContent = p.nazov;
    const m = document.createElement("span"); m.className = "mesto"; m.textContent = p.mesto;
    d.append(t, h, m);
    if (p.popis) { const o = document.createElement("p"); o.textContent = p.popis; d.appendChild(o); }
    if (p.web) { const a = document.createElement("a"); a.href = p.web; a.target = "_blank"; a.rel = "noopener"; a.textContent = p.web.replace(/^https?:\/\//, "").replace(/\/$/, ""); d.appendChild(a); }
    popup.setLngLat(lngLat).setDOMContent(d).addTo(map);
  }
  function vyber(id) {
    vybrane = id;
    if (hotovo) map.setFilter("bod-vyber", ["==", ["get", "id"], id || ""]);
  }

  return {
    init(container) {
      el = container; el.classList.add("mapa-gl");
      // knižnicu načítame, keď sa mapa blíži do zorného poľa; poistka: najneskôr pár sekúnd po načítaní stránky
      let spustene = false;
      const spusti = () => { if (spustene) return; spustene = true; io.disconnect(); nacitaj(vytvor); };
      const io = new IntersectionObserver((z) => { if (z[0].isIntersecting) spusti(); }, { rootMargin: "600px" });
      io.observe(el);
      const neskor = () => setTimeout(spusti, 4000);
      document.readyState === "complete" ? neskor() : window.addEventListener("load", neskor);
    },
    // zoznam organizácií: [{id, nazov, typ, mesto, popis, web, lat, lon}]
    setOrgs(list, vsetky) {
      orgData = { type: "FeatureCollection", features: list.filter((o) => o.lat && o.lon).map((o) => ({ type: "Feature",
        geometry: { type: "Point", coordinates: [o.lon, o.lat] },
        properties: { id: o.id, nazov: o.nazov, typ: o.typ, mesto: o.mesto, popis: o.popis || "", web: o.web || "" } })) };
      if (!hotovo) return;
      zmazZhluky(); map.getSource("org").setData(orgData); popup.remove(); vyber(null);
      if (!vsetky && orgData.features.length) {
        const b = new maplibregl.LngLatBounds(); orgData.features.forEach((f) => b.extend(f.geometry.coordinates));
        map.fitBounds(b, { padding: 90, maxZoom: 10.5, duration: pokoj ? 0 : 900 });
      } else if (vsetky && videna) domov();
    },
    // počty za kraj: {"Prešovský": {ludia: 2, org: 3}, …}; hranice sa načítajú z data/sk-kraje.json
    setKraje(pocty) {
      krajePocty = pocty || {};
      const pouzi = (geo) => {
        geo.features.forEach((f) => { const k = (f.properties.nazov || "").replace(" kraj", ""); const p = krajePocty[k] || {}; f.properties.ludia = p.ludia || 0; f.properties.org = p.org || 0; });
        krajeGeo = geo; if (hotovo) map.getSource("kraje").setData(geo);
      };
      if (krajeGeo) return pouzi(krajeGeo);
      fetch("data/sk-kraje.json").then((r) => r.json()).then(pouzi).catch(() => {});
    },
    focus(o) {
      if (!hotovo || !o.lat) return;
      vyber(o.id);
      map.flyTo({ center: [o.lon, o.lat], zoom: 12.2, pitch: maly() ? 0 : 56, bearing: maly() ? 0 : -18, duration: pokoj ? 0 : 1800, essential: true });
      ukaz(o, [o.lon, o.lat]);
    },
    onSelect(cb) { naVyber = cb; },
    get map() { return map; }
  };
})();
