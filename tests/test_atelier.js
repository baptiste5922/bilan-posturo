/*
 * Atelier de composition d'un client (contrat C9-T2) : `outils/atelier/`.
 *
 * Dix groupes, chacun un garde-fou à éprouver par mutation volontaire
 * (docs/audits/C9-T2-mises-en-echec.md) :
 *
 *   T1 — `ouvrir` crée exactement ses quatre entrées, clés d'identité tirées du
 *        serveur (jamais d'une liste écrite ici seulement) ;
 *   T2 — confinement : un dossier de travail dans le dépôt, égal à lui, ou
 *        atteint par un lien est refusé, la racine reste inchangée (M1) ;
 *   T3 — création exclusive : `composer` n'écrase pas `schema.json` (M2) ;
 *        `apercu` remplace son fichier, mais pas un lien ;
 *   T4 — liste fermée des noms écrits (M3) ;
 *   T5 — `verifier` : identité, clés, convention de nommage ;
 *   T6 — `verifier` : le logo, jugé par le vrai serveur, motif nommé (M4) ;
 *   T7 — `verifier` : rappel « grille » ;
 *   T8 — aperçu : `<base href>`, JSON embarqué, échappement de `<` (M5) ;
 *   T9 — aperçu exécuté : aucun `fetch`, démarrage du moteur retiré, rendu égal
 *        à l'instantané du pilote (M6) ;
 *   T10 — rien n'est écrit dans le dépôt, le pilote est intact.
 *
 * Toutes les racines sont jetables : `mkdtemp` sous `os.tmpdir()`, puis
 * `realpath` (`/var` est un lien vers `/private/var` sous macOS). Aucune garde
 * d'écriture n'est éprouvée dans le dépôt réel : un `finally` ne protège pas
 * d'une interruption. La racine « du dépôt » des tests est une racine jetable
 * passée par `options.racineDepot`.
 *
 * Messages d'échec : une clé, un motif, un nom de fichier — jamais une valeur
 * d'identité. Les courriel et téléphone de test sont assemblés à l'exécution :
 * `tests/test_identite_absente.py` refuse leur forme complète dans le dépôt.
 *
 * Aucune dépendance. Les messages de l'outil sont lus sur son erreur standard.
 *
 *     node tests/test_atelier.js
 */

const fs = require("fs");
const os = require("os");
const path = require("path");
const url = require("url");
const vm = require("vm");
const assert = require("assert");
const crypto = require("crypto");
const childProcess = require("child_process");

const dom = require("./outils/dom-minimal.js");

const RACINE = path.join(__dirname, "..");
const CHEMIN_ATELIER = path.join(RACINE, "outils", "atelier", "atelier.js");
const CHEMIN_AUXILIAIRE = path.join(RACINE, "outils", "atelier", "lire_serveur.py");
const CHEMIN_SERVEUR = path.join(RACINE, "serveur", "serveur.py");
const DOSSIER_FORMULAIRE = path.join(RACINE, "formulaire");
const CHEMIN_MOTEUR = path.join(DOSSIER_FORMULAIRE, "moteur", "rendu.js");
const CHEMIN_SCRIPT = path.join(DOSSIER_FORMULAIRE, "script.js");
const RECETTE_COMPLETE = path.join(RACINE, "templates", "podologue-complet.json");
const RECETTE_COURTE = path.join(RACINE, "templates", "podologue-court.json");
const SCHEMA_PILOTE = path.join(RACINE, "clients", "cabinet-01", "schema.json");
const SCHEMA_MIROIR = path.join(DOSSIER_FORMULAIRE, "schema.json");
const SCHEMA_GRILLES = path.join(__dirname, "donnees", "schema-v2-grilles-fictives.json");
const INSTANTANE = path.join(__dirname, "donnees", "rendu-schema-production.txt");

const atelier = require(CHEMIN_ATELIER);
const composeur = require(path.join(RACINE, "outils", "composer-schema.js"));

// État du dépôt AVANT tout cas (T10) : la capture doit précéder la suite.
const etatDepot = {
    porcelaine: gitPorcelaine(),
    pilote: sha256(SCHEMA_PILOTE),
    miroir: sha256(SCHEMA_MIROIR)
};

function gitPorcelaine() {
    const sortie = childProcess.spawnSync("git", ["-C", RACINE, "status", "--porcelain"], { encoding: "utf8" });
    assert.strictEqual(sortie.status, 0, "git status a échoué : " + sortie.stderr);
    return sortie.stdout;
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

/* ================================= Racines ================================== */

const racinesCreees = [];

/** Une racine jetable, résolue (`/var` → `/private/var`), effacée en fin de suite. */
function racineJetable(prefixe) {
    const dossier = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), prefixe + "-")));
    racinesCreees.push(dossier);
    return dossier;
}

/** Peut-on créer un lien symbolique ici ? (Windows sans privilège : non.) */
function liensPossibles() {
    const racine = racineJetable("sonde-lien");
    try {
        fs.symlinkSync(racine, path.join(racine, "lien"), "dir");
        return true;
    } catch (erreur) {
        return false;
    }
}
const LIENS = liensPossibles();

/** Le contenu d'un dossier, récursivement : noms relatifs triés, `/` pour un dossier. */
function lister(dossier, relatif) {
    const base = relatif || "";
    let sortie = [];
    fs.readdirSync(path.join(dossier, base), { withFileTypes: true }).forEach(function (e) {
        const nom = path.posix.join(base.split(path.sep).join("/"), e.name);
        if (e.isDirectory()) {
            sortie.push(nom + "/");
            sortie = sortie.concat(lister(dossier, path.join(base, e.name)));
        } else {
            sortie.push(nom);
        }
    });
    return sortie.sort();
}

