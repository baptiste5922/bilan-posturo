/*
 * Schémas par client (contrat C1-T4a) : `clients/<client>/schema.json`.
 *
 * Quatre groupes, chacun un garde-fou à éprouver par mutation volontaire
 * (docs/audits/C1-T4a-mises-en-echec.md) :
 *
 *   G1 — les dossiers : `clients/` existe, n'est pas vide, et chaque dossier
 *        est nommé `cabinet-NN` et porte un `schema.json` ;
 *   G2 — la validité : le moteur (`validerSchema()`) accepte chaque schéma ;
 *   G3 — le miroir : `formulaire/schema.json` et `clients/cabinet-01/schema.json`
 *        sont égaux octet pour octet (le serveur ne sert que `formulaire/`) ;
 *   G4 — le brouillon de production : les clés de brouillon du formulaire
 *        rendu par le moteur sont, dans les deux sens, celles du formulaire
 *        installé au cabinet (étiquette `production-cabinet-01`). Un brouillon
 *        commencé sur la version installée doit se rouvrir sur la suivante.
 *
 * G4 lit un blob qui porte l'identité réelle du cabinet, et la sortie de cette
 * suite finit dans un journal de CI public. Règle : un message d'échec ne cite
 * que des clés de champs, des chemins d'images et des valeurs de constantes
 * de code, jamais un texte du blob.
 *
 * Aucune dépendance. L'analyseur HTML est celui de `tests/test_comparaison_dom.js`
 * (extrait dans `tests/outils/analyseur-html.js`) ; `cleChamp()` est la vraie
 * fonction de `formulaire/script.js`, chargée en `vm` (patron de
 * `tests/test_nommage.js`), jamais réécrite ici.
 *
 *     node tests/test_schema_client.js
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");
const { execFileSync } = require("child_process");

const dom = require("./outils/dom-minimal.js");
const { analyserHtml, extraireElement } = require("./outils/analyseur-html.js");

const RACINE = path.join(__dirname, "..");
const DOSSIER_CLIENTS = path.join(RACINE, "clients");
const CHEMIN_MIROIR = path.join(RACINE, "formulaire", "schema.json");
const CHEMIN_COQUILLE = path.join(RACINE, "formulaire", "index.html");
const CHEMIN_MOTEUR = path.join(RACINE, "formulaire", "moteur", "rendu.js");
const CHEMIN_SCRIPT = path.join(RACINE, "formulaire", "script.js");

const ETIQUETTE_PRODUCTION = "production-cabinet-01";
const MOTIF_NOM_CLIENT = /^cabinet-[0-9]{2,}$/;
const CLIENT_DU_MIROIR = "cabinet-01";

/* ================================= Lectures ================================= */

function normaliser(texte) {
    return texte.replace(/\r\n/g, "\n");
}

/** Les sous-dossiers de `clients/`, lus sur le disque : jamais une liste écrite. */
function dossiersClients() {
    return fs.readdirSync(DOSSIER_CLIENTS, { withFileTypes: true })
        .filter(function (entree) { return entree.isDirectory(); })
        .map(function (entree) { return entree.name; })
        .sort();
}

/**
 * Un fichier du blob de l'étiquette de production, par `git cat-file`, sans
 * shell. L'étiquette absente est un ÉCHEC et jamais un saut : un test qui se
 * sauterait en silence dans un clone sans étiquettes ne garderait plus rien.
 */
function lireEnProduction(cheminDansLeDepot) {
    try {
        execFileSync("git", ["rev-parse", "--verify", "--quiet", ETIQUETTE_PRODUCTION + "^{commit}"],
            { cwd: RACINE, stdio: ["ignore", "pipe", "pipe"] });
    } catch (erreur) {
        throw new Error(
            "l'étiquette « " + ETIQUETTE_PRODUCTION + " » est introuvable dans ce dépôt : la compatibilité " +
            "des brouillons ne peut pas être vérifiée. Remède : git fetch --tags (un clone d'intégration " +
            "continue se fait avec fetch-depth: 0). Ce test ne se saute jamais."
        );
    }
    try {
        return normaliser(execFileSync("git", ["cat-file", "-p", ETIQUETTE_PRODUCTION + ":" + cheminDansLeDepot],
            { cwd: RACINE, encoding: "utf8", maxBuffer: 64 * 1024 * 1024, stdio: ["ignore", "pipe", "pipe"] }));
    } catch (erreur) {
        throw new Error(
            "« " + cheminDansLeDepot + " » est illisible dans l'objet de l'étiquette " + ETIQUETTE_PRODUCTION +
            " (code de git : " + erreur.status + ")."
        );
    }
}

