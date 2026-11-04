/*
 * Tests du type `grille` (C1-T6, format de schéma en version 2) : validation,
 * rendu, clés de cellule, brouillon, et non-régression du rendu de la
 * version 1.
 *
 * Rien n'est recopié de la spécification ni du moteur quand il peut en être
 * lu : la version maximale vient de l'en-tête de `docs/schema-formulaire.md`,
 * les versions et les types connus de `formulaire/moteur/rendu.js` (chargé par
 * `vm`), les clés attendues de la donnée fictive
 * `tests/donnees/schema-v2-grilles-fictives.json`. Seule la règle de
 * dérivation d'une clé de cellule est écrite ici, parce que c'est elle qu'on
 * éprouve — avec une ancre littérale, `grille-1__ligne-2__colonne-4`.
 *
 * Le brouillon n'est pas simulé : `cleChamp()`, `champsDuFormulaire()`,
 * `collecterBilan()` et `restaurerBilan()` sont extraites telles quelles de
 * `formulaire/script.js` et jouées sur les contrôles que le moteur a rendus.
 *
 * L'instantané de la version 1 (`tests/donnees/rendu-schema-production.txt`)
 * est la sérialisation du rendu de `formulaire/schema.json` par le moteur du
 * commit 1ec796c, produite par :
 *
 *     git show 1ec796c:formulaire/moteur/rendu.js > /chemin/hors/depot/rendu-1ec796c.js
 *     node tests/outils/serialiser-rendu.js /chemin/hors/depot/rendu-1ec796c.js \
 *         formulaire/schema.json > tests/donnees/rendu-schema-production.txt
 *
 *     node tests/test_grille.js
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");
const dom = require("./outils/dom-minimal.js");
const { serialiserRendu } = require("./outils/serialiser-rendu.js");

const RACINE = path.join(__dirname, "..");
const CHEMIN_MOTEUR = path.join(RACINE, "formulaire", "moteur", "rendu.js");
const CHEMIN_SCRIPT = path.join(RACINE, "formulaire", "script.js");
const CHEMIN_SPEC = path.join(RACINE, "docs", "schema-formulaire.md");
const CHEMIN_SCHEMA_PROD = path.join(RACINE, "formulaire", "schema.json");
const CHEMIN_DONNEE = path.join(__dirname, "donnees", "schema-v2-grilles-fictives.json");
const CHEMIN_INSTANTANE = path.join(__dirname, "donnees", "rendu-schema-production.txt");

function lireNormalise(chemin) {
    return fs.readFileSync(chemin, "utf-8").replace(/\r\n/g, "\n");
}

function cloner(valeur) {
    return JSON.parse(JSON.stringify(valeur));
}

/* ================================== Moteur ================================= */

const avertissements = [];
const contexte = {
    console: {
        warn: function () { avertissements.push(Array.prototype.join.call(arguments, " ")); },
        error() {}, log() {}
    }
};
vm.createContext(contexte);
contexte.document = Object.assign(dom.creerDocument(), { addEventListener() {} });
vm.runInContext(fs.readFileSync(CHEMIN_MOTEUR, "utf-8"), contexte, { filename: "rendu.js" });
const validerSchema = contexte.validerSchema;
const rendre = contexte.rendre;

const specTexte = lireNormalise(CHEMIN_SPEC);
const donnee = JSON.parse(lireNormalise(CHEMIN_DONNEE));

function versionMaxDeLaSpec() {
    const m = specTexte.split("\n").slice(0, 3).join("\n")
        .match(/Version du format de schéma : (\d+)/);
    assert.ok(m, "l'en-tête de la spécification n'annonce pas de « Version du format de schéma : N »");
    return parseInt(m[1], 10);
}

/** Toutes les grilles de la donnée fictive : { bloc, champ, indexBloc }. */
function grillesDe(schema) {
    const trouvees = [];
    schema.blocs.forEach(function (bloc, indexBloc) {
        bloc.champs.forEach(function (champ) {
            if (champ.type === "grille") trouvees.push({ bloc, champ, indexBloc });
        });
    });
    return trouvees;
}

/** La règle de dérivation de la spécification (§6) — c'est elle qu'on éprouve. */
function cleCellule(grille, ligne, colonne) {
    return grille.cle + "__" + ligne.cle + "__" + colonne.cle;
}

function cellulesActives(grille) {
    const cellules = [];
    grille.lignes.forEach(function (ligne) {
        const neutres = ligne.neutralisees || [];
        grille.colonnes.forEach(function (colonne) {
            if (neutres.indexOf(colonne.cle) === -1) {
                cellules.push({ cle: cleCellule(grille, ligne, colonne), ligne, colonne });
            }
        });
    });
    return cellules;
}

/** Une grille valide minimale (la grille 1 de la donnée) dans un schéma d'un bloc. */
function schemaUneGrille(modifier) {
    const grille = cloner(grillesDe(donnee)[0].champ);
    const bloc = { cle: "bloc-1", champs: [grille] };
    const schema = { version_schema: versionMaxDeLaSpec(), blocs: [bloc] };
    if (modifier) modifier(grille, bloc, schema);
    return schema;
}

function rendreSchema(schema) {
    const conteneur = contexte.document.createElement("main");
    const resultat = rendre(schema, contexte.document, conteneur);
    return { resultat, conteneur };
}

/* ============================= Outils d'inspection ============================ */

function elementsDe(noeud, predicat, accumule) {
    accumule = accumule || [];
    if (noeud.genre === "texte") return accumule;
    if (predicat(noeud)) accumule.push(noeud);
    (noeud.enfants || []).forEach(function (e) { elementsDe(e, predicat, accumule); });
    return accumule;
}