function sha256(chemin) {
    return crypto.createHash("sha256").update(fs.readFileSync(chemin)).digest("hex");
}

/** Un seul process Node : l'erreur standard et le code de sortie de l'outil, en ligne de commande. */
function lancer(args, env) {
    const resultat = childProcess.spawnSync(process.execPath, [CHEMIN_ATELIER].concat(args),
        { encoding: "utf8", env: Object.assign({}, process.env, env || {}) });
    return { code: resultat.status, erreur: resultat.stderr, sortie: resultat.stdout };
}

// L'état de serveur/ AVANT le premier appel à l'auxiliaire : sans `-B`, ce premier
// import écrirait un __pycache__ neuf (sur un clone frais, où il n'existe pas encore).
const serveurAvant = JSON.stringify(listerAvecDates(path.join(RACINE, "serveur")));

const python = atelier.trouverPython();
assert.ok(python.commande, "aucun interpréteur Python utilisable : " + (python.refus || []).join(" "));
const DEFAUTS = python.defauts;

// Valeurs dictées « hors document » : assemblées à l'exécution (voir l'en-tête).
const COURRIEL_TEST = ["contact", "exemple.test"].join("@");
const TELEPHONE_TEST = ["06", "12", "34", "56", "78"].join(" ");

function identiteComplete(changements) {
    const identite = {
        nom: "Texte 1", praticien: "Texte 2", adresse: "Texte 3",
        courriel: COURRIEL_TEST, telephone: TELEPHONE_TEST,
        logo: "", convention_nommage: "{nom}_{prenom}_{date}"
    };
    return Object.assign(identite, changements || {});
}

/** Un dossier de travail ouvert et composé (recette courte), identité complète. */
function preparer(nom, changementsIdentite, recette) {
    const racine = racineJetable("atelier-" + nom);
    const travail = path.join(racine, "t");
    const refus = atelier.ouvrir(travail, recette || RECETTE_COURTE);
    assert.deepStrictEqual(refus, [], "ouvrir : " + refus.join(" | "));
    const composition = atelier.composer(travail);
    assert.deepStrictEqual(composition.refus, [], "composer : " + composition.refus.join(" | "));
    fs.writeFileSync(path.join(travail, "identite-cabinet.json"),
        JSON.stringify(identiteComplete(changementsIdentite), null, 2) + "\n");
    return travail;
}

function ecrireIdentiteBrute(travail, objet) {
    fs.writeFileSync(path.join(travail, "identite-cabinet.json"), JSON.stringify(objet, null, 2) + "\n");
}

function texteDeRefus(resultat) {
    return resultat.refus.join("\n");
}

/* ============================= T1 — ouvrir ================================= */

cas("T1 : ouvrir crée exactement quatre entrées, clés d'identité = sortie de l'auxiliaire, dans l'ordre", () => {
    const racine = racineJetable("t1");
    const travail = path.join(racine, "t");
    const refus = atelier.ouvrir(travail, RECETTE_COURTE);
    assert.deepStrictEqual(refus, [], refus.join(" | "));
    assert.deepStrictEqual(lister(travail),
        ["identite-cabinet.json", "images/", "images/cabinet/", "recette.json"]);
    assert.ok(!fs.existsSync(path.join(travail, "schema.json")), "ouvrir n'écrit pas schema.json");

    // La sortie de l'auxiliaire, demandée ici directement, sans passer par l'outil.
    const direct = childProcess.spawnSync(python.commande, ["-I", "-B", CHEMIN_AUXILIAIRE, "defauts"], { encoding: "utf8" });
    assert.strictEqual(direct.status, 0, "l'auxiliaire doit répondre 0");
    const defauts = JSON.parse(direct.stdout);
    const texte = fs.readFileSync(path.join(travail, "identite-cabinet.json"), "utf8");
    const identite = JSON.parse(texte);
    assert.deepStrictEqual(Object.keys(identite), defauts.cles, "clés de l'identité, dans l'ordre");
    assert.deepStrictEqual(identite, defauts.defauts, "valeurs par défaut de CONFIG_DEFAUT");
    assert.strictEqual(texte, JSON.stringify(identite, null, 2) + "\n", "sérialisation canonique");
    assert.strictEqual(defauts.logo_par_defaut, defauts.defauts.logo);
    // La recette est copiée à l'octet.
    assert.ok(fs.readFileSync(RECETTE_COURTE).equals(fs.readFileSync(path.join(travail, "recette.json"))),
        "recette.json doit être la copie exacte");
});

cas("T1 : les sept clés de l'auxiliaire sont, dans l'ordre, celles du bloc cabinet de serveur.py", () => {
    // Recoupement indépendant : le texte de serveur.py, lu par un motif, contre l'import.
    const source = fs.readFileSync(CHEMIN_SERVEUR, "utf8");
    const bloc = /"cabinet": \{([\s\S]*?)\n    \},/.exec(source);
    assert.ok(bloc, "le bloc \"cabinet\" de CONFIG_DEFAUT est introuvable dans serveur.py");
    const cles = [];
    const motif = /^\s+"(\w+)":/gm;
    let trouve;
    while ((trouve = motif.exec(bloc[1])) !== null) cles.push(trouve[1]);
    assert.strictEqual(cles.length, 7, "sept clés attendues dans serveur.py");
    assert.deepStrictEqual(DEFAUTS.cles, cles);
});

