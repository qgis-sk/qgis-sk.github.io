// QGIS Slovensko – administrácia registrácií. Všetky údaje sa vkladajú cez textContent (žiadne innerHTML).
(function () {
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  let data = null, seen = null, timer = null;

  async function api(path, body) {
    const opt = body ? { method: "POST", headers: { "Content-Type": "application/json", "X-Admin": "1" }, body: JSON.stringify(body) } : {};
    const r = await fetch("/admin/api/" + path, opt);
    const j = await r.json().catch(() => ({}));
    if (r.status === 401 && path !== "login") { show(false); throw new Error("401"); }
    if (!r.ok) throw new Error(j.chyba || "Chyba " + r.status);
    return j;
  }
  const cas = (s) => s ? new Date(s).toLocaleString("sk-SK", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
  const dnes = () => new Date().toLocaleDateString("sv-SE");   // RRRR-MM-DD v miestnom čase

  function show(logged) {
    $("login").hidden = logged; $("app").hidden = !logged;
    clearInterval(timer);
    if (logged) { load(); timer = setInterval(load, 30000); }
  }

  async function load() {
    try { data = await api("prehlad"); } catch (e) { return; }
    $("refreshed").textContent = "obnovené " + new Date().toLocaleTimeString("sk-SK");
    const fresh = new Set(data.jednotlivci.map((r) => r.id));
    const nove = seen ? new Set([...fresh].filter((i) => !seen.has(i))) : new Set();
    cards(); ludia(nove); org(); pribehy(); navstevnost();
    if (nove.size) document.title = "(" + nove.size + ") QGIS Slovensko – správa registrácií";
    seen = seen ? new Set([...seen, ...fresh]) : fresh;
  }

  function cards() {
    const s = data.stat, d = data.dni.find((x) => x.den === dnes()) || {};
    const dnesReg = data.jednotlivci.filter((r) => new Date(r.vytvorene).toLocaleDateString("sv-SE") === dnes()).length;
    const cak = data.organizacie.filter((o) => o.stav === "nová").length;
    const items = [[s.ludia_spolu, "ľudí v komunite"], [s.nove_registracie, "cez nový formulár"], [dnesReg, "registrácií dnes"],
      [cak, "organizácií čaká na overenie", cak > 0], [d.navstevnici || 0, "návštevníkov dnes"], [d.formular || 0, "otvorení formulára dnes"], [s.kraj_neznamy, "ľudí bez známeho kraja"]];
    if (data.cakajuce) items.push([data.cakajuce, "čaká na potvrdenie e-mailom"]);
    const c = $("cards"); c.replaceChildren();
    items.forEach(([n, t, alert]) => { const k = el("div", "card" + (alert ? " alert" : "")); k.append(el("b", null, n), el("span", null, t)); c.append(k); });
  }

  function ludia(nove) {
    const q = $("hladat").value.trim().toLowerCase();
    const tb = $("t-ludia").tBodies[0]; tb.replaceChildren();
    const rows = data.jednotlivci.filter((r) => !q || [r.meno, r.email, r.kraj, r.organizacia].join(" ").toLowerCase().includes(q));
    $("ludia-empty").hidden = data.jednotlivci.length > 0;
    rows.forEach((r) => {
      const tr = el("tr", nove.has(r.id) ? "new" : "");
      const mail = el("a", null, r.email); mail.href = "mailto:" + r.email;
      const tdm = el("td"); tdm.append(mail);
      const pozn = el("td");
      if (r.clenstvo) pozn.append(el("span", "tag o", "chce členstvo v OZ"));
      if (r.novinky) pozn.append(el("span", "tag", "novinky"));
      if (r.pribeh || r.pribeh_odkaz) pozn.append(el("span", "tag o", "príklad použitia"));
      (r.prispiet || []).forEach((p) => pozn.append(el("span", "tag", p)));
      if (r.upravene !== r.vytvorene) pozn.append(el("span", "muted", " upravené " + cas(r.upravene)));
      const del = el("button", "danger", "Zmazať");
      del.onclick = async () => { if (confirm("Naozaj zmazať registráciu: " + r.meno + " (" + r.email + ")? Nedá sa to vrátiť.")) { await api("zmazat", { co: "jednotlivci", id: r.id }); load(); } };
      const tdd = el("td"); tdd.append(del);
      tr.append(el("td", null, cas(r.vytvorene)), el("td", null, r.meno), tdm, el("td", null, r.kraj), el("td", null, r.organizacia || ""),
        el("td", null, (r.oblast || []).join(", ")), el("td", null, r.skusenost || ""), pozn, tdd);
      tb.append(tr);
    });
  }

  function org() {
    const box = $("org-list"); box.replaceChildren();
    if (!data.organizacie.length) box.append(el("p", "muted", "Zatiaľ žiadna organizácia cez nový formulár."));
    data.organizacie.forEach((o) => {
      const d = el("div", "org" + (o.stav === "nová" ? " nova" : ""));
      d.append(el("h3", null, o.nazov));
      d.append(el("p", null, [o.obec, o.pracovisko, o.typ, o.ico ? "IČO " + o.ico : "IČO neuvedené", cas(o.vytvorene)].filter(Boolean).join(" · ")));
      if (o.rpo_nazov) d.append(el("p", null, "Register: " + o.rpo_nazov + ", " + o.rpo_adresa));
      d.append(el("p", null, "Popis: " + o.popis));
      if (o.web) { const p = el("p"), a = el("a", null, o.web); a.href = o.web; a.target = "_blank"; a.rel = "noopener noreferrer"; p.append("Web: ", a); d.append(p); }
      if ((o.ponuka || []).length) { const p = el("p", null, "Ponúka: "); o.ponuka.forEach((x) => p.append(el("span", "tag", x))); d.append(p); }
      const k = el("p", null, "Kontakt: " + o.kontakt_meno + ", "), a = el("a", null, o.kontakt_email); a.href = "mailto:" + o.kontakt_email; k.append(a); d.append(k);
      const row = el("div", "row"), sel = el("select");
      ["nová", "overená", "zamietnutá"].forEach((s) => { const op = el("option", null, s); op.value = s; op.selected = o.stav === s; sel.append(op); });
      sel.onchange = async () => { await api("organizacia", { id: o.id, stav: sel.value }); load(); };
      const del = el("button", "danger", "Zmazať");
      del.onclick = async () => { if (confirm("Naozaj zmazať organizáciu: " + o.nazov + "? Nedá sa to vrátiť.")) { await api("zmazat", { co: "organizacie", id: o.id }); load(); } };
      row.append(el("span", "muted", "Stav:"), sel, el("span", "spacer"), del); d.append(row); box.append(d);
    });
  }

  function pribehy() {
    const box = $("pribehy-list"); box.replaceChildren();
    const all = data.jednotlivci.filter((r) => r.pribeh || r.pribeh_odkaz).map((r) => ({ kto: r.meno, mail: r.email, r }))
      .concat(data.organizacie.filter((r) => r.pribeh || r.pribeh_odkaz).map((r) => ({ kto: r.nazov, mail: r.kontakt_email, r })));
    if (!all.length) box.append(el("p", "muted", "Zatiaľ sa nikto nepodelil o príklad použitia."));
    all.forEach(({ kto, mail, r }) => {
      const d = el("div", "pribeh"), s = el("small", null, kto + " · " + mail + " · " + cas(r.upravene));
      d.append(s); if (r.pribeh) d.append(el("div", null, r.pribeh));
      if (r.pribeh_odkaz) { const a = el("a", null, r.pribeh_odkaz); a.href = r.pribeh_odkaz; a.target = "_blank"; a.rel = "noopener noreferrer"; d.append(a); }
      box.append(d);
    });
  }

  function navstevnost() {
    const tb = $("t-dni").tBodies[0]; tb.replaceChildren();
    data.dni.forEach((d) => { const tr = el("tr"); tr.append(el("td", null, d.den.split("-").reverse().join(". ")));
      [d.navstevnici, d.zobrazenia, d.formular, d.registracie, d.organizacie].forEach((n) => tr.append(el("td", "num", n))); tb.append(tr); });
    const fill = (id, rows, key) => { const b = $(id).tBodies[0]; b.replaceChildren(); rows.forEach((r) => { const tr = el("tr"); tr.append(el("td", null, r[key]), el("td", "num", r.n)); b.append(tr); }); };
    fill("t-zdroje", data.zdroje, "zdroj"); fill("t-stranky", data.stranky, "stranka");
  }

  document.querySelectorAll("#tabs button").forEach((b) => b.onclick = () => {
    document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("active", x === b));
    ["ludia", "org", "pribehy", "navstevnost"].forEach((t) => { $("tab-" + t).hidden = t !== b.dataset.tab; });
  });
  $("hladat").oninput = () => data && ludia(new Set());
  $("refresh").onclick = load;
  $("logout").onclick = async () => { try { await api("logout", {}); } catch (e) {} seen = null; show(false); };
  window.addEventListener("focus", () => { document.title = "QGIS Slovensko – správa registrácií"; });
  $("login-form").onsubmit = async (e) => {
    e.preventDefault(); const f = e.target, err = $("login-err"); err.hidden = true;
    try { const j = await api("login", { meno: f.meno.value, heslo: f.heslo.value }); f.heslo.value = ""; $("who").textContent = j.meno; show(true); }
    catch (x) { err.textContent = x.message; err.hidden = false; }
  };
  api("ja").then((j) => { if (j.meno) { $("who").textContent = j.meno; show(true); } else { show(false);
    if (!j.nastavene) { $("login-err").textContent = "Administrácia ešte nemá žiadny účet. Vytvorte ho na serveri príkazom qgis-sk-admin."; $("login-err").hidden = false; } } }).catch(() => show(false));
})();
