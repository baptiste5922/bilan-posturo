/*
 * Le dernier filet de `demarrerMoteur()`, exécuté pour de vrai (constat
 * élevé, audit C1-T3b) : la coquille charge DEUX scripts
 * (`moteur/rendu.js` puis `script.js`), chacun retéléchargé à chaque
 * ouverture (`Cache-Control: no-store`, `serveur/serveur.py:400`). Si
 * `formulaire/script.js` manque ou arrive tronqué alors que `rendu.js` et
 * `schema.json` arrivent intacts, `rendre()` réussit — mais
 * `demarrerApplication` et `annoncer` (toutes deux définies par ce même
 * fichier manquant) n'existent pas. Ce test reproduit précisément ce cas et
 * vérifie que le message de repli reste visible. Avant le correctif,
 * `#attente-moteur.remove()` s'exécutait avant toute vérification de
 * `demarrerApplication` : le formulaire avait l'air normal et ne disait
 * rien, alors qu'aucun brouillon ni dessin ni export ne fonctionnait.
 *
 * Double de DOM dédié, écrit dans ce fichier : celui de
 * `tests/outils/dom-minimal.js` n'expose délibérément ni
 * `getElementById`, ni `querySelector`, ni `remove()` — exactement ce dont
 * `demarrerMoteur()` a besoin pour se brancher sur la coquille, mais que
 * `rendre()` n'a pas le droit d'utiliser (voir l'en-tête de ce fichier).
 * Aucune dépendance : pas de `jsdom`.
 *
 *     node tests/test_demarrage_moteur.js
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const CHEMIN_MOTEUR = path.join(__dirname, "..", "formulaire", "moteur", "rendu.js");
const CHEMIN_SCHEMA = path.join(__dirname, "..", "formulaire", "schema.json");

/* ============================ Double de DOM ============================ */

function creerNoeudTexte(valeur) {
    return { genre: "texte", valeur: String(valeur) };
}

function texteDe(noeud) {
    if (noeud.genre === "texte") return noeud.valeur;
    return (noeud.enfants || []).map(texteDe).join("");
}

function creerElement(balise) {
    const attributs = new Map();
    const enfants = [];
    let hidden = false;

    const noeud = {
        genre: "element",
        balise: String(balise),
        enfants,
        parent: null,

        appendChild(enfant) {
            if (enfant.genre === "fragment") {
                enfant.enfants.forEach(function (e) { e.parent = noeud; enfants.push(e); });
                enfant.enfants.length = 0;
            } else {
                enfant.parent = noeud;
                enfants.push(enfant);
            }
            return enfant;
        },
        setAttribute(nom, valeur) { attributs.set(nom, String(valeur)); },
        getAttribute(nom) { return attributs.has(nom) ? attributs.get(nom) : null; },
        classList: { add() {} },
        // Suffisant pour ce fichier précis : premier descendant de la
        // balise demandée, en profondeur — demarrerMoteur() n'appelle
        // jamais que `querySelector("main")`.
        querySelector(baliseCherchee) {
            const pile = enfants.slice();
            while (pile.length) {
                const n = pile.shift();
                if (n.genre === "element" && n.balise === baliseCherchee) return n;
                if (n.enfants) pile.push.apply(pile, n.enfants);
            }
            return null;
        },
        remove() {
            if (noeud.parent) {
                const i = noeud.parent.enfants.indexOf(noeud);
                if (i !== -1) noeud.parent.enfants.splice(i, 1);
            }
        },
        get hidden() { return hidden; },
        set hidden(valeur) { hidden = !!valeur; }
    };

    Object.defineProperty(noeud, "textContent", {
        get() { return texteDe(noeud); },
        set(valeur) {
            enfants.length = 0;
            enfants.push(creerNoeudTexte(valeur));
        }
    });

    return noeud;
}

function creerFragment() {
    const enfants = [];
    return {
        genre: "fragment",
        enfants,
        appendChild(enfant) {
            if (enfant.genre === "fragment") {
                enfant.enfants.forEach(function (e) { enfants.push(e); });
                enfant.enfants.length = 0;
            } else {
                enfants.push(enfant);
            }
            return enfant;
        }
    };
}

function chercherParId(noeud, id) {
    if (noeud.genre === "element" && noeud.getAttribute("id") === id) return noeud;
    for (const enfant of (noeud.enfants || [])) {
        const trouve = chercherParId(enfant, id);
        if (trouve) return trouve;
    }
    return null;
}