cas("T1 : ouvrir refuse un dossier existant, une recette illisible et un parent absent, sans rien créer", () => {
    const racine = racineJetable("t1b");
    const existant = path.join(racine, "existant");
    fs.mkdirSync(existant);
    assert.ok(atelier.ouvrir(existant, RECETTE_COURTE).length > 0, "dossier existant refusé");
    assert.deepStrictEqual(lister(existant), [], "le dossier existant n'est pas touché");

    const neuf = path.join(racine, "neuf");
    assert.ok(atelier.ouvrir(neuf, path.join(racine, "inexistante.json")).length > 0, "recette illisible refusée");
    assert.ok(!fs.existsSync(neuf), "rien n'est créé quand la recette est illisible");

    assert.ok(atelier.ouvrir(path.join(racine, "absent", "t"), RECETTE_COURTE).length > 0, "parent absent refusé");
    assert.ok(!fs.existsSync(path.join(racine, "absent")), "aucun dossier intermédiaire créé");
});

cas("T1 : l'auxiliaire n'écrit rien sous serveur/ et n'appelle ni main, ni demarrer, ni charger_config", () => {
    childProcess.spawnSync(python.commande, ["-I", "-B", CHEMIN_AUXILIAIRE, "defauts"], { encoding: "utf8" });
    const racine = racineJetable("t1c");
    ecrireIdentiteBrute(racine, identiteComplete());
    childProcess.spawnSync(python.commande, ["-I", "-B", CHEMIN_AUXILIAIRE, "identite",
        path.join(racine, "identite-cabinet.json"), racine], { encoding: "utf8" });
    assert.strictEqual(JSON.stringify(listerAvecDates(path.join(RACINE, "serveur"))), serveurAvant,
        "serveur/ a changé (un __pycache__ écrit ?)");
    const source = fs.readFileSync(CHEMIN_AUXILIAIRE, "utf8");
    assert.ok(!/\b(main|demarrer|charger_config)\(/.test(source), "l'auxiliaire ne doit appeler ni main, ni demarrer, ni charger_config");
    assert.ok(!/^\s*assert /m.test(source), "pas d'assert nu : il s'évaporerait sous python -O");
});

function listerAvecDates(dossier) {
    const sortie = [];
    fs.readdirSync(dossier, { withFileTypes: true }).forEach(function (e) {
        const chemin = path.join(dossier, e.name);
        if (e.isDirectory()) {
            listerAvecDates(chemin).forEach(function (x) { sortie.push(e.name + "/" + x); });
        } else {
            sortie.push(e.name + "@" + fs.statSync(chemin).mtimeMs);
        }
    });
    return sortie.sort();
}

cas("T1 : l'auxiliaire rend 2 sans argument et 1 sur une identité illisible, sans citer son contenu", () => {
    const usage = childProcess.spawnSync(python.commande, ["-I", "-B", CHEMIN_AUXILIAIRE], { encoding: "utf8" });
    assert.strictEqual(usage.status, 2);
    const racine = racineJetable("t1d");
    fs.writeFileSync(path.join(racine, "x.json"), "{ ceci " + COURRIEL_TEST + " n'est pas du JSON");
    const illisible = childProcess.spawnSync(python.commande,
        ["-I", "-B", CHEMIN_AUXILIAIRE, "identite", path.join(racine, "x.json"), racine], { encoding: "utf8" });
    assert.strictEqual(illisible.status, 1);
    assert.ok(illisible.stderr.indexOf(COURRIEL_TEST) === -1, "le contenu de l'identité ne doit pas être cité");
});

cas("T1 : trouverPython saute un interpréteur défaillant et refuse explicitement s'il n'en reste aucun", () => {
    const racine = racineJetable("t1e");
    const faux = path.join(racine, "python-qui-n-existe-pas");
    const aucun = atelier.trouverPython({ candidats: [faux] });
    assert.ok(aucun.refus && aucun.refus.join(" ").indexOf("aucun interpréteur Python") !== -1, "refus explicite attendu");
    const suivant = atelier.trouverPython({ candidats: [faux, python.commande] });
    assert.strictEqual(suivant.commande, python.commande, "le premier qui répond est retenu");
    // ATELIER_PYTHON cassé : l'outil retombe sur python3 / python.
    const sortie = lancer(["verifier", racine], { ATELIER_PYTHON: faux });
    assert.ok(sortie.erreur.indexOf("aucun interpréteur Python") === -1, "le repli sur python3 / python doit jouer");
});

/* =========================== T2 — confinement =============================== */

cas("T2 : un dossier de travail sous la racine du dépôt, égal à elle, ou atteint par un lien est refusé", () => {
    const depot = racineJetable("t2-depot");
    const avant = lister(depot);
    const options = { racineDepot: depot };

    // Sous la racine : le dossier à créer a la racine pour parent.
    assert.ok(atelier.ouvrir(path.join(depot, "client"), RECETTE_COURTE, options).length > 0, "sous la racine : refusé");
    // Sous un sous-dossier existant de la racine.
    fs.mkdirSync(path.join(depot, "sous"));
    assert.ok(atelier.ouvrir(path.join(depot, "sous", "client"), RECETTE_COURTE, options).length > 0, "sous un sous-dossier : refusé");
    // Égal à la racine : écrire dedans est refusé.
    assert.ok(atelier.ecrireDansTravail(depot, "schema.json", "{}", options).length > 0, "égal à la racine : refusé");
    assert.ok(atelier.composer(depot, options).refus.length > 0, "composer dans la racine : refusé");
    assert.ok(atelier.apercu(depot, options).length > 0, "apercu dans la racine : refusé");
    fs.rmdirSync(path.join(depot, "sous"));
    assert.deepStrictEqual(lister(depot), avant, "la racine doit rester inchangée");
});

cas("T2 : un lien vers la racine du dépôt ne contourne pas la garde", () => {
    if (!LIENS) return saute("T2 lien", "création de lien impossible ici");
    const depot = racineJetable("t2l-depot");
    const ailleurs = racineJetable("t2l-ailleurs");
    const lien = path.join(ailleurs, "lien");
    fs.symlinkSync(depot, lien, "dir");
    const options = { racineDepot: depot };
    assert.ok(atelier.ouvrir(path.join(lien, "client"), RECETTE_COURTE, options).length > 0, "via le lien : refusé");
    assert.ok(atelier.ecrireDansTravail(lien, "schema.json", "{}", options).length > 0, "écrire via le lien : refusé");
    assert.ok(atelier.ouvrir(lien, RECETTE_COURTE, options).length > 0, "le lien lui-même : refusé");
    // Un lien pendant vers un nom neuf de la racine n'est pas suivi non plus.
    const pendant = path.join(ailleurs, "pendant");
    fs.symlinkSync(path.join(depot, "neuf"), pendant, "dir");
    assert.ok(atelier.ouvrir(pendant, RECETTE_COURTE, options).length > 0, "lien pendant : refusé");
    assert.deepStrictEqual(lister(depot), [], "la racine doit rester inchangée");
});

cas("T2 : la racine réelle du dépôt est reconnue par défaut (sans rien écrire dedans)", () => {
    assert.ok(atelier.refusConfinement(RACINE).length > 0, "la racine du dépôt doit être refusée");
    assert.ok(atelier.refusConfinement(DOSSIER_FORMULAIRE).length > 0, "formulaire/ doit être refusé");
    assert.ok(atelier.refusConfinement(path.join(RACINE, "outils", "atelier")).length > 0, "outils/atelier/ doit être refusé");
    assert.deepStrictEqual(atelier.refusConfinement(racineJetable("t2d")), [], "un dossier hors du dépôt est admis");
    // Un dossier inexistant : l'identité des ancêtres ne s'établit pas, on refuse.
    assert.ok(atelier.refusConfinement(path.join(racineJetable("t2e"), "absent")).length > 0, "dossier inexistant : refus par prudence");
});

cas("ligne de commande : une commande inconnue ou un argument manquant rend 2", () => {
    // Le refus d'un dossier dans le dépôt RÉEL n'est pas joué ici (voir l'en-tête) : A6 le fait à la main.
    assert.strictEqual(lancer([]).code, 2, "sans argument");
    assert.strictEqual(lancer(["ouvrir"]).code, 2, "ouvrir sans dossier");
    assert.strictEqual(lancer(["ouvrir", "x"]).code, 2, "ouvrir sans --recette");
    assert.strictEqual(lancer(["verifier"]).code, 2, "verifier sans dossier");
    assert.strictEqual(lancer(["deviner", "x"]).code, 2, "commande inconnue");
});

/* ======================== T3 — création exclusive ========================== */

cas("T3 : composer refuse d'écraser schema.json", () => {
    const travail = preparer("t3", { logo: "" });
    const chemin = path.join(travail, "schema.json");
    const avant = fs.readFileSync(chemin, "utf8");
    fs.writeFileSync(chemin, avant.replace("Texte", "Retouche"));
    const retouche = fs.readFileSync(chemin, "utf8");
    const second = atelier.composer(travail);
    assert.ok(second.refus.length > 0, "composer doit refuser un schema.json existant");
    assert.ok(texteDeRefus(second).indexOf("existe déjà") !== -1, "le refus doit dire pourquoi : " + texteDeRefus(second));
    assert.strictEqual(fs.readFileSync(chemin, "utf8"), retouche, "la retouche à la main doit survivre");
    assert.strictEqual(lancer(["composer", travail]).code, 1, "la ligne de commande rend 1");
});

cas("T3 : composer avec la recette complète redonne le schéma du pilote à l'octet", () => {
    const travail = preparer("t3b", {}, RECETTE_COMPLETE);
    assert.ok(fs.readFileSync(path.join(travail, "schema.json")).equals(fs.readFileSync(SCHEMA_PILOTE)));
});

cas("T3 : apercu remplace son fichier mais refuse un apercu-atelier.html qui est un lien", () => {
    const travail = preparer("t3c");
    assert.deepStrictEqual(atelier.apercu(travail), []);
    const chemin = path.join(travail, "apercu-atelier.html");
    const premiere = fs.readFileSync(chemin, "utf8");
    // Un schéma retouché : l'aperçu suivant doit le refléter (remplacement réel).
    const schema = JSON.parse(fs.readFileSync(path.join(travail, "schema.json"), "utf8"));
    schema.blocs[0].champs[0].libelle = "Libellé retouché 1 :";
    fs.writeFileSync(path.join(travail, "schema.json"), JSON.stringify(schema, null, 2) + "\n");
    assert.deepStrictEqual(atelier.apercu(travail), []);
    const seconde = fs.readFileSync(chemin, "utf8");
    assert.notStrictEqual(seconde, premiere, "l'aperçu doit être réécrit");
    assert.ok(seconde.indexOf("Libellé retouché 1") !== -1);

    if (!LIENS) return saute("T3 lien", "création de lien impossible ici");
    const cible = path.join(racineJetable("t3-cible"), "important.txt");
    fs.writeFileSync(cible, "à ne pas toucher");
    fs.unlinkSync(chemin);
    fs.symlinkSync(cible, chemin);
    const refus = atelier.apercu(travail);
    assert.ok(refus.length > 0, "un lien à la place de l'aperçu doit être refusé");
    assert.strictEqual(fs.readFileSync(cible, "utf8"), "à ne pas toucher", "la cible du lien ne doit pas être écrite");
    assert.ok(fs.lstatSync(chemin).isSymbolicLink(), "le lien n'est pas supprimé");
});

/* ====================== T4 — liste fermée des noms ========================= */

cas("T4 : aucun nom hors de la liste fermée n'est écrit", () => {
    const racine = racineJetable("t4");
    const travail = path.join(racine, "t");
    fs.mkdirSync(travail);
    ["../x", "x.json", "images/logo.png", "recette.json/../x", path.join(racine, "absolu.json"), "", "SCHEMA.JSON", 42, null]
        .forEach(function (nom) {
            const refus = atelier.ecrireDansTravail(travail, nom, "contenu");
            assert.ok(refus.length > 0, "le nom " + JSON.stringify(nom) + " devrait être refusé");
        });
    assert.deepStrictEqual(lister(racine), ["t/"], "rien n'a été écrit hors de la liste");
    // Les quatre noms de la liste sont admis (un par un, en création exclusive).
    atelier.NOMS_ECRITS.forEach(function (nom) {
        assert.deepStrictEqual(atelier.ecrireDansTravail(travail, nom, "{}"), [], nom + " devrait être admis");
        assert.ok(atelier.ecrireDansTravail(travail, nom, "{}").length > 0, nom + " ne s'écrase pas");
    });
    // Seul l'aperçu se remplace.
    assert.ok(atelier.ecrireDansTravail(travail, "schema.json", "{}", { remplacer: true }).length > 0, "schema.json ne se remplace pas");
    assert.deepStrictEqual(atelier.ecrireDansTravail(travail, "apercu-atelier.html", "x", { remplacer: true }), []);
    // Les sous-dossiers aussi sont une liste fermée.
    assert.ok(atelier.creerSousDossier(travail, "autre").length > 0);
    assert.ok(atelier.creerSousDossier(travail, "../autre").length > 0);
    assert.deepStrictEqual(lister(racine).filter(function (n) { return n.indexOf("autre") !== -1; }), []);
});

/* ============================ T5 — verifier ================================ */

cas("T5 : une identité complète, logo vide, rend 0 ; en ligne de commande aussi", () => {
    const travail = preparer("t5a");
    const resultat = atelier.verifierTravail(travail);
    assert.deepStrictEqual(resultat.refus, [], texteDeRefus(resultat));
    const cli = lancer(["verifier", travail]);
    assert.strictEqual(cli.code, 0, cli.erreur);
    assert.ok(/^À FAIRE : /m.test(cli.erreur), "les rappels sont préfixés « À FAIRE : »");
});

cas("T5 : praticien vide → refus (1), sans citer de valeur d'identité", () => {
    const travail = preparer("t5b", { praticien: "  " });
    const resultat = atelier.verifierTravail(travail);
    assert.ok(texteDeRefus(resultat).indexOf("praticien") !== -1, texteDeRefus(resultat));
    const cli = lancer(["verifier", travail]);
    assert.strictEqual(cli.code, 1);
    assert.ok(/^REFUS : /m.test(cli.erreur), "les refus sont préfixés « REFUS : »");
    [COURRIEL_TEST, TELEPHONE_TEST, "Texte 1", "Texte 3"].forEach(function (valeur) {
        assert.ok(cli.erreur.indexOf(valeur) === -1, "une valeur d'identité apparaît dans la sortie de l'outil");
    });
});

cas("T5 : clé en trop, clé absente, valeur qui n'est pas une chaîne → refus nommant la clé", () => {
    let travail = preparer("t5c");
    ecrireIdentiteBrute(travail, Object.assign(identiteComplete(), { couleur: "Texte 9" }));
    let resultat = atelier.verifierTravail(travail);
    assert.ok(/en trop : couleur/.test(texteDeRefus(resultat)), texteDeRefus(resultat));
    assert.ok(texteDeRefus(resultat).indexOf("Texte 9") === -1, "la valeur ne doit pas être citée");

    travail = preparer("t5d");
    const sans = identiteComplete();
    delete sans.telephone;
    ecrireIdentiteBrute(travail, sans);
    resultat = atelier.verifierTravail(travail);
    assert.ok(/absente\(s\) : telephone/.test(texteDeRefus(resultat)), texteDeRefus(resultat));

    travail = preparer("t5e");
    ecrireIdentiteBrute(travail, Object.assign(identiteComplete(), { adresse: 12 }));
    resultat = atelier.verifierTravail(travail);
    assert.ok(/pas des chaînes : adresse/.test(texteDeRefus(resultat)), texteDeRefus(resultat));

    travail = preparer("t5f");
    fs.writeFileSync(path.join(travail, "identite-cabinet.json"), "{ " + COURRIEL_TEST + " }");
    resultat = atelier.verifierTravail(travail);
    assert.ok(resultat.refus.length > 0, "une identité qui n'est pas du JSON est refusée");
    assert.ok(texteDeRefus(resultat).indexOf(COURRIEL_TEST) === -1, "le contenu illisible ne doit pas être cité");
});

cas("T5 : convention de nommage — un marqueur inconnu est refusé, les marqueurs du formulaire passent", () => {
    let travail = preparer("t5g", { convention_nommage: "Bilan_{inconnu}_{date}" });
    let resultat = atelier.verifierTravail(travail);
    assert.ok(texteDeRefus(resultat).indexOf("{inconnu}") !== -1, texteDeRefus(resultat));

    travail = preparer("t5h", { convention_nommage: "{date}_{nom}_{prenom}_{patient}" });
    assert.deepStrictEqual(atelier.verifierTravail(travail).refus, []);

    travail = preparer("t5i", { convention_nommage: "Bilan_{date" });
    resultat = atelier.verifierTravail(travail);
    assert.ok(texteDeRefus(resultat).indexOf("accolade") !== -1, texteDeRefus(resultat));
});

cas("T5 : la liste des marqueurs est lue dans script.js ; une ligne absente ou en double → « source illisible »", () => {
    const lus = atelier.lireMarqueurs(CHEMIN_SCRIPT);
    assert.deepStrictEqual(lus.marqueurs, ["date", "nom", "prenom", "patient"], JSON.stringify(lus));

    const racine = racineJetable("t5s");
    const source = fs.readFileSync(CHEMIN_SCRIPT, "utf8");
    const ligne = /^[ \t]*const marqueurs = \{[^}]*\};[ \t\r]*$/m.exec(source)[0];
    const sans = path.join(racine, "sans.js");
    fs.writeFileSync(sans, source.replace(ligne, "const autre = {};"));
    const double = path.join(racine, "double.js");
    fs.writeFileSync(double, source.replace(ligne, ligne + "\n" + ligne));
    const modifie = path.join(racine, "modifie.js");
    fs.writeFileSync(modifie, source.replace(ligne, ligne.replace("patient: patient", "patient: patient, extra: 1")));
    assert.ok(atelier.lireMarqueurs(sans).refus[0].indexOf("source illisible") !== -1);
    assert.ok(atelier.lireMarqueurs(double).refus[0].indexOf("source illisible") !== -1);
    assert.ok(atelier.lireMarqueurs(path.join(racine, "absent.js")).refus[0].indexOf("source illisible") !== -1);
    // Un marqueur ajouté au formulaire est suivi, sans toucher à l'atelier.
    assert.deepStrictEqual(atelier.lireMarqueurs(modifie).marqueurs, ["date", "nom", "prenom", "patient", "extra"]);

    const travail = preparer("t5t");
    const resultat = atelier.verifierTravail(travail, { cheminScript: sans });
    assert.ok(texteDeRefus(resultat).indexOf("source illisible") !== -1, "verifier refuse tout, il ne devine pas");
});

