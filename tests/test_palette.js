/*
 * Test de la conversion de couleur du générateur de PDF (formulaire/script.js).
 *
 * couleurEnRgb() est le seul point qui traduit un token CSS (« #cec1a3 »,
 * potentiellement non nettoyé par getPropertyValue(), ou une des formes de
 * repli « rgb(r, g, b) »/« rgba(r, g, b, a) » rendues par le navigateur) en
 * triplet pour jsPDF. Une régression ici fait sortir un PDF aux couleurs
 * fausses, une page noircie par un NaN passé à setFillColor, ou — défaut
 * relevé à l'audit — un fond transparent aplati en noir illisible au moment
 * du JPEG.
 *
 *     node tests/test_palette.js
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");

const SCRIPT = path.join(__dirname, "..", "formulaire", "script.js");

// Même squelette que tests/test_file_depots.js, repris à l'identique : le
// double IndexedDB n'est pas exercé par ce test, mais script.js le référence
// dans des fonctions non appelées ici, et le garder évite toute divergence
// avec le contexte qui a servi à valider le reste du fichier.
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

// script.js est chargé en entier : son code de niveau module
// (document.addEventListener aux lignes 1 et 692) n'exige rien de plus que
// ce contexte minimal, qui ne fournit ni getComputedStyle ni
// document.documentElement — couleurEnRgb() n'en a pas besoin.
function charger() {
    const elements = {};
    const element = (id) => (elements[id] = elements[id] || {
        id, hidden: true, textContent: "", disabled: false,
        style: {}, classList: { contains: () => false },
        addEventListener(type, f) { this["on" + type] = f; }
    });
    const contexte = {
        console, setTimeout, clearTimeout, setInterval: () => 0, Promise, Date, JSON,
        AbortController: class { constructor() { this.signal = {}; } abort() {} },
        fetch: () => Promise.reject(new TypeError("Failed to fetch")),
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
    return contexte;
}

const c = charger();

// Le tableau renvoyé par couleurEnRgb() est construit dans le contexte vm :
// un Array de cette autre « réalité » échoue deepStrictEqual par simple
// défaut de référence, sans rapport avec son contenu. On le ramène ici.
const rvb = (valeur) => {
    const resultat = c.couleurEnRgb(valeur);
    return resultat === null ? null : Array.from(resultat);
};

try {
    assert.deepStrictEqual(rvb("#cec1a3"), [206, 193, 163]);
    console.log("1. forme #RRGGBB");

    assert.deepStrictEqual(rvb(" #3B4133 "), [59, 65, 51]);
    console.log("2. espaces de tête et casse haute");

    assert.deepStrictEqual(rvb("#abc"), [170, 187, 204]);
    console.log("3. forme courte #RGB");

    assert.deepStrictEqual(rvb("rgb(206, 193, 163)"), [206, 193, 163]);
    console.log("4. forme rgb(), repli du navigateur");

    assert.deepStrictEqual(rvb("rgba(206, 193, 163, 1)"), [206, 193, 163]);
    console.log("5. forme rgba() avec un alpha opaque");

    assert.strictEqual(c.couleurEnRgb("rgba(0, 0, 0, 0)"), null);
    console.log("6. alpha nul : null, jamais aplati en noir opaque");

    assert.strictEqual(c.couleurEnRgb("rgb(300, 1, 1)"), null);
    console.log("7. composante hors 0-255 : null");

    assert.strictEqual(c.couleurEnRgb(""), null);
    assert.strictEqual(c.couleurEnRgb("var(--fond)"), null);
    assert.strictEqual(c.couleurEnRgb("#12345"), null);
    console.log("8. valeurs vide, non résolue ou mal formée : null, jamais un NaN");

    console.log("\nTout est vert.");
} catch (e) {
    console.error("ÉCHEC :", e.message);
    process.exit(1);
}