function parBalise(noeud, balise) {
    return elementsDe(noeud, function (n) { return n.balise === balise; });
}

function parId(noeud, id) {
    const trouves = elementsDe(noeud, function (n) { return n.getAttribute("id") === id; });
    return trouves.length === 1 ? trouves[0] : null;
}

function aClasse(noeud, classe) {
    return (noeud.getAttribute("class") || "").split(/\s+/).indexOf(classe) !== -1;
}

function controlesDe(noeud) {
    return elementsDe(noeud, function (n) { return n.balise === "input"; });
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

function refus(schema) { return validerSchema(schema); }

function exigerRefus(schema, regle, fragments, cadre) {
    const messages = refus(schema);
    const bons = messages.filter(function (m) {
        return m.indexOf("règle " + regle) !== -1 &&
            (fragments || []).every(function (f) { return m.indexOf(f) !== -1; });
    });
    assert.ok(bons.length >= 1,
        cadre + " : un refus « règle " + regle + " »" +
        (fragments && fragments.length ? " nommant " + fragments.join(" + ") : "") +
        " était attendu, trouvé : " + JSON.stringify(messages));
}

/* ============================ 1. Donnée et versions ============================ */

cas("la donnée fictive est une version 2 valide et se rend sans erreur", () => {
    assert.deepStrictEqual(Array.from(refus(donnee)), [], "la donnée fictive doit être valide");
    const { resultat, conteneur } = rendreSchema(donnee);
    assert.strictEqual(resultat.ok, true, "rendre() doit réussir : " + JSON.stringify(resultat.erreurs));
    assert.strictEqual(conteneur.enfants.length, donnee.blocs.length, "un nœud par bloc");
    assert.strictEqual(grillesDe(donnee).length, 3, "la donnée fictive porte trois grilles");
});

cas("la version max de la spécification, celle du moteur et celle de la donnée concordent", () => {
    const max = versionMaxDeLaSpec();
    const connues = vm.runInContext("VERSIONS_CONNUES", contexte);
    assert.strictEqual(Math.max.apply(null, Array.from(connues)), max,
        "la plus haute version connue du moteur (" + Array.from(connues) + ") doit être celle de la spécification (" + max + ")");
    assert.strictEqual(donnee.version_schema, max, "la donnée fictive doit être à la version maximale");
    assert.ok(Array.from(connues).indexOf(1) !== -1, "la version 1 doit rester acceptée");
});

cas("la version maximale de la spécification + 1 est refusée (règle 2), sans rendu", () => {
    const schema = cloner(donnee);
    schema.version_schema = versionMaxDeLaSpec() + 1;
    exigerRefus(schema, 2, [], "version inconnue");
    const { resultat, conteneur } = rendreSchema(schema);
    assert.strictEqual(resultat.ok, false);
    assert.strictEqual(conteneur.enfants.length, 0, "aucun nœud inséré malgré le refus");
});

cas("une grille dans un document de version 1 est refusée, nommée « règle 16 »", () => {
    const schema = cloner(donnee);
    schema.version_schema = 1;
    exigerRefus(schema, 16, ["bloc 1, champ 0"], "grille en version 1");
    // et non plus comme un type inconnu : le numéro de la règle est le contrat
    assert.ok(!refus(schema).some(function (m) { return /règle 7/.test(m); }),
        "la grille en version 1 ne doit pas être signalée comme type inconnu (règle 7)");
    const { resultat, conteneur } = rendreSchema(schema);
    assert.strictEqual(resultat.ok, false);
    assert.strictEqual(conteneur.enfants.length, 0);
});

cas("un type réellement inconnu reste une règle 7 en version 2", () => {
    const schema = schemaUneGrille(function (g) { g.type = "liste"; });
    exigerRefus(schema, 7, ["liste"], "type inconnu");
});

cas("la spécification annonce les règles 15 à 20 et porte un exemple de grille valide", () => {
    for (let n = 15; n <= 20; n += 1) {
        assert.ok(new RegExp("^" + n + "\\. ", "m").test(specTexte),
            "la règle " + n + " est absente de la section « Règles de validation »");
    }
    const motif = /```json\n([\s\S]*?)```/g;
    let m, nbExemples = 0;
    while ((m = motif.exec(specTexte)) !== null) {
        if (m[1].indexOf('"type": "grille"') === -1) continue;
        nbExemples += 1;
        const exemple = JSON.parse(m[1]);
        const schema = { version_schema: versionMaxDeLaSpec(), blocs: [{ cle: "bloc-1", champs: [exemple] }] };
        assert.deepStrictEqual(Array.from(refus(schema)), [],
            "l'exemple de grille de la spécification doit être accepté par le moteur");
        assert.strictEqual(rendreSchema(schema).resultat.ok, true);
    }
    assert.ok(nbExemples >= 1, "la spécification doit porter au moins un exemple JSON de grille");
});

/* ================================ 2. Règle 17 ================================== */

cas("règle 17 : la grille 3, aux bornes (12 colonnes, 20 lignes, groupe vide), est valide", () => {
    const g3 = grillesDe(donnee)[2].champ;
    assert.strictEqual(g3.colonnes.length, 12);
    assert.strictEqual(g3.lignes.length, 20);
    assert.ok(g3.groupes.some(function (g) { return g.libelle === ""; }), "un groupe à libellé vide");
    assert.deepStrictEqual(Array.from(refus({ version_schema: donnee.version_schema, blocs: [{ cle: "bloc-1", champs: [cloner(g3)] }] })), []);
});

cas("règle 17 : libellé de grille et de groupe vides permis, libellé non chaîne refusé", () => {
    assert.deepStrictEqual(Array.from(refus(schemaUneGrille(function (g) { g.libelle = ""; }))), [], "coin vide permis");
    assert.deepStrictEqual(Array.from(refus(schemaUneGrille(function (g) { g.groupes[0].libelle = ""; }))), [], "groupe sans libellé permis");
    exigerRefus(schemaUneGrille(function (g) { g.libelle = 12; }), 17, ["bloc 0, champ 0", "libelle"], "libellé numérique");
    exigerRefus(schemaUneGrille(function (g) { delete g.libelle; }), 17, ["bloc 0, champ 0", "libelle"], "libellé absent");
    exigerRefus(schemaUneGrille(function (g) { g.groupes[1].libelle = null; }), 17, ["groupe 1"], "libellé de groupe nul");
});

const clausesCle = [
    ["cle de grille absente", function (g) { delete g.cle; }, ["« cle »"]],
    ["cle de grille vide", function (g) { g.cle = ""; }, ["« cle »"]],
    ["cle de grille en majuscules", function (g) { g.cle = "Grille-1"; }, ["« cle »"]],
    ["cle de grille accentuée", function (g) { g.cle = "grillé-1"; }, ["« cle »"]],
    ["cle de grille avec soulignement", function (g) { g.cle = "grille_1"; }, ["« cle »"]],
    ["cle de grille avec espace", function (g) { g.cle = "grille 1"; }, ["« cle »"]],
    ["cle de grille avec #", function (g) { g.cle = "grille#1"; }, ["« cle »"]],
    ["cle de grille à tirets doublés", function (g) { g.cle = "grille--1"; }, ["« cle »"]],
    ["cle de grille de 41 caractères", function (g) { g.cle = "a".repeat(41); }, ["« cle »"]],
    ["cle de colonne avec soulignement", function (g) { g.colonnes[1].cle = "colonne_2"; }, ["colonne 1", "« cle »"]],
    ["cle de colonne accentuée", function (g) { g.colonnes[2].cle = "colonné-3"; }, ["colonne 2", "« cle »"]],
    ["cle de colonne absente", function (g) { delete g.colonnes[0].cle; }, ["colonne 0", "« cle »"]],
    ["cle de colonne de 41 caractères", function (g) { g.colonnes[3].cle = "c".repeat(41); }, ["colonne 3", "« cle »"]],
    ["cle de ligne avec espace", function (g) { g.lignes[0].cle = "ligne 1"; }, ["ligne 0", "« cle »"]],
    ["cle de ligne avec soulignement", function (g) { g.lignes[2].cle = "ligne_3"; }, ["ligne 2", "« cle »"]],
    ["cle de ligne en majuscules", function (g) { g.lignes[3].cle = "LIGNE-4"; }, ["ligne 3", "« cle »"]],
    ["cle de colonne dupliquée", function (g) { g.colonnes[1].cle = g.colonnes[0].cle; }, ["colonne 1", "dupliquée"]],
    ["cle de ligne dupliquée", function (g) { g.lignes[1].cle = g.lignes[0].cle; }, ["ligne 1", "dupliquée"]]
];
clausesCle.forEach(function (c) {
    cas("règle 17 : " + c[0] + " refusée", () => {
        exigerRefus(schemaUneGrille(c[1]), 17, ["bloc 0, champ 0"].concat(c[2]), c[0]);
    });
});

const clausesStructure = [
    ["colonnes absentes", function (g) { delete g.colonnes; }, ["colonnes"]],
    ["colonnes vides", function (g) { g.colonnes = []; }, ["colonnes"]],
    ["colonnes non liste", function (g) { g.colonnes = "colonne-1"; }, ["colonnes"]],
    ["13 colonnes", function (g) {
        g.groupes = undefined;
        while (g.colonnes.length < 13) {
            g.colonnes.push({ cle: "colonne-" + (g.colonnes.length + 1), libelle: "Colonne " + (g.colonnes.length + 1), nature: "case" });
        }
    }, ["colonnes", "12"]],
    ["colonne non objet", function (g) { g.colonnes[0] = "colonne-1"; }, ["colonne 0"]],
    ["libellé de colonne vide", function (g) { g.colonnes[2].libelle = ""; }, ["colonne 2", "libelle"]],
    ["libellé de colonne absent", function (g) { delete g.colonnes[2].libelle; }, ["colonne 2", "libelle"]],
    ["nature de colonne inconnue (trois états)", function (g) { g.colonnes[0].nature = "trois-etats"; }, ["colonne 0", "nature"]],
    ["nature de colonne d'un autre type de champ", function (g) { g.colonnes[1].nature = "radio"; }, ["colonne 1", "nature"]],
    ["nature de colonne absente", function (g) { delete g.colonnes[3].nature; }, ["colonne 3", "nature"]],
    ["lignes absentes", function (g) { delete g.lignes; }, ["lignes"]],
    ["lignes vides", function (g) { g.lignes = []; }, ["lignes"]],
    ["lignes non liste", function (g) { g.lignes = {}; }, ["lignes"]],
    ["21 lignes", function (g) {
        while (g.lignes.length < 21) {
            g.lignes.push({ cle: "ligne-" + (g.lignes.length + 1), libelle: "Ligne " + (g.lignes.length + 1) });
        }
    }, ["lignes", "20"]],
    ["ligne non objet", function (g) { g.lignes[1] = null; }, ["ligne 1"]],
    ["libellé de ligne vide", function (g) { g.lignes[0].libelle = ""; }, ["ligne 0", "libelle"]],
    ["libellé de ligne absent", function (g) { delete g.lignes[3].libelle; }, ["ligne 3", "libelle"]],
    ["neutralisees non liste", function (g) { g.lignes[0].neutralisees = "colonne-1"; }, ["ligne 0", "neutralisees"]],
    ["neutralisees avec un doublon", function (g) { g.lignes[0].neutralisees = ["colonne-1", "colonne-1"]; }, ["ligne 0", "neutralisees"]],
    ["neutralisees citant une colonne inexistante", function (g) { g.lignes[0].neutralisees = ["colonne-9"]; }, ["ligne 0", "neutralisees"]],
    ["neutralisees qui retirent toutes les cellules", function (g) {
        g.lignes[1].neutralisees = g.colonnes.map(function (c) { return c.cle; });
    }, ["ligne 1", "neutralisees"]],
    ["groupes vides", function (g) { g.groupes = []; }, ["groupes"]],
    ["groupes non liste", function (g) { g.groupes = "Groupe 1"; }, ["groupes"]],
    ["groupe non objet", function (g) { g.groupes[0] = 2; }, ["groupe 0"]],
    ["étendue de groupe nulle", function (g) { g.groupes[0].etendue = 0; g.groupes[1].etendue = 4; }, ["groupe 0", "etendue"]],
    ["étendue de groupe non entière", function (g) { g.groupes[0].etendue = 1.5; g.groupes[1].etendue = 2.5; }, ["groupe 0", "etendue"]],
    ["étendue de groupe en chaîne", function (g) { g.groupes[0].etendue = "2"; }, ["groupe 0", "etendue"]],
    ["étendue de groupe absente", function (g) { delete g.groupes[0].etendue; }, ["groupe 0", "etendue"]],
    ["somme des étendues trop petite", function (g) { g.groupes[1].etendue = 1; }, ["groupes", "somme"]],
    ["somme des étendues trop grande", function (g) { g.groupes[1].etendue = 3; }, ["groupes", "somme"]]
];
clausesStructure.forEach(function (c) {
    cas("règle 17 : " + c[0] + " refusé(e)", () => {
        const schema = schemaUneGrille(c[1]);
        // `undefined` retire la clé comme le ferait JSON.stringify : le schéma
        // reçu par le moteur vient toujours d'un JSON.
        exigerRefus(cloner(schema), 17, ["bloc 0, champ 0"].concat(c[2]), c[0]);
        const { resultat, conteneur } = rendreSchema(cloner(schema));
        assert.strictEqual(resultat.ok, false, c[0] + " : rendre() doit refuser");
        assert.strictEqual(conteneur.enfants.length, 0, c[0] + " : rien ne doit être inséré");
    });
});

cas("règle 17 : un attribut inconnu dans une colonne, une ligne ou un groupe est averti, pas refusé", () => {
    const schema = schemaUneGrille(function (g) {
        g.colonnes[0].couleur_a = "x";
        g.lignes[0].couleur_b = "y";
        g.groupes[0].couleur_c = "z";
    });
    avertissements.length = 0;
    assert.deepStrictEqual(Array.from(refus(schema)), [], "un attribut inconnu ne refuse rien");
    ["couleur_a", "couleur_b", "couleur_c"].forEach(function (nom) {
        assert.ok(avertissements.some(function (a) { return a.indexOf(nom) !== -1; }),
            "l'attribut inconnu « " + nom + " » doit être averti en console (trouvé : " + JSON.stringify(avertissements) + ")");
    });
});

cas("règle 17 : un attribut connu ne déclenche aucun avertissement", () => {
    avertissements.length = 0;
    assert.deepStrictEqual(Array.from(refus(donnee)), []);
    assert.deepStrictEqual(avertissements, [], "la donnée fictive ne doit provoquer aucun avertissement");
});

/* ================================ 3. Règle 18 ================================== */

cas("règle 18 : une clé de cellule égale à la clé d'un champ qui la précède est refusée", () => {
    const g = grillesDe(donnee)[0].champ;
    const cle = cellulesActives(g)[0].cle;
    const schema = schemaUneGrille();
    schema.blocs.unshift({ cle: "bloc-0", champs: [{ cle: cle, type: "texte", libelle: "Texte 0" }] });
    exigerRefus(schema, 18, ["bloc 1, champ 0"], "cellule après un champ");
});

cas("règle 18 : un champ qui reprend, après la grille, la clé d'une cellule est refusé", () => {
    const g = grillesDe(donnee)[0].champ;
    const cle = cellulesActives(g)[0].cle;
    const schema = schemaUneGrille();
    schema.blocs.push({ cle: "bloc-2", champs: [{ cle: cle, type: "texte", libelle: "Texte 2" }] });
    const messages = refus(schema);
    assert.ok(messages.some(function (m) { return /règle (8|18)/.test(m) && m.indexOf(cle) !== -1; }),
        "la clé de la cellule, reprise par un champ postérieur, doit être refusée : " + JSON.stringify(messages));
});

cas("règle 18 : une clé de cellule égale à la clé d'un bloc est refusée, avant comme après la grille", () => {
    const g = grillesDe(donnee)[0].champ;
    const cle = cellulesActives(g)[0].cle;
    [true, false].forEach(function (avant) {
        const schema = schemaUneGrille();
        const autre = { cle: cle, champs: [{ cle: "texte-2", type: "texte", libelle: "Texte 2" }] };
        if (avant) schema.blocs.unshift(autre); else schema.blocs.push(autre);
        exigerRefus(schema, 18, [cle], "cellule égale à un bloc (" + (avant ? "avant" : "après") + ")");
    });
});

cas("règle 18 : une cellule neutralisée n'enregistre aucune clé (un autre champ peut la reprendre)", () => {
    const g = cloner(grillesDe(donnee)[0].champ);
    const neutralisee = cleCellule(g, g.lignes[0], g.colonnes[1]); // ligne-1 / colonne-2
    assert.deepStrictEqual(Array.from(g.lignes[0].neutralisees), ["colonne-2"]);
    const schema = schemaUneGrille();
    schema.blocs.push({ cle: "bloc-2", champs: [{ cle: neutralisee, type: "texte", libelle: "Texte 2" }] });
    assert.deepStrictEqual(Array.from(refus(schema)), [], "la clé d'une cellule neutralisée n'est émise nulle part");
});

cas("règle 8 : la clé de la grille elle-même est unique dans le document et jamais réservée", () => {
    const schema = schemaUneGrille();
    schema.blocs.push({ cle: "bloc-2", champs: [{ cle: "grille-1", type: "texte", libelle: "Texte 2" }] });
    exigerRefus(schema, 8, ["grille-1"], "champ qui reprend la clé de la grille");
    const reservee = schemaUneGrille(function (g) { g.cle = "logo"; });
    assert.ok(refus(reservee).some(function (m) { return /réservée à la coquille/.test(m) && /logo/.test(m); }),
        "la clé de grille « logo » est réservée à la coquille");
    const autreGrille = schemaUneGrille();
    autreGrille.blocs.push({ cle: "bloc-2", champs: [cloner(autreGrille.blocs[0].champs[0])] });
    exigerRefus(autreGrille, 8, ["grille-1"], "deux grilles de même clé");
});

/* ============================ 4. Règles 19 et 20 =============================== */

[["defaut", "x"], ["indication", "x"], ["apparence", "titre_avant"]].forEach(function (c) {
    cas("règle 19 : « " + c[0] + " » est interdit sur une grille", () => {
        exigerRefus(schemaUneGrille(function (g) { g[c[0]] = c[1]; }), 19, ["bloc 0, champ 0", c[0]], c[0]);
    });
});

[["titre", "Bloc 1"], ["titre_cle", "bloc-1"], ["titre_apparence", "h3"],
 ["disposition", "en-ligne"], ["balise", "section"]].forEach(function (c) {
    cas("règle 20 : « " + c[0] + " » est interdit sur le bloc d'une grille", () => {
        exigerRefus(schemaUneGrille(function (g, bloc) { bloc[c[0]] = c[1]; }), 20, ["bloc 0", c[0]], c[0]);
        const { resultat, conteneur } = rendreSchema(schemaUneGrille(function (g, bloc) { bloc[c[0]] = c[1]; }));
        assert.strictEqual(resultat.ok, false);
        assert.strictEqual(conteneur.enfants.length, 0);
    });
});

cas("règle 20 : le bloc d'une grille ne porte qu'elle (grille après un champ, avant un champ, deux grilles)", () => {
    const autreChamp = { cle: "texte-9", type: "texte", libelle: "Texte 9" };
    exigerRefus(schemaUneGrille(function (g, bloc) { bloc.champs.push(autreChamp); }), 20, ["bloc 0"], "champ après la grille");
    exigerRefus(schemaUneGrille(function (g, bloc) { bloc.champs.unshift(autreChamp); }), 20, ["bloc 0"], "champ avant la grille");
    exigerRefus(schemaUneGrille(function (g, bloc) {
        const seconde = cloner(g);
        seconde.cle = "grille-9";
        bloc.champs.push(seconde);
    }), 20, ["bloc 0"], "deux grilles dans un bloc");
});

cas("règle 15 (consignée) : une balise de bloc hors div/section est refusée", () => {
    const schema = cloner(donnee);
    schema.blocs[0].balise = "article";
    exigerRefus(schema, 15, ["bloc d'index 0"], "balise inconnue");
});

/* ================================ 5. Rendu DOM ================================= */

function rendreDonnee() {
    const { resultat, conteneur } = rendreSchema(donnee);
    assert.strictEqual(resultat.ok, true);
    return conteneur;
}

function tableDeGrille(conteneur, indexBloc) {
    return conteneur.enfants[indexBloc];
}

cas("DOM : la table est le bloc, avec ses classes et son id", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).forEach(function (g) {
        const table = tableDeGrille(conteneur, g.indexBloc);
        assert.strictEqual(table.balise, "table", "la grille est une <table>");
        assert.strictEqual(table.getAttribute("id"), g.bloc.cle, "id de la table = cle du bloc");
        assert.ok(aClasse(table, "bloc") && aClasse(table, "grille"), "classes « bloc » et « grille »");
        assert.strictEqual(parBalise(table, "thead").length, 1);
        assert.strictEqual(parBalise(table, "tbody").length, 1);
    });
});

