#!/usr/bin/env node
/*
 * Composition d'un schéma de formulaire à partir de fragments (contrat C1-T5).
 *
 * OUTIL D'ATELIER : il tourne sur le poste de l'opérateur, jamais chez un
 * client, et ne voyage dans aucun paquet (`outils/faire-paquet.sh` copie une
 * liste fermée). Le formulaire de la tablette reçoit un `schema.json` complet,
 * comme avant : le moteur n'apprend pas à « inclure » un fichier à l'exécution.
 *
 *     node outils/composer-schema.js <recette.json>
 *         écrit le schéma composé sur la sortie standard (code 0), ou rien et
 *         les refus sur l'erreur standard (code 1) ;
 *     node outils/composer-schema.js <recette.json> --sortie <fichier>
 *         l'écrit dans un fichier NEUF (refus s'il existe) et jamais sous
 *         formulaire/ : le miroir du pilote n'est pas écrit par l'outil ;
 *     node outils/composer-schema.js --verifier <schema.json>
 *         valide un schéma complet (code 0 ou 1).
 *
 * Une recette (`templates/<nom>.json`) nomme des fragments (`blocs/<nom>.json`),
 * résolus dans `blocs/` uniquement. Formats : blocs/LISEZMOI.md et
 * templates/LISEZMOI.md.
 *
 * Validation : le VRAI moteur (`formulaire/moteur/rendu.js`, chargé en `vm`),
 * jamais une réécriture de ses règles. Un avertissement du moteur (attribut
 * facultatif inconnu, simplement ignoré à l'exécution) est ICI un refus : à
 * l'atelier, un attribut inconnu est une faute de frappe, et le laisser passer
 * livrerait un champ muet.
 *
 * Node nu : `fs`, `path`, `vm` et rien d'autre (aucun `npm ci` en CI).
 * Les fonctions `composer`, `verifier` et `lireFragment` sont exportées pour
 * l'atelier de C9-T2 et pour tests/test_blocs.js. Aucun `assert` : un refus est
 * un message accumulé, jamais une exception.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RACINE = path.join(__dirname, "..");
const DOSSIER_BLOCS = path.join(RACINE, "blocs");
const DOSSIER_FORMULAIRE = path.join(RACINE, "formulaire");
const CHEMIN_MOTEUR = path.join(DOSSIER_FORMULAIRE, "moteur", "rendu.js");

// Un nom de fragment ne peut contenir ni « / », ni « \ », ni « . » : il ne peut
// donc ni remonter d'un dossier ni désigner un autre dossier que blocs/.
const MOTIF_NOM_FRAGMENT = /^[a-z0-9]+(-[a-z0-9]+)*$/;

const CLES_FRAGMENT = ["version_fragment", "description", "blocs"];
const CLES_RECETTE = ["version_recette", "description", "version_schema", "fragments"];

/* ============================== Petits outils ============================== */

function estObjet(valeur) {
    return valeur !== null && typeof valeur === "object" && !Array.isArray(valeur);
}

/** Les clés de `objet` hors de `permises`, puis les clés de `permises` absentes. */
function ecartDeCles(objet, permises) {
    const cles = Object.keys(objet);
    return {
        inconnues: cles.filter(function (c) { return permises.indexOf(c) === -1; }),
        absentes: permises.filter(function (c) { return cles.indexOf(c) === -1; })
    };
}

function refusDeCles(objet, permises, etiquette) {
    const refus = [];
    const ecart = ecartDeCles(objet, permises);
    if (ecart.inconnues.length > 0) {
        refus.push(etiquette + " : clé(s) inconnue(s) refusée(s) : " + ecart.inconnues.join(", "));
    }
    if (ecart.absentes.length > 0) {
        refus.push(etiquette + " : clé(s) obligatoire(s) absente(s) : " + ecart.absentes.join(", "));
    }
    return refus;
}

/** Le texte JSON d'un fichier, sans jamais lever : `{ valeur }` ou `{ refus }`. */
function lireJson(chemin, etiquette) {
    let texte;
    try {
        texte = fs.readFileSync(chemin, "utf8");
    } catch (erreur) {
        return { refus: [etiquette + " : lecture impossible (" + erreur.code + ")."] };
    }
    try {
        return { valeur: JSON.parse(texte) };
    } catch (erreur) {
        return { refus: [etiquette + " : ce n'est pas du JSON (" + erreur.message + ")."] };
    }
}