cas("T5 : un schéma refusé par le moteur est refusé par verifier ; un schema.json absent aussi", () => {
    const travail = preparer("t5m");
    fs.writeFileSync(path.join(travail, "schema.json"), JSON.stringify({ version_schema: 1, blocs: [] }));
    assert.ok(atelier.verifierTravail(travail).refus.length > 0, "schéma sans bloc : refusé par le moteur");
    fs.unlinkSync(path.join(travail, "schema.json"));
    assert.ok(texteDeRefus(atelier.verifierTravail(travail)).indexOf("composer") !== -1, "il faut dire de lancer composer");
});

/* ============================== T6 — le logo =============================== */

const SIGNATURE_PNG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

function poserLogo(travail, nom, contenu) {
    fs.writeFileSync(path.join(travail, "images", "cabinet", nom), contenu);
}

cas("T6 : un PNG valide sous images/cabinet/ passe", () => {
    const travail = preparer("t6a", { logo: "images/cabinet/logo.png" });
    poserLogo(travail, "logo.png", Buffer.concat([SIGNATURE_PNG, Buffer.alloc(64)]));
    assert.deepStrictEqual(atelier.verifierTravail(travail).refus, []);
});

cas("T6 : signature fausse, trop gros, lien, absent, mauvais emplacement → refus avec le motif du serveur", () => {
    let travail = preparer("t6b", { logo: "images/cabinet/logo.png" });
    poserLogo(travail, "logo.png", Buffer.from("pas une image du tout"));
    assert.ok(texteDeRefus(atelier.verifierTravail(travail)).indexOf("« illisible »") !== -1, "signature fausse");
    assert.strictEqual(lancer(["verifier", travail]).code, 1);

    travail = preparer("t6c", { logo: "images/cabinet/logo.png" });
    poserLogo(travail, "logo.png", Buffer.concat([SIGNATURE_PNG, Buffer.alloc(512 * 1024)]));
    assert.ok(texteDeRefus(atelier.verifierTravail(travail)).indexOf("« trop-volumineux »") !== -1, "plus de 512 Kio");

    travail = preparer("t6d", { logo: "images/cabinet/logo.png" });
    assert.ok(texteDeRefus(atelier.verifierTravail(travail)).indexOf("« absent »") !== -1, "fichier absent");

    travail = preparer("t6e", { logo: "logo.png" });
    assert.ok(texteDeRefus(atelier.verifierTravail(travail)).indexOf("« forme-invalide »") !== -1, "hors de images/cabinet/");

    if (!LIENS) return saute("T6 lien", "création de lien impossible ici");
    travail = preparer("t6f", { logo: "images/cabinet/logo.png" });
    const reel = path.join(racineJetable("t6-reel"), "vrai.png");
    fs.writeFileSync(reel, Buffer.concat([SIGNATURE_PNG, Buffer.alloc(64)]));
    fs.symlinkSync(reel, path.join(travail, "images", "cabinet", "logo.png"));
    assert.ok(texteDeRefus(atelier.verifierTravail(travail)).indexOf("« lien-symbolique »") !== -1, "lien symbolique");
});