cas("DOM : en-tête avec groupes (rowspan sur le coin, colspan sur les groupes, texte exact)", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).filter(function (g) { return g.champ.groupes; }).forEach(function (g) {
        const champ = g.champ;
        const thead = parBalise(tableDeGrille(conteneur, g.indexBloc), "thead")[0];
        const rangees = thead.enfants;
        assert.strictEqual(rangees.length, 2, "deux rangées d'en-tête avec groupes");
        const [haut, bas] = rangees;
        assert.strictEqual(haut.balise, "tr");
        const coin = haut.enfants[0];
        assert.strictEqual(coin.balise, "th");
        assert.ok(aClasse(coin, "titre_section"), "le coin porte « titre_section »");
        assert.strictEqual(coin.getAttribute("rowspan"), "2");
        assert.strictEqual(coin.textContent, champ.libelle, "libellé de grille exact, sans ponctuation ajoutée");
        const groupesTh = haut.enfants.slice(1);
        assert.strictEqual(groupesTh.length, champ.groupes.length);
        groupesTh.forEach(function (th, i) {
            assert.strictEqual(th.balise, "th");
            assert.strictEqual(th.getAttribute("colspan"), String(champ.groupes[i].etendue));
            assert.strictEqual(th.textContent, champ.groupes[i].libelle, "libellé de groupe exact");
        });
        assert.strictEqual(bas.enfants.length, champ.colonnes.length, "une cellule d'en-tête par colonne");
        bas.enfants.forEach(function (th, i) {
            assert.strictEqual(th.balise, "th");
            assert.strictEqual(th.textContent, champ.colonnes[i].libelle, "libellé de colonne exact");
        });
    });
});

