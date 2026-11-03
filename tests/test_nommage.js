/*
 * Tests de la convention de nommage des PDF, et du refus d'export sans
 * identité (contrat C2-T1).
 *
 * construireNomFichier() (formulaire/script.js) substitue désormais un
 * gabarit déclaré en configuration (cabinet.convention_nommage) plutôt que
 * de composer le nom en dur. La non-régression — le gabarit par défaut rend
 * EXACTEMENT ce qu'il rendait hier, caractère pour caractère — est la
 * condition qui protège la production (contrat C2-T1, §9) : la matrice du
 * test 1 recopie la sortie d'avant la tâche comme oracle figé.
 *
 * Même outillage que tests/test_file_depots.js : un contexte vm minimal,
 * document et fetch simulés au strict nécessaire.
 *
 *     node tests/test_nommage.js
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");

const SCRIPT = path.join(__dirname, "..", "formulaire", "script.js");

/**
 * Construit un contexte vm chargé avec script.js. `reponseCabinet` :
 *   - null  -> /cabinet toujours injoignable (TypeError, comme un fetch réel
 *     sur un serveur éteint) ; `cabinet` reste null tant que chargerCabinet()
 *     n'a jamais réussi ;
 *   - un objet -> /cabinet répond 200 avec ce corps JSON.
 */
function charger(reponseCabinet) {
    const elements = {};
    const element = (id) => (elements[id] = elements[id] || {
        id, value: "", hidden: true, textContent: "", className: "",
        style: {}, classList: { contains: () => false },
        addEventListener(type, f) { this["on" + type] = f; }
    });
    let appelsJsPDF = 0;
    const contexte = {
        console, setTimeout, clearTimeout, setInterval: () => 0, Promise, Date, JSON,
        AbortController: class { constructor() { this.signal = {}; } abort() {} },
        fetch(url) {
            if (String(url).startsWith("/cabinet")) {
                return reponseCabinet === null
                    ? Promise.reject(new TypeError("Failed to fetch"))
                    : Promise.resolve({
                        ok: true,
                        json: () => Promise.resolve(reponseCabinet)
                    });
            }
            return Promise.reject(new Error("fetch non simulé pour " + url));
        },
        document: {
            addEventListener() {}, getElementById: element,
            querySelectorAll: () => [], querySelector: () => null
        },
        window: {
            addEventListener() {},
            // La garde d'export (test 4) ne doit jamais aller jusqu'à
            // instancier jsPDF : un constructeur qui lève le prouve mieux
            // qu'un compteur qu'on pourrait oublier d'incrémenter ailleurs.
            jspdf: {
                jsPDF: function () {
                    appelsJsPDF++;
                    throw new Error(
                        "jsPDF ne doit jamais être instancié sans identité confirmée");
                }
            }
        },
        navigator: { onLine: true },
        localStorage: { getItem: () => null, setItem() {}, removeItem() {} }
    };
    vm.createContext(contexte);
    vm.runInContext(fs.readFileSync(SCRIPT, "utf8"), contexte);
    contexte._elements = elements;
    contexte._appelsJsPDF = () => appelsJsPDF;
    return contexte;
}

function remplir(c, valeurs) {
    Object.keys(valeurs).forEach(function (id) {
        c._elements[id] = c._elements[id] || { value: "" };
        c._elements[id].value = valeurs[id];
    });
}

