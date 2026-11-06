/*
 * Bibliothèque de blocs et templates de départ (contrat C1-T5) : `blocs/`,
 * `templates/` et `outils/composer-schema.js`.
 *
 * Neuf groupes, chacun un garde-fou à éprouver par mutation volontaire
 * (docs/audits/C1-T5-mises-en-echec.md) :
 *
 *   B1 — blocs/ : que des `*.json` réels (jamais un lien) et `LISEZMOI.md` ;
 *        chaque fragment a un nom conforme, des clés fermées dans l'ordre, une
 *        forme canonique ;
 *   B2 — templates/ : idem pour les recettes ; leurs fragments existent, sans
 *        doublon, sans chemin ;
 *   B3 — chaque template se compose sans refus ni avertissement ET se rend par
 *        le vrai moteur (chargé ici indépendamment du script) ;
 *   B4 — la composition de `podologue-complet` redonne à l'octet
 *        `clients/cabinet-01/schema.json` (D9 : pas d'assouplissement en silence) ;
 *   B5 — un bloc de fragment dont la clé est celle d'un bloc du pilote lui est
 *        identique (les clés de brouillon sont gelées) ; aucun bloc dans deux
 *        fragments ;
 *   B6 — aucune grille dans un fragment ; chaque template en version 1 ;
 *   B7 — (tests/test_paquet.py) ni blocs/ ni templates/ dans l'archive ;
 *   B8 — la ligne de commande : sortie, refus d'écraser, refus sous
 *        formulaire/, avertissement du moteur = refus, nom de fragment sans chemin ;
 *   B9 — chaque image des fragments existe sous formulaire/.
 *
 * Les listes se DÉRIVENT du disque (`readdirSync`) et du pilote, jamais d'une
 * liste écrite à la main. Message d'échec : une clé, un nom de fragment, un
 * chemin d'image ou une position, jamais le texte d'un libellé.
 *
 * Aucune dépendance. Le moteur est chargé ici en `vm` (patron de
 * tests/test_schema_client.js), à part de celui que charge `composer-schema.js`.
 *
 *     node tests/test_blocs.js
 */

const fs = require("fs");
const os = require("os");
const path = require("path");
const vm = require("vm");
const crypto = require("crypto");
const assert = require("assert");
const { spawnSync } = require("child_process");

const dom = require("./outils/dom-minimal.js");

const RACINE = path.join(__dirname, "..");
const DOSSIER_BLOCS = path.join(RACINE, "blocs");
const DOSSIER_TEMPLATES = path.join(RACINE, "templates");
const DOSSIER_FORMULAIRE = path.join(RACINE, "formulaire");
const CHEMIN_PILOTE = path.join(RACINE, "clients", "cabinet-01", "schema.json");
const CHEMIN_MOTEUR = path.join(DOSSIER_FORMULAIRE, "moteur", "rendu.js");
const CHEMIN_SCRIPT = path.join(RACINE, "outils", "composer-schema.js");
const TEMPLATE_COMPLET = path.join(DOSSIER_TEMPLATES, "podologue-complet.json");
const TEMPLATE_COURT = path.join(DOSSIER_TEMPLATES, "podologue-court.json");

const MOTIF_NOM = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const CLES_FRAGMENT = ["version_fragment", "description", "blocs"];
const CLES_RECETTE = ["version_recette", "description", "version_schema", "fragments"];

const composeur = require(CHEMIN_SCRIPT);

/* ================================= Lectures ================================= */

function canonique(objet) {
    return JSON.stringify(objet, null, 2) + "\n";
}

function sha256(octets) {
    return crypto.createHash("sha256").update(octets).digest("hex");
}

/** Les entrées d'un dossier, lues sur le disque (`.DS_Store` ne compte pas). */
function entrees(dossier) {
    return fs.readdirSync(dossier, { withFileTypes: true })
        .filter(function (e) { return e.name !== ".DS_Store"; })
        .sort(function (a, b) { return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0); });
}

/** Les noms (sans `.json`) des fichiers JSON ordinaires d'un dossier. */
function nomsJson(dossier) {
    return entrees(dossier)
        .filter(function (e) { return e.isFile() && /\.json$/.test(e.name); })
        .map(function (e) { return e.name.replace(/\.json$/, ""); });
}