/** Le moteur de rendu, chargé comme dans tests/test_comparaison_dom.js. */
function chargerMoteur() {
    const contexte = { console };
    vm.createContext(contexte);
    contexte.document = Object.assign(dom.creerDocument(), { addEventListener() {} });
    vm.runInContext(fs.readFileSync(CHEMIN_MOTEUR, "utf-8"), contexte, { filename: "rendu.js" });
    assert.strictEqual(typeof contexte.validerSchema, "function", "validerSchema doit être exportée par rendu.js");
    assert.strictEqual(typeof contexte.rendre, "function", "rendre doit être exportée par rendu.js");
    return contexte;
}

/**
 * La vraie `cleChamp()` de formulaire/script.js, chargée en `vm` avec le
 * strict minimum de globales (patron de tests/test_nommage.js) : le fichier
 * s'exécute en entier, la fonction n'est pas recopiée.
 */
function chargerCleChamp() {
    const contexte = {
        console, setTimeout, clearTimeout, setInterval: () => 0, Promise, Date, JSON,
        AbortController: class { constructor() { this.signal = {}; } abort() {} },
        fetch() { return Promise.reject(new Error("fetch non simulé")); },
        document: {
            addEventListener() {},
            getElementById: () => ({ addEventListener() {}, style: {}, classList: { contains: () => false } }),
            querySelectorAll: () => [], querySelector: () => null
        },
        window: { addEventListener() {} },
        navigator: { onLine: true },
        localStorage: { getItem: () => null, setItem() {}, removeItem() {} }
    };
    vm.createContext(contexte);
    vm.runInContext(fs.readFileSync(CHEMIN_SCRIPT, "utf8"), contexte, { filename: "script.js" });
    assert.strictEqual(typeof vm.runInContext("cleChamp", contexte), "function", "cleChamp absente de script.js");
    return vm.runInContext("cleChamp", contexte);
}

/* ============================ Projection d'un arbre ============================ */

const BALISES_CHAMP = new Set(["input", "textarea", "select"]);

/**
 * Ce que `champsDuFormulaire()` verrait dans un vrai navigateur : les champs
 * `input`, `textarea`, `select`, dans l'ordre du document, sous la forme que
 * lit `cleChamp()` (id, name, value). Un radio ou une case sans attribut
 * `value` vaut « on », comme dans un navigateur.
 */
function collecter(racine) {
    const champs = [];
    const images = [];
    (function marcher(n) {
        if (n.genre !== "element") return;
        if (BALISES_CHAMP.has(n.balise)) {
            const type = (n.getAttribute("type") || "").toLowerCase();
            let valeur = n.getAttribute("value");
            if (valeur === null) valeur = (type === "radio" || type === "checkbox") ? "on" : "";
            champs.push({ id: n.getAttribute("id") || "", name: n.getAttribute("name") || "", value: valeur });
        }
        if (n.balise === "img" && (n.getAttribute("class") || "").split(/\s+/).includes("dessinable")) {
            images.push(n.getAttribute("src"));
        }
        n.enfants.forEach(marcher);
    })(racine);
    return { champs: champs, images: images };
}

/** Le motif ancré de la constante, présent une seule fois, sinon échec. */
function valeurCleBrouillon(source, origine) {
    const trouvees = Array.from(source.matchAll(/^const CLE_BROUILLON = "([^"]+)";$/gm));
    assert.strictEqual(trouvees.length, 1,
        "la constante CLE_BROUILLON doit apparaître exactement une fois dans " + origine +
        " (trouvé : " + trouvees.length + ")");
    return trouvees[0][1];
}

