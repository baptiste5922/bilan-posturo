/*
 * Tests de l'export en présence d'une grille (amendement A1 de C1-T6) :
 * mesure des grilles, réduction d'une grille trop large dans la copie
 * capturée, refus de l'export au-delà de la largeur de référence.
 *
 * Contexte : l'export capture `#form-bilan` par html2canvas, et l'échelle de
 * tout le PDF est la largeur de ce conteneur. Ce qui dépasse à droite n'est pas
 * dans l'image : une grille plus large que le conteneur serait rognée, sans un
 * mot. Voir docs/contrats/C1-T6.md, « Amendement A1 ».
 *
 * Les doubles de ce fichier DISTINGUENT LES SÉLECTEURS. Ceux de
 * tests/test_concurrence_export.js rendent l'élément lui-même pour tout
 * sélecteur : le nouveau code y verrait `#form-bilan` comme une grille de
 * 100 px qui tient, et le test passerait par accident.
 *
 * `script.js` est chargé dans un contexte `vm`, jamais recopié. La constante
 * `LARGEUR_GRILLE_REFERENCE_PX` est lue dans le source chargé.
 *
 *     node tests/test_export_grille.js
 *     SCRIPT_A_TESTER=/copie/mutée/script.js node tests/test_export_grille.js
 *
 * Le cas « sans grille » compare les options passées à html2canvas à celles
 * du `script.js` du commit 1ec796c (lu par `git show`, jamais recopié). Dans un
 * clone superficiel qui n'a pas ce commit, ce seul cas est sauté, en le disant
 * — sauf quand la variable `CI` est posée : la CI porte tout l'historique
 * (`fetch-depth: 0`), et un commit absent y est alors un échec, sans quoi une
 * régression du clone repasserait au vert en silence (C1-T6b, D5).
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");
const { execFileSync } = require("child_process");

const RACINE = path.join(__dirname, "..");
const SCRIPT = process.env.SCRIPT_A_TESTER
    ? path.resolve(process.env.SCRIPT_A_TESTER)
    : path.join(RACINE, "formulaire", "script.js");
// Sha complet : `git cat-file -e` en vérifie la présence sans ambiguïté.
const COMMIT_DE_REPERE = "1ec796c172bf1dcc9129bd0331fa6368edddb8c0";
const COMMIT_DE_REPERE_COURT = COMMIT_DE_REPERE.slice(0, 7);

// Le refus de A1-D4, mot pour mot : le contrat le fixe.
const MESSAGE_ATTENDU = "Une grille de ce formulaire est trop large pour être imprimée "
    + "lisiblement : le PDF n'a pas été créé. Votre saisie est conservée. Prévenez le support.";

const CABINET_BON = {
    praticien: "Dr Témoin", adresse: "1 rue du Test",
    courriel: "", telephone: "", convention_nommage: ""
};

function faireIndexedDB() {
    const magasins = {};
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
        open(nom, version) {
            const requete = {
                result: {
                    objectStoreNames: { contains: (n) => n in magasins },
                    createObjectStore(n) { magasins[n] = new Map(); return objectStore(n); },
                    transaction: () => ({ objectStore })
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

/** Une boîte : `gauche` et `largeur` suffisent, le reste en découle. */
function boite(gauche, largeur, haut, hauteur) {
    return {
        left: gauche, right: gauche + largeur, width: largeur,
        top: haut, bottom: haut + hauteur, height: hauteur
    };
}

/**
 * Une table du formulaire affiché : `type` vaut "grille" (classe `grille`) ou
 * "tableau" (la table à choix exclusif de la V1, sans cette classe).
 */
function table(type, gauche, largeur) {
    return { type, boite: boite(gauche, largeur, 200, 300) };
}

/**
 * Le seul vocabulaire de sélecteurs que le code testé a le droit d'employer :
 * `table.grille` ne rend que les grilles, `table` rend toutes les tables,
 * `.bloc` rend un bloc, et tout le reste ne rend rien.
 */
function tablesPourSelecteur(selecteur, tables) {
    if (/\btable\.grille\b/.test(selecteur)) return tables.filter((t) => t.type === "grille");
    if (/\btable\b/.test(selecteur)) return tables;
    return [];
}

/**
 * Construit un contexte vm chargé avec `scriptChemin`, autour d'un formulaire
 * de largeur `largeurForm` (bord gauche à 10) contenant les `tables` données.
 * Rend le contexte et des compteurs : html2canvas, mettreEnFile, annonces.
 */