cas("T6 : le logo par défaut du pilote passe avec un rappel « À FAIRE » ; le logo vide sans rappel", () => {
    let travail = preparer("t6g", { logo: DEFAUTS.logo_par_defaut });
    let resultat = atelier.verifierTravail(travail);
    assert.deepStrictEqual(resultat.refus, [], texteDeRefus(resultat));
    assert.ok(resultat.afaire.some(function (a) { return a.indexOf("logo") !== -1 && a.indexOf("feuille de route") !== -1; }));

    travail = preparer("t6h", { logo: "" });
    resultat = atelier.verifierTravail(travail);
    assert.ok(!resultat.afaire.some(function (a) { return a.indexOf("logo") !== -1; }), "pas de rappel de logo quand il n'y en a pas");
});

/* ============================ T7 — les grilles ============================= */

cas("T7 : un schéma à grilles passe (0) avec un « À FAIRE » qui cite la tablette du client", () => {
    const travail = preparer("t7");
    fs.copyFileSync(SCHEMA_GRILLES, path.join(travail, "schema.json"));
    const cli = lancer(["verifier", travail]);
    assert.strictEqual(cli.code, 0, cli.erreur);
    const lignes = cli.erreur.split("\n").filter(function (l) { return l.indexOf("À FAIRE : ") === 0; });
    assert.ok(lignes.some(function (l) { return l.indexOf("tablette du client") !== -1; }), cli.erreur);
    // Sans grille, pas de rappel.
    const sans = preparer("t7b");
    assert.ok(!lancer(["verifier", sans]).erreur.includes("tablette du client"), "pas de rappel sans grille");
});