cas("DOM : en-tête sans groupes (une seule rangée, pas de rowspan)", () => {
    const conteneur = rendreDonnee();
    const sansGroupes = grillesDe(donnee).filter(function (g) { return !g.champ.groupes; });
    assert.ok(sansGroupes.length >= 1, "la donnée fictive doit porter une grille sans groupes");
    sansGroupes.forEach(function (g) {
        const thead = parBalise(tableDeGrille(conteneur, g.indexBloc), "thead")[0];
        assert.strictEqual(thead.enfants.length, 1, "une seule rangée d'en-tête");
        const ths = thead.enfants[0].enfants;
        assert.strictEqual(ths.length, 1 + g.champ.colonnes.length);
        assert.ok(aClasse(ths[0], "titre_section"));
        assert.strictEqual(ths[0].getAttribute("rowspan"), null);
        assert.strictEqual(ths[0].textContent, g.champ.libelle);
        ths.slice(1).forEach(function (th, i) { assert.strictEqual(th.textContent, g.champ.colonnes[i].libelle); });
        assert.strictEqual(parBalise(thead, "th").filter(function (th) { return th.getAttribute("colspan") !== null; }).length, 0);
    });
});

cas("DOM : la somme des colspan égale le nombre de colonnes, pour chaque grille à groupes", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).filter(function (g) { return g.champ.groupes; }).forEach(function (g) {
        const haut = parBalise(tableDeGrille(conteneur, g.indexBloc), "thead")[0].enfants[0];
        const somme = haut.enfants.slice(1).reduce(function (s, th) { return s + parseInt(th.getAttribute("colspan"), 10); }, 0);
        assert.strictEqual(somme, g.champ.colonnes.length);
    });
});

