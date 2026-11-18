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

  const Mapa = window.QgisMapa;
  Mapa.init(mapEl);
  const heroEl = document.getElementById("hero-mapa");
  heroEl && Mapa.nahlad(heroEl);
  // štítok v náhľade mapy v úvode: počet ľudí a organizácií
  function heroPocty(ludia, org) {
    const e = document.getElementById("hero-map-pocty");
    if (e && org) e.textContent = (ludia ? ludia + " ľudí · " : "") + org + " organizácií";
  }
  Mapa.onSelect((id) => highlight(id));

  let all = [];
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
      heroPocty(st.individualni_clenovia, all.length);
      renderDash(all, st);
      liveStat(all);
      buildChips();
      render();
    })
    .catch(() => {
      listEl.innerHTML = '<p class="muted">Zoznam organizácií sa nepodarilo načítať.</p>';
    });

  // Malý dashboard: komunita podľa krajov (organizácie z dát mapy, jednotlivci zo stat.json)
  function renderDash(orgs, st) {
    const el = document.getElementById("kraje-dash");
    if (!el) return;
    const KRAJE = ["Bratislavský", "Trnavský", "Trenčiansky", "Nitriansky", "Žilinský", "Banskobystrický", "Prešovský", "Košický"];
    const oc = {};
    orgs.forEach((o) => { const k = (o.kraj || "").replace(" kraj", ""); if (k) oc[k] = (oc[k] || 0) + 1; });
    const ic = st.jednotlivci_kraje || {};
    const hasInd = Object.keys(ic).length > 0;
    const pocty = {}; KRAJE.forEach((k) => { pocty[k] = { ludia: ic[k] || 0, org: oc[k] || 0 }; });
    Mapa.setKraje(pocty);
    const maxO = Math.max(1, ...KRAJE.map((k) => oc[k] || 0));
    const maxI = Math.max(1, ...KRAJE.map((k) => ic[k] || 0));
    el.innerHTML = KRAJE.map((k) => {
      const o = oc[k] || 0, i = ic[k] || 0;
      const lud = i === 1 ? "človek" : (i >= 2 && i <= 4 ? "ľudia" : "ľudí");
      const val = hasInd ? (i + " " + lud + " · " + o + " org.") : (o ? o + " org." : "zatiaľ nikto");
      return '<div class="kr' + (o || i ? "" : " empty") + '"><span class="kn">' + k + '</span><span class="kb">' +
        (hasInd ? '<i class="i" style="width:' + (100 * i / maxI).toFixed(0) + '%"></i>' : "") +
        '<i class="o" style="width:' + (100 * o / maxO).toFixed(0) + '%"></i></span><span class="kv">' + val + "</span></div>";
    }).join("") +
      (hasInd && st.jednotlivci_kraj_neznamy ? '<div class="kr unknown"><span class="kn">Kraj nepoznáme</span><span class="kb"></span><span class="kv">' + st.jednotlivci_kraj_neznamy + " ľudí</span></div>" : "") +
      (hasInd ? '<div class="legend"><span class="i">jednotlivci</span><span>organizácie</span></div>' : "");
    const note = document.getElementById("kraje-dash-note");
    if (note) note.textContent = !hasInd
      ? "Zatiaľ vidno organizácie. Počty ľudí po krajoch pribudnú s prvými registráciami."
      : st.jednotlivci_kraj_neznamy
        ? "Pri pôvodných registráciách kraj odhadujeme podľa zamestnávateľa alebo ho nepoznáme (" + st.jednotlivci_kraj_neznamy + " ľudí). Registrovali ste sa už dávnejšie? "
        : "Jednotlivcov uvádzame iba ako počet za kraj, bez mien a adries.";
    if (note && hasInd && st.jednotlivci_kraj_neznamy) {
      const a = document.createElement("a");
      a.href = "pridat-sa.html"; a.textContent = "Doplňte si kraj: vyplňte formulár rovnakým e-mailom ako vtedy.";
      note.append(a, " Nezapočítame vás dvakrát.");
    }
  }

  // Živé počty ľudí z registračnej služby (ak je dostupná); inak ostávajú čísla zo stat.json
  function liveStat(orgs) {
    const api = (window.QGISSK || {}).api;
    if (!api) return;
    fetch(api + "/api/stat").then((r) => r.ok ? r.json() : null).then((s) => {
      if (!s || !s.povodni_nacitani) return;   // bez načítaných pôvodných registrácií by číslo bolo neúplné
      const st = { individualni_clenovia: s.ludia_spolu, jednotlivci_kraje: s.kraje, jednotlivci_kraj_neznamy: s.kraj_neznamy };
      ["stat-ind", "ind-count-band"].forEach((id) => { const el = document.getElementById(id); if (el) el.textContent = s.ludia_spolu; });
      heroPocty(s.ludia_spolu, orgs.length);
      renderDash(orgs, st);
    }).catch(() => {});
  }

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
    const list = visible();
    countEl && (countEl.textContent = list.length);
    listEl.innerHTML = list.length ? "" : '<p class="muted">Nič sa nenašlo.</p>';
    list.forEach((o) => {
      o.id = "org-" + all.indexOf(o);
      const el = document.createElement("div");
      el.className = "org";
      el.id = o.id;
      const cak = o.registracia === "člen";
      const stav = cak ? '<span style="color:#ee7913">na potvrdenie</span>' : (o.stav === "overené" ? '<span style="color:#589632">sídlo overené</span>' : '<span style="color:#ee7913">sídlo neoverené</span>');
      el.innerHTML =
        '<div class="riadok"><i class="bodka ' + (o.typ === "firma" ? "ora" : "zel") + (cak ? " cak" : "") + '"></i>' +
        '<span class="n">' + esc(o.nazov) + '</span><span class="city">' + esc(o.mesto) + "</span></div>" +
        '<div class="viac"><div class="t">' + (TYPY[o.typ] || o.typ) + " · " + stav + "</div>" +
        (o.popis ? "<p>" + esc(o.popis) + "</p>" : "") +
        (o.web ? '<p><a href="' + o.web + '" target="_blank" rel="noopener">' + esc(o.web.replace(/^https?:\/\//, "").replace(/\/$/, "")) + "</a></p>" : "") + "</div>";
      el.title = o.nazov + ", " + o.mesto;
      el.addEventListener("click", (e) => {
        if (e.target.closest("a")) return;
        highlight(o.id);
        Mapa.focus(o);
      });
      listEl.appendChild(el);
    });
    Mapa.setOrgs(list, list.length === all.length);
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

// Odkazy na registračné formuláre sa berú z js/config.js
document.addEventListener("DOMContentLoaded", () => {
  const cfg = window.QGISSK || {};
  document.querySelectorAll("a[data-form]").forEach((a) => {
    const url = a.dataset.form === "organizacia" ? cfg.formOrganizacia : cfg.formJednotlivec;
    if (url) a.href = url;
  });
});
