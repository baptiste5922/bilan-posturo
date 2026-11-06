#!/usr/bin/env node
/*
 * Atelier de composition d'un client (contrat C9-T2).
 *
 * OUTIL D'ATELIER : il tourne sur le poste de l'opérateur, jamais chez un
 * client, et ne voyage dans aucun paquet. Il fabrique un client dans un
 * DOSSIER DE TRAVAIL HORS DU DÉPÔT, une commande par étape :
 *
 *     node outils/atelier/atelier.js ouvrir   <travail> --recette <recette.json>
 *     node outils/atelier/atelier.js composer <travail>
 *     node outils/atelier/atelier.js verifier <travail>
 *     node outils/atelier/atelier.js apercu   <travail>
 *
 * Procédure et disposition du dossier : outils/atelier/LISEZMOI.md.
 *
 * Aucune règle n'est recopiée ici (« dériver du code, jamais transcrire ») :
 * le schéma est jugé par le VRAI moteur (via composer-schema.js), les clés du
 * bloc `cabinet`, la règle du logo et le critère « praticien renseigné » par le
 * VRAI serveur (outils/atelier/lire_serveur.py, qui l'importe), les marqueurs de
 * nommage par le VRAI formulaire (formulaire/script.js, lu à l'exécution).
 *
 * Confidentialité : l'atelier manipule l'identité et le logo d'un client réel,
 * qui ne doivent jamais entrer dans un dépôt public. Toute écriture passe par
 * `ecrireDansTravail` (ou `creerDossier*`) : liste fermée de noms, refus de
 * tout dossier dont un ancêtre réel est la racine du dépôt (identité
 * périphérique + inœud, comme composer-schema.js), création exclusive `wx`,
 * refus des liens. Aucun port n'est ouvert, aucune dépendance npm.
 *
 * Node nu. Aucun `assert` : un refus est un message, jamais une exception.
 */

const fs = require("fs");
const path = require("path");
const url = require("url");
const childProcess = require("child_process");
const composerSchema = require("../composer-schema.js");

const RACINE_DEPOT = path.join(__dirname, "..", "..");
const CHEMIN_AUXILIAIRE = path.join(__dirname, "lire_serveur.py");

// Les seuls noms que l'atelier écrit dans un dossier de travail. Une liste
// fermée : un nom venu d'ailleurs (« ../x », un chemin absolu) n'y figure pas.
const NOMS_ECRITS = ["recette.json", "schema.json", "identite-cabinet.json", "apercu-atelier.html"];
// Le seul fichier réécrit à chaque commande ; tous les autres sont neufs ou rien.
const NOMS_REMPLACABLES = ["apercu-atelier.html"];
// Les seuls sous-dossiers créés, dans cet ordre (mkdir non récursif).
const SOUS_DOSSIERS = ["images", "images/cabinet"];

// La ligne de formulaire/script.js qui définit les marqueurs de
// `convention_nommage` : ancrée, et qui doit se retrouver EXACTEMENT une fois.
// Sans cela, `verifier` refuse (source illisible) plutôt que de deviner.
const MOTIF_LIGNE_MARQUEURS = /^[ \t]*const marqueurs = \{([^}]*)\};[ \t\r]*$/gm;

/* ============================== Petits outils ============================== */

function estObjet(valeur) {
    return valeur !== null && typeof valeur === "object" && !Array.isArray(valeur);
}

function serialiser(valeur) {
    return JSON.stringify(valeur, null, 2) + "\n";
}

function racineDuDepot(options) {
    return (options && options.racineDepot) || RACINE_DEPOT;
}

/* ================================ Auxiliaire =============================== */

let cachePython = null;

/**
 * Cherche un interpréteur qui sait lancer l'auxiliaire. Ordre :
 * `ATELIER_PYTHON`, `python3`, `python`. Le premier qui rend du JSON valide et
 * le code 0 gagne : sous Windows, `python3` peut être l'amorce du Store (code
 * 9009), qu'on saute sans rien en conclure. `options.candidats` (tests).
 * Rend `{ commande, defauts }` ou `{ refus }`.
 */