/* ============================== T8 — l'aperçu ============================== */

function extraire(html, motif, message) {
    const trouve = motif.exec(html);
    assert.ok(trouve, message);
    return trouve[1];
}

function desechapper(attribut) {
    return attribut.replace(/&quot;/g, "\"").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
}

cas("T8 : <base href> = pathToFileURL(formulaire) + « / », y compris pour un chemin à caractères spéciaux", () => {
    const schema = JSON.parse(fs.readFileSync(SCHEMA_PILOTE, "utf8"));
    const html = atelier.construirePage(schema);
    const base = desechapper(extraire(html, /<base href="([^"]*)">/, "<base href> introuvable"));
    assert.strictEqual(base, url.pathToFileURL(DOSSIER_FORMULAIRE).href + "/");
    assert.strictEqual((html.match(/<base /g) || []).length, 1, "une seule balise <base>");

    const bizarre = path.join(os.tmpdir(), "a&b \"c\"<d>", "formulaire");
    const page = atelier.construirePage(schema, { dossierFormulaire: bizarre });
    assert.strictEqual(desechapper(extraire(page, /<base href="([^"]*)">/, "<base href> introuvable")),
        url.pathToFileURL(bizarre).href + "/");
    assert.ok(page.indexOf("a&b") === -1, "le « & » du chemin doit être écrit « &amp; » dans l'attribut");
});