function serialiser(schema) {
    return JSON.stringify(schema, null, 2) + "\n";
}

/* ================================= Moteur ================================== */

/**
 * Le moteur de rendu chargé en `vm`, avec un `console` dont `warn` collecte.
 * Sans `document` : le seul accès au DOM au niveau module du moteur est gardé.
 * Le moteur est lu à chaque appel de vérification, pas mis en cache : l'outil
 * est un processus court, et un cache survivrait à un moteur modifié en cours
 * de session d'atelier.
 */
function chargerMoteur() {
    const avertissements = [];
    const console = {
        warn: function () { avertissements.push(Array.prototype.join.call(arguments, " ")); },
        log: function () {},
        error: function () {}
    };
    const contexte = { console: console };
    vm.createContext(contexte);
    vm.runInContext(fs.readFileSync(CHEMIN_MOTEUR, "utf8"), contexte, { filename: "rendu.js" });
    if (typeof contexte.validerSchema !== "function") {
        throw new Error("validerSchema n'est pas exportée par formulaire/moteur/rendu.js.");
    }
    return { moteur: contexte, avertissements: avertissements };
}

/* ============================= Vérification ================================ */

/**
 * Valide un schéma COMPLET et rend la liste des refus (vide si valide) :
 * refus du moteur, avertissements du moteur (refus à l'atelier), et existence
 * sur disque de chaque image annotable. Le moteur ne contrôle que la FORME du
 * chemin d'une image (`cheminImageAutorise`), jamais son existence : un fichier
 * absent donnerait au cabinet une image vide, le lendemain matin.
 *
 * `options.dossierFormulaire` (défaut : formulaire/) sert aux tests.
 */
function verifier(schema, options) {
    const dossierFormulaire = (options && options.dossierFormulaire) || DOSSIER_FORMULAIRE;
    const charge = chargerMoteur();
    const refus = [];

    Array.from(charge.moteur.validerSchema(schema)).forEach(function (r) { refus.push(String(r)); });
    charge.avertissements.forEach(function (a) { refus.push("avertissement du moteur (refusé à l'atelier) : " + a); });

    if (estObjet(schema) && Array.isArray(schema.blocs)) {
        schema.blocs.forEach(function (bloc, indexBloc) {
            if (!estObjet(bloc) || !Array.isArray(bloc.champs)) return;
            bloc.champs.forEach(function (champ, indexChamp) {
                if (!estObjet(champ) || champ.type !== "image-annotable" || typeof champ.fichier !== "string") return;
                // Un chemin que le moteur a refusé est déjà dans `refus` ; on ne le
                // résout pas : il pourrait sortir de formulaire/.
                if (champ.fichier.indexOf("..") !== -1 || path.isAbsolute(champ.fichier)) return;
                const cible = path.join(dossierFormulaire, champ.fichier);
                let existe = false;
                try { existe = fs.statSync(cible).isFile(); } catch (erreur) { existe = false; }
                if (!existe) {
                    refus.push("bloc " + indexBloc + ", champ " + indexChamp + " : l'image « " + champ.fichier +
                        " » n'existe pas sous formulaire/.");
                }
            });
        });
    }
    return refus;
}

/** Valide le fichier d'un schéma complet : `{ refus, schema }`. */
function verifierFichier(chemin, options) {
    const lu = lireJson(chemin, "schéma « " + chemin + " »");
    if (lu.refus) return { refus: lu.refus, schema: null };
    return { refus: verifier(lu.valeur, options), schema: lu.valeur };
}

/* ================================ Fragments ================================ */

/**
 * Lit `blocs/<nom>.json` et rend `{ refus, fragment }`. Contrôle : nom conforme
 * au motif, fichier réel (`lstat` : un lien symbolique est refusé, il pourrait
 * pointer hors de blocs/), clés fermées, version, description, blocs.
 * `dossierBlocs` (défaut : blocs/) sert aux tests.
 */