/** Reconstitue le strict nécessaire de la coquille : #form-bilan > main > #attente-moteur. */
function construireCoquille() {
    const formBilan = creerElement("div");
    formBilan.setAttribute("id", "form-bilan");
    formBilan.setAttribute("data-moteur", "");
    const main = creerElement("main");
    const attente = creerElement("p");
    attente.setAttribute("id", "attente-moteur");
    attente.textContent = "Chargement du formulaire… Si rien ne s'affiche après "
        + "quelques secondes, utilisez le favori « Formulaire — secours V1 » "
        + "(adresse : index-v1.html) pour continuer la consultation.";
    main.appendChild(attente);
    formBilan.appendChild(main);
    return { formBilan, main, attente };
}

function creerDocument(racine) {
    return {
        createElement: creerElement,
        createTextNode: creerNoeudTexte,
        createDocumentFragment: creerFragment,
        getElementById(id) { return chercherParId(racine, id); },
        addEventListener() {} // ne jamais déclencher DOMContentLoaded tout seul ici
    };
}

/* ============================ Chargement du moteur ============================ */

/**
 * Charge `rendu.js` dans un contexte neuf, avec un `fetch` simulé et, selon
 * `avecScriptJs`, un `annoncer`/`demarrerApplication` simulant la présence
 * ou l'absence de `formulaire/script.js`. `demarrerMoteur` n'est jamais
 * appelée par le chargement lui-même (`addEventListener` est un no-op) :
 * chaque scénario l'appelle explicitement, puis attend la chaîne de
 * promesses avant d'inspecter le DOM.
 */
function chargerMoteur(reponseFetch, avecScriptJs) {
    const contexte = { console };
    vm.createContext(contexte);

    const coquille = construireCoquille();
    contexte.document = creerDocument(coquille.formBilan);
    contexte.fetch = function () { return reponseFetch(); };

    let demarrerApplicationAppelee = false;
    const messagesAnnonces = [];
    if (avecScriptJs) {
        contexte.annoncer = function (message, type, persistant) {
            messagesAnnonces.push({ message, type, persistant });
        };
        contexte.demarrerApplication = function () { demarrerApplicationAppelee = true; };
    }
    // Sinon (formulaire/script.js absent) : `annoncer` et
    // `demarrerApplication` restent indéfinies dans ce contexte, exactement
    // comme elles le seraient dans un vrai navigateur si ce fichier n'avait
    // jamais chargé.

    vm.runInContext(fs.readFileSync(CHEMIN_MOTEUR, "utf-8"), contexte, { filename: "rendu.js" });

    return {
        contexte, coquille, messagesAnnonces,
        applicationDemarree() { return demarrerApplicationAppelee; }
    };
}

function schemaValide() {
    return JSON.parse(fs.readFileSync(CHEMIN_SCHEMA, "utf-8"));
}

/** Laisse la chaîne de promesses de demarrerMoteur() se résoudre entièrement. */
function attendreResolution() {
    return new Promise(function (resolve) { setTimeout(resolve, 0); })
        .then(function () { return new Promise(function (resolve) { setTimeout(resolve, 0); }); })
        .then(function () { return new Promise(function (resolve) { setTimeout(resolve, 0); }); });
}

async function scenarioNominal() {
    const etat = chargerMoteur(function () {
        return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve(schemaValide()); } });
    }, true);
    etat.contexte.demarrerMoteur();
    await attendreResolution();

    assert.strictEqual(etat.applicationDemarree(), true,
        "scénario nominal : demarrerApplication() doit avoir été appelée");
    assert.strictEqual(chercherParId(etat.coquille.formBilan, "attente-moteur"), null,
        "scénario nominal : #attente-moteur doit avoir été retiré");
    console.log("1. scénario nominal : #attente-moteur retiré, demarrerApplication() appelée");
}

async function scenarioScriptJsAbsent() {
    // LE constat élevé : schéma valide, rendu réussi, mais
    // formulaire/script.js absent (demarrerApplication et annoncer
    // indéfinies). #attente-moteur NE DOIT PAS disparaître, et doit rester
    // un message visible nommant le favori et l'adresse.
    const etat = chargerMoteur(function () {
        return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve(schemaValide()); } });
    }, false);
    etat.contexte.demarrerMoteur();
    await attendreResolution();

    const attente = chercherParId(etat.coquille.formBilan, "attente-moteur");
    assert.notStrictEqual(attente, null,
        "formulaire/script.js absent : #attente-moteur a été retiré alors que l'application n'a jamais démarré " +
        "(régression du constat élevé, audit C1-T3b)");
    assert.strictEqual(attente.hidden, false,
        "formulaire/script.js absent : #attente-moteur ne doit pas être masqué");
    assert.ok(/secours V1/.test(attente.textContent) && /index-v1\.html/.test(attente.textContent),
        "formulaire/script.js absent : le message restant doit nommer le favori et l'adresse " +
        "(trouvé : « " + attente.textContent + " »)");
    // Les 28 blocs ont bien été rendus (rendre() a réussi) : ce n'est donc
    // pas un schéma refusé qui explique le message, et sans le correctif le
    // formulaire aurait l'air fonctionnel.
    assert.ok(etat.coquille.main.enfants.length > 1,
        "le rendu du schéma doit avoir eu lieu malgré l'absence de formulaire/script.js");
    console.log("2. formulaire/script.js absent : #attente-moteur reste affiché, favori et adresse nommés");
}