cas("DOM : une ligne par ligne du schéma, intitulé en <td>, libellé exact", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).forEach(function (g) {
        const lignes = parBalise(tableDeGrille(conteneur, g.indexBloc), "tbody")[0].enfants;
        assert.strictEqual(lignes.length, g.champ.lignes.length);
        lignes.forEach(function (tr, i) {
            assert.strictEqual(tr.balise, "tr");
            assert.strictEqual(tr.enfants.length, 1 + g.champ.colonnes.length, "intitulé + une cellule par colonne");
            assert.strictEqual(tr.enfants[0].balise, "td", "l'intitulé de ligne est un <td> (un <th> de corps serait blanc sur blanc)");
            assert.strictEqual(tr.enfants[0].textContent, g.champ.lignes[i].libelle);
            tr.enfants.slice(1).forEach(function (td) { assert.strictEqual(td.balise, "td"); });
        });
    });
});

cas("DOM : les id des contrôles sont exactement les clés dérivées de la donnée, sans doublon", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).forEach(function (g) {
        const attendues = cellulesActives(g.champ).map(function (c) { return c.cle; });
        const obtenues = controlesDe(tableDeGrille(conteneur, g.indexBloc)).map(function (n) { return n.getAttribute("id"); });
        assert.deepStrictEqual(obtenues.slice().sort(), attendues.slice().sort(), "id rendus = clés dérivées (" + g.champ.cle + ")");
        assert.strictEqual(new Set(obtenues).size, obtenues.length, "aucun id en double");
    });
    // L'ancre littérale de la spécification (§6) : grille, ligne, colonne séparées par « __ ».
    const g1 = tableDeGrille(conteneur, 1);
    assert.notStrictEqual(parId(g1, "grille-1__ligne-2__colonne-4"), null,
        "l'id littéral « grille-1__ligne-2__colonne-4 » doit exister");
    // Tous les id du document rendu sont uniques, grilles et autres champs confondus.
    const tous = elementsDe(conteneur, function (n) { return n.getAttribute("id") !== null; })
        .map(function (n) { return n.getAttribute("id"); });
    assert.strictEqual(new Set(tous).size, tous.length, "aucun id en double dans tout le document rendu");
});