/** Le corps de `cleChamp()`, de sa déclaration à l'accolade fermante ancrée en colonne 0. */
function corpsCleChamp(source, origine) {
    const trouvees = Array.from(source.matchAll(/^function cleChamp\(champ\) \{\n[\s\S]*?\n\}$/gm));
    assert.strictEqual(trouvees.length, 1,
        "cleChamp() doit être déclarée exactement une fois dans " + origine + " (trouvé : " + trouvees.length + ")");
    return trouvees[0][0];
}

function ensembleMoins(a, b) {
    return Array.from(a).filter(function (x) { return !b.has(x); }).sort();
}

/* ================================== Cadre =================================== */

let nbCas = 0;
const echecs = [];
function cas(nom, fn) {
    nbCas += 1;
    try {
        fn();
        console.log("ok - " + nom);
    } catch (erreur) {
        echecs.push(nom);
        console.log("ECHEC - " + nom + "\n    " + String(erreur.message).split("\n").join("\n    "));
    }
}

/* ============================== G1 — Dossiers ============================== */

let noms = [];
cas("G1 : clients/ existe et contient au moins un dossier", () => {
    assert.ok(fs.existsSync(DOSSIER_CLIENTS) && fs.statSync(DOSSIER_CLIENTS).isDirectory(),
        "le dossier clients/ est absent");
    noms = dossiersClients();
    assert.ok(noms.length >= 1,
        "clients/ ne contient aucun dossier de client : un test vert à vide ne garderait rien");
});

cas("G1 : chaque dossier est nommé cabinet-NN et porte un schema.json", () => {
    assert.ok(noms.length >= 1, "aucun dossier à contrôler (voir le cas précédent)");
    const mal = noms.filter(function (n) { return !MOTIF_NOM_CLIENT.test(n); });
    assert.deepStrictEqual(mal, [],
        "dossier(s) mal nommé(s) (attendu : " + MOTIF_NOM_CLIENT + ", jamais d'après une ville) : " + mal.join(", "));
    const sansSchema = noms.filter(function (n) {
        return !fs.existsSync(path.join(DOSSIER_CLIENTS, n, "schema.json"));
    });
    assert.deepStrictEqual(sansSchema, [], "dossier(s) sans schema.json : " + sansSchema.join(", "));
});

/* ============================== G2 — Validité ============================== */

cas("G2 : le moteur accepte le schema.json de chaque client", () => {
    assert.ok(noms.length >= 1, "aucun dossier à contrôler (voir G1)");
    const moteur = chargerMoteur();
    noms.forEach(function (nom) {
        const brut = fs.readFileSync(path.join(DOSSIER_CLIENTS, nom, "schema.json"), "utf-8");
        let schema;
        try {
            schema = JSON.parse(normaliser(brut));
        } catch (erreur) {
            assert.fail(nom + " : schema.json n'est pas du JSON (" + erreur.message + ")");
        }
        const refus = Array.from(moteur.validerSchema(schema));
        assert.deepStrictEqual(refus, [], nom + " : schéma refusé par le moteur");
    });
});

/* =============================== G3 — Miroir =============================== */

cas("G3 : formulaire/schema.json et clients/cabinet-01/schema.json sont égaux octet pour octet", () => {
    const miroir = fs.readFileSync(CHEMIN_MIROIR);
    const client = fs.readFileSync(path.join(DOSSIER_CLIENTS, CLIENT_DU_MIROIR, "schema.json"));
    assert.ok(miroir.equals(client),
        "les deux copies divergent (" + miroir.length + " octets contre " + client.length + ") : toute " +
        "modification se fait dans les deux (clients/LISEZMOI.md)");
});

/* ================== G4 — Brouillon de production compatible ================== */

