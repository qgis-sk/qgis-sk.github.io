// Registračné formuláre qgis.sk → registračná služba (window.QGISSK.api)
(function () {
  const API = (window.QGISSK || {}).api;
  const t0 = Date.now();
  const vals = (form, name) => [...form.querySelectorAll('input[name="' + name + '"]:checked')].map((i) => i.value);

  function wire(formId, path, build, done) {
    const form = document.getElementById(formId);
    if (!form) return;
    const err = form.querySelector(".form-error");
    const btn = form.querySelector('button[type="submit"]');
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      form.querySelectorAll(".bad").forEach((el) => el.classList.remove("bad"));
      const data = build(form);
      data.t = (Date.now() - t0) / 1000;
      data.web_stranka = form.elements.web_stranka.value;
      btn.disabled = true; const label = btn.textContent; btn.textContent = "Odosielam…";
      try {
        const r = await fetch(API + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
        const j = await r.json();
        if (!r.ok) {
          err.textContent = j.chyba || "Odoslanie zlyhalo."; err.hidden = false;
          const el = j.pole && form.elements[j.pole];
          if (el && el.classList) { el.classList.add("bad"); el.focus(); }
          return;
        }
        done(form, j, data);
      } catch (x) {
        err.textContent = "Nepodarilo sa spojiť so serverom. Skúste to prosím o chvíľu."; err.hidden = false;
      } finally {
        btn.disabled = false; btn.textContent = label;
      }
    });
  }

  wire("form-jednotlivec", "/api/jednotlivec", (f) => ({
    meno: f.elements.meno.value, email: f.elements.email.value, kraj: f.elements.kraj.value,
    oblast: vals(f, "oblast"), skusenost: f.elements.skusenost.value, organizacia: f.elements.organizacia.value,
    zaujmy: vals(f, "zaujmy"), prispiet: vals(f, "prispiet"),
    novinky: f.elements.novinky.checked, clenstvo: f.elements.clenstvo.checked, suhlas: f.elements.suhlas.checked,
    pribeh: f.elements.pribeh.value, pribeh_odkaz: f.elements.pribeh_odkaz.value
  }), (f, j, d) => {
    if (j.potvrdit) {
      const w = document.getElementById("wait-jednotlivec");
      document.getElementById("wait-email").textContent = d.email;
      f.hidden = true; w.hidden = false; w.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    const box = document.getElementById("done-jednotlivec");
    const kde = d.kraj === "Mimo Slovenska" ? "mimo Slovenska" : "v kraji " + d.kraj;
    document.getElementById("done-text").textContent =
      (j.aktualizacia ? "Vaše údaje sme aktualizovali. " : j.povodna_registracia ? "Vašu pôvodnú registráciu sme doplnili o kraj. " : "") +
      "Ste " + j.poradie_v_kraji + ". človek " + kde + " a v komunite je nás už " + j.ludia_spolu + ".";
    f.hidden = true; box.hidden = false; box.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  wire("form-organizacia", "/api/organizacia", (f) => ({
    ico: f.elements.ico.value.replace(/\s/g, ""), nazov: f.elements.nazov.value, typ: f.elements.typ.value,
    popis: f.elements.popis.value, web: f.elements.web.value, pracovisko: f.elements.pracovisko.value,
    ponuka: vals(f, "ponuka"), kontakt_meno: f.elements.kontakt_meno.value, kontakt_email: f.elements.kontakt_email.value,
    suhlas: f.elements.suhlas.checked, pribeh: f.elements.pribeh.value, pribeh_odkaz: f.elements.pribeh_odkaz.value
  }), (f) => {
    const box = document.getElementById("done-organizacia");
    f.hidden = true; box.hidden = false; box.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  // Potvrdenie registrácie odkazom z e-mailu (potvrdenie.html?t=…)
  const potv = document.getElementById("potv-title");
  if (potv) {
    const t = new URLSearchParams(location.search).get("t") || "";
    const fail = (msg) => { potv.textContent = "Registráciu sa nepodarilo potvrdiť"; document.getElementById("potv-err-text").textContent = msg; document.getElementById("potv-err").hidden = false; };
    fetch(API + "/api/potvrdit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ t: t }) })
      .then((r) => r.json().then((j) => ({ ok: r.ok, j: j })))
      .then(({ ok, j }) => {
        if (!ok) return fail(j.chyba || "Odkaz nie je platný.");
        const kde = j.kraj === "Mimo Slovenska" ? "mimo Slovenska" : "v kraji " + j.kraj;
        potv.textContent = "Registrácia je potvrdená";
        document.getElementById("potv-text").textContent =
          (j.aktualizacia ? "Vaše údaje sme aktualizovali. " : j.povodna_registracia ? "Vašu pôvodnú registráciu sme doplnili o kraj. " : "") +
          "Ste " + j.poradie_v_kraji + ". človek " + kde + " a v komunite je nás už " + j.ludia_spolu + ".";
        document.getElementById("potv-ok").hidden = false;
        history.replaceState(null, "", location.pathname);
      })
      .catch(() => fail("Nepodarilo sa spojiť so serverom. Skúste odkaz otvoriť o chvíľu znova."));
  }

  // IČO → názov a sídlo z registra
  const ico = document.getElementById("ico");
  if (ico) {
    const info = document.getElementById("ico-info");
    const nazov = document.getElementById("nazov");
    const look = async () => {
      const v = ico.value.replace(/\s/g, "");
      if (!/^\d{8}$/.test(v)) { info.textContent = "IČO má 8 číslic."; info.className = "warn"; return; }
      info.textContent = "Hľadám v registri…"; info.className = "";
      try {
        const r = await fetch(API + "/api/ico?ico=" + v); const j = await r.json();
        if (!r.ok) { info.textContent = j.chyba; info.className = "warn"; return; }
        info.textContent = "Našli sme: " + j.nazov + ", " + j.adresa + (j.zaniknuta ? " (v registri vedená ako zaniknutá)" : "");
        info.className = "good";
        if (!nazov.value) nazov.value = j.nazov;
      } catch (x) { info.textContent = "Register sa nepodarilo načítať. Pokračujte, sídlo overíme neskôr."; info.className = "warn"; }
    };
    document.getElementById("ico-btn").addEventListener("click", look);
    ico.addEventListener("change", look);
    const popis = document.getElementById("popis"), n = document.getElementById("popis-n");
    popis.addEventListener("input", () => { n.textContent = popis.value.length; });
  }
})();