function lireObjet(chemin) {
    return JSON.parse(fs.readFileSync(chemin, "utf8"));
}

/** Le moteur de rendu, chargé comme dans tests/test_schema_client.js, avec un `console` qui collecte. */
function chargerMoteur() {
    const avertissements = [];
    const contexte = {
        console: {
            warn: function () { avertissements.push(Array.prototype.join.call(arguments, " ")); },
            log: function () {}, error: function () {}
        }
    };
    vm.createContext(contexte);
    contexte.document = Object.assign(dom.creerDocument(), { addEventListener() {} });
    vm.runInContext(fs.readFileSync(CHEMIN_MOTEUR, "utf8"), contexte, { filename: "rendu.js" });
    assert.strictEqual(typeof contexte.validerSchema, "function", "validerSchema doit être exportée par rendu.js");
    assert.strictEqual(typeof contexte.rendre, "function", "rendre doit être exportée par rendu.js");
    return { moteur: contexte, avertissements: avertissements };
}

/** Le chemin du premier écart entre deux valeurs JSON, sans en citer aucune valeur. */
function premierEcart(a, b, chemin) {
    if (a === b) return null;
    if (typeof a !== "object" || typeof b !== "object" || a === null || b === null || Array.isArray(a) !== Array.isArray(b)) {
        return chemin;
    }
    const cles = Array.from(new Set(Object.keys(a).concat(Object.keys(b))));
    for (let i = 0; i < cles.length; i += 1) {
        const ecart = premierEcart(a[cles[i]], b[cles[i]], chemin + (Array.isArray(a) ? "[" + cles[i] + "]" : "." + cles[i]));
        if (ecart !== null) return ecart;
    }
    return null;
}

/** Tous les blocs de tous les fragments : `{ fragment, bloc, index }`. */
function blocsDesFragments() {
    const liste = [];
    nomsJson(DOSSIER_BLOCS).forEach(function (nom) {
        lireObjet(path.join(DOSSIER_BLOCS, nom + ".json")).blocs.forEach(function (bloc, index) {
            liste.push({ fragment: nom, bloc: bloc, index: index });
        });
    });
    return liste;
}

function champsDe(bloc) {
    return Array.isArray(bloc.champs) ? bloc.champs : [];
}

/* ================================== Cadre =================================== */

let nbCas = 0;
let nbSautes = 0;
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

function saute(nom, raison) {
    nbSautes += 1;
    console.log("SAUTÉ - " + nom + " (" + raison + ")");
}

/* ============================ B1 — blocs/ (fragments) ============================ */

let fragments = [];
cas("B1 : blocs/ existe et contient au moins un fragment", () => {
    assert.ok(fs.existsSync(DOSSIER_BLOCS) && fs.statSync(DOSSIER_BLOCS).isDirectory(), "le dossier blocs/ est absent");
    fragments = nomsJson(DOSSIER_BLOCS);
    assert.ok(fragments.length >= 1, "blocs/ ne contient aucun fragment : un test vert à vide ne garderait rien");
});

cas("B1 : rien dans blocs/ hors LISEZMOI.md et des fichiers *.json réels (ni lien, ni autre fichier)", () => {
    assert.ok(fragments.length >= 1, "aucun fragment à contrôler (voir le cas précédent)");
    const intrus = entrees(DOSSIER_BLOCS).filter(function (e) {
        const fragment = e.isFile() && /\.json$/.test(e.name);
        const lisezmoi = e.isFile() && e.name === "LISEZMOI.md";
        return !fragment && !lisezmoi;
    }).map(function (e) { return e.name; });
    assert.deepStrictEqual(intrus, [],
        "entrée(s) de blocs/ qui ne sont ni LISEZMOI.md ni un *.json ordinaire (lien symbolique, dossier, autre fichier) : " +
        intrus.join(", "));
});