(async () => {
    // 1. Non-régression : sans cabinet chargé (donc sans convention_nommage
    //    connue), construireNomFichier() retombe sur le gabarit par défaut
    //    et rend EXACTEMENT la sortie d'avant C2-T1 — recopiée ici comme
    //    oracle figé — sur la matrice : nom seul, prénom seul, les deux,
    //    aucun, accents, date absente.
    let c = charger(null);
    const casDefaut = [
        { nom: "Dupont", prenom: "Léa", date: "2026-08-22",
          attendu: "Bilan_2026-08-22_Dupont-Léa.pdf" },
        { nom: "Martin", prenom: "", date: "2026-08-22",
          attendu: "Bilan_2026-08-22_Martin.pdf" },
        { nom: "", prenom: "Claire", date: "2026-08-22",
          attendu: "Bilan_2026-08-22_Claire.pdf" },
        { nom: "", prenom: "", date: "2026-08-22",
          attendu: "Bilan_2026-08-22_sans-nom.pdf" },
        { nom: "Guérin", prenom: "Éloïse", date: "2026-08-22",
          attendu: "Bilan_2026-08-22_Guérin-Éloïse.pdf" }
    ];
    casDefaut.forEach(function (cas) {
        remplir(c, { "nom": cas.nom, "prenom": cas.prenom, "date-bilan": cas.date });
        assert.strictEqual(c.construireNomFichier(), cas.attendu,
            "cas « " + JSON.stringify(cas) + " »");
    });
    // Date absente : repli sur la date du jour, jamais figée en dur dans ce test.
    remplir(c, { "nom": "", "prenom": "", "date-bilan": "" });
    const aujourdhui = new Date().toISOString().slice(0, 10);
    assert.strictEqual(c.construireNomFichier(), "Bilan_" + aujourdhui + "_sans-nom.pdf");
    console.log("1. gabarit par défaut : sortie identique, caractère pour caractère, à "
              + "celle d'avant C2-T1 (nom seul, prénom seul, les deux, aucun, accents, "
              + "date absente)");

    // 2. Gabarit personnalisé chargé depuis /cabinet : honoré, les quatre
    //    marqueurs ({date}, {nom}, {prenom}, {patient}) substitués.
    c = charger({ convention_nommage: "{nom}_{prenom}_{date}" });
    await c.chargerCabinet();
    remplir(c, { "nom": "Martin", "prenom": "Alice", "date-bilan": "2026-01-01" });
    assert.strictEqual(c.construireNomFichier(), "Martin_Alice_2026-01-01.pdf");

    c = charger({ convention_nommage: "{patient}-{date}-rapport" });
    await c.chargerCabinet();
    remplir(c, { "nom": "Dupont", "prenom": "Léa", "date-bilan": "2026-08-22" });
    assert.strictEqual(c.construireNomFichier(), "Dupont-Léa-2026-08-22-rapport.pdf");
    console.log("2. gabarit personnalisé honoré, les quatre marqueurs substitués");

    // 3. Un marqueur inconnu est remplacé par la chaîne vide ; un gabarit
    //    vide, ou qui ne rend que des marqueurs inconnus, retombe sur le
    //    gabarit par défaut plutôt que de produire un nom vide.
    c = charger({ convention_nommage: "{inconnu}-{date}" });
    await c.chargerCabinet();
    remplir(c, { "nom": "", "prenom": "", "date-bilan": "2026-08-22" });
    assert.strictEqual(c.construireNomFichier(), "-2026-08-22.pdf");

    c = charger({ convention_nommage: "" });
    await c.chargerCabinet();
    remplir(c, { "nom": "", "prenom": "", "date-bilan": "2026-08-22" });
    assert.strictEqual(c.construireNomFichier(), "Bilan_2026-08-22_sans-nom.pdf");

    c = charger({ convention_nommage: "{inconnu}" });
    await c.chargerCabinet();
    remplir(c, { "nom": "", "prenom": "", "date-bilan": "2026-08-22" });
    assert.strictEqual(c.construireNomFichier(), "Bilan_2026-08-22_sans-nom.pdf");
    console.log("3. marqueur inconnu : remplacé par la chaîne vide ; gabarit vide (ou "
              + "réduit à un marqueur inconnu) : repli sur le gabarit par défaut");

    // 4. L'export est refusé tant que l'identité n'est pas confirmée
    //    (décision D7) : aucun PDF n'est jamais instancié, et un bandeau
    //    d'erreur persistant apparaît. /cabinet reste injoignable même
    //    après la retentative que fait exporterBilanPDF().
    c = charger(null);
    c._elements["form-bilan"] = { id: "form-bilan" };
    await c.exporterBilanPDF();
    assert.strictEqual(c._appelsJsPDF(), 0,
        "jsPDF ne doit jamais être instancié sans identité confirmée");
    assert.strictEqual(c._elements["zone-messages"].hidden, false);
    assert.match(c._elements["zone-messages"].className, /erreur/);
    console.log("4. export refusé sans identité : aucun PDF instancié, bandeau "
              + "d'erreur persistant, message nommant le geste de réparation");

    console.log("\nTout est vert.");
})().catch((erreur) => {
    console.error(erreur);
    process.exit(1);
});