cas("DOM : cellules neutralisées vides et sans contrôle ; nombre de contrôles = lignes × colonnes − neutralisées", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).forEach(function (g) {
        const table = tableDeGrille(conteneur, g.indexBloc);
        const nbNeutralisees = g.champ.lignes.reduce(function (s, l) { return s + (l.neutralisees || []).length; }, 0);
        assert.strictEqual(controlesDe(table).length,
            g.champ.lignes.length * g.champ.colonnes.length - nbNeutralisees,
            "nombre de contrôles de " + g.champ.cle);
        const neutres = elementsDe(table, function (n) { return aClasse(n, "grille-neutralisee"); });
        assert.strictEqual(neutres.length, nbNeutralisees, "autant de cellules « grille-neutralisee » que de neutralisées");
        neutres.forEach(function (td) {
            assert.strictEqual(td.balise, "td");
            assert.strictEqual(td.enfants.length, 0, "une cellule neutralisée n'a aucun enfant : ni contrôle, ni texte");
        });
        // La neutralisation tombe sur la bonne cellule, pas seulement au bon nombre.
        parBalise(table, "tbody")[0].enfants.forEach(function (tr, i) {
            const ligne = g.champ.lignes[i];
            g.champ.colonnes.forEach(function (colonne, j) {
                const td = tr.enfants[1 + j];
                const neutre = (ligne.neutralisees || []).indexOf(colonne.cle) !== -1;
                assert.strictEqual(aClasse(td, "grille-neutralisee"), neutre, ligne.cle + " / " + colonne.cle);
                assert.strictEqual(controlesDe(td).length, neutre ? 0 : 1);
            });
        });
    });
    assert.ok(grillesDe(donnee).some(function (g) {
        return g.champ.lignes.filter(function (l) { return (l.neutralisees || []).length > 0; }).length >= 2;
    }), "la donnée fictive neutralise des cellules sur au moins deux lignes");
});