cas("B1 : chaque fragment a un nom conforme, des clés fermées dans l'ordre, une description, des blocs, la forme canonique", () => {
    assert.ok(fragments.length >= 1, "aucun fragment à contrôler (voir le premier cas B1)");
    const fautes = [];
    fragments.forEach(function (nom) {
        const brut = fs.readFileSync(path.join(DOSSIER_BLOCS, nom + ".json"), "utf8");
        let objet;
        try {
            objet = JSON.parse(brut);
        } catch (erreur) {
            fautes.push(nom + " : n'est pas du JSON");
            return;
        }
        if (!MOTIF_NOM.test(nom)) fautes.push(nom + " : nom non conforme à " + MOTIF_NOM);
        if (objet === null || typeof objet !== "object" || Array.isArray(objet)) {
            fautes.push(nom + " : la racine n'est pas un objet");
            return;
        }
        if (JSON.stringify(Object.keys(objet)) !== JSON.stringify(CLES_FRAGMENT)) {
            fautes.push(nom + " : clés « " + Object.keys(objet).join(", ") + " » au lieu de « " + CLES_FRAGMENT.join(", ") + " »");
        }
        if (objet.version_fragment !== 1) fautes.push(nom + " : version_fragment doit valoir 1");
        if (typeof objet.description !== "string" || objet.description.trim() === "") {
            fautes.push(nom + " : description vide ou absente");
        }
        if (!Array.isArray(objet.blocs) || objet.blocs.length === 0) fautes.push(nom + " : blocs vide ou absent");
        if (brut !== canonique(objet)) {
            fautes.push(nom + " : pas sous forme canonique (JSON.stringify(objet, null, 2) + LF)");
        }
    });
    assert.deepStrictEqual(fautes, [], "fragment(s) fautif(s) :\n" + fautes.join("\n"));
});

/* ============================ B2 — templates/ (recettes) ============================ */

let recettes = [];
cas("B2 : templates/ existe et contient au moins une recette", () => {
    assert.ok(fs.existsSync(DOSSIER_TEMPLATES) && fs.statSync(DOSSIER_TEMPLATES).isDirectory(), "le dossier templates/ est absent");
    recettes = nomsJson(DOSSIER_TEMPLATES);
    assert.ok(recettes.length >= 1, "templates/ ne contient aucune recette : un test vert à vide ne garderait rien");
});

cas("B2 : rien dans templates/ hors LISEZMOI.md et des fichiers *.json réels", () => {
    assert.ok(recettes.length >= 1, "aucune recette à contrôler (voir le cas précédent)");
    const intrus = entrees(DOSSIER_TEMPLATES).filter(function (e) {
        const recette = e.isFile() && /\.json$/.test(e.name);
        const lisezmoi = e.isFile() && e.name === "LISEZMOI.md";
        return !recette && !lisezmoi;
    }).map(function (e) { return e.name; });
    assert.deepStrictEqual(intrus, [],
        "entrée(s) de templates/ qui ne sont ni LISEZMOI.md ni un *.json ordinaire : " + intrus.join(", "));
});

cas("B2 : chaque recette a des clés fermées, des fragments existants, sans doublon, sans chemin, la forme canonique", () => {
    assert.ok(recettes.length >= 1, "aucune recette à contrôler (voir le premier cas B2)");
    const disponibles = new Set(fs.existsSync(DOSSIER_BLOCS) ? nomsJson(DOSSIER_BLOCS) : []);
    const fautes = [];
    recettes.forEach(function (nom) {
        const brut = fs.readFileSync(path.join(DOSSIER_TEMPLATES, nom + ".json"), "utf8");
        let objet;
        try {
            objet = JSON.parse(brut);
        } catch (erreur) {
            fautes.push(nom + " : n'est pas du JSON");
            return;
        }
        if (!MOTIF_NOM.test(nom)) fautes.push(nom + " : nom non conforme à " + MOTIF_NOM);
        if (objet === null || typeof objet !== "object" || Array.isArray(objet)) {
            fautes.push(nom + " : la racine n'est pas un objet");
            return;
        }
        if (JSON.stringify(Object.keys(objet)) !== JSON.stringify(CLES_RECETTE)) {
            fautes.push(nom + " : clés « " + Object.keys(objet).join(", ") + " » au lieu de « " + CLES_RECETTE.join(", ") + " »");
        }
        if (objet.version_recette !== 1) fautes.push(nom + " : version_recette doit valoir 1");
        if (typeof objet.description !== "string" || objet.description.trim() === "") {
            fautes.push(nom + " : description vide ou absente");
        }
        if (!Number.isInteger(objet.version_schema)) fautes.push(nom + " : version_schema doit être un entier");
        if (!Array.isArray(objet.fragments) || objet.fragments.length === 0) {
            fautes.push(nom + " : fragments vide ou absent");
        } else {
            const vus = new Set();
            objet.fragments.forEach(function (f) {
                if (typeof f !== "string" || !MOTIF_NOM.test(f)) {
                    fautes.push(nom + " : nom de fragment « " + String(f) + " » refusé (motif " + MOTIF_NOM + ", aucun chemin)");
                    return;
                }
                if (vus.has(f)) fautes.push(nom + " : fragment « " + f + " » cité deux fois");
                vus.add(f);
                if (!disponibles.has(f)) fautes.push(nom + " : fragment « " + f + " » absent de blocs/");
            });
        }
        if (brut !== canonique(objet)) fautes.push(nom + " : pas sous forme canonique");
    });
    assert.deepStrictEqual(fautes, [], "recette(s) fautive(s) :\n" + fautes.join("\n"));
});