let production = null;
let moteurMesure = null;
cas("G4 : l'étiquette de production se lit, et les deux formulaires se construisent", () => {
    const htmlProduction = lireEnProduction("formulaire/index.html");
    const formProduction = analyserHtml(dom.creerDocument(),
        extraireElement(htmlProduction, '<div id="form-bilan">', "div"))[0];
    production = collecter(formProduction);

    const moteur = chargerMoteur();
    const schema = JSON.parse(normaliser(fs.readFileSync(
        path.join(DOSSIER_CLIENTS, CLIENT_DU_MIROIR, "schema.json"), "utf-8")));
    const document = moteur.document;
    const formMoteur = document.createElement("div");
    formMoteur.setAttribute("id", "form-bilan");
    analyserHtml(document, extraireElement(normaliser(fs.readFileSync(CHEMIN_COQUILLE, "utf-8")),
        "<header", "header")).forEach(function (n) { formMoteur.appendChild(n); });
    const main = document.createElement("main");
    formMoteur.appendChild(main);
    const resultat = moteur.rendre(schema, document, main);
    assert.ok(resultat.ok, "le moteur refuse le schéma de " + CLIENT_DU_MIROIR + " : " + resultat.erreurs.join(" | "));
    moteurMesure = collecter(formMoteur);

    assert.ok(production.champs.length >= 40,
        "le formulaire de production n'a livré que " + production.champs.length + " champ(s) : lecture suspecte");
    assert.ok(moteurMesure.champs.length >= 40,
        "le moteur n'a rendu que " + moteurMesure.champs.length + " champ(s) : rendu suspect");
});

cas("G4 : mêmes clés de brouillon, dans les deux sens (cleChamp de script.js)", () => {
    assert.ok(production && moteurMesure, "construction impossible (voir le cas précédent)");
    const cleChamp = chargerCleChamp();
    const cles = function (champs) {
        return champs.map(function (c) { return cleChamp(c); }).filter(function (k) { return k !== null; });
    };
    const clesProduction = cles(production.champs);
    const clesMoteur = cles(moteurMesure.champs);
    const ensembleProduction = new Set(clesProduction);
    const ensembleMoteur = new Set(clesMoteur);

    const perdues = ensembleMoins(ensembleProduction, ensembleMoteur);
    const nouvelles = ensembleMoins(ensembleMoteur, ensembleProduction);
    assert.deepStrictEqual(perdues, [],
        "clé(s) de brouillon de la production ABSENTES du moteur (un brouillon les perdrait) : " + perdues.join(", "));
    assert.deepStrictEqual(nouvelles, [],
        "clé(s) du moteur INCONNUES de la production : " + nouvelles.join(", "));
    assert.strictEqual(clesMoteur.length, clesProduction.length,
        "nombre de champs à clé différent : production " + clesProduction.length + ", moteur " + clesMoteur.length);
});

cas("G4 : mêmes images annotables, dans le même ordre (les traits sont indexés par position)", () => {
    assert.ok(production && moteurMesure, "construction impossible (voir le premier cas G4)");
    assert.strictEqual(production.images.length, 4, "4 images annotables attendues en production");
    assert.deepStrictEqual(moteurMesure.images, production.images,
        "la liste ordonnée des src des images annotables diverge de la production");
});

cas("G4 : même clé de stockage du brouillon et même cleChamp() dans les deux script.js", () => {
    const scriptProduction = lireEnProduction("formulaire/script.js");
    const scriptCourant = normaliser(fs.readFileSync(CHEMIN_SCRIPT, "utf-8"));
    const clePro = valeurCleBrouillon(scriptProduction, "le script.js de production");
    const cleCourante = valeurCleBrouillon(scriptCourant, "le script.js courant");
    assert.strictEqual(cleCourante, clePro,
        "CLE_BROUILLON diverge : production « " + clePro + " », courant « " + cleCourante + " »");
    assert.strictEqual(
        corpsCleChamp(scriptCourant, "le script.js courant"),
        corpsCleChamp(scriptProduction, "le script.js de production"),
        "le corps de cleChamp() diverge entre la production et le script.js courant"
    );
});

console.log("\n" + nbCas + " cas joués, " + echecs.length + " en échec.");
if (echecs.length > 0) {
    console.log("Échecs : " + echecs.join(" ; "));
    process.exit(1);
}
console.log("Tout est vert.");
