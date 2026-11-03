/*
 * Pied de page de version (C4-T4) : afficherVersion() de formulaire/script.js,
 * extraite du fichier de production et jouée contre un double de document.
 *
 *     node tests/test_version.js
 *     SCRIPT_A_TESTER=/copie/mutée/script.js node tests/test_version.js
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");

const SCRIPT = process.env.SCRIPT_A_TESTER
    ? path.resolve(process.env.SCRIPT_A_TESTER)
    : path.join(__dirname, "..", "formulaire", "script.js");
const VERSION = JSON.parse(fs.readFileSync(
    path.join(__dirname, "..", "formulaire", "version.json"), "utf8")).version;

function extraireFonction(source, nom) {
    const debut = source.indexOf("async function " + nom + "(");
    assert.ok(debut !== -1, nom + "() introuvable dans " + SCRIPT);
    let i = source.indexOf("{", debut), profondeur = 0;
    for (; i < source.length; i += 1) {
        if (source[i] === "{") profondeur += 1;
        if (source[i] === "}" && --profondeur === 0) break;
    }
    return source.slice(debut, i + 1);
}

function contexte(reponseFetch) {
    const elements = {};
    const corps = { enfants: [], appendChild(e) { this.enfants.push(e); elements[e.id] = e; } };
    const appels = [];
    const c = {
        console: { warn() {} },
        fetch(url, options) { appels.push({ url, options }); return reponseFetch(); },
        document: {
            body: corps,
            getElementById: (id) => elements[id] || null,
            createElement: (balise) => ({ tagName: balise, id: "", textContent: "" })
        }
    };
    vm.createContext(c);
    vm.runInContext(extraireFonction(fs.readFileSync(SCRIPT, "utf8"), "afficherVersion")
        + "\nthis.afficherVersion = afficherVersion;", c);
    c._corps = corps;
    c._appels = appels;
    return c;
}

const repondre = (corps, ok = true) => () => Promise.resolve({ ok, json: () => Promise.resolve(corps) });

(async () => {
    // 1. La version lue dans version.json s'affiche, à la fin du <body>.
    {
        const c = contexte(repondre({ version: VERSION }));
        await c.afficherVersion();
        assert.strictEqual(c._appels[0].url, "version.json", "la version est lue dans version.json");
        assert.strictEqual(c._corps.enfants.length, 1, "un seul pied de page ajouté au <body>");
        const pied = c._corps.enfants[0];
        assert.strictEqual(pied.id, "version-application");
        assert.ok(pied.textContent.indexOf(VERSION) !== -1,
            "le pied de page porte le numéro de version.json : " + pied.textContent);
        // Un second appel met à jour le même paragraphe, sans en ajouter un.
        await c.afficherVersion();
        assert.strictEqual(c._corps.enfants.length, 1, "pas de second pied de page");
        console.log("1. le pied de page affiche la version de version.json, une seule fois");
    }

    // 2. Aucune panne ne lève ni n'affiche de numéro inventé.
    for (const [nom, reponse] of [
        ["réponse non ok", repondre({ version: VERSION }, false)],
        ["numéro absent", repondre({})],
        ["numéro non textuel", repondre({ version: 3 })],
        ["serveur injoignable", () => Promise.reject(new Error("injoignable"))]
    ]) {
        const c = contexte(reponse);
        await c.afficherVersion();
        assert.strictEqual(c._corps.enfants.length, 0, nom + " : aucun pied de page");
    }
    console.log("2. une panne n'affiche rien et ne lève pas");

    console.log("\nTout est vert.");
})().catch((erreur) => {
    console.error(erreur);
    process.exit(1);
});