/* ============================ B3 — composition et rendu ============================ */

cas("B3 : chaque template se compose sans refus ni avertissement et se rend par le moteur", () => {
    assert.ok(recettes.length >= 1, "aucune recette à contrôler (voir B2)");
    recettes.forEach(function (nom) {
        const resultat = composeur.composer(path.join(DOSSIER_TEMPLATES, nom + ".json"));
        assert.deepStrictEqual(resultat.refus, [], nom + " : la composition est refusée");
        assert.ok(resultat.schema && resultat.schema.blocs.length >= 1, nom + " : composition vide");

        // Moteur chargé à part du script : un script qui taxerait le moteur de
        // bienveillance (ou qui le contournerait) ne trompe pas ce contrôle.
        const charge = chargerMoteur();
        const schema = JSON.parse(canonique(resultat.schema));
        const refusMoteur = Array.from(charge.moteur.validerSchema(schema));
        assert.deepStrictEqual(refusMoteur, [], nom + " : schéma refusé par validerSchema()");
        assert.deepStrictEqual(charge.avertissements, [], nom + " : le moteur avertit");
        const document = charge.moteur.document;
        const conteneur = document.createElement("main");
        const rendu = charge.moteur.rendre(schema, document, conteneur);
        assert.ok(rendu.ok, nom + " : rendre() refuse : " + String(rendu.erreurs));
        assert.ok(conteneur.enfants.length >= 1, nom + " : rendre() n'a rien construit");
        assert.deepStrictEqual(charge.avertissements, [], nom + " : le moteur avertit au rendu");
    });
});

/* ============================== B4 — Ancrage au pilote ============================== */

cas("B4 : la composition de podologue-complet est égale à l'octet à clients/cabinet-01/schema.json", () => {
    assert.ok(fs.existsSync(TEMPLATE_COMPLET), "templates/podologue-complet.json est absent");
    const resultat = composeur.composer(TEMPLATE_COMPLET);
    assert.deepStrictEqual(resultat.refus, [], "podologue-complet : la composition est refusée");
    const compose = Buffer.from(resultat.texte, "utf8");
    const pilote = fs.readFileSync(CHEMIN_PILOTE);
    assert.ok(compose.equals(pilote),
        "la composition (" + compose.length + " octets, sha " + sha256(compose).slice(0, 8) + "…) diverge du pilote (" +
        pilote.length + " octets, sha " + sha256(pilote).slice(0, 8) + "…) : toute modification du pilote se fait aussi " +
        "dans le fragment concerné (D9)");
});

/* ================================= B5 — Clés gelées ================================= */

cas("B5 : un bloc de fragment dont la clé est celle d'un bloc du pilote lui est identique", () => {
    const tous = blocsDesFragments();
    assert.ok(tous.length >= 1, "aucun bloc de fragment à contrôler (blocs/ absent ou vide)");
    const pilote = lireObjet(CHEMIN_PILOTE);
    const parCle = new Map();
    pilote.blocs.forEach(function (b) { parCle.set(b.cle, b); });
    let compares = 0;
    const fautes = [];
    tous.forEach(function (e) {
        if (!parCle.has(e.bloc.cle)) return;
        compares += 1;
        const ecart = premierEcart(e.bloc, parCle.get(e.bloc.cle), "");
        if (ecart !== null) {
            fautes.push("fragment « " + e.fragment + " », bloc « " + e.bloc.cle + " » : diffère du pilote à « " + ecart + " »");
        }
    });
    assert.ok(compares >= 1, "aucun bloc de fragment n'a pu être comparé au pilote : le contrôle serait vide");
    assert.deepStrictEqual(fautes, [], fautes.join("\n"));
});