function lireFragment(nom, dossierBlocs) {
    const dossier = dossierBlocs || DOSSIER_BLOCS;
    if (typeof nom !== "string" || !MOTIF_NOM_FRAGMENT.test(nom)) {
        return { refus: ["nom de fragment refusé (attendu : minuscules, chiffres et tirets, sans chemin ni point) : " +
            JSON.stringify(nom)], fragment: null };
    }
    const chemin = path.join(dossier, nom + ".json");
    const etiquette = "fragment « " + nom + " »";

    let infos;
    try {
        infos = fs.lstatSync(chemin);
    } catch (erreur) {
        return { refus: [etiquette + " : introuvable dans blocs/."], fragment: null };
    }
    if (infos.isSymbolicLink() || !infos.isFile()) {
        return { refus: [etiquette + " : ce n'est pas un fichier ordinaire (lien symbolique refusé)."], fragment: null };
    }

    const lu = lireJson(chemin, etiquette);
    if (lu.refus) return { refus: lu.refus, fragment: null };
    const fragment = lu.valeur;
    if (!estObjet(fragment)) return { refus: [etiquette + " : la racine doit être un objet JSON."], fragment: null };

    const refus = refusDeCles(fragment, CLES_FRAGMENT, etiquette);
    if ("version_fragment" in fragment && fragment.version_fragment !== 1) {
        refus.push(etiquette + " : version_fragment doit valoir 1.");
    }
    if ("description" in fragment && (typeof fragment.description !== "string" || fragment.description.trim() === "")) {
        refus.push(etiquette + " : description doit être une phrase non vide.");
    }
    if ("blocs" in fragment && (!Array.isArray(fragment.blocs) || fragment.blocs.length === 0)) {
        refus.push(etiquette + " : blocs doit être une liste non vide.");
    }
    return { refus: refus, fragment: refus.length === 0 ? fragment : null };
}

/* ================================= Recette ================================= */

/**
 * Compose une recette : `{ refus, schema, texte }`. `texte` est le schéma
 * sérialisé comme les schémas des clients (`JSON.stringify(…, null, 2)` + LF),
 * ce qui permet de redonner un schéma existant à l'octet. En cas de refus,
 * `schema` et `texte` sont `null`.
 *
 * `options` (tests) : `dossierBlocs`, `dossierFormulaire`.
 */
function composer(cheminRecette, options) {
    const opts = options || {};
    const lu = lireJson(cheminRecette, "recette « " + path.basename(String(cheminRecette)) + " »");
    if (lu.refus) return { refus: lu.refus, schema: null, texte: null };
    const recette = lu.valeur;
    if (!estObjet(recette)) return { refus: ["recette : la racine doit être un objet JSON."], schema: null, texte: null };

    const refus = refusDeCles(recette, CLES_RECETTE, "recette");
    if ("version_recette" in recette && recette.version_recette !== 1) {
        refus.push("recette : version_recette doit valoir 1.");
    }
    if ("description" in recette && (typeof recette.description !== "string" || recette.description.trim() === "")) {
        refus.push("recette : description doit être une phrase non vide.");
    }
    if ("version_schema" in recette && !Number.isInteger(recette.version_schema)) {
        refus.push("recette : version_schema doit être un entier.");
    }
    const blocs = [];
    if ("fragments" in recette) {
        if (!Array.isArray(recette.fragments) || recette.fragments.length === 0) {
            refus.push("recette : fragments doit être une liste non vide de noms.");
        } else {
            const vus = new Set();
            recette.fragments.forEach(function (nom) {
                if (vus.has(nom)) refus.push("recette : fragment « " + String(nom) + " » cité deux fois.");
                vus.add(nom);
                const lecture = lireFragment(nom, opts.dossierBlocs);
                lecture.refus.forEach(function (r) { refus.push(r); });
                if (lecture.fragment) lecture.fragment.blocs.forEach(function (b) { blocs.push(b); });
            });
        }
    }
    if (refus.length > 0) return { refus: refus, schema: null, texte: null };

    const schema = { version_schema: recette.version_schema, blocs: blocs };
    const refusSchema = verifier(schema, { dossierFormulaire: opts.dossierFormulaire });
    if (refusSchema.length > 0) return { refus: refusSchema, schema: null, texte: null };
    return { refus: [], schema: schema, texte: serialiser(schema) };
}

/* ================================ Écriture ================================= */

/**
 * Le dossier `dossier` est-il formulaire/ ou l'un de ses sous-dossiers ? Compare
 * l'IDENTITÉ des dossiers (périphérique + inœud) en remontant les ancêtres, et
 * non des chaînes de caractères : un lien symbolique vers formulaire/, une
 * casse différente sur un disque insensible à la casse, un `..` ne trompent
 * pas une comparaison d'inœuds.
 */