cas("T8 : le JSON embarqué se relit égal au schéma ; un libellé « </script><script> » n'apparaît jamais tel quel", () => {
    const schema = { version_schema: 1, blocs: [{ cle: "bloc-1", champs: [
        { cle: "texte-1", type: "zone-texte", libelle: "</script><script>alert(1)</script> <!-- &   :" }
    ] }] };
    const html = atelier.construirePage(schema);
    assert.ok(html.indexOf("</script><script>") === -1, "le libellé hostile apparaît tel quel dans la page");
    assert.strictEqual((html.match(/<script/g) || []).length, 3, "trois balises <script> exactement");
    assert.strictEqual((html.match(/<\/script>/g) || []).length, 3, "trois fermetures exactement");
    const json = extraire(html, /<script type="application\/json" id="schema-apercu">([\s\S]*?)<\/script>/, "JSON embarqué introuvable");
    assert.ok(json.indexOf("<") === -1, "aucun « < » dans le JSON embarqué");
    assert.deepStrictEqual(JSON.parse(json), schema);
    // Le pilote entier, aussi.
    const pilote = JSON.parse(fs.readFileSync(SCHEMA_PILOTE, "utf8"));
    const page = atelier.construirePage(pilote);
    assert.deepStrictEqual(JSON.parse(extraire(page, /id="schema-apercu">([\s\S]*?)<\/script>/, "JSON embarqué introuvable")), pilote);
});