function trouverPython(options) {
    const imposes = options && options.candidats;
    if (!imposes && cachePython) return cachePython;
    const candidats = imposes || [process.env.ATELIER_PYTHON, "python3", "python"];
    for (let i = 0; i < candidats.length; i += 1) {
        const commande = candidats[i];
        if (!commande) continue;
        const essai = childProcess.spawnSync(commande, ["-I", "-B", CHEMIN_AUXILIAIRE, "defauts"],
            { encoding: "utf8", windowsHide: true });
        if (essai.error || essai.status !== 0) continue;
        let defauts;
        try { defauts = JSON.parse(essai.stdout); } catch (erreur) { continue; }
        if (!estObjet(defauts) || !Array.isArray(defauts.cles)) continue;
        const trouve = { commande: commande, defauts: defauts };
        if (!imposes) cachePython = trouve;
        return trouve;
    }
    return { refus: ["aucun interpréteur Python utilisable (essayés : ATELIER_PYTHON, python3, python) : " +
        "l'atelier lit les clés et la règle du logo dans serveur/serveur.py, il ne les recopie pas."] };
}

/** Le verdict du serveur sur l'identité : `{ valeur }` ou `{ refus }`. */
function jugerIdentite(python, cheminIdentite, travail) {
    const essai = childProcess.spawnSync(python.commande,
        ["-I", "-B", CHEMIN_AUXILIAIRE, "identite", cheminIdentite, travail],
        { encoding: "utf8", windowsHide: true });
    if (essai.error || essai.status !== 0) {
        return { refus: ["identite-cabinet.json : illisible pour l'auxiliaire du serveur (code " + essai.status + ")."] };
    }
    try {
        return { valeur: JSON.parse(essai.stdout) };
    } catch (erreur) {
        return { refus: ["l'auxiliaire du serveur n'a pas rendu de JSON."] };
    }
}

/* ============================ Garde d'écriture ============================= */

/**
 * Refus de confinement d'un dossier EXISTANT : vide s'il est hors du dépôt.
 * Ferme sur l'incertitude : si l'identité des ancêtres ne peut pas être établie,
 * on refuse (ce qu'on ne peut pas prouver hors du dépôt n'est pas écrit).
 */
function refusConfinement(dossier, options) {
    try {
        if (composerSchema.estSousFormulaire(dossier, racineDuDepot(options))) {
            return ["écriture refusée : le dossier de travail est dans le dépôt (ou le dépôt lui-même). " +
                "Un client se fabrique HORS du dépôt public."];
        }
    } catch (erreur) {
        return ["écriture refusée : impossible d'établir que le dossier de travail est hors du dépôt (" +
            erreur.code + ")."];
    }
    return [];
}

/** Le dossier réel d'un dossier de travail existant : `{ dossier }` ou `{ refus }`. */
function dossierReel(travail) {
    try {
        const reel = fs.realpathSync(travail);
        if (!fs.statSync(reel).isDirectory()) return { refus: ["le dossier de travail n'est pas un dossier."] };
        return { dossier: reel };
    } catch (erreur) {
        return { refus: ["dossier de travail introuvable (" + erreur.code + ")."] };
    }
}

/**
 * LA voie d'écriture de fichiers : rend la liste des refus (vide si écrit).
 * Nom dans la liste fermée ; dossier hors du dépôt ; création exclusive (`wx`,
 * qui ne suit pas un lien et n'écrase rien). `options.remplacer`, réservé à
 * `apercu-atelier.html` : le fichier existant doit être ordinaire (`lstat` : un
 * lien est refusé), il est supprimé puis recréé en `wx`.
 * `options.racineDepot` (tests) remplace la racine réelle du dépôt.
 */