function estSousFormulaire(dossier, dossierFormulaire) {
    const reference = fs.statSync(dossierFormulaire, { bigint: true });
    let courant = fs.realpathSync(dossier);
    for (;;) {
        const infos = fs.statSync(courant, { bigint: true });
        if (infos.dev === reference.dev && infos.ino === reference.ino) return true;
        const parent = path.dirname(courant);
        if (parent === courant) return false;
        courant = parent;
    }
}

/**
 * Écrit `texte` dans un fichier NEUF. Rend la liste des refus (vide si écrit).
 * Drapeau `wx` : le pilote (`clients/cabinet-01/schema.json`) ne peut pas être
 * écrasé, ni un fichier quelconque, ni via un lien symbolique (O_EXCL ne suit
 * pas les liens).
 */
function ecrireSortie(cheminSortie, texte, options) {
    const dossierFormulaire = (options && options.dossierFormulaire) || DOSSIER_FORMULAIRE;
    const parent = path.dirname(path.resolve(cheminSortie));
    let parentExiste = false;
    try { parentExiste = fs.statSync(parent).isDirectory(); } catch (erreur) { parentExiste = false; }
    if (!parentExiste) return ["--sortie : le dossier parent n'existe pas (l'outil n'en crée aucun)."];
    if (estSousFormulaire(parent, dossierFormulaire)) {
        return ["--sortie : écriture sous formulaire/ refusée (le miroir du pilote n'est jamais écrit par cet outil)."];
    }
    try {
        fs.writeFileSync(path.resolve(cheminSortie), texte, { flag: "wx" });
    } catch (erreur) {
        if (erreur.code === "EEXIST") return ["--sortie : le fichier existe déjà, refus de l'écraser."];
        return ["--sortie : écriture impossible (" + erreur.code + ")."];
    }
    return [];
}

/* ============================== Ligne de commande ========================== */

function resume(schema) {
    const champs = schema.blocs.reduce(function (somme, bloc) { return somme + bloc.champs.length; }, 0);
    return schema.blocs.length + " blocs, " + champs + " champs";
}

function refuser(refus) {
    refus.forEach(function (r) { process.stderr.write("REFUS : " + r + "\n"); });
    process.exitCode = 1;
}

function utilisation() {
    process.stderr.write(
        "Usage :\n" +
        "  node outils/composer-schema.js <recette.json> [--sortie <fichier>]\n" +
        "  node outils/composer-schema.js --verifier <schema.json>\n");
    process.exitCode = 2;
}

function principal(argv) {
    if (argv.length === 2 && argv[0] === "--verifier") {
        const resultat = verifierFichier(argv[1]);
        if (resultat.refus.length > 0) return refuser(resultat.refus);
        process.stderr.write("Schéma valide (" + resume(resultat.schema) + ").\n");
        return;
    }
    const positionnels = [];
    let sortie = null;
    for (let i = 0; i < argv.length; i += 1) {
        if (argv[i] === "--sortie") {
            if (sortie !== null || i + 1 >= argv.length) return utilisation();
            sortie = argv[i + 1];
            i += 1;
        } else if (argv[i].indexOf("--") === 0) {
            return utilisation();
        } else {
            positionnels.push(argv[i]);
        }
    }
    if (positionnels.length !== 1) return utilisation();

    const resultat = composer(positionnels[0]);
    if (resultat.refus.length > 0) return refuser(resultat.refus);
    if (sortie !== null) {
        const refusEcriture = ecrireSortie(sortie, resultat.texte);
        if (refusEcriture.length > 0) return refuser(refusEcriture);
        process.stderr.write("Schéma écrit (" + resume(resultat.schema) + ").\n");
        return;
    }
    process.stdout.write(resultat.texte);
    process.stderr.write("Schéma composé (" + resume(resultat.schema) + ").\n");
}

module.exports = { composer: composer, verifier: verifier, lireFragment: lireFragment, estSousFormulaire: estSousFormulaire,
    ecartDeCles: ecartDeCles, CLES_RECETTE: CLES_RECETTE };

if (require.main === module) {
    principal(process.argv.slice(2));
}