cas("T8 : la page charge moteur/rendu.js et jamais script.js ; la bannière est hors de #form-bilan", () => {
    const html = atelier.construirePage(JSON.parse(fs.readFileSync(SCHEMA_PILOTE, "utf8")));
    assert.ok(html.indexOf("<script src=\"moteur/rendu.js\">") !== -1);
    const sources = (html.match(/<script[^>]*\ssrc="[^"]*"/g) || []).map(function (b) { return /src="([^"]*)"/.exec(b)[1]; });
    assert.deepStrictEqual(sources, ["moteur/rendu.js"], "le seul script externe est le moteur (ni script.js, ni jsPDF, ni html2canvas)");
    const banniere = html.indexOf("Aperçu d'atelier — ce n'est pas le PDF");
    assert.ok(banniere !== -1, "bannière absente");
    assert.ok(banniere < html.indexOf("id=\"form-bilan\""), "la bannière doit précéder #form-bilan, non l'habiter");
    assert.ok(html.indexOf("id=\"largeur-fenetre\"") !== -1, "largeur de la fenêtre absente");
});

/* ======================= T9 — l'aperçu, exécuté ============================ */

/** Le double de DOM d'une page d'aperçu : ce que le script de la page et le moteur utilisent. */
function creerPage(html, largeur) {
    const base = dom.creerDocument();
    const noeuds = {};
    const ecouteurs = {};
    const document = Object.assign(base, {
        getElementById(id) { return noeuds[id] || null; },
        addEventListener(nom, f) { (ecouteurs[nom] = ecouteurs[nom] || []).push(f); },
        removeEventListener(nom, f) { ecouteurs[nom] = (ecouteurs[nom] || []).filter(function (x) { return x !== f; }); },
        ecouteurs: ecouteurs,
        declencher(nom) { (ecouteurs[nom] || []).slice().forEach(function (f) { f(); }); }
    });
    const main = document.createElement("main");
    const formulaire = Object.assign(document.createElement("div"), {
        querySelector(selecteur) { return selecteur === "main" ? main : null; }
    });
    noeuds["form-bilan"] = formulaire;
    ["largeur-fenetre", "erreurs-apercu", "schema-apercu"].forEach(function (id) { noeuds[id] = document.createElement("x"); });
    noeuds["schema-apercu"].textContent = extraire(html, /id="schema-apercu">([\s\S]*?)<\/script>/, "JSON embarqué introuvable");
    const appels = { fetch: 0, ecouteursFenetre: {} };
    const contexte = {
        console: { warn() {}, error() {}, log() {} },
        document: document,
        window: { innerWidth: largeur, addEventListener(nom, f) { appels.ecouteursFenetre[nom] = f; } },
        fetch() { appels.fetch += 1; return Promise.reject(new Error("fetch interdit")); }
    };
    vm.createContext(contexte);
    return { contexte: contexte, document: document, main: main, noeuds: noeuds, appels: appels };
}

/** Joue la page : le moteur d'abord (comme `<script src>`), puis le script inline qu'on relit dans le HTML. */
function jouerPage(html, largeur) {
    const page = creerPage(html, largeur);
    vm.runInContext(fs.readFileSync(CHEMIN_MOTEUR, "utf8"), page.contexte, { filename: "rendu.js" });
    page.ecouteursAvant = (page.document.ecouteurs.DOMContentLoaded || []).length;
    const script = extraire(html, /<script id="script-apercu">\n([\s\S]*?)\n<\/script>/, "script de la page introuvable");
    vm.runInContext(script, page.contexte, { filename: "apercu-atelier.html" });
    return page;
}

cas("T9 : l'aperçu exécuté ne fait aucun fetch et retire demarrerMoteur ; le <main> égale l'instantané du pilote", () => {
    const composition = composeur.composer(RECETTE_COMPLETE);
    assert.deepStrictEqual(composition.refus, []);
    const html = atelier.construirePage(composition.schema);
    const page = jouerPage(html, 1234);

    assert.strictEqual(page.ecouteursAvant, 1, "rendu.js doit avoir inscrit demarrerMoteur (sinon le test est vide)");
    assert.strictEqual(typeof page.contexte.demarrerMoteur, "function");
    assert.deepStrictEqual(page.document.ecouteurs.DOMContentLoaded, [], "demarrerMoteur doit être retiré");
    page.document.declencher("DOMContentLoaded");
    assert.strictEqual(page.appels.fetch, 0, "aucun fetch ne doit partir");

    // Windows peut extraire le fichier en CRLF (autocrlf) : on compare le contenu, pas les fins de ligne.
    const attendu = fs.readFileSync(INSTANTANE, "utf8").replace(/\r\n/g, "\n");
    const obtenu = JSON.stringify(dom.serialiser(page.main), null, 1) + "\n";
    assert.ok(obtenu === attendu, "le <main> rendu diffère de tests/donnees/rendu-schema-production.txt");
    assert.strictEqual(page.noeuds["largeur-fenetre"].textContent, "1234", "largeur affichée");
    assert.strictEqual(page.noeuds["erreurs-apercu"].hidden, undefined, "aucune erreur affichée");
    // Au redimensionnement, la largeur suit.
    page.contexte.window.innerWidth = 801;
    page.appels.ecouteursFenetre.resize();
    assert.strictEqual(page.noeuds["largeur-fenetre"].textContent, "801");
});

cas("T9 : un schéma refusé par le moteur affiche ses erreurs sous la bannière et ne touche pas au <main>", () => {
    const html = atelier.construirePage({ version_schema: 99, blocs: [] });
    const page = jouerPage(html, 1000);
    assert.strictEqual(page.noeuds["erreurs-apercu"].hidden, false, "la zone d'erreurs doit être montrée");
    assert.ok(page.noeuds["erreurs-apercu"].textContent.length > 0, "les erreurs du moteur doivent être écrites");
    assert.deepStrictEqual(page.main.enfants, [], "le <main> ne doit pas être touché");
    assert.strictEqual(page.appels.fetch, 0);
});

cas("T9 : apercu refuse un schéma que le moteur refuse, et n'écrit alors rien", () => {
    const travail = preparer("t9c");
    fs.writeFileSync(path.join(travail, "schema.json"), JSON.stringify({ version_schema: 1, blocs: [] }));
    assert.ok(atelier.apercu(travail).length > 0);
    assert.ok(!fs.existsSync(path.join(travail, "apercu-atelier.html")));
    assert.strictEqual(lancer(["apercu", travail]).code, 1);
});

/* ==================== Aucune dépendance, aucun port ========================= */

cas("l'atelier n'importe que fs, path, url, child_process et composer-schema.js, n'ouvre aucun port", () => {
    const source = fs.readFileSync(CHEMIN_ATELIER, "utf8");
    const requis = (source.match(/require\("[^"]+"\)/g) || []).map(function (r) { return r.slice(9, -2); }).sort();
    assert.deepStrictEqual(requis, ["../composer-schema.js", "child_process", "fs", "path", "url"]);
    assert.ok(!/require\("(http|https|net|tls|dgram)"\)|\.listen\(/.test(source), "l'atelier ouvre un port");
    assert.ok(!/^\s*assert\b/m.test(source), "pas d'assert dans l'outil : un refus est un message");
});

/* ==================== T10 — le filet : rien dans le dépôt ================== */

cas("T10 : git status est identique avant et après la suite ; les schémas du pilote sont intacts", () => {
    assert.strictEqual(gitPorcelaine(), etatDepot.porcelaine, "la suite a laissé des traces dans le dépôt");
    assert.strictEqual(sha256(SCHEMA_PILOTE), etatDepot.pilote);
    assert.strictEqual(sha256(SCHEMA_MIROIR), etatDepot.miroir);
    assert.strictEqual(etatDepot.pilote, etatDepot.miroir, "le miroir doit rester égal au schéma du client");
});

/* ================================== Bilan =================================== */

racinesCreees.forEach(function (dossier) {
    try { fs.rmSync(dossier, { recursive: true, force: true }); } catch (erreur) { /* le système nettoiera */ }
});

console.log("\n" + nbCas + " cas joués, " + echecs.length + " en échec" +
    (nbSautes > 0 ? ", " + nbSautes + " sous-cas SAUTÉ(S) annoncé(s)" : "") + ".");
if (echecs.length > 0) {
    console.log("En échec :\n  - " + echecs.join("\n  - "));
    process.exit(1);
}
console.log("Tout est vert.");
