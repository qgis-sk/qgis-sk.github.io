/**
 * QGIS Slovensko – vytvorenie dvoch registračných formulárov (Google Apps Script).
 *
 * Použitie: https://script.google.com → Nový projekt → vložiť tento súbor → spustiť funkciu
 * vytvorFormulare() → povoliť prístup. V zázname (Zobraziť → Záznamy) nájdete odkazy na oba
 * formuláre a na tabuľku odpovedí. Odkazy na vyplnenie vložte do js/config.js.
 *
 * Tabuľka odpovedí obsahuje osobné údaje: NEZDIEĽAŤ verejne. Mapa číta inú, verejnú tabuľku
 * „QGIS SK – organizácie na mape“, do ktorej sa organizácie prenášajú po overení.
 */
const GDPR = "https://qgis.sk/pravidla.html#osobne-udaje";
const KRAJE = ["Bratislavský", "Trnavský", "Trenčiansky", "Nitriansky", "Žilinský",
               "Banskobystrický", "Prešovský", "Košický", "Pôsobím mimo Slovenska"];

function vytvorFormulare() {
  const ss = SpreadsheetApp.create("QGIS SK – registrácie 2026 (odpovede, neverejné)");
  const email = FormApp.createTextValidation().requireTextIsEmail().build();

  // ---------- 1. Jednotlivec ----------
  const f1 = FormApp.create("QGIS Slovensko – pridať sa ku komunite (jednotlivec)");
  f1.setDescription(
    "Registrácia do slovenskej QGIS komunity je bezplatná a nezáväzná a neznamená členstvo " +
    "v občianskom združení. Na komunitnej mape sa nezobrazíte, pripočítame vás iba do počtu " +
    "za váš kraj. Vyplnenie trvá asi minútu. Informácie o spracúvaní osobných údajov: " + GDPR);
  f1.addTextItem().setTitle("Meno a priezvisko").setRequired(true);
  f1.addTextItem().setTitle("E-mail").setValidation(email).setRequired(true);
  f1.addListItem().setTitle("Kraj, v ktorom pôsobíte")
    .setHelpText("Podľa toho, kde pracujete, študujete alebo žijete. Použijeme iba ako počet za kraj.")
    .setChoiceValues(KRAJE).setRequired(true);
  f1.addCheckboxItem().setTitle("Oblasť, v ktorej pôsobíte")
    .setChoiceValues(["Verejná správa a samospráva", "Súkromný sektor", "Akademická sféra a výskum",
                      "Študent/ka", "Občianska spoločnosť", "QGIS používam vo voľnom čase"])
    .setRequired(true);
  f1.addMultipleChoiceItem().setTitle("Ako dlho pracujete s QGIS?")
    .setChoiceValues(["Začínam", "Bežne ho používam", "Pokročilý používateľ", "Vyvíjam pluginy alebo učím QGIS"]);
  f1.addTextItem().setTitle("Organizácia, kde pracujete alebo študujete (nepovinné)")
    .setHelpText("Neznamená to registráciu organizácie. Tú robí samostatný formulár.");
  f1.addCheckboxItem().setTitle("Čo vás zaujíma?")
    .setChoiceValues(["Novinky o QGIS", "Stretnutia a konferencie", "Školenia a workshopy",
                      "Pomoc pri riešení problémov", "Ponuky spolupráce a práce", "Slovenské dáta a návody"]);
  f1.addCheckboxItem().setTitle("Vedeli by ste niečím prispieť? (nepovinné)")
    .setChoiceValues(["Prednáška alebo ukážka", "Návod alebo článok", "Preklad QGIS do slovenčiny",
                      "Pomoc s organizáciou podujatia", "Lektorovanie"]);
  f1.addMultipleChoiceItem().setTitle("Chcete dostávať e-mailom novinky QGIS Slovensko?")
    .setChoiceValues(["Áno", "Nie"]).setRequired(true);
  f1.addMultipleChoiceItem().setTitle("Máte záujem aj o formálne členstvo v občianskom združení QGIS Slovensko?")
    .setHelpText("Ak áno, ozveme sa vám s ďalším postupom.")
    .setChoiceValues(["Áno, ozvite sa mi", "Zatiaľ nie"]);
  f1.addCheckboxItem().setTitle("Súhlas so spracúvaním osobných údajov")
    .setChoiceValues(["Súhlasím, aby QGIS Slovensko, o. z. spracúvalo uvedené údaje na účel vedenia " +
                      "zoznamu členov komunity. Súhlas môžem kedykoľvek odvolať."])
    .setRequired(true);
  f1.setConfirmationMessage("Ďakujeme, vitajte v slovenskej QGIS komunite. Mapa: https://qgis.sk/#komunita");
  f1.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  // ---------- 2. Organizácia ----------
  const f2 = FormApp.create("QGIS Slovensko – pridať organizáciu na komunitnú mapu");
  f2.setDescription(
    "Pre firmy, úrady, školy a samosprávy, ktoré pracujú s QGIS. Zápis je bezplatný. Na mape " +
    "zverejníme názov, sídlo, web a krátky popis. Kontaktné údaje nezverejňujeme. Sídlo overíme " +
    "podľa IČO v Registri právnických osôb. Informácie o spracúvaní osobných údajov: " + GDPR);
  f2.addTextItem().setTitle("Oficiálny názov organizácie").setRequired(true);
  f2.addTextItem().setTitle("IČO")
    .setHelpText("Podľa IČO overíme názov a sídlo, adresu preto vypĺňať nemusíte. Zahraničné organizácie: registračné číslo a krajina.")
    .setRequired(true);
  f2.addMultipleChoiceItem().setTitle("Typ organizácie")
    .setChoiceValues(["Firma", "Štátna inštitúcia", "Škola alebo univerzita", "Samospráva (obec, mesto, kraj)",
                      "Občianske združenie alebo komunita"])
    .setRequired(true);
  f2.addTextItem().setTitle("Pracovisko, ktoré sa má zobraziť na mape (nepovinné)")
    .setHelpText("Vyplňte iba vtedy, ak sa má zobraziť iná adresa ako sídlo, napríklad katedra alebo pobočka. Ulica, číslo, obec.");
  f2.addTextItem().setTitle("Web (nepovinné)");
  f2.addParagraphTextItem().setTitle("Ako QGIS používate? Jedna veta, zobrazí sa na mape.")
    .setHelpText("Napríklad: Územné plánovanie a pasport zelene. Najviac 150 znakov.")
    .setValidation(FormApp.createParagraphTextValidation().requireTextLengthLessThanOrEqualTo(150).build())
    .setRequired(true);
  f2.addCheckboxItem().setTitle("Čo môžete komunite ponúknuť? (nepovinné)")
    .setChoiceValues(["Školenia", "Služby alebo vývoj", "Stáže a témy záverečných prác",
                      "Priestory na stretnutie", "Otvorené dáta", "Prípadovú štúdiu na web"]);
  f2.addTextItem().setTitle("Kontaktná osoba: meno a priezvisko").setHelpText("Nezverejňujeme.").setRequired(true);
  f2.addTextItem().setTitle("Kontaktná osoba: pracovný e-mail").setHelpText("Nezverejňujeme.")
    .setValidation(email).setRequired(true);
  f2.addCheckboxItem().setTitle("Potvrdenie a súhlas")
    .setChoiceValues(["Som oprávnený/á zaregistrovať organizáciu a súhlasím so zverejnením jej názvu, " +
                      "sídla, webu a popisu na komunitnej mape qgis.sk."])
    .setRequired(true);
  f2.setConfirmationMessage("Ďakujeme. Po overení sídla sa organizácia objaví na mape pri najbližšej aktualizácii: https://qgis.sk/#komunita");
  f2.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  Logger.log("Jednotlivec – vyplnenie: " + f1.getPublishedUrl());
  Logger.log("Jednotlivec – úprava:    " + f1.getEditUrl());
  Logger.log("Organizácia – vyplnenie: " + f2.getPublishedUrl());
  Logger.log("Organizácia – úprava:    " + f2.getEditUrl());
  Logger.log("Tabuľka odpovedí:        " + ss.getUrl());
}