cas("B5 : aucun bloc ne figure dans deux fragments (ni deux fois dans le même)", () => {
    const tous = blocsDesFragments();
    assert.ok(tous.length >= 1, "aucun bloc de fragment à contrôler (blocs/ absent ou vide)");
    const vus = new Map();
    const doublons = [];
    tous.forEach(function (e) {
        if (vus.has(e.bloc.cle)) {
            doublons.push("bloc « " + e.bloc.cle + " » dans « " + vus.get(e.bloc.cle) + " » et « " + e.fragment + " »");
        } else {
            vus.set(e.bloc.cle, e.fragment);
        }
    });
    assert.deepStrictEqual(doublons, [], doublons.join("\n"));
});

/* ================================= B6 — Aucune grille ================================= */

cas("B6 : aucune grille dans un fragment ou un template ; chaque template en version_schema 1", () => {
    assert.ok(fragments.length >= 1 && recettes.length >= 1, "blocs/ ou templates/ vide (voir B1, B2)");
    const fautes = [];
    fragments.forEach(function (nom) {
        const brut = fs.readFileSync(path.join(DOSSIER_BLOCS, nom + ".json"), "utf8");
        if (brut.indexOf('"grille"') !== -1) fautes.push("fragment « " + nom + " » : la valeur « grille » apparaît");
        lireObjet(path.join(DOSSIER_BLOCS, nom + ".json")).blocs.forEach(function (bloc, i) {
            champsDe(bloc).forEach(function (champ, j) {
                if (champ && champ.type === "grille") {
                    fautes.push("fragment « " + nom + " », bloc " + i + ", champ " + j + " : type grille");
                }
            });
        });
    });
    recettes.forEach(function (nom) {
        const brut = fs.readFileSync(path.join(DOSSIER_TEMPLATES, nom + ".json"), "utf8");
        if (brut.indexOf('"grille"') !== -1) fautes.push("template « " + nom + " » : la valeur « grille » apparaît");
        if (lireObjet(path.join(DOSSIER_TEMPLATES, nom + ".json")).version_schema !== 1) {
            fautes.push("template « " + nom + " » : version_schema doit valoir 1 (la version 2 est celle des grilles, D6)");
        }
    });
    assert.deepStrictEqual(fautes, [], fautes.join("\n"));
});

/* ================================= B7 — Paquet ================================= */

console.log("-- B7 : l'archive du paquet est gardée par tests/test_paquet.py --");

/* ================================= B8 — Ligne de commande ================================= */

function lancer(args, options) {
    const resultat = spawnSync(process.execPath, [(options && options.script) || CHEMIN_SCRIPT].concat(args),
        { cwd: (options && options.cwd) || RACINE, encoding: "buffer" });
    return {
        status: resultat.status,
        sortie: resultat.stdout,
        erreur: resultat.stderr.toString("utf8")
    };
}

function dossierTemporaire() {
    return fs.mkdtempSync(path.join(os.tmpdir(), "bilan-blocs-"));
}

function nettoyer(dossier) {
    fs.rmSync(dossier, { recursive: true, force: true });
}

/** Un fichier laissé sous formulaire/ par une garde défaillante est supprimé, puis signalé. */
function retirerIntrus(chemin) {
    if (fs.existsSync(chemin)) {
        fs.unlinkSync(chemin);
        return true;
    }
    return false;
}

cas("B8 : la sortie standard est, octet pour octet, le schéma du pilote", () => {
    const r = lancer([TEMPLATE_COMPLET]);
    assert.strictEqual(r.status, 0, "code " + r.status + " : " + r.erreur);
    assert.ok(r.sortie.equals(fs.readFileSync(CHEMIN_PILOTE)), "la sortie diffère du pilote");
});

cas("B8 : un refus ne met rien sur la sortie standard et rend 1", () => {
    const dossier = dossierTemporaire();
    try {
        const recette = path.join(dossier, "mauvaise.json");
        fs.writeFileSync(recette, canonique({ version_recette: 1, description: "x", version_schema: 1, fragments: ["inexistant"] }));
        const r = lancer([recette]);
        assert.strictEqual(r.status, 1, "code " + r.status + " attendu 1");
        assert.strictEqual(r.sortie.length, 0, "la sortie standard devait rester vide");
        assert.ok(r.erreur.indexOf("inexistant") !== -1, "le refus doit nommer le fragment : " + r.erreur);
    } finally {
        nettoyer(dossier);
    }
});