function charger(scriptChemin, largeurForm, tables) {
    const elements = {};
    const compteurs = { html2canvas: 0, options: null, mettreEnFile: 0, depots: 0, annonces: [] };

    const formBoite = boite(10, largeurForm, 0, 1000);
    const form = {
        id: "form-bilan", style: {}, children: [],
        getBoundingClientRect: () => formBoite,
        querySelectorAll(selecteur) {
            if (/\.bloc\b/.test(selecteur)) {
                return [{ id: "bloc", className: "bloc",
                          getBoundingClientRect: () => boite(10, largeurForm, 0, 500) }];
            }
            return tablesPourSelecteur(selecteur, tables).map((t) => ({
                type: t.type, getBoundingClientRect: () => t.boite
            }));
        }
    };

    function creerElement(id) {
        return {
            id, value: "", hidden: true, textContent: "", className: "",
            style: {}, classList: { contains: () => false }, children: [],
            appendChild(enfant) { this.children.push(enfant); this.textContent += enfant.textContent || ""; },
            addEventListener(type, f) { this["on" + type] = f; },
            getBoundingClientRect: () => boite(0, 100, 0, 100),
            querySelectorAll: () => []
        };
    }
    const element = (id) => {
        if (id === "form-bilan") return form;
        return (elements[id] = elements[id] || creerElement(id));
    };

    const pdfFactice = () => ({
        addPage() {}, setFillColor() {}, rect() {}, addImage() {},
        setFontSize() {}, setTextColor() {}, text() {},
        output() { return "blob-factice"; }, save() {}
    });
    const canvasFactice = (largeur, hauteur) => ({
        width: largeur, height: hauteur,
        getContext() { return { fillStyle: "", fillRect() {}, drawImage() {} }; },
        toDataURL() { return "data:image/jpeg;base64,"; }
    });

    const contexte = {
        console: { log() {}, warn() {}, error() {} },   // le « PDF généré » de script.js n'a rien à faire ici
        setTimeout, clearTimeout, setInterval: () => 0,
        Promise, Date, JSON, Math,
        AbortController: class { constructor() { this.signal = {}; } abort() {} },
        getComputedStyle() { return { getPropertyValue: () => "#FFFFFF", backgroundColor: "#FFFFFF" }; },
        html2canvas(el, options) {
            compteurs.html2canvas += 1;
            compteurs.options = options;
            return Promise.resolve(canvasFactice(largeurForm, 500));
        },
        fetch(url) {
            const chemin = String(url).split("?")[0];
            if (chemin === "/cabinet") return Promise.resolve({ ok: true, json: () => Promise.resolve(CABINET_BON) });
            if (chemin === "/depot") {
                compteurs.depots += 1;
                return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true, fichier: "Bilan_test.pdf" }) });
            }
            if (chemin === "/sante") return Promise.resolve({ ok: true });
            return Promise.reject(new Error("fetch non simulé pour " + url));
        },
        document: {
            addEventListener() {},
            getElementById: element,
            documentElement: {}, body: {},
            createElement(tag) {
                if (tag === "canvas") return canvasFactice(0, 0);
                return { tagName: tag, textContent: "" };
            },
            // Le formulaire AFFICHÉ : preparerClone() y relit ses mesures.
            querySelectorAll(selecteur) { return form.querySelectorAll(selecteur); },
            querySelector: () => null
        },
        window: {
            addEventListener() {}, isSecureContext: true, showDirectoryPicker: undefined,
            jspdf: { jsPDF: function () { return pdfFactice(); } },
            getComputedStyle() { return {}; }
        },
        navigator: { onLine: true },
        localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
        indexedDB: faireIndexedDB(),
        btoa: (s) => Buffer.from(s, "binary").toString("base64"),
        unescape, encodeURIComponent
    };
    vm.createContext(contexte);
    vm.runInContext(fs.readFileSync(scriptChemin, "utf8"), contexte, { filename: path.basename(scriptChemin) });

    // Espions : les fonctions de script.js sont des propriétés du contexte, et
    // exporterBilanPDF() les retrouve par leur nom à chaque appel.
    const mettreEnFileOrigine = contexte.mettreEnFile;
    contexte.mettreEnFile = function () {
        compteurs.mettreEnFile += 1;
        return mettreEnFileOrigine.apply(this, arguments);
    };
    contexte.annoncer = function (message, genre, persistant) {
        compteurs.annonces.push({ message, genre, persistant });
    };
    contexte._compteurs = compteurs;
    contexte._form = form;
    contexte._bouton = element("btn-export");
    return contexte;
}