cas("DOM : natures de cellule — case, ou texte court de 8 caractères sans suggestion ; aucun name", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).forEach(function (g) {
        const table = tableDeGrille(conteneur, g.indexBloc);
        cellulesActives(g.champ).forEach(function (c) {
            const entree = parId(table, c.cle);
            assert.notStrictEqual(entree, null, c.cle + " : contrôle introuvable");
            assert.strictEqual(entree.balise, "input");
            assert.strictEqual(entree.getAttribute("name"), null, c.cle + " : un contrôle de grille ne porte aucun name");
            if (c.colonne.nature === "case") {
                assert.strictEqual(entree.getAttribute("type"), "checkbox", c.cle);
                assert.strictEqual(entree.getAttribute("maxlength"), null);
            } else {
                assert.strictEqual(entree.getAttribute("type"), "text", c.cle);
                assert.strictEqual(entree.getAttribute("maxlength"), "8", c.cle + " : maxlength=8 (le PDF tronquerait au-delà)");
                assert.strictEqual(entree.getAttribute("autocomplete"), "off", c.cle + " : autocomplete=off");
                assert.ok(aClasse(entree, "grille-texte"), c.cle + " : classe grille-texte");
            }
        });
    });
    const natures = new Set();
    grillesDe(donnee).forEach(function (g) { g.champ.colonnes.forEach(function (c) { natures.add(c.nature); }); });
    assert.deepStrictEqual(Array.from(natures).sort(), ["case", "texte-court"], "la donnée fictive emploie les deux natures");
});

cas("DOM : aucun texte composé par le moteur (pas de ponctuation, d'aria-label ni de title ajoutés)", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).forEach(function (g) {
        const table = tableDeGrille(conteneur, g.indexBloc);
        const textes = [g.champ.libelle]
            .concat((g.champ.groupes || []).map(function (x) { return x.libelle; }))
            .concat(g.champ.colonnes.map(function (x) { return x.libelle; }))
            .concat(g.champ.lignes.map(function (x) { return x.libelle; }));
        const rendus = parBalise(table, "th").concat(elementsDe(table, function (n) {
            return n.balise === "td" && n.enfants.length === 1 && n.enfants[0].genre === "texte";
        })).map(function (n) { return n.textContent; });
        assert.deepStrictEqual(rendus.slice().sort(), textes.slice().sort(), "les textes rendus sont ceux du schéma, à l'identique");
        elementsDe(table, function () { return true; }).forEach(function (n) {
            ["aria-label", "title", "for"].forEach(function (a) {
                assert.strictEqual(n.getAttribute(a), null, "attribut « " + a + " » inventé par le moteur sur <" + n.balise + ">");
            });
        });
    });
});

cas("DOM : un libellé de schéma ne devient jamais du balisage", () => {
    const piege = '<img src=x onerror="alert(1)">&amp;';
    const schema = schemaUneGrille(function (g) {
        g.libelle = piege;
        g.groupes[0].libelle = piege;
        g.colonnes[0].libelle = piege;
        g.lignes[0].libelle = piege;
    });
    const { resultat, conteneur } = rendreSchema(schema);
    assert.strictEqual(resultat.ok, true);
    assert.strictEqual(parBalise(conteneur, "img").length, 0, "aucun élément <img> ne doit naître d'un libellé");
    const ths = parBalise(conteneur, "th").filter(function (t) { return t.textContent === piege; });
    assert.strictEqual(ths.length, 3, "le coin, le groupe et la colonne portent le texte brut, tel quel");
});

cas("DOM : les valeurs de rowspan et colspan sont des entiers écrits par le moteur", () => {
    const conteneur = rendreDonnee();
    grillesDe(donnee).forEach(function (g) {
        parBalise(tableDeGrille(conteneur, g.indexBloc), "th").forEach(function (th) {
            ["rowspan", "colspan"].forEach(function (a) {
                const v = th.getAttribute(a);
                if (v !== null) assert.ok(/^[1-9][0-9]*$/.test(v), a + " doit être un entier décimal, trouvé « " + v + " »");
            });
        });
    });
});

/* ============================ 6. Brouillon (script.js) ========================== */

function extraireFonction(source, nom) {
    const debut = source.indexOf("function " + nom + "(");
    assert.ok(debut !== -1, nom + "() introuvable dans " + CHEMIN_SCRIPT);
    let i = source.indexOf("{", debut), profondeur = 0;
    for (; i < source.length; i += 1) {
        if (source[i] === "{") profondeur += 1;
        if (source[i] === "}" && --profondeur === 0) break;
    }
    return source.slice(debut, i + 1);
}

/** Un contrôle du double de brouillon, adossé au nœud que le moteur a rendu. */
function controleDeBrouillon(noeud) {
    const type = noeud.getAttribute("type");
    return {
        noeud: noeud,
        id: noeud.getAttribute("id") || "",
        name: noeud.getAttribute("name") || "",
        value: "",
        type: type,
        checked: false,
        style: {},
        classList: { contains() { return false; } }
    };
}