cas("B8 : --sortie crée un fichier neuf égal à la composition, et refuse d'écraser un fichier existant", () => {
    const dossier = dossierTemporaire();
    try {
        const neuf = path.join(dossier, "neuf.json");
        const premier = lancer([TEMPLATE_COURT, "--sortie", neuf]);
        assert.strictEqual(premier.status, 0, "écriture d'un fichier neuf refusée : " + premier.erreur);
        assert.ok(fs.readFileSync(neuf).equals(Buffer.from(composeur.composer(TEMPLATE_COURT).texte, "utf8")),
            "le fichier écrit diffère de la composition");

        const existant = path.join(dossier, "existant.json");
        fs.writeFileSync(existant, "contenu d'origine\n");
        const avant = sha256(fs.readFileSync(existant));
        const second = lancer([TEMPLATE_COURT, "--sortie", existant]);
        assert.notStrictEqual(second.status, 0, "--sortie sur un fichier existant doit échouer");
        assert.strictEqual(sha256(fs.readFileSync(existant)), avant, "le fichier existant a été modifié");

        // Le drapeau `wx` ne suit pas un lien : un lien vers un fichier existant est refusé aussi.
        const lien = path.join(dossier, "lien.json");
        let lienCree = true;
        try { fs.symlinkSync(existant, lien); } catch (erreur) { lienCree = false; }
        if (lienCree) {
            const tiers = lancer([TEMPLATE_COURT, "--sortie", lien]);
            assert.notStrictEqual(tiers.status, 0, "--sortie via un lien vers un fichier existant doit échouer");
            assert.strictEqual(sha256(fs.readFileSync(existant)), avant, "le fichier visé par le lien a été modifié");
        } else {
            saute("B8 : --sortie via un lien vers un fichier existant", "lien symbolique impossible ici");
        }

        const sansParent = lancer([TEMPLATE_COURT, "--sortie", path.join(dossier, "absent", "x.json")]);
        assert.notStrictEqual(sansParent.status, 0, "--sortie dans un dossier absent doit échouer");
        assert.ok(!fs.existsSync(path.join(dossier, "absent")), "l'outil ne doit créer aucun dossier");
    } finally {
        nettoyer(dossier);
    }
});

cas("B8 : --sortie sous formulaire/ est refusée, directement et par un lien symbolique", () => {
    const intrusDirect = path.join(DOSSIER_FORMULAIRE, "zz-essai-composer-schema.json");
    const dossier = dossierTemporaire();
    try {
        const direct = lancer([TEMPLATE_COURT, "--sortie", intrusDirect]);
        const ecrit = retirerIntrus(intrusDirect);
        assert.ok(!ecrit, "un fichier a été écrit sous formulaire/ (il a été supprimé)");
        assert.notStrictEqual(direct.status, 0, "--sortie sous formulaire/ doit échouer");

        // Le dossier moteur, sous-dossier de formulaire/ : la remontée d'ancêtres doit le voir.
        const sousDossier = path.join(DOSSIER_FORMULAIRE, "moteur", "zz-essai-composer-schema.json");
        const imbrique = lancer([TEMPLATE_COURT, "--sortie", sousDossier]);
        const ecritImbrique = retirerIntrus(sousDossier);
        assert.ok(!ecritImbrique, "un fichier a été écrit sous formulaire/moteur/ (il a été supprimé)");
        assert.notStrictEqual(imbrique.status, 0, "--sortie sous formulaire/moteur/ doit échouer");

        const lien = path.join(dossier, "vers-formulaire");
        let lienCree = true;
        try { fs.symlinkSync(DOSSIER_FORMULAIRE, lien, "dir"); } catch (erreur) { lienCree = false; }
        if (lienCree) {
            const parLien = lancer([TEMPLATE_COURT, "--sortie", path.join(lien, "zz-essai-composer-schema.json")]);
            const ecritLien = retirerIntrus(intrusDirect);
            assert.ok(!ecritLien, "un fichier a été écrit sous formulaire/ par le lien (il a été supprimé)");
            assert.notStrictEqual(parLien.status, 0, "--sortie via un lien vers formulaire/ doit échouer");
        } else {
            saute("B8 : --sortie via un lien symbolique vers formulaire/", "lien symbolique impossible ici");
        }
    } finally {
        retirerIntrus(intrusDirect);
        retirerIntrus(path.join(DOSSIER_FORMULAIRE, "moteur", "zz-essai-composer-schema.json"));
        nettoyer(dossier);
    }
});