/** Le document cloné par html2canvas : mêmes tables, styles propres à la copie. */
function creerClone(tables) {
    const clones = tables.map((t) => ({ type: t.type, style: {} }));
    return {
        clones,
        querySelectorAll(selecteur) { return tablesPourSelecteur(selecteur, clones); }
    };
}

const reference = (c) => vm.runInContext("LARGEUR_GRILLE_REFERENCE_PX", c);

let nbCas = 0;
const echecs = [];
async function cas(nom, fn) {
    nbCas += 1;
    try {
        await fn();
        console.log("ok - " + nom);
    } catch (erreur) {
        echecs.push(nom);
        console.log("ECHEC - " + nom + "\n    " + String(erreur.message).split("\n").join("\n    "));
    }
}

const aucunStyle = (clone) => Object.keys(clone.style).length === 0;

/** Un export complet, identité chargée, d'un formulaire donné. */
async function exporter(c) {
    await c.chargerCabinet();
    c.appliquerCabinet();
    await c.exporterBilanPDF();
}

(async () => {
    // ---------------------------------------------------------------- mesure
    await cas("mesurerGrilles : seules les table.grille sont mesurées, dans l'ordre du document", () => {
        const c = charger(SCRIPT, 1000, [table("tableau", 10, 400), table("grille", 10, 300), table("grille", 10, 1500)]);
        const mesures = c.mesurerGrilles(c._form);
        assert.strictEqual(mesures.length, 2, "une mesure par grille, aucune pour le tableau de la V1");
        // disponible = bord droit du conteneur (10 + 1000) moins bord gauche de la table (10)
        assert.strictEqual(mesures[0].largeur, 300);
        assert.strictEqual(mesures[0].disponible, 1000);
        assert.strictEqual(mesures[0].facteur, 1, "une grille qui tient : facteur 1");
        assert.strictEqual(mesures[1].largeur, 1500);
        assert.strictEqual(mesures[1].disponible, 1000);
        assert.strictEqual(mesures[1].facteur, 1000 / 1500, "une grille qui dépasse : disponible / largeur");
    });

    await cas("mesurerGrilles : une grille qui épouse exactement le conteneur tient (facteur 1)", () => {
        const c = charger(SCRIPT, 1000, [table("grille", 10, 1000)]);
        assert.strictEqual(c.mesurerGrilles(c._form)[0].facteur, 1);
    });

    // ------------------------------------------------------------- réduction
    await cas("preparerClone : une grille qui tient ne reçoit aucun style", () => {
        const tables = [table("grille", 10, 900)];
        const c = charger(SCRIPT, 1000, tables);
        const clone = creerClone(tables);
        c.preparerClone(clone);
        assert.ok(aucunStyle(clone.clones[0]), "aucun style posé : " + JSON.stringify(clone.clones[0].style));
    });

    await cas("preparerClone : une grille qui dépasse (sous la référence) est réduite, elle seule, origine en haut à gauche", () => {
        const c0 = charger(SCRIPT, 1000, []);
        const ref = reference(c0);
        // Une grille à la référence moins 100 px dans un conteneur de 300 px de moins :
        // elle dépasse le conteneur sans dépasser la référence.
        const largeurForm = ref - 300;
        const tables = [table("tableau", 10, 200), table("grille", 10, largeurForm - 100),
                        table("grille", 10, ref - 100)];
        const c = charger(SCRIPT, largeurForm, tables);
        const clone = creerClone(tables);
        c.preparerClone(clone);
        const [tableau, tient, reduite] = clone.clones;
        assert.ok(aucunStyle(tableau), "la table de la V1 n'est jamais touchée");
        assert.ok(aucunStyle(tient), "la grille qui tient n'est pas touchée");
        const facteur = largeurForm / (ref - 100);
        assert.strictEqual(reduite.style.transform, "scale(" + facteur + ")",
            "transform attendu sur la seule grille de même rang : " + JSON.stringify(reduite.style));
        assert.strictEqual(reduite.style.transformOrigin, "top left");
    });

    await cas("preparerClone : la copie seule est modifiée, jamais le formulaire affiché", () => {
        const c0 = charger(SCRIPT, 1000, []);
        const ref = reference(c0);
        const tables = [table("grille", 10, ref - 100)];
        const c = charger(SCRIPT, ref - 300, tables);
        const clone = creerClone(tables);
        c.preparerClone(clone);
        assert.ok(clone.clones[0].style.transform, "la copie est réduite");
        assert.strictEqual(tables[0].style, undefined, "aucun style posé sur la table affichée");
    });

    await cas("preparerClone : sans aucune grille (tableau de la V1 compris), aucun transform", () => {
        const tables = [table("tableau", 10, 5000), table("tableau", 10, 200)];
        const c = charger(SCRIPT, 1000, tables);
        const clone = creerClone(tables);
        c.preparerClone(clone);
        assert.ok(clone.clones.every(aucunStyle), "aucun style, même sur un tableau plus large que le conteneur");
    });

    // ----------------------------------------------------------------- refus
    async function exportAvec(largeurForm, largeurGrille) {
        const c = charger(SCRIPT, largeurForm, [table("grille", 10, largeurGrille)]);
        await exporter(c);
        return c;
    }

    await cas("export : une grille qui dépasse mais dont la largeur égale la référence est acceptée", async () => {
        const ref = reference(charger(SCRIPT, 1000, []));
        const c = await exportAvec(ref - 200, ref);
        assert.strictEqual(c._compteurs.html2canvas, 1, "html2canvas doit être appelé : largeur == référence");
        assert.deepStrictEqual(c._compteurs.annonces.filter((a) => a.message === MESSAGE_ATTENDU), []);
    });

    await cas("export : une grille qui dépasse avec une largeur de référence + 1 est refusée", async () => {
        const ref = reference(charger(SCRIPT, 1000, []));
        const c = await exportAvec(ref - 200, ref + 1);
        assert.strictEqual(c._compteurs.html2canvas, 0, "html2canvas ne doit pas être appelé");
    });

    await cas("export : une grille plus large que la référence mais qui tient dans un conteneur large est acceptée", async () => {
        const ref = reference(charger(SCRIPT, 1000, []));
        const c = await exportAvec(ref + 500, ref + 300);
        assert.strictEqual(c._compteurs.html2canvas, 1, "elle tient : rien à réduire, rien à refuser");
    });

    await cas("export refusé : message de A1-D4, rien n'est capturé ni mis en file ni déposé", async () => {
        const ref = reference(charger(SCRIPT, 1000, []));
        const c = await exportAvec(ref - 200, ref + 1);
        const annonces = c._compteurs.annonces;
        assert.strictEqual(annonces.length, 1, "un seul message : " + JSON.stringify(annonces));
        assert.strictEqual(annonces[0].message, MESSAGE_ATTENDU, "texte fixé par A1-D4, mot pour mot");
        assert.strictEqual(annonces[0].genre, "erreur");
        assert.strictEqual(annonces[0].persistant, true);
        assert.strictEqual(c._compteurs.html2canvas, 0, "refus avant html2canvas");
        assert.strictEqual(c._compteurs.mettreEnFile, 0, "refus avant mettreEnFile : aucun PDF faux dans la file");
        assert.strictEqual(c._compteurs.depots, 0, "aucun dépôt");
    });

    await cas("export refusé : le bouton est réaffiché et un second export repart (exportEnCours relâché)", async () => {
        const ref = reference(charger(SCRIPT, 1000, []));
        const largeurForm = ref - 200;
        const tables = [table("grille", 10, ref + 1)];
        const c = charger(SCRIPT, largeurForm, tables);
        await exporter(c);
        assert.strictEqual(c._compteurs.html2canvas, 0);
        assert.strictEqual(c._bouton.style.display, "block", "le bouton d'export doit réapparaître");
        // La grille se corrige (le schéma est réparé, la fenêtre s'élargit) : le même contexte exporte.
        tables[0].boite = boite(10, ref - 400, 200, 300);
        await c.exporterBilanPDF();
        assert.strictEqual(c._compteurs.html2canvas, 1, "le second export doit partir : le drapeau a été relâché");
    });

    await cas("export refusé : aucun message de refus quand le formulaire n'a pas de grille", async () => {
        const c = charger(SCRIPT, 1000, [table("tableau", 10, 99999)]);
        await exporter(c);
        assert.strictEqual(c._compteurs.html2canvas, 1);
        assert.deepStrictEqual(c._compteurs.annonces.filter((a) => a.message === MESSAGE_ATTENDU), []);
    });

    // ---------------------------------------- aucun accès au DOM au chargement
    await cas("A1-D6 : script.js se charge sans toucher au DOM (seul addEventListener est permis)", () => {
        const accessInterdit = (nom) => new Proxy({ addEventListener() {} }, {
            get(cible, propriete) {
                if (propriete in cible) return cible[propriete];
                throw new Error("accès à " + nom + "." + String(propriete) + " au niveau module");
            }
        });
        const contexte = {
            console: { log() {}, warn() {}, error() {} },
            setTimeout, clearTimeout, setInterval: () => 0, Promise, Date, JSON, Math,
            document: accessInterdit("document"),
            window: accessInterdit("window"),
            navigator: { onLine: true },
            localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
            indexedDB: {}
        };
        vm.createContext(contexte);
        vm.runInContext(fs.readFileSync(SCRIPT, "utf8"), contexte, { filename: path.basename(SCRIPT) });
        assert.strictEqual(typeof contexte.mesurerGrilles, "function", "le script s'est bien chargé en entier");
    });

    // ------------------------------------------------- inertie sans grille
    let commitPresent = true;
    try {
        execFileSync("git", ["cat-file", "-e", COMMIT_DE_REPERE + "^{commit}"],
            { cwd: RACINE, stdio: "ignore" });
    } catch (e) { commitPresent = false; }

    let scriptReference = null;
    if (commitPresent) {
        scriptReference = execFileSync("git", ["show", COMMIT_DE_REPERE + ":formulaire/script.js"],
            { cwd: RACINE, stdio: ["ignore", "pipe", "ignore"], maxBuffer: 16 * 1024 * 1024 });
    }

    if (scriptReference === null && process.env.CI) {
        await cas("sans grille : html2canvas reçoit les mêmes options que le script.js de " + COMMIT_DE_REPERE_COURT, () => {
            throw new Error("commit de repère " + COMMIT_DE_REPERE_COURT + " absent alors que CI est posé : "
                + "le clone de la CI doit porter l'historique (fetch-depth: 0)");
        });
    } else if (scriptReference === null) {
        console.log("saut - options de capture sans grille identiques à celles de " + COMMIT_DE_REPERE_COURT
            + " : commit absent (clone superficiel), cas non joué");
    } else {
        await cas("sans grille : html2canvas reçoit les mêmes options que le script.js de " + COMMIT_DE_REPERE_COURT, async () => {
            // Le script de référence est écrit dans un fichier temporaire hors du dépôt.
            const os = require("os");
            const dossier = fs.mkdtempSync(path.join(os.tmpdir(), "script-reference-"));
            const chemin = path.join(dossier, "script.js");
            fs.writeFileSync(chemin, scriptReference);
            try {
                const tablesDe = () => [table("tableau", 10, 400)];
                const ancien = charger(chemin, 1000, tablesDe());
                await exporter(ancien);
                const nouveau = charger(SCRIPT, 1000, tablesDe());
                await exporter(nouveau);
                const a = ancien._compteurs.options, n = nouveau._compteurs.options;
                assert.ok(a && n, "les deux exports doivent atteindre html2canvas");
                assert.deepStrictEqual(Object.keys(n).sort(), Object.keys(a).sort(), "mêmes options, ni plus ni moins");
                Object.keys(a).forEach(function (cle) {
                    if (typeof a[cle] === "function") {
                        assert.strictEqual(typeof n[cle], "function", cle + " doit rester une fonction");
                        assert.strictEqual(n[cle].name, a[cle].name, cle + " : même fonction nommée");
                    } else {
                        assert.deepStrictEqual(n[cle], a[cle], "option « " + cle + " » inchangée");
                    }
                });
            } finally {
                fs.rmSync(dossier, { recursive: true, force: true });
            }
        });
    }

    console.log("\n" + nbCas + " cas joués, " + echecs.length + " en échec.");
    if (echecs.length > 0) {
        console.log("Échecs : " + echecs.join(" ; "));
        process.exit(1);
    }
    console.log("Tout est vert.");
})().catch((erreur) => {
    console.error(erreur);
    process.exit(1);
});