async function scenarioMessageNommeFavoriEtAdresse() {
    // Faible (audit C1-T3b) : rien ne garantissait que le message émis par
    // afficherErreurMoteur() (via annoncer(), donc formulaire/script.js
    // présent) nomme toujours le favori ET l'adresse — seul le message
    // STATIQUE du HTML l'était (tests/test_comparaison_dom.js). Schéma
    // refusé : script.js est bien présent (annoncer existe), mais le rendu
    // échoue quand même.
    const schemaRefuse = { version_schema: 2, blocs: [{ cle: "x", champs: [] }] };
    const etat = chargerMoteur(function () {
        return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve(schemaRefuse); } });
    }, true);
    etat.contexte.demarrerMoteur();
    await attendreResolution();

    assert.strictEqual(etat.messagesAnnonces.length, 1,
        "schéma refusé : afficherErreurMoteur() doit avoir annoncé exactement un message");
    const message = etat.messagesAnnonces[0].message;
    assert.ok(/secours V1/.test(message) && /index-v1\.html/.test(message),
        "le message annoncé par afficherErreurMoteur() doit nommer le favori ET l'adresse " +
        "(trouvé : « " + message + " »)");
    assert.strictEqual(etat.messagesAnnonces[0].persistant, true,
        "le message de repli doit être persistant (ne pas disparaître seul)");
    console.log("3. schéma refusé : le message annoncé nomme le favori « secours V1 » et l'adresse index-v1.html");
}

/**
 * Scénario 4 — `script.js` absent ET #form-bilan introuvable : les deux
 * premiers canaux d'`afficherErreurMoteur()` tombent ensemble, puisque
 * #attente-moteur habite précisément le conteneur disparu et qu'`annoncer`
 * vient de `script.js`. C'est le chemin n°9 du réaudit C1-T3b. Le troisième
 * canal, #zone-messages, vit hors de #form-bilan (`index.html:67`) : c'est lui
 * qui doit parler. Un filet ne doit pas dépendre de ce qu'il surveille.
 */
async function scenarioAucunConteneurNiScriptJs() {
    const zone = creerElement("div");
    zone.setAttribute("id", "zone-messages");
    zone.hidden = true;

    const contexte = { console: { error() {}, warn() {} } };
    vm.createContext(contexte);
    // Ni #form-bilan, ni <main>, ni #attente-moteur : seul #zone-messages répond.
    contexte.document = {
        createElement: creerElement,
        createTextNode: creerNoeudTexte,
        createDocumentFragment: creerFragment,
        getElementById(id) { return id === "zone-messages" ? zone : null; },
        addEventListener() {}
    };
    contexte.fetch = function () { return Promise.reject(new Error("rien ne charge")); };
    // `annoncer` et `demarrerApplication` restent indéfinies : script.js absent.
    vm.runInContext(fs.readFileSync(CHEMIN_MOTEUR, "utf-8"), contexte, { filename: "rendu.js" });

    contexte.demarrerMoteur();
    await attendreResolution();

    const texte = zone.textContent || "";
    assert.ok(texte.length > 0 && zone.hidden === false,
        "aucun conteneur et pas de script.js : le message de repli doit paraître dans "
        + "#zone-messages, qui vit hors de #form-bilan — sinon la page reste muette "
        + "(chemin n°9, réaudit C1-T3b)");
    assert.ok(/secours V1/.test(texte) && /index-v1\.html/.test(texte),
        "ce dernier message doit lui aussi nommer le favori ET l'adresse "
        + "(trouvé : « " + texte + " »)");
    console.log("4. aucun conteneur et pas de script.js : #zone-messages porte le message, hors du conteneur surveillé");
}

(async function () {
    try {
        await scenarioNominal();
        await scenarioScriptJsAbsent();
        await scenarioMessageNommeFavoriEtAdresse();
        await scenarioAucunConteneurNiScriptJs();
        console.log("\nTout est vert.");
    } catch (erreur) {
        console.error("ÉCHEC :", erreur.message);
        process.exitCode = 1;
    }
})();
