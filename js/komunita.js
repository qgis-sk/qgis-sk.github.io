// Mapa a zoznam organizácií – dáta z data/organizacie.json
(function () {
  const TYPY = {
    firma: "Firma",
    institucia: "Inštitúcia",
    skola: "Škola / univerzita",
    samosprava: "Samospráva",
    komunita: "Komunita"
  };

  const mapEl = document.getElementById("mapa");
  const listEl = document.getElementById("org-list");
  const searchEl = document.getElementById("org-search");
  const chipsEl = document.getElementById("org-chips");
  const countEl = document.getElementById("org-count");
  if (!mapEl || !listEl) return;

  const map = L.map(mapEl, { scrollWheelZoom: false }).setView([48.7, 19.7], 7);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">prispievatelia OpenStreetMap</a>'
  }).addTo(map);

  const icon = (typ) => L.divIcon({
    className: "org-marker",
    html: '<span style="display:block;width:16px;height:16px;border-radius:50%;background:' +
      (typ === "firma" ? "#ee7913" : "#589632") +
      ';border:3px solid #fff;box-shadow:0 1px 6px rgba(0,0,0,.35)"></span>',
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  });

  let all = [];
  let markers = {};
  let filterTyp = "all";
  let q = "";

  fetch("data/organizacie.json")
    .then((r) => r.json())
    .then((d) => {
      all = d.organizacie || [];
      const st = d.stat || {};
      const so = document.getElementById("stat-org"); if (so) so.textContent = all.length;
      const si = document.getElementById("stat-ind"); if (si && st.individualni_clenovia) si.textContent = st.individualni_clenovia;
      const sb = document.getElementById("org-count-band"); if (sb) sb.textContent = all.length;
      const ib = document.getElementById("ind-count-band"); if (ib && st.individualni_clenovia) ib.textContent = st.individualni_clenovia;
      const su = document.getElementById("stat-upd"); if (su && d.aktualizovane) su.textContent = d.aktualizovane.split("-").reverse().join(". ");
      buildChips();
      render();
    })
    .catch(() => {
      listEl.innerHTML = '<p class="muted">Zoznam organizácií sa nepodarilo načítať.</p>';
    });

  function buildChips() {
    const present = new Set(all.map((o) => o.typ));
    const chips = ['<button class="chip active" data-typ="all">Všetky</button>'];
    Object.keys(TYPY).forEach((k) => {
      if (present.has(k)) chips.push('<button class="chip" data-typ="' + k + '">' + TYPY[k] + "</button>");
    });
    chipsEl.innerHTML = chips.join("");
    chipsEl.addEventListener("click", (e) => {
      const b = e.target.closest(".chip");
      if (!b) return;
      filterTyp = b.dataset.typ;
      chipsEl.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === b));
      render();
    });
  }

  searchEl && searchEl.addEventListener("input", () => { q = searchEl.value.trim().toLowerCase(); render(); });

  function visible() {
    return all.filter((o) =>
      (filterTyp === "all" || o.typ === filterTyp) &&
      (!q || (o.nazov + " " + o.mesto + " " + (o.popis || "")).toLowerCase().includes(q))
    );
  }

  function render() {
    Object.values(markers).forEach((m) => map.removeLayer(m));
    markers = {};
    const list = visible();
    countEl && (countEl.textContent = list.length);
    listEl.innerHTML = list.length ? "" : '<p class="muted">Nič sa nenašlo.</p>';
    const bounds = [];
    list.forEach((o, i) => {
      const id = "org-" + i;
      if (o.lat && o.lon) {
        const m = L.marker([o.lat, o.lon], { icon: icon(o.typ) })
          .addTo(map)
          .bindPopup("<strong>" + esc(o.nazov) + "</strong><br>" + esc(o.mesto) +
            (o.web ? '<br><a href="' + o.web + '" target="_blank" rel="noopener">web</a>' : ""));
        m.on("click", () => highlight(id));
        markers[id] = m;
        bounds.push([o.lat, o.lon]);
      }
      const el = document.createElement("div");
      el.className = "org";
      el.id = id;
      el.innerHTML =
        '<div class="t">' + (TYPY[o.typ] || o.typ) + (o.registracia === "člen" ? ' · <span style="color:#ee7913">na potvrdenie</span>' : (o.stav === "overené" ? ' · <span style="color:#589632">sídlo overené</span>' : ' · <span style="color:#ee7913">sídlo neoverené</span>')) + (o.krajina && o.krajina !== "SK" ? " · " + esc(o.krajina) : "") + "</div>" +
        "<h4>" + esc(o.nazov) + "</h4>" +
        '<div class="city">' + esc(o.mesto) + "</div>" +
        (o.popis ? "<p>" + esc(o.popis) + "</p>" : "") +
        (o.web ? '<p><a href="' + o.web + '" target="_blank" rel="noopener">' + esc(o.web.replace(/^https?:\/\//, "").replace(/\/$/, "")) + "</a></p>" : "");
      el.addEventListener("click", () => {
        highlight(id);
        if (markers[id]) { map.flyTo(markers[id].getLatLng(), 11, { duration: .6 }); markers[id].openPopup(); }
      });
      listEl.appendChild(el);
    });
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 9 });
  }

  function highlight(id) {
    listEl.querySelectorAll(".org").forEach((e) => e.classList.toggle("active", e.id === id));
    const el = document.getElementById(id);
    el && el.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function esc(s) {
    return String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
})();

// Mobilná navigácia
document.addEventListener("DOMContentLoaded", () => {
  const t = document.querySelector(".nav-toggle");
  const n = document.querySelector(".nav");
  t && n && t.addEventListener("click", () => n.classList.toggle("open"));
  n && n.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => n.classList.remove("open")));
});