function ecrireDansTravail(travail, nom, contenu, options) {
    const opts = options || {};
    if (typeof nom !== "string" || NOMS_ECRITS.indexOf(nom) === -1) {
        return ["écriture refusée : « " + String(nom) + " » ne figure pas dans la liste fermée des fichiers de l'atelier."];
    }
    if (opts.remplacer && NOMS_REMPLACABLES.indexOf(nom) === -1) {
        return ["écriture refusée : « " + nom + " » ne se remplace pas (création exclusive seulement)."];
    }
    const lu = dossierReel(travail);
    if (lu.refus) return lu.refus;
    const refus = refusConfinement(lu.dossier, opts);
    if (refus.length > 0) return refus;

    const cible = path.join(lu.dossier, nom);
    if (opts.remplacer) {
        let infos = null;
        try {
            infos = fs.lstatSync(cible);
        } catch (erreur) {
            if (erreur.code !== "ENOENT") return ["« " + nom + " » : lecture impossible (" + erreur.code + ")."];
        }
        if (infos) {
            if (!infos.isFile()) {
                return ["« " + nom + " » n'est pas un fichier ordinaire (lien refusé) : il n'est pas remplacé."];
            }
            try {
                fs.unlinkSync(cible);
            } catch (erreur) {
                return ["« " + nom + " » : suppression impossible (" + erreur.code + ")."];
            }
        }
    }
    try {
        fs.writeFileSync(cible, contenu, { flag: "wx" });
    } catch (erreur) {
        if (erreur.code === "EEXIST") {
            return ["« " + nom + " » existe déjà : refus de l'écraser (le retoucher, ou l'effacer à la main)."];
        }
        return ["« " + nom + " » : écriture impossible (" + erreur.code + ")."];
    }
    return [];
}

/**
 * Crée UN dossier, non récursivement : son parent doit exister et être hors du
 * dépôt. Même contrôle que `ecrireDansTravail`, pour les deux seuls `mkdir` de
 * l'atelier (le dossier de travail, puis ses sous-dossiers). Rend les refus.
 */
function creerDossier(chemin, options) {
    const absolu = path.resolve(chemin);
    const parent = dossierReel(path.dirname(absolu));
    if (parent.refus) return ["le dossier parent doit exister (l'atelier ne crée aucun dossier intermédiaire)."];
    const refus = refusConfinement(parent.dossier, options);
    if (refus.length > 0) return refus;
    try {
        fs.mkdirSync(path.join(parent.dossier, path.basename(absolu)));
    } catch (erreur) {
        if (erreur.code === "EEXIST") return ["le dossier existe déjà : refus de réutiliser un dossier de travail."];
        return ["création du dossier impossible (" + erreur.code + ")."];
    }
    return [];
}

/** Crée un sous-dossier de la liste fermée (`images`, puis `images/cabinet`). */
function creerSousDossier(travail, relatif, options) {
    if (SOUS_DOSSIERS.indexOf(relatif) === -1) {
        return ["création refusée : « " + String(relatif) + " » ne figure pas dans la liste fermée des dossiers."];
    }
    return creerDossier(path.join(travail, relatif.split("/").join(path.sep)), options);
}

/* ================================== ouvrir ================================= */

function ouvrir(travail, cheminRecette, options) {
    const python = trouverPython(options);
    if (python.refus) return python.refus;

    // La recette est lue AVANT toute création : un chemin faux ne laisse pas
    // un dossier à moitié ouvert.
    let recette;
    try {
        recette = fs.readFileSync(cheminRecette);
    } catch (erreur) {
        return ["recette illisible (" + erreur.code + ")."];
    }

    let refus = creerDossier(travail, options);
    if (refus.length > 0) return refus;
    // Octet pour octet, comme `cp` : la recette de départ n'est pas reformatée.
    refus = ecrireDansTravail(travail, "recette.json", recette, options);
    if (refus.length > 0) return refus;

    const identite = {};
    python.defauts.cles.forEach(function (cle) { identite[cle] = python.defauts.defauts[cle]; });
    refus = ecrireDansTravail(travail, "identite-cabinet.json", serialiser(identite), options);
    if (refus.length > 0) return refus;

    for (let i = 0; i < SOUS_DOSSIERS.length; i += 1) {
        refus = creerSousDossier(travail, SOUS_DOSSIERS[i], options);
        if (refus.length > 0) return refus;
    }
    return [];
}

/* ================================= composer ================================ */

/** Rend `{ refus, schema }` ; écrit `schema.json` en création exclusive. */
function composer(travail, options) {
    const lu = dossierReel(travail);
    if (lu.refus) return { refus: lu.refus, schema: null };
    const resultat = composerSchema.composer(path.join(lu.dossier, "recette.json"), options);
    if (resultat.refus.length > 0) return { refus: resultat.refus, schema: null };
    const refus = ecrireDansTravail(travail, "schema.json", resultat.texte, options);
    return { refus: refus, schema: refus.length === 0 ? resultat.schema : null };
}