cas("brouillon : collecterBilan/restaurerBilan de script.js font l'aller-retour des cellules", () => {
    const conteneur = rendreDonnee();
    const controles = elementsDe(conteneur, function (n) { return n.balise === "input" || n.balise === "textarea"; })
        .map(controleDeBrouillon);

    const sandbox = {
        zonesDessin: [],
        document: { querySelectorAll: function () { return controles; } },
        Date: Date
    };
    vm.createContext(sandbox);
    const source = fs.readFileSync(CHEMIN_SCRIPT, "utf-8");
    vm.runInContext(
        ["cleChamp", "champsDuFormulaire", "collecterBilan", "restaurerBilan"]
            .map(function (n) { return extraireFonction(source, n); }).join("\n")
        + "\nthis.collecterBilan = collecterBilan; this.restaurerBilan = restaurerBilan;",
        sandbox
    );

    const g1 = grillesDe(donnee)[0].champ, g2 = grillesDe(donnee)[1].champ;
    const parCle = {};
    controles.forEach(function (c) { parCle[c.id] = c; });

    // Deux cases sur une même ligne de la grille 1, un texte de huit caractères dans la grille 2.
    const casesCochees = cellulesActives(g1).filter(function (c) { return c.ligne.cle === g1.lignes[1].cle; }).slice(0, 2);
    assert.strictEqual(casesCochees.length, 2, "deux cases sur une même ligne");
    casesCochees.forEach(function (c) { parCle[c.cle].checked = true; });
    const texte = cellulesActives(g2).filter(function (c) { return c.colonne.nature === "texte-court"; })[0];
    parCle[texte.cle].value = "WWWWWWWW";

    const bilan = sandbox.collecterBilan();
    casesCochees.forEach(function (c) {
        assert.strictEqual(bilan.coches[c.cle], true, c.cle + " : coche attendue dans « coches »");
        assert.ok(!(c.cle in bilan.valeurs), c.cle + " : une case ne doit pas figurer dans « valeurs »");
    });
    assert.strictEqual(bilan.valeurs[texte.cle], "WWWWWWWW", texte.cle + " : valeur attendue dans « valeurs »");
    assert.ok(!(texte.cle in bilan.coches), texte.cle + " : un texte ne doit pas figurer dans « coches »");
    grillesDe(donnee).forEach(function (g) {
        cellulesActives(g.champ).forEach(function (c) {
            const dansCoches = c.cle in bilan.coches, dansValeurs = c.cle in bilan.valeurs;
            assert.strictEqual(dansCoches, c.colonne.nature === "case", c.cle + " : « coches » ssi nature case");
            assert.strictEqual(dansValeurs, c.colonne.nature === "texte-court", c.cle + " : « valeurs » ssi nature texte-court");
        });
    });

    // Aller-retour : tout est remis à zéro, puis restauré depuis le brouillon sérialisé.
    const copie = JSON.parse(JSON.stringify(bilan));
    controles.forEach(function (c) { c.checked = false; c.value = ""; });
    sandbox.restaurerBilan(copie);
    casesCochees.forEach(function (c) { assert.strictEqual(parCle[c.cle].checked, true, c.cle + " : coche restaurée"); });
    assert.strictEqual(parCle[texte.cle].value, "WWWWWWWW", "texte restauré");
    const autres = controles.filter(function (c) {
        return !casesCochees.some(function (x) { return x.cle === c.id; }) && c.id !== texte.cle;
    });
    autres.forEach(function (c) { assert.ok(!c.checked && c.value === "", c.id + " : aucune autre valeur ne doit apparaître"); });
});

cas("brouillon : réordonner lignes et colonnes ne déplace aucune clé", () => {
    const permute = cloner(donnee);
    const g = grillesDe(permute)[0].champ;
    g.lignes.reverse();
    g.colonnes.reverse();
    g.groupes = [{ libelle: "Groupe 1", etendue: 4 }];
    const avant = new Set(cellulesActives(grillesDe(donnee)[0].champ).map(function (c) { return c.cle; }));
    const apres = new Set(cellulesActives(g).map(function (c) { return c.cle; }));
    assert.deepStrictEqual(Array.from(apres).sort(), Array.from(avant).sort());
    const { resultat, conteneur } = rendreSchema(permute);
    assert.strictEqual(resultat.ok, true, JSON.stringify(resultat.erreurs));
    const ids = controlesDe(tableDeGrille(conteneur, 1)).map(function (n) { return n.getAttribute("id"); }).sort();
    assert.deepStrictEqual(ids, Array.from(avant).sort(), "mêmes id après permutation");
});

/* ======================== 7. Version 1 : rendu à l'identique ===================== */

cas("v1 : le rendu de formulaire/schema.json est identique à l'instantané du commit 1ec796c", () => {
    const attendu = lireNormalise(CHEMIN_INSTANTANE);
    assert.ok(attendu.length > 1000, "l'instantané de référence est vide ou tronqué");
    const obtenu = serialiserRendu(CHEMIN_MOTEUR, CHEMIN_SCHEMA_PROD);
    if (obtenu !== attendu) {
        const a = attendu.split("\n"), o = obtenu.split("\n");
        let i = 0;
        while (i < a.length && i < o.length && a[i] === o[i]) i += 1;
        assert.fail("le rendu de la version 1 a changé, première divergence à la ligne " + (i + 1)
            + " : attendu « " + (a[i] || "").trim() + " », obtenu « " + (o[i] || "").trim() + " »");
    }
});

cas("v1 : le schéma de production reste en version 1 et sans grille", () => {
    const prod = JSON.parse(lireNormalise(CHEMIN_SCHEMA_PROD));
    assert.strictEqual(prod.version_schema, 1);
    assert.strictEqual(grillesDe(prod).length, 0);
    assert.deepStrictEqual(Array.from(refus(prod)), []);
});

console.log("\n" + nbCas + " cas joués, " + echecs.length + " en échec.");
if (echecs.length > 0) {
    console.log("Échecs : " + echecs.join(" ; "));
    process.exit(1);
}
console.log("Tout est vert.");
