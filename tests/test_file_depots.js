/*
 * Tests de la file d'attente des dépôts (formulaire/script.js).
 *
 * La file est le filet qui garantit qu'un bilan généré finit sur le PC même
 * si le serveur du cabinet est arrêté : elle mérite d'être vérifiée, et elle
 * ne peut pas l'être par les tests Python, qui s'arrêtent au serveur.
 *
 * IndexedDB, fetch et le DOM sont simulés au strict nécessaire — assez pour
 * exercer la file, pas pour faire tourner le formulaire entier.
 *
 *     node tests/test_file_depots.js
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");

const SCRIPT = path.join(__dirname, "..", "formulaire", "script.js");

function faireIndexedDB() {
    const magasins = {};              // nom -> Map(cle -> valeur)
    const sequences = {};
    let versionBase = 0;
    const ok = (resultat) => {
        const r = { result: resultat };
        setTimeout(() => r.onsuccess && r.onsuccess(), 0);
        return r;
    };
    const objectStore = (nom) => ({
        add(valeur) {
            sequences[nom] = (sequences[nom] || 0) + 1;
            const id = sequences[nom];
            magasins[nom].set(id, Object.assign({ id }, valeur));
            return ok(id);
        },
        put(valeur, cle) { magasins[nom].set(cle, valeur); return ok(undefined); },
        get(cle) { return ok(magasins[nom].get(cle)); },
        getAll() { return ok([...magasins[nom].values()]); },
        delete(cle) { magasins[nom].delete(cle); return ok(undefined); }
    });
    return {
        _magasins: magasins,
        open(nom, version) {
            const requete = {
                result: {
                    objectStoreNames: { contains: (n) => n in magasins },
                    createObjectStore(n) { magasins[n] = new Map(); return objectStore(n); },
                    transaction: (n) => ({ objectStore })
                }
            };
            setTimeout(() => {
                if (version > versionBase) { versionBase = version; requete.onupgradeneeded(); }
                requete.onsuccess();
            }, 0);
            return requete;
        }
    };
}

function charger(reponsesFetch) {
    const elements = {};
    const element = (id) => (elements[id] = elements[id] || {
        id, hidden: true, textContent: "", disabled: false,
        style: {}, classList: { contains: () => false },
        addEventListener(type, f) { this["on" + type] = f; }
    });
    const contexte = {
        console, setTimeout, clearTimeout, setInterval: () => 0, Promise, Date, JSON,
        AbortController: class { constructor() { this.signal = {}; } abort() {} },
        fetch: reponsesFetch,
        indexedDB: faireIndexedDB(),
        document: { addEventListener() {}, getElementById: element,
                    querySelectorAll: () => [], querySelector: () => null },
        window: { addEventListener() {}, isSecureContext: true },
        navigator: { onLine: true },
        localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
        btoa: (s) => Buffer.from(s, "binary").toString("base64"),
        unescape, encodeURIComponent
    };
    contexte.window.showDirectoryPicker = undefined;
    vm.createContext(contexte);
    vm.runInContext(fs.readFileSync(SCRIPT, "utf8"), contexte);
    contexte._elements = elements;
    return contexte;
}

const reponse = (statut, corps) => Promise.resolve({
    ok: statut >= 200 && statut < 300, status: statut,
    json: () => Promise.resolve(corps)
});

(async () => {
    // 1. Serveur joignable : la file se vide, la barre reste masquée.
    let c = charger(() => reponse(200, { ok: true, fichier: "Bilan_a.pdf" }));
    assert.ok(await c.mettreEnFile("pdf-a", "Bilan_a.pdf"));
    let bilan = await c.ecoulerFile();
    assert.deepStrictEqual([bilan.envoyes, bilan.restants, bilan.fichier],
                           [1, 0, "Bilan_a.pdf"]);
    assert.strictEqual(c._elements["barre-attente"].hidden, true);
    console.log("1. dépôt nominal : file vidée");

    // 2. Serveur injoignable : le bilan reste en file, la barre s'affiche.
    let joignable = false;
    c = charger(() => joignable
        ? reponse(200, { ok: true, fichier: "Bilan_b.pdf" })
        : Promise.reject(new TypeError("Failed to fetch")));
    await c.mettreEnFile("pdf-b", "Bilan_b.pdf");
    bilan = await c.ecoulerFile();
    assert.deepStrictEqual([bilan.envoyes, bilan.restants], [0, 1]);
    assert.strictEqual(c._elements["barre-attente"].hidden, false);
    assert.match(c._elements["texte-attente"].textContent, /1 bilan en attente/);
    console.log("2. serveur éteint : bilan conservé, barre affichée");

    // 3. Le serveur revient : le même bilan part sans nouvelle saisie.
    joignable = true;
    bilan = await c.ecoulerFile();
    assert.deepStrictEqual([bilan.envoyes, bilan.restants], [1, 0]);
    assert.strictEqual(c._elements["barre-attente"].hidden, true);
    console.log("3. serveur revenu : dépôt rattrapé automatiquement");

    // 4. Refus définitif : retiré de la file, jamais rejoué en boucle.
    let appels = 0;
    c = charger(() => { appels++; return reponse(400, { erreur: "Le fichier reçu n'est pas un PDF" }); });
    await c.mettreEnFile("pas-un-pdf", "Bilan_c.pdf");
    bilan = await c.ecoulerFile();
    assert.deepStrictEqual([bilan.refuses, bilan.restants], [1, 0]);
    await c.ecoulerFile();
    assert.strictEqual(appels, 1, "un refus définitif ne doit pas être rejoué");
    console.log("4. refus définitif : retiré, non rejoué");

    // 5. Erreur serveur récupérable (disque plein) : conservé.
    c = charger(() => reponse(500, { erreur: "Écriture impossible sur le PC" }));
    await c.mettreEnFile("pdf-d", "Bilan_d.pdf");
    bilan = await c.ecoulerFile();
    assert.deepStrictEqual([bilan.refuses, bilan.restants], [0, 1]);
    console.log("5. erreur 500 : conservé pour un nouvel essai");

    // 6. Écoulements concurrents : un seul envoi, pas de doublon.
    let envois = 0;
    c = charger(() => { envois++; return new Promise((r) => setTimeout(
        () => r({ ok: true, status: 200, json: () => Promise.resolve({ ok: true, fichier: "Bilan_e.pdf" }) }), 20)); });
    await c.mettreEnFile("pdf-e", "Bilan_e.pdf");
    await Promise.all([c.ecoulerFile(), c.ecoulerFile(), c.ecoulerFile()]);
    assert.strictEqual(envois, 1, "le même bilan a été déposé " + envois + " fois");
    console.log("6. écoulements simultanés : aucun doublon");

    // 7. Plusieurs en attente : on n'insiste pas après le premier échec réseau.
    let tentatives = 0;
    c = charger(() => { tentatives++; return Promise.reject(new TypeError("Failed to fetch")); });
    for (const n of ["f", "g", "h"]) await c.mettreEnFile("pdf-" + n, "Bilan_" + n + ".pdf");
    bilan = await c.ecoulerFile();
    assert.strictEqual(bilan.restants, 3);
    assert.strictEqual(tentatives, 1, tentatives + " tentatives au lieu d'une");
    assert.match(c._elements["texte-attente"].textContent, /3 bilans en attente/);
    console.log("7. file multiple : une seule tentative, accord du pluriel");

    console.log("\nTout est vert.");
})().catch((e) => { console.error("ÉCHEC :", e.message); process.exit(1); });