/* ================================= verifier ================================ */

/** Les marqueurs de `convention_nommage`, lus dans le formulaire : `{ marqueurs }` ou `{ refus }`. */
function lireMarqueurs(cheminScript) {
    let source;
    try {
        source = fs.readFileSync(cheminScript, "utf8");
    } catch (erreur) {
        return { refus: ["source illisible : formulaire/script.js (" + erreur.code + ")."] };
    }
    const lignes = source.match(MOTIF_LIGNE_MARQUEURS) || [];
    if (lignes.length !== 1) {
        return { refus: ["source illisible : la définition des marqueurs de nommage est introuvable ou ambiguë dans " +
            "formulaire/script.js (" + lignes.length + " occurrence(s) au lieu d'une) ; l'atelier ne devine pas."] };
    }
    const interieur = new RegExp(MOTIF_LIGNE_MARQUEURS.source, "m").exec(lignes[0])[1];
    const marqueurs = [];
    const motifCle = /(?:^|,)\s*(\w+)\s*:/g;
    let trouve;
    while ((trouve = motifCle.exec(interieur)) !== null) marqueurs.push(trouve[1]);
    if (marqueurs.length === 0) return { refus: ["source illisible : aucun marqueur lisible dans formulaire/script.js."] };
    return { marqueurs: marqueurs };
}

function refusConvention(convention, marqueurs) {
    const refus = [];
    const motif = /\{([^{}]*)\}/g;
    let trouve;
    while ((trouve = motif.exec(convention)) !== null) {
        if (marqueurs.indexOf(trouve[1]) === -1) {
            refus.push("convention_nommage : le marqueur « {" + trouve[1] + "} » est inconnu du formulaire " +
                "(connus : " + marqueurs.map(function (m) { return "{" + m + "}"; }).join(", ") + ").");
        }
    }
    if (/[{}]/.test(convention.replace(/\{[^{}]*\}/g, ""))) {
        refus.push("convention_nommage : accolade isolée (un marqueur s'écrit {nom}).");
    }
    return refus;
}

function aFaireGrille(schema) {
    if (!estObjet(schema) || !Array.isArray(schema.blocs)) return false;
    return schema.blocs.some(function (bloc) {
        return estObjet(bloc) && Array.isArray(bloc.champs) &&
            bloc.champs.some(function (champ) { return estObjet(champ) && champ.type === "grille"; });
    });
}

function lireJsonTravail(dossier, nom) {
    let texte;
    try {
        texte = fs.readFileSync(path.join(dossier, nom), "utf8");
    } catch (erreur) {
        return { refus: ["« " + nom + " » : lecture impossible (" + erreur.code + ")."] };
    }
    try {
        return { valeur: JSON.parse(texte) };
    } catch (erreur) {
        // Le message de JSON.parse peut citer un extrait du contenu : on ne le
        // reprend pas, l'identité d'un client ne doit pas circuler.
        return { refus: ["« " + nom + " » : ce n'est pas du JSON valide."] };
    }
}

/**
 * Vérifie un dossier de travail : `{ refus, afaire, schema }`. Rien n'est
 * écrit. `options.cheminScript` (tests) remplace formulaire/script.js.
 */