/**
 * Une racine d'atelier minimale dans un dossier temporaire : le script, le
 * moteur, les images, les fragments et les templates réels. Le script calcule
 * sa racine depuis son emplacement : en le copiant, on peut abîmer un fragment
 * SANS toucher au dépôt.
 */
function racineMinimale(dossier) {
    fs.mkdirSync(path.join(dossier, "outils"));
    fs.copyFileSync(CHEMIN_SCRIPT, path.join(dossier, "outils", "composer-schema.js"));
    fs.mkdirSync(path.join(dossier, "formulaire", "moteur"), { recursive: true });
    fs.copyFileSync(CHEMIN_MOTEUR, path.join(dossier, "formulaire", "moteur", "rendu.js"));
    fs.mkdirSync(path.join(dossier, "formulaire", "images"));
    entrees(path.join(DOSSIER_FORMULAIRE, "images")).forEach(function (e) {
        if (e.isFile()) {
            fs.copyFileSync(path.join(DOSSIER_FORMULAIRE, "images", e.name), path.join(dossier, "formulaire", "images", e.name));
        }
    });
    fs.mkdirSync(path.join(dossier, "blocs"));
    nomsJson(DOSSIER_BLOCS).forEach(function (nom) {
        fs.copyFileSync(path.join(DOSSIER_BLOCS, nom + ".json"), path.join(dossier, "blocs", nom + ".json"));
    });
    fs.mkdirSync(path.join(dossier, "templates"));
    fs.copyFileSync(TEMPLATE_COURT, path.join(dossier, "templates", "podologue-court.json"));
    return path.join(dossier, "outils", "composer-schema.js");
}

cas("B8 : un attribut inconnu dans un fragment est un refus (l'avertissement du moteur n'est pas toléré)", () => {
    const dossier = dossierTemporaire();
    try {
        const script = racineMinimale(dossier);
        const recette = path.join(dossier, "templates", "podologue-court.json");
        // Témoin : la racine minimale, intacte, compose. Sans lui, un refus pourrait
        // venir d'une copie incomplète et non de l'attribut.
        const temoin = lancer([recette], { script: script, cwd: dossier });
        assert.strictEqual(temoin.status, 0, "témoin : la racine minimale intacte doit composer (" + temoin.erreur + ")");

        const chemin = path.join(dossier, "blocs", "anamnese.json");
        const fragment = lireObjet(chemin);
        fragment.blocs[0].champs[0].attribut_inconnu = true;
        fs.writeFileSync(chemin, canonique(fragment));
        const r = lancer([recette], { script: script, cwd: dossier });
        assert.strictEqual(r.status, 1, "code " + r.status + " attendu 1");
        assert.strictEqual(r.sortie.length, 0, "la sortie standard devait rester vide");
        assert.ok(r.erreur.indexOf("attribut_inconnu") !== -1, "le refus doit nommer l'attribut : " + r.erreur);
    } finally {
        nettoyer(dossier);
    }
});

cas("B8 : un nom de fragment avec chemin est refusé (../clients/cabinet-01/schema)", () => {
    const dossier = dossierTemporaire();
    try {
        const recette = path.join(dossier, "traversee.json");
        fs.writeFileSync(recette, canonique({
            version_recette: 1, description: "x", version_schema: 1, fragments: ["../clients/cabinet-01/schema"]
        }));
        const r = lancer([recette]);
        assert.strictEqual(r.status, 1, "code " + r.status + " attendu 1");
        assert.strictEqual(r.sortie.length, 0, "la sortie standard devait rester vide");
        assert.ok(r.erreur.indexOf("nom de fragment refusé") !== -1,
            "le refus doit venir du motif du nom, pas d'une lecture du fichier visé : " + r.erreur);
        const api = composeur.lireFragment("../clients/cabinet-01/schema");
        assert.strictEqual(api.fragment, null, "lireFragment() doit refuser un nom avec chemin");
        assert.ok(api.refus.length >= 1, "lireFragment() doit expliquer son refus");
    } finally {
        nettoyer(dossier);
    }
});