function verifierTravail(travail, options) {
    const opts = options || {};
    const refus = [];
    const afaire = [];
    const lu = dossierReel(travail);
    if (lu.refus) return { refus: lu.refus, afaire: afaire, schema: null };

    // Le schéma, par le vrai moteur.
    const lectureSchema = lireJsonTravail(lu.dossier, "schema.json");
    let schema = null;
    if (lectureSchema.refus) {
        refus.push(lectureSchema.refus[0] + " Lancer « composer » d'abord.");
    } else {
        schema = lectureSchema.valeur;
        composerSchema.verifier(schema).forEach(function (r) { refus.push("schéma : " + r); });
        if (aFaireGrille(schema)) {
            afaire.push("le schéma contient une grille, que cet outil n'éprouve pas : trois conditions " +
                "(docs/schema-formulaire.md, section des grilles) dont un export d'essai sur la tablette du client, " +
                "à sa largeur (refus au-delà de 1 192 px ; coupure entre deux pages sous ~735 px de fenêtre).");
        }
    }

    // L'identité, par le vrai serveur.
    const python = trouverPython(opts);
    if (python.refus) {
        python.refus.forEach(function (r) { refus.push(r); });
    } else {
        const lectureIdentite = lireJsonTravail(lu.dossier, "identite-cabinet.json");
        if (lectureIdentite.refus) {
            refus.push(lectureIdentite.refus[0]);
        } else if (!estObjet(lectureIdentite.valeur)) {
            refus.push("« identite-cabinet.json » : la racine doit être un objet JSON.");
        } else {
            const identite = lectureIdentite.valeur;
            const cles = python.defauts.cles;
            const presentes = Object.keys(identite);
            const enTrop = presentes.filter(function (c) { return cles.indexOf(c) === -1; });
            const absentes = cles.filter(function (c) { return presentes.indexOf(c) === -1; });
            // Seules les CLÉS sont nommées, jamais une valeur.
            if (enTrop.length > 0) refus.push("identité : clé(s) en trop : " + enTrop.join(", ") + ".");
            if (absentes.length > 0) refus.push("identité : clé(s) absente(s) : " + absentes.join(", ") + ".");
            const pasChaines = cles.filter(function (c) { return c in identite && typeof identite[c] !== "string"; });
            if (pasChaines.length > 0) refus.push("identité : valeur(s) qui ne sont pas des chaînes : " + pasChaines.join(", ") + ".");

            const verdict = jugerIdentite(python, path.join(lu.dossier, "identite-cabinet.json"), lu.dossier);
            if (verdict.refus) {
                verdict.refus.forEach(function (r) { refus.push(r); });
            } else {
                if (!verdict.valeur.praticien_renseigne && typeof identite.praticien === "string") {
                    refus.push("identité : « praticien » est vide (l'export serait refusé au cabinet).");
                }
                const motifLogo = verdict.valeur.logo[1];
                if (motifLogo) {
                    refus.push("identité : le logo est refusé par le serveur (motif « " + motifLogo + " »). " +
                        "Un logo se pose sous images/cabinet/ du dossier de travail, ou « logo » est laissé vide.");
                } else if (identite.logo === python.defauts.logo_par_defaut) {
                    afaire.push("le logo est celui du pilote (« " + identite.logo + " ») : confirmer avec la " +
                        "feuille de route du client (section 1) qu'il n'en a pas d'autre.");
                }
            }

            // La convention de nommage, contre les marqueurs du vrai formulaire.
            if (typeof identite.convention_nommage === "string") {
                const marqueurs = lireMarqueurs(opts.cheminScript || path.join(RACINE_DEPOT, "formulaire", "script.js"));
                if (marqueurs.refus) {
                    marqueurs.refus.forEach(function (r) { refus.push(r); });
                } else {
                    refusConvention(identite.convention_nommage, marqueurs.marqueurs).forEach(function (r) { refus.push(r); });
                }
            }
        }
    }

    // Rappel permanent : aucun mécanisme ne livre la palette d'un client (D-O2).
    afaire.push("la palette est celle du pilote (cinq couleurs de formulaire/style.css) : la palette propre " +
        "au client n'est livrée par aucun outil (D-O2).");
    return { refus: refus, afaire: afaire, schema: schema };
}

/* ================================== apercu ================================= */

function echapperAttribut(texte) {
    return String(texte).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Le script de la page : retire le démarrage normal du moteur (qui ferait un
// `fetch("schema.json")` et démarrerait script.js), puis rend le schéma
// embarqué. Une seule chaîne, relue telle quelle par les tests.
const SCRIPT_APERCU = [
    "(function () {",
    "    \"use strict\";",
    "    // rendu.js a inscrit demarrerMoteur sur DOMContentLoaded : on le retire",
    "    // aussitôt, sans quoi un fetch partirait et script.js serait attendu.",
    "    if (typeof demarrerMoteur === \"function\") {",
    "        document.removeEventListener(\"DOMContentLoaded\", demarrerMoteur);",
    "    }",
    "    function montrerLargeur() {",
    "        var cible = document.getElementById(\"largeur-fenetre\");",
    "        if (cible) cible.textContent = String(window.innerWidth);",
    "    }",
    "    function montrerErreurs(lignes) {",
    "        var zone = document.getElementById(\"erreurs-apercu\");",
    "        if (!zone) return;",
    "        zone.textContent = lignes.join(\"\\n\");",
    "        zone.hidden = false;",
    "    }",
    "    montrerLargeur();",
    "    window.addEventListener(\"resize\", montrerLargeur);",
    "    if (typeof rendre !== \"function\") {",
    "        montrerErreurs([\"Le moteur (moteur/rendu.js) n'a pas chargé.\"]);",
    "        return;",
    "    }",
    "    var zoneRendu = document.getElementById(\"form-bilan\").querySelector(\"main\");",
    "    var schema;",
    "    try {",
    "        schema = JSON.parse(document.getElementById(\"schema-apercu\").textContent);",
    "    } catch (erreur) {",
    "        montrerErreurs([\"Le schéma embarqué est illisible.\"]);",
    "        return;",
    "    }",
    "    var resultat = rendre(schema, document, zoneRendu);",
    "    if (!resultat.ok) {",
    "        montrerErreurs(resultat.erreurs.map(String));",
    "    }",
    "})();"
].join("\n");

/**
 * La page d'aperçu, en HTML statique : le vrai moteur et la vraie feuille de
 * style sont chargés EN LECTURE depuis formulaire/ du dépôt (`<base href>`),
 * jamais `script.js` (effets au chargement : /cabinet, brouillon, IndexedDB).
 * Le schéma est embarqué en JSON, tout `<` écrit `\u003c` : un libellé venu d'un
 * tiers ne referme jamais la balise `<script>`.
 * `options.dossierFormulaire` (tests) remplace formulaire/.
 */
function construirePage(schema, options) {
    const dossierFormulaire = (options && options.dossierFormulaire) || path.join(RACINE_DEPOT, "formulaire");
    const base = url.pathToFileURL(dossierFormulaire).href.replace(/\/*$/, "/");
    const json = JSON.stringify(schema).replace(/</g, "\\u003c");
    return [
        "<!DOCTYPE html>",
        "<html lang=\"fr\">",
        "<head>",
        "<meta charset=\"UTF-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
        "<meta name=\"robots\" content=\"noindex, nofollow\">",
        "<base href=\"" + echapperAttribut(base) + "\">",
        "<title>Aperçu d'atelier</title>",
        "<link rel=\"stylesheet\" href=\"style.css\">",
        "<style>",
        "#bandeau-atelier { position: sticky; top: 0; z-index: 10; padding: 8px 12px; background: #fff3cd;",
        "  color: #2b2b2b; border-bottom: 2px solid #b8860b; font: 14px/1.4 sans-serif; }",
        "#erreurs-apercu { margin: 8px 12px; padding: 8px; background: #f8d7da; color: #721c24;",
        "  white-space: pre-wrap; font: 13px/1.4 monospace; }",
        "</style>",
        "</head>",
        "<body>",
        "<div id=\"bandeau-atelier\" role=\"note\">",
        "<strong>Aperçu d'atelier — ce n'est pas le PDF.</strong> Largeur de la fenêtre : " +
            "<span id=\"largeur-fenetre\">?</span> px.<br>",
        "Limites : pas d'en-tête du cabinet, pas de stylet, pas de PDF, pas de pagination. La largeur compte " +
            "(grilles : refus au-delà de 1 192 px, coupure sous ~735 px) : ouvrir à la largeur relevée sur la tablette du client.",
        "</div>",
        "<pre id=\"erreurs-apercu\" hidden></pre>",
        "<div id=\"form-bilan\"><main></main></div>",
        "<script type=\"application/json\" id=\"schema-apercu\">" + json + "</script>",
        "<script src=\"moteur/rendu.js\"></script>",
        "<script id=\"script-apercu\">",
        SCRIPT_APERCU,
        "</script>",
        "</body>",
        "</html>",
        ""
    ].join("\n");
}

/** Écrit `apercu-atelier.html` ; refuse si le schéma est refusé. Rend les refus. */
function apercu(travail, options) {
    const lu = dossierReel(travail);
    if (lu.refus) return lu.refus;
    const lectureSchema = lireJsonTravail(lu.dossier, "schema.json");
    if (lectureSchema.refus) return [lectureSchema.refus[0] + " Lancer « composer » d'abord."];
    const refusSchema = composerSchema.verifier(lectureSchema.valeur);
    if (refusSchema.length > 0) return refusSchema.map(function (r) { return "schéma : " + r; });
    return ecrireDansTravail(travail, "apercu-atelier.html", construirePage(lectureSchema.valeur, options),
        Object.assign({}, options, { remplacer: true }));
}

/* ============================== Ligne de commande ========================== */

function ecrireRefus(refus) {
    refus.forEach(function (r) { process.stderr.write("REFUS : " + r + "\n"); });
}

function utilisation() {
    process.stderr.write(
        "Usage :\n" +
        "  node outils/atelier/atelier.js ouvrir   <travail> --recette <recette.json>\n" +
        "  node outils/atelier/atelier.js composer <travail>\n" +
        "  node outils/atelier/atelier.js verifier <travail>\n" +
        "  node outils/atelier/atelier.js apercu   <travail>\n" +
        "<travail> : un dossier HORS du dépôt, neuf pour « ouvrir ». Voir outils/atelier/LISEZMOI.md.\n");
    return 2;
}

/** Exécute une commande ; rend le code de sortie (0, 1 refus, 2 usage). */
function principal(argv, options) {
    const commande = argv[0];
    const reste = argv.slice(1);
    if (commande === "ouvrir") {
        const positionnels = [];
        let recette = null;
        for (let i = 0; i < reste.length; i += 1) {
            if (reste[i] === "--recette") {
                if (recette !== null || i + 1 >= reste.length) return utilisation();
                recette = reste[i + 1];
                i += 1;
            } else if (reste[i].indexOf("--") === 0) {
                return utilisation();
            } else {
                positionnels.push(reste[i]);
            }
        }
        if (positionnels.length !== 1 || recette === null) return utilisation();
        const refus = ouvrir(positionnels[0], recette, options);
        if (refus.length > 0) { ecrireRefus(refus); return 1; }
        process.stderr.write("Dossier de travail ouvert : recette.json, identite-cabinet.json, images/cabinet/. " +
            "Étape suivante : « composer ».\n");
        return 0;
    }
    if (["composer", "verifier", "apercu"].indexOf(commande) === -1 || reste.length !== 1) return utilisation();

    if (commande === "composer") {
        const resultat = composer(reste[0], options);
        if (resultat.refus.length > 0) { ecrireRefus(resultat.refus); return 1; }
        process.stderr.write("Schéma composé : schema.json (" + resultat.schema.blocs.length + " blocs). " +
            "Le retoucher à la main, puis « verifier ».\n");
        return 0;
    }
    if (commande === "verifier") {
        const resultat = verifierTravail(reste[0], options);
        ecrireRefus(resultat.refus);
        resultat.afaire.forEach(function (a) { process.stderr.write("À FAIRE : " + a + "\n"); });
        if (resultat.refus.length > 0) return 1;
        process.stderr.write("Dossier de travail valide (" + resultat.schema.blocs.length + " blocs).\n");
        return 0;
    }
    const refus = apercu(reste[0], options);
    if (refus.length > 0) { ecrireRefus(refus); return 1; }
    process.stderr.write("Aperçu écrit : apercu-atelier.html (ce n'est pas le PDF ; ouvrir à la largeur de la tablette du client).\n");
    return 0;
}

module.exports = {
    ouvrir: ouvrir,
    composer: composer,
    verifierTravail: verifierTravail,
    apercu: apercu,
    construirePage: construirePage,
    ecrireDansTravail: ecrireDansTravail,
    refusConfinement: refusConfinement,
    creerDossier: creerDossier,
    creerSousDossier: creerSousDossier,
    trouverPython: trouverPython,
    lireMarqueurs: lireMarqueurs,
    principal: principal,
    SCRIPT_APERCU: SCRIPT_APERCU,
    NOMS_ECRITS: NOMS_ECRITS
};

if (require.main === module) {
    process.exitCode = principal(process.argv.slice(2));
}