cas("B8 : un fragment qui est un lien symbolique est refusé", () => {
    const dossier = dossierTemporaire();
    try {
        const lien = path.join(dossier, "lie.json");
        let lienCree = true;
        try { fs.symlinkSync(path.join(DOSSIER_BLOCS, "anamnese.json"), lien); } catch (erreur) { lienCree = false; }
        if (!lienCree) {
            saute("B8 : un fragment qui est un lien symbolique est refusé", "lien symbolique impossible ici");
            return;
        }
        const r = composeur.lireFragment("lie", dossier);
        assert.strictEqual(r.fragment, null, "un lien symbolique doit être refusé");
        assert.ok(r.refus.length >= 1, "le refus doit être expliqué");
        // Témoin : le même fragment, copié en fichier ordinaire, est accepté.
        fs.copyFileSync(path.join(DOSSIER_BLOCS, "anamnese.json"), path.join(dossier, "copie.json"));
        const temoin = composeur.lireFragment("copie", dossier);
        assert.deepStrictEqual(temoin.refus, [], "témoin : la copie ordinaire doit être acceptée");
    } finally {
        nettoyer(dossier);
    }
});

cas("B8 : --verifier rend 0 sur le pilote et 1 sur un schéma muni d'un attribut inconnu", () => {
    const ok = lancer(["--verifier", CHEMIN_PILOTE]);
    assert.strictEqual(ok.status, 0, "le pilote doit être valide : " + ok.erreur);
    const dossier = dossierTemporaire();
    try {
        const schema = lireObjet(CHEMIN_PILOTE);
        schema.blocs[0].champs[0].attribut_inconnu = true;
        const chemin = path.join(dossier, "inconnu.json");
        fs.writeFileSync(chemin, canonique(schema));
        const ko = lancer(["--verifier", chemin]);
        assert.strictEqual(ko.status, 1, "code " + ko.status + " attendu 1");
    } finally {
        nettoyer(dossier);
    }
});

/* ================================= B9 — Images ================================= */

cas("B9 : chaque image des fragments existe sous formulaire/", () => {
    const tous = blocsDesFragments();
    assert.ok(tous.length >= 1, "aucun bloc de fragment à contrôler (blocs/ absent ou vide)");
    let nbImages = 0;
    const manquantes = [];
    tous.forEach(function (e) {
        champsDe(e.bloc).forEach(function (champ) {
            if (!champ || champ.type !== "image-annotable") return;
            nbImages += 1;
            const fichier = String(champ.fichier);
            const absolu = path.resolve(DOSSIER_FORMULAIRE, fichier);
            const sous = absolu.indexOf(path.join(DOSSIER_FORMULAIRE, "images") + path.sep) === 0;
            if (!sous || !fs.existsSync(absolu) || !fs.statSync(absolu).isFile()) {
                manquantes.push("fragment « " + e.fragment + " », bloc « " + e.bloc.cle + " » : image « " + fichier + " » introuvable sous formulaire/images/");
            }
        });
    });
    assert.ok(nbImages >= 1, "aucune image trouvée dans les fragments : le contrôle serait vide");
    assert.deepStrictEqual(manquantes, [], manquantes.join("\n"));
});

cas("B9 : l'outil refuse une image absente de formulaire/", () => {
    const schema = { version_schema: 1, blocs: [{ cle: "bloc-image", champs: [{
        cle: "image-1", type: "image-annotable", libelle: "Texte 1", fichier: "images/inexistante.png", texte_alternatif: "Texte 1"
    }] }] };
    const refus = composeur.verifier(schema);
    assert.ok(refus.some(function (r) { return r.indexOf("images/inexistante.png") !== -1; }),
        "l'outil doit nommer l'image absente (refus : " + refus.join(" | ") + ")");
});

/* ================================== Bilan =================================== */

console.log("\n" + nbCas + " cas joués, " + echecs.length + " en échec" + (nbSautes > 0 ? ", " + nbSautes + " sous-cas SAUTÉ(S) annoncé(s)" : "") + ".");
if (echecs.length > 0) {
    console.log("En échec :\n  - " + echecs.join("\n  - "));
    process.exit(1);
}
console.log("Tout est vert.");
