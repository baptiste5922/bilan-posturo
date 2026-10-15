/*
 * Comparaison automatisée V1 ↔ moteur (contrat C1-T3, critère 2), plus les
 * chemins de refus du validateur (critère 6) et l'ajout d'un champ sans
 * JavaScript (critère 5).
 *
 * Portée de cette passe (étapes 1 à 8 seulement, voir le compte rendu de la
 * tâche) : `formulaire/index.html` reste la V1 intacte — il n'y a pas encore
 * de coquille ni d'`index-v1.html`. La comparaison lit donc `#form-bilan`
 * directement dans `formulaire/index.html`, et reconstitue côté moteur un
 * conteneur équivalent : l'en-tête recopié tel quel depuis
 * `formulaire/index-moteur.html` (vérifié identique à celui d'`index.html`)
 * suivi des 28 blocs rendus par `formulaire/moteur/rendu.js` à partir de
 * `formulaire/schema.json`. Les deux côtés comptent ainsi 29 blocs, comme
 * l'exige le critère 2.
 *
 * Aucune dépendance : pas de `jsdom` (indisponible en intégration continue,
 * aucun `npm ci` n'y est exécuté). Le DOM des deux côtés est le double de
 * `tests/outils/dom-minimal.js` ; le HTML de la V1 est lu par un petit
 * analyseur ad hoc écrit plus bas (balises, attributs, texte), suffisant
 * pour ce fichier précis — ce n'est pas un analyseur HTML général.
 *
 *     node tests/test_comparaison_dom.js
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const dom = require("./outils/dom-minimal.js");

const CHEMIN_HTML = path.join(__dirname, "..", "formulaire", "index.html");
const CHEMIN_INDEX_MOTEUR = path.join(__dirname, "..", "formulaire", "index-moteur.html");
const CHEMIN_MOTEUR = path.join(__dirname, "..", "formulaire", "moteur", "rendu.js");
const CHEMIN_SCHEMA = path.join(__dirname, "..", "formulaire", "schema.json");

function lireNormalise(chemin) {
    return fs.readFileSync(chemin, "utf-8").replace(/\r\n/g, "\n");
}

/* ============================ Mini-analyseur HTML ============================ */
/*
 * Construit, à partir d'un fragment de HTML bien formé (celui de ce dépôt,
 * écrit à la main, sans commentaire ni CDATA à l'intérieur de #form-bilan),
 * un arbre dans le double DOM de `tests/outils/dom-minimal.js` — le même
 * type de nœud que celui que produit `rendre()`, pour pouvoir comparer les
 * deux côtés avec les mêmes fonctions de projection.
 */

const BALISES_VIDES = new Set(["img", "input", "br", "meta", "link", "hr"]);

function analyserAttributs(texte) {
    const motif = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
    const attributs = [];
    let m;
    while ((m = motif.exec(texte)) !== null) {
        if (!m[1]) continue;
        const valeur = m[2] !== undefined ? m[2] : (m[3] !== undefined ? m[3] : (m[4] !== undefined ? m[4] : ""));
        attributs.push([m[1], valeur]);
    }
    return attributs;
}

/** Retourne les nœuds racines (frères) décrits par `html`, construits via `document`. */
function analyserHtml(document, html) {
    const motifTag = /<(\/?)([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^<>]*?)?)\s*(\/?)\s*>/g;
    const racine = [];
    const pile = [];

    function parent() { return pile.length ? pile[pile.length - 1] : null; }
    function ajouter(noeud) {
        const p = parent();
        if (p) p.appendChild(noeud); else racine.push(noeud);
    }

    let dernierIndex = 0;
    let m;
    while ((m = motifTag.exec(html)) !== null) {
        if (m.index > dernierIndex) {
            const texte = html.slice(dernierIndex, m.index);
            if (texte !== "") ajouter(document.createTextNode(texte));
        }
        dernierIndex = motifTag.lastIndex;

        const fermeture = m[1] === "/";
        const balise = m[2].toLowerCase();
        const autoFerme = m[4] === "/";

        if (fermeture) {
            for (let i = pile.length - 1; i >= 0; i--) {
                if (pile[i].balise === balise) { pile.length = i; break; }
            }
            continue;
        }

        const element = document.createElement(balise);
        analyserAttributs(m[3] || "").forEach(function (paire) {
            element.setAttribute(paire[0], paire[1]);
        });
        ajouter(element);

        if (!autoFerme && !BALISES_VIDES.has(balise)) {
            pile.push(element);
        }
    }
    if (dernierIndex < html.length) {
        const texte = html.slice(dernierIndex);
        if (texte !== "") ajouter(document.createTextNode(texte));
    }
    return racine;
}

/** Extrait, par comptage de profondeur, le fragment `<BALISE ...>…</BALISE>` qui
 *  commence à la première occurrence de `debutLitteral`. */
function extraireElement(html, debutLitteral, balise) {
    const debut = html.indexOf(debutLitteral);
    if (debut === -1) {
        throw new Error("fragment introuvable : " + debutLitteral);
    }
    const motif = new RegExp("<(/?)" + balise + "\\b[^>]*>", "g");
    motif.lastIndex = debut;
    let profondeur = 0;
    let m;
    while ((m = motif.exec(html)) !== null) {
        if (m[1] === "/") {
            profondeur--;
            if (profondeur === 0) return html.slice(debut, motif.lastIndex);
        } else {
            profondeur++;
        }
    }
    throw new Error("balise fermante correspondante introuvable pour : " + debutLitteral);
}

/* ============================ Projection (critère 2) ============================ */

function classesDe(noeud) {
    const c = noeud.getAttribute("class");
    return c ? c.split(/\s+/).filter(Boolean) : [];
}

function texteDe(noeud) {
    if (noeud.genre === "texte") return noeud.valeur;
    return noeud.enfants.map(texteDe).join("");
}

function normaliserTexte(texte) {
    if (texte === null || texte === undefined) return null;
    return texte
        .replace(/&nbsp;/gi, " ")
        .replace(/ /g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/:$/, "")
        .trim();
}

function memesEnsembles(a, b) {
    const sa = JSON.stringify([...new Set(a)].sort());
    const sb = JSON.stringify([...new Set(b)].sort());
    return sa === sb;
}

/**
 * Tous les éléments dont la classe contient "bloc", en ordre de document,
 * avec la chaîne de leurs ancêtres (de `racine` exclue jusqu'au parent
 * direct, dans cet ordre). Sans cette chaîne, une divergence de
 * positionnement dans l'arbre — un bloc sorti de `<main>`, par exemple —
 * est invisible à la comparaison : c'est le constat n°1 de l'audit C1-T3
 * (`main { padding: 10px }`, `style.css:23`, perdu si le fragment du
 * moteur atterrit après `</main>` plutôt que dedans).
 */
function collecterBlocsAvecAncetres(racine) {
    const resultats = [];
    (function marcher(noeud, pile) {
        if (noeud.genre !== "element") return;
        if (classesDe(noeud).includes("bloc")) {
            resultats.push({ noeud: noeud, ancetres: pile.slice() });
        }
        noeud.enfants.forEach(function (enfant) { marcher(enfant, pile.concat([noeud])); });
    })(racine, []);
    return resultats;
}

/**
 * Tolérance (i), au même titre que (f)/(g)/(h) : `<section id="consultation">`
 * est le seul ancêtre du HTML V1 sans aucun effet CSS ni JS — aucun
 * sélecteur ne le cible (`grep -n "consultation" formulaire/style.css
 * formulaire/script.js` ne rend que des commentaires sans rapport). Il
 * enveloppe les blocs 3 à 29 sans y ajouter de mise en page ; le moteur ne
 * le reproduit pas et place ces blocs en enfants directs de `<main>`. Sans
 * ce filtre, la comparaison des ancêtres échouerait sur une différence de
 * profondeur sans aucune conséquence réelle — ce que la tolérance (f) fait
 * déjà pour la balise de `patient_infos`, en plus étroit.
 */
function filtrerAncetresInertes(chaine) {
    return chaine.filter(function (n) {
        return !(n.balise === "section" && n.getAttribute("id") === "consultation");
    });
}

function decrireChaineAncetres(chaine) {
    return chaine.map(function (n) {
        return { balise: n.balise, id: n.getAttribute("id"), classes: classesDe(n).sort() };
    });
}

/** Détails d'un bloc-tableau (les deux `<table>` du formulaire) : titre de
 *  la première colonne d'en-tête, texte des autres en-têtes, et nom de
 *  chaque ligne — tout ce que la comparaison générale des champs ne voit
 *  jamais, puisqu'elle ne s'applique pas aux blocs `<table>` (constat n°2,
 *  audit C1-T3). */
function enfantsDirects(noeud, balise) {
    return noeud.enfants.filter(function (n) { return n.genre === "element" && n.balise === balise; });
}

function extraireDetailsTable(table) {
    const thead = enfantsDirects(table, "thead")[0];
    const tbody = enfantsDirects(table, "tbody")[0];
    const trEntete = thead ? enfantsDirects(thead, "tr")[0] : null;
    const thsEntete = trEntete ? enfantsDirects(trEntete, "th") : [];
    const titre = thsEntete.length ? normaliserTexte(texteDe(thsEntete[0])) : null;
    const entetes = thsEntete.slice(1).map(function (th) { return normaliserTexte(texteDe(th)); });
    const lignes = (tbody ? enfantsDirects(tbody, "tr") : []).map(function (tr) {
        const tds = enfantsDirects(tr, "td");
        return tds.length ? normaliserTexte(texteDe(tds[0])) : null;
    });
    return { titre: titre, entetes: entetes, lignes: lignes };
}

function contientEntreeSaisie(noeud) {
    if (noeud.genre !== "element") return false;
    if (["input", "textarea", "select"].includes(noeud.balise)) return true;
    return noeud.enfants.some(contientEntreeSaisie);
}

/**
 * Le titre d'un bloc : un <h3>/<label> enfant direct, sans `for`, qui
 * n'enveloppe pas lui-même un champ (ce qui le distinguerait d'un libellé de
 * case/radio) et dont le texte n'est pas vide — exclut le `<label
 * class="checkbox-label-simple"></label>` vide qui précède « Usées » dans
 * les blocs "chaussures" (anomalie non cataloguée du HTML V1, sans effet
 * visuel ni fonctionnel, mais que ce critère de recherche attraperait sinon
 * à tort comme un titre de bloc).
 */
function extraireTitreBloc(bloc) {
    const candidat = bloc.enfants.find(function (n) {
        if (n.genre !== "element") return false;
        if (n.balise !== "h3" && n.balise !== "label") return false;
        if (n.getAttribute("for")) return false;
        if (contientEntreeSaisie(n)) return false;
        return normaliserTexte(texteDe(n)) !== "";
    });
    return candidat ? normaliserTexte(texteDe(candidat)) : null;
}

function indexerLabelsPourAttribut(racine) {
    const index = new Map();
    (function marcher(n) {
        if (n.genre !== "element") return;
        if (n.balise === "label") {
            const pourId = n.getAttribute("for");
            if (pourId) index.set(pourId, normaliserTexte(texteDe(n)));
        }
        n.enfants.forEach(marcher);
    })(racine);
    return index;
}

/**
 * Les champs de saisie (input/textarea/select) d'un bloc, en ordre de
 * document, avec leur libellé associé : l'enveloppe <label> la plus proche
 * d'abord, le `for` sinon. L'enveloppe prime parce qu'un `for` peut, par
 * défaut du HTML V1, désigner le titre du bloc plutôt que le champ lui-même
 * (bloc 5 « Déjà SO: », dont le `<label for="SO_oui">` est le titre du bloc,
 * pas le libellé propre de l'option « Oui ») — l'enveloppe, elle, n'a jamais
 * cette ambiguïté : un `<label class="radio-label">` ne contient qu'une
 * seule option.
 */
function collecterChamps(bloc) {
    const labelsParFor = indexerLabelsPourAttribut(bloc);
    const champs = [];

    (function marcher(noeud, pile) {
        if (noeud.genre !== "element") return;
        if (["input", "textarea", "select"].includes(noeud.balise)) {
            const id = noeud.getAttribute("id");
            let libelle = null;
            for (let i = pile.length - 1; i >= 0; i--) {
                if (pile[i].balise === "label") {
                    libelle = normaliserTexte(texteDe(pile[i]));
                    break;
                }
            }
            if (libelle === null && id && labelsParFor.has(id)) {
                libelle = labelsParFor.get(id);
            }
            champs.push({
                balise: noeud.balise,
                type: noeud.getAttribute("type"),
                id: id,
                classes: classesDe(noeud),
                libelle: libelle === null ? "" : libelle
            });
            return;
        }
        noeud.enfants.forEach(function (enfant) { marcher(enfant, pile.concat([noeud])); });
    })(bloc, []);

    return champs;
}

function extraireNomsRadioTable(table) {
    const noms = [];
    (function marcher(n) {
        if (n.genre !== "element") return;
        if (n.balise === "input" && n.getAttribute("type") === "radio") {
            noms.push(n.getAttribute("name"));
        }
        n.enfants.forEach(marcher);
    })(table);
    return noms;
}

function collecterImagesDessinables(racine) {
    const images = [];
    (function marcher(n) {
        if (n.genre !== "element") return;
        if (n.balise === "img" && classesDe(n).includes("dessinable")) {
            images.push({ alt: n.getAttribute("alt"), classes: classesDe(n).sort() });
        }
        n.enfants.forEach(marcher);
    })(racine);
    return images;
}

/*
 * Tolérances déclarées par le contrat (critère 2, section 8), et elles
 * seules pour (a) à (e). Trois divergences supplémentaires, (f) à (h), se
 * sont révélées nécessaires à l'exécution et ne sont anticipées par aucune
 * des cinq déclarées par le contrat ; chacune est pourtant déjà décrite,
 * ailleurs dans ce même contrat, comme une anomalie du HTML V1 volontairement
 * non reproduite (section 7, tableau des anomalies A5/A6) ou comme une
 * conséquence du principe D9 (aucune table de correspondance par `cle` de
 * bloc à l'intérieur du moteur). Signalé en détail dans le compte rendu de
 * la tâche, à l'attention de l'auditeur : le contrat n'énumère que 5
 * tolérances alors que ses propres décisions (A5, A6) et son silence sur le
 * conteneur de `patient_infos` en impliquent 3 de plus.
 *
 *   (a) un id émis sur les 9 blocs qui n'en ont pas aujourd'hui
 *   (b) un id émis sur les 3 images squelette_* (non comparé : voir plus bas)
 *   (c) le name des 4 groupes de radios à id, partagé/distinct seulement
 *   (d) l'attribut for d'un libellé de bloc, non émis par le moteur
 *   (e) les attributs nom= (A1) et le type d'un textarea (A5 — étendue en
 *       (h) ci-dessous, la même anomalie que le contrat cite sans en tirer
 *       la conséquence sur cette comparaison précise)
 *   (f) — non déclarée par le contrat — `patient_infos` (bloc 2) est un
 *       <section> en V1, seul bloc ordinaire dans ce cas ; aucun sélecteur
 *       de style.css ni de script.js ne dépend de la balise (seul l'id est
 *       ciblé). Reproduire cette exception par le `cle` du bloc à
 *       l'intérieur du moteur referait exactement ce que D9 interdit.
 *   (g) — non déclarée par le contrat, conséquence directe de A6 — le champ
 *       `empreinte_encre` porte `class="custom-checkbox"` sur l'<input> lui-
 *       même en V1 (imbrication de labels, anomalie A6) ; le moteur la porte
 *       sur le <span> voisin, comme tous les autres champs "case". Le
 *       contrat classe lui-même A6 comme non reproduite et renvoie la
 *       divergence visuelle au critère 3 (humain, hors de cette passe).
 *   (h) — non déclarée par le contrat, conséquence directe de A5 — le champ
 *       `orientation` porte `type="text"` sur son <textarea> en V1 ; le
 *       moteur ne pose jamais de `type` sur un textarea. Le contrat classe
 *       lui-même A5 comme non reproduite, « sans effet sur un textarea ».
 */
const INDICES_SANS_ID = new Set([0, 2, 3, 4, 5, 6, 23, 24, 25]); // (a), 0-based
const INDEX_PATIENT_INFOS = 1; // (f)
const ID_CHAMP_TOLERE_CLASSES = "empreinte_encre"; // (g)
const ID_CHAMP_TOLERE_TYPE = "orientation"; // (h)

function comparerChamps(champsV1, champsMoteur, indexBloc, ecarts) {
    if (champsV1.length !== champsMoteur.length) {
        ecarts.push("bloc " + indexBloc + " : " + champsV1.length + " champ(s) en V1, "
            + champsMoteur.length + " côté moteur");
        return;
    }
    champsV1.forEach(function (cV1, j) {
        const cM = champsMoteur[j];
        const position = "bloc " + indexBloc + ", champ " + j + " (" + (cV1.id || "sans id") + ")";

        if (cV1.balise !== cM.balise) {
            ecarts.push(position + " : balise « " + cV1.balise + " » (V1) vs « " + cM.balise + " » (moteur)");
        }

        let typeV1 = cV1.type;
        if (cV1.id === ID_CHAMP_TOLERE_TYPE) typeV1 = null; // (h)
        if (typeV1 !== cM.type) {
            ecarts.push(position + " : attribut type « " + cV1.type + " » (V1) vs « " + cM.type + " » (moteur)");
        }

        if (cV1.id !== cM.id) {
            ecarts.push(position + " : id « " + cV1.id + " » (V1) vs « " + cM.id + " » (moteur)");
        }

        let classesV1 = cV1.classes;
        if (cV1.id === ID_CHAMP_TOLERE_CLASSES) classesV1 = classesV1.filter((c) => c !== "custom-checkbox"); // (g)
        if (!memesEnsembles(classesV1, cM.classes)) {
            ecarts.push(position + " : classes différentes — V1=[" + cV1.classes + "] moteur=[" + cM.classes + "]");
        }

        if (cV1.libelle !== cM.libelle) {
            ecarts.push(position + " : libellé « " + cV1.libelle + " » (V1) vs « " + cM.libelle + " » (moteur)");
        }
    });
}

/**
 * `blocsV1`/`blocsMoteur` : listes de `{ noeud, ancetres }` rendues par
 * `collecterBlocsAvecAncetres()`.
 */
function comparerProjections(blocsV1, blocsMoteur) {
    const ecarts = [];

    if (blocsV1.length !== blocsMoteur.length) {
        ecarts.push("nombre de blocs différent : V1=" + blocsV1.length + ", moteur=" + blocsMoteur.length);
        return ecarts;
    }

    blocsV1.forEach(function (entreeV1, i) {
        const entreeM = blocsMoteur[i];
        const nV1 = entreeV1.noeud;
        const nM = entreeM.noeud;
        const classesV1 = classesDe(nV1).sort();
        const classesM = classesDe(nM).sort();
        const idV1 = nV1.getAttribute("id");
        const idM = nM.getAttribute("id");

        const balisesTolerees = i === INDEX_PATIENT_INFOS && nV1.balise === "section" && nM.balise === "div"; // (f)
        if (nV1.balise !== nM.balise && !balisesTolerees) {
            ecarts.push("bloc " + i + " : balise « " + nV1.balise + " » (V1) vs « " + nM.balise + " » (moteur)");
        }

        if (INDICES_SANS_ID.has(i)) {
            if (idV1 !== null) ecarts.push("bloc " + i + " : attendu sans id en V1, trouvé « " + idV1 + " »"); // (a)
        } else if (idV1 !== idM) {
            ecarts.push("bloc " + i + " : id « " + idV1 + " » (V1) vs « " + idM + " » (moteur)");
        }

        if (!memesEnsembles(classesV1, classesM)) {
            ecarts.push("bloc " + i + " (" + (idV1 || idM || "sans id") + ") : classes différentes — "
                + "V1=[" + classesV1 + "] moteur=[" + classesM + "]");
        }

        // Constat n°1 (audit C1-T3) : la chaîne des ancêtres, pas seulement
        // le bloc lui-même — un fragment inséré après `</main>` plutôt que
        // dedans a des blocs par ailleurs identiques, mais mal placés.
        const ancetresV1 = decrireChaineAncetres(filtrerAncetresInertes(entreeV1.ancetres)); // tolérance (i)
        const ancetresM = decrireChaineAncetres(entreeM.ancetres);
        if (JSON.stringify(ancetresV1) !== JSON.stringify(ancetresM)) {
            ecarts.push("bloc " + i + " (" + (idV1 || idM || "sans id") + ") : ancêtres différents — "
                + "V1=" + JSON.stringify(ancetresV1) + " moteur=" + JSON.stringify(ancetresM));
        }

        const titreV1 = extraireTitreBloc(nV1);
        const titreM = extraireTitreBloc(nM);

        if (nV1.balise === "table" || nM.balise === "table") {
            const nomsV1 = extraireNomsRadioTable(nV1);
            const nomsM = extraireNomsRadioTable(nM);
            if (JSON.stringify(nomsV1) !== JSON.stringify(nomsM)) {
                ecarts.push("bloc " + i + " (tableau) : name des radios différents — "
                    + "V1=[" + nomsV1 + "] moteur=[" + nomsM + "]");
            }

            // Constat n°2 (audit C1-T3) : sans ceci, le titre du tableau, ses
            // en-têtes de colonnes et le nom de ses lignes — du vocabulaire
            // clinique imprimé dans le PDF — pouvaient être renommés
            // arbitrairement dans schema.json sans faire rougir ce test.
            const detailsV1 = extraireDetailsTable(nV1);
            const detailsM = extraireDetailsTable(nM);
            if (detailsV1.titre !== detailsM.titre) {
                ecarts.push("bloc " + i + " (tableau) : titre « " + detailsV1.titre + " » (V1) vs « " + detailsM.titre + " » (moteur)");
            }
            if (JSON.stringify(detailsV1.entetes) !== JSON.stringify(detailsM.entetes)) {
                ecarts.push("bloc " + i + " (tableau) : en-têtes de colonnes différents — "
                    + "V1=" + JSON.stringify(detailsV1.entetes) + " moteur=" + JSON.stringify(detailsM.entetes));
            }
            if (JSON.stringify(detailsV1.lignes) !== JSON.stringify(detailsM.lignes)) {
                ecarts.push("bloc " + i + " (tableau) : noms de ligne différents — "
                    + "V1=" + JSON.stringify(detailsV1.lignes) + " moteur=" + JSON.stringify(detailsM.lignes));
            }
        } else {
            if (titreV1 !== titreM) {
                ecarts.push("bloc " + i + " : titre « " + titreV1 + " » (V1) vs « " + titreM + " » (moteur)");
            }
            comparerChamps(collecterChamps(nV1), collecterChamps(nM), i, ecarts);
        }
    });

    return ecarts;
}

/* ================================ Programme ================================ */

try {
    const htmlV1 = lireNormalise(CHEMIN_HTML);
    const htmlIndexMoteur = lireNormalise(CHEMIN_INDEX_MOTEUR);

    // --- Charger le moteur dans le double DOM, comme le ferait le navigateur,
    //     mais sans jamais déclencher DOMContentLoaded (le double n'a pas de
    //     formulaire réel à rendre tout seul : les tests appellent
    //     validerSchema()/rendre() directement, comme les sept scénarios de
    //     tests/test_file_depots.js appellent les fonctions de script.js).
    const contexteMoteur = { console };
    vm.createContext(contexteMoteur);
    contexteMoteur.document = Object.assign(dom.creerDocument(), { addEventListener() {} });
    vm.runInContext(fs.readFileSync(CHEMIN_MOTEUR, "utf-8"), contexteMoteur, { filename: "rendu.js" });
    const { validerSchema, rendre } = contexteMoteur;
    assert.strictEqual(typeof validerSchema, "function", "validerSchema doit être exportée par rendu.js");
    assert.strictEqual(typeof rendre, "function", "rendre doit être exportée par rendu.js");

    const schemaProduction = JSON.parse(lireNormalise(CHEMIN_SCHEMA));

    // --- 1. Construire la projection complète côté V1 : tout #form-bilan,
    //        en-tête compris (29 blocs), lu dans formulaire/index.html,
    //        encore la V1 intacte à ce stade de la tâche.
    const htmlFormBilan = extraireElement(htmlV1, '<div id="form-bilan">', "div");
    const racineV1 = analyserHtml(dom.creerDocument(), htmlFormBilan)[0];
    const blocsV1 = collecterBlocsAvecAncetres(racineV1);
    if (blocsV1.length !== 29) {
        throw new Error("V1 : " + blocsV1.length + " bloc(s) trouvés dans #form-bilan, 29 attendus");
    }

    // --- 2. Construire la projection côté moteur : l'en-tête, recopié tel
    //        quel dans formulaire/index-moteur.html (vérifié identique à
    //        celui de la V1), puis un <main> dans lequel rendre() insère les
    //        28 blocs du schéma — jamais directement dans #form-bilan
    //        (constat n°1, audit C1-T3 : en V1 les blocs vivent DANS <main>,
    //        `main { padding: 10px }`, style.css:23, pas après lui).
    const headerV1 = extraireElement(htmlV1, "<header", "header");
    const headerIndexMoteur = extraireElement(htmlIndexMoteur, "<header", "header");
    if (headerV1.replace(/\s+/g, " ").trim() !== headerIndexMoteur.replace(/\s+/g, " ").trim()) {
        throw new Error(
            "formulaire/index-moteur.html ne recopie pas l'en-tête de formulaire/index.html à l'identique " +
            "(espaces mis à part) : la coquille provisoire a dérivé de la V1."
        );
    }

    // Constat n°9 (audit C1-T3) : le message qui dirige vers la fiche de
    // secours doit survivre même si formulaire/moteur/rendu.js ne se charge
    // jamais — il doit donc exister dans le HTML statique, pas uniquement
    // être écrit par du JavaScript.
    if (!/id="attente-moteur"[^>]*>[^<]*secours V1/i.test(htmlIndexMoteur)) {
        throw new Error(
            "formulaire/index-moteur.html : aucun message statique #attente-moteur dirigeant vers « secours V1 » " +
            "(constat n°9, audit C1-T3) — un échec de chargement de rendu.js resterait silencieux."
        );
    }
    // Constat n°10 (audit C1-T3) : pas d'onclick= en ligne sur cette page
    // provisoire (incompatible avec la CSP à venir, C6-T1) — le bouton
    // d'export y est câblé par demarrerApplication() (script.js), pas par
    // un attribut HTML.
    if (/id="btn-export"[^>]*onclick=/i.test(htmlIndexMoteur)) {
        throw new Error("formulaire/index-moteur.html : onclick= en ligne sur #btn-export (constat n°10, audit C1-T3).");
    }

    const conteneurMoteur = contexteMoteur.document.createElement("div");
    conteneurMoteur.setAttribute("id", "form-bilan");
    analyserHtml(contexteMoteur.document, headerIndexMoteur).forEach(function (n) {
        conteneurMoteur.appendChild(n);
    });
    const mainMoteur = contexteMoteur.document.createElement("main");
    conteneurMoteur.appendChild(mainMoteur);

    const resultatProduction = rendre(schemaProduction, contexteMoteur.document, mainMoteur);
    if (!resultatProduction.ok) {
        throw new Error("formulaire/schema.json est refusé par le moteur : " + resultatProduction.erreurs.join(" | "));
    }
    const blocsMoteur = collecterBlocsAvecAncetres(conteneurMoteur);
    if (blocsMoteur.length !== 29) {
        throw new Error("moteur : " + blocsMoteur.length + " bloc(s) rendus, 29 attendus (en-tête + 28 blocs du schéma)");
    }

    // --- 3. La comparaison proprement dite (critère 2).
    const ecarts = comparerProjections(blocsV1, blocsMoteur);

    // --- 4. Les 4 img.dessinable, séparément (rang, alt, classes — jamais l'id, tolérance (b)).
    const imagesV1 = collecterImagesDessinables(racineV1);
    const imagesMoteur = collecterImagesDessinables(conteneurMoteur);
    if (imagesV1.length !== 4 || imagesMoteur.length !== 4) {
        ecarts.push("images dessinables : V1=" + imagesV1.length + ", moteur=" + imagesMoteur.length + " (4 attendues)");
    } else {
        imagesV1.forEach(function (imgV1, i) {
            const imgM = imagesMoteur[i];
            if (imgV1.alt !== imgM.alt) {
                ecarts.push("image " + i + " : alt « " + imgV1.alt + " » (V1) vs « " + imgM.alt + " » (moteur)");
            }
            if (!memesEnsembles(imgV1.classes, imgM.classes)) {
                ecarts.push("image " + i + " : classes différentes — V1=[" + imgV1.classes + "] moteur=[" + imgM.classes + "]");
            }
        });
    }

    // --- 5. Les 8 radios de tableau : name exactement test_positif, membre_court, dorsal, lombaire (tolérance (c) pour les 4 autres groupes, vérifiée séparément plus bas).
    const nomsTableTousV1 = [];
    blocsV1.forEach(function (b) { if (b.noeud.balise === "table") nomsTableTousV1.push(...new Set(extraireNomsRadioTable(b.noeud))); });
    assert.deepStrictEqual(nomsTableTousV1, ["test_positif", "membre_court", "dorsal", "lombaire"],
        "name des 8 radios de tableau, V1 : attendu test_positif, membre_court, dorsal, lombaire");
    const nomsTableTousM = [];
    blocsMoteur.forEach(function (b) { if (b.noeud.balise === "table") nomsTableTousM.push(...new Set(extraireNomsRadioTable(b.noeud))); });
    assert.deepStrictEqual(nomsTableTousM, ["test_positif", "membre_court", "dorsal", "lombaire"],
        "name des 8 radios de tableau, moteur : attendu test_positif, membre_court, dorsal, lombaire");

    // --- 6. Tolérance (c) : les 4 groupes de radios à id (SO, appui, isthme, spin)
    //        partagent un name au sein du groupe, distinct d'un groupe à l'autre — côté moteur seulement,
    //        puisque c'est une propriété du nom *synthétisé*, pas une valeur imposée par la V1.
    const GROUPES_RADIO_A_ID = [["SO_oui", "SO_non"], ["anterieur", "posterieur"], ["isthme_g", "isthme_d"], ["gauche", "droit"]];
    const nomsDesGroupes = GROUPES_RADIO_A_ID.map(function (paire) {
        const trouver = function (id) {
            let resultat = null;
            (function marcher(n) {
                if (n.genre === "element") {
                    if (n.balise === "input" && n.getAttribute("id") === id) resultat = n.getAttribute("name");
                    n.enfants.forEach(marcher);
                }
            })(conteneurMoteur);
            return resultat;
        };
        const nomA = trouver(paire[0]);
        const nomB = trouver(paire[1]);
        assert.strictEqual(nomA, nomB, "le groupe " + paire.join("/") + " doit partager un même name");
        return nomA;
    });
    assert.strictEqual(new Set(nomsDesGroupes).size, 4, "les 4 groupes de radios à id doivent avoir des name distincts");

    if (ecarts.length > 0) {
        throw new Error("divergence(s) hors tolérance :\n  - " + ecarts.join("\n  - "));
    }
    console.log("1. comparaison V1 <-> moteur : 29 blocs, champs et images identiques (hors tolérances déclarées)");

    // --- 7. Critère 6 : un schéma cassé ne rend rien.
    function conteneurVide() {
        const c = contexteMoteur.document.createElement("div");
        c.setAttribute("id", "form-bilan");
        return c;
    }

    const casClesRacine = { version_schema: 1, blocs: [{ cle: "x", champs: [] }], en_trop: true };
    const refusClesRacine = validerSchema(casClesRacine);
    assert.ok(refusClesRacine.some((m) => /règle 1/.test(m)), "clé racine en trop : règle 1 attendue");
    const conteneurA = conteneurVide();
    assert.strictEqual(rendre(casClesRacine, contexteMoteur.document, conteneurA).ok, false);
    assert.strictEqual(conteneurA.enfants.length, 0, "aucun nœud inséré malgré le refus (clé racine en trop)");

    const casVersion = { version_schema: 2, blocs: [{ cle: "x", champs: [] }] };
    const refusVersion = validerSchema(casVersion);
    assert.ok(refusVersion.some((m) => /règle 2/.test(m)), "version inconnue : règle 2 attendue");
    const conteneurB = conteneurVide();
    assert.strictEqual(rendre(casVersion, contexteMoteur.document, conteneurB).ok, false);
    assert.strictEqual(conteneurB.enfants.length, 0, "aucun nœud inséré malgré le refus (version inconnue)");

    const casTypeEcarte = { version_schema: 1, blocs: [{ cle: "x", champs: [{ cle: "y", type: "liste", libelle: "Y" }] }] };
    const refusType = validerSchema(casTypeEcarte);
    assert.ok(refusType.some((m) => /règle 7/.test(m)), "type écarté : règle 7 attendue");
    const conteneurC = conteneurVide();
    assert.strictEqual(rendre(casTypeEcarte, contexteMoteur.document, conteneurC).ok, false);
    assert.strictEqual(conteneurC.enfants.length, 0, "aucun nœud inséré malgré le refus (type écarté)");

    console.log("2. trois schémas cassés (clé racine en trop, version inconnue, type « liste ») : "
        + "refusés en nommant la règle, aucun nœud inséré");

    // --- Constat n°3 de l'audit C1-T3 : un champ sans `cle` ne doit jamais
    //     être rendu avec un attribut dérivé de `undefined`. Un "tableau"
    //     combiné à un autre champ, et un "radio" en disposition "atcd",
    //     sont les deux scénarios démontrés.
    const casTableauCombine = {
        version_schema: 1,
        blocs: [{
            cle: "x",
            champs: [
                {
                    type: "tableau", libelle: "T", entetes: ["A", "B"],
                    lignes: [{ nom: "N", cle: "n", colonnes: [{ valeur: "a", libelle: "A" }, { valeur: "b", libelle: "B" }] }]
                },
                { cle: "autre", type: "texte", libelle: "Autre" }
            ]
        }]
    };
    assert.ok(validerSchema(casTableauCombine).length > 0,
        "un type « tableau » combiné à un autre champ dans le même bloc doit être refusé");

    const casRadioEnAtcd = {
        version_schema: 1,
        blocs: [{
            cle: "x", disposition: "atcd",
            champs: [{ type: "radio", valeurs: [{ cle: "a", valeur: "a", libelle: "A" }, { cle: "b", valeur: "b", libelle: "B" }] }]
        }]
    };
    assert.ok(validerSchema(casRadioEnAtcd).length > 0,
        "un « radio » en disposition « atcd » doit être refusé");
    console.log("3. champ sans cle (tableau combiné, radio en atcd) : refusé, jamais id=\"undefined\"");

    // --- Constat n°4 de l'audit C1-T3 : les id émis par la coquille
    //     (form-bilan, date-bilan, maintitle, logo, infos_podo) sont un jeu
    //     réservé, interdit comme cle de bloc, cle de champ, ou titre_cle.
    const casCleBlocReservee = { version_schema: 1, blocs: [{ cle: "date-bilan", champs: [] }] };
    assert.ok(validerSchema(casCleBlocReservee).length > 0,
        "une « cle » de bloc réservée à la coquille doit être refusée");

    const casCleChampReservee = { version_schema: 1, blocs: [{ cle: "x", champs: [{ cle: "logo", type: "texte", libelle: "L" }] }] };
    assert.ok(validerSchema(casCleChampReservee).length > 0,
        "une « cle » de champ réservée à la coquille doit être refusée");

    const casTitreCleReservee = { version_schema: 1, blocs: [{ cle: "x", titre: "T", titre_cle: "maintitle", champs: [] }] };
    assert.ok(validerSchema(casTitreCleReservee).length > 0,
        "un « titre_cle » réservé à la coquille doit être refusé");
    console.log("4. cle/titre_cle réservée à la coquille (form-bilan, date-bilan, maintitle, logo, infos_podo) : refusée");

    // --- Constat n°8 de l'audit C1-T3 : le `fichier` d'une image-annotable
    //     est le seul puits sortant nouveau de la tâche — un schéma viendra
    //     demain de l'atelier C9. Doit être un chemin relatif sous images/,
    //     sans traversée de répertoire, antislash ni schéma d'URL.
    const cheminsRefuses = [
        "https://exemple.invalide/pixel.png",
        "//exemple.invalide/pixel.png",
        "../../../etc/passwd.png",
        "/etc/passwd.png",
        "images\\..\\x.png",
        "data:image/png;base64,AAA="
    ];
    cheminsRefuses.forEach(function (fichier) {
        const casCheminRefuse = {
            version_schema: 1,
            blocs: [{ cle: "x", champs: [{ cle: "y", type: "image-annotable", libelle: "Y", fichier: fichier, texte_alternatif: "alt" }] }]
        };
        assert.ok(validerSchema(casCheminRefuse).length > 0,
            "chemin d'image non contenu refusé : " + fichier);
    });
    const casCheminAutorise = {
        version_schema: 1,
        blocs: [{ cle: "x", champs: [{ cle: "y", type: "image-annotable", libelle: "Y", fichier: "images/essai.png", texte_alternatif: "alt" }] }]
    };
    assert.strictEqual(validerSchema(casCheminAutorise).length, 0,
        "un chemin relatif sous images/ reste accepté");
    console.log("5. « fichier » d'une image-annotable : relatif, sous images/, "
        + "sans « .. », antislash ni schéma d'URL — sinon refusé");

    // --- Constat n°5 de l'audit C1-T3 : tout schéma non rendable doit être
    //     refusé par une règle nommée, et rendre() ne doit jamais lever —
    //     même si (hypothèse non testée ici) une future règle manquait à
    //     l'attraper, le filet de sécurité de rendre() ne doit jamais
    //     laisser remonter une exception.
    const casTexteEnLigne = {
        version_schema: 1,
        blocs: [{ cle: "x", disposition: "en-ligne", champs: [{ cle: "y", type: "texte", libelle: "Y" }] }]
    };
    assert.ok(validerSchema(casTexteEnLigne).length > 0, "un « texte » en disposition « en-ligne » doit être refusé");
    let leve = false;
    let resultatTexteEnLigne;
    try {
        resultatTexteEnLigne = rendre(casTexteEnLigne, contexteMoteur.document, conteneurVide());
    } catch (erreurInattendue) {
        leve = true;
    }
    assert.strictEqual(leve, false, "rendre() ne doit jamais lever (texte en disposition en-ligne)");
    assert.strictEqual(resultatTexteEnLigne.ok, false);

    const casTableauSansEntetes = {
        version_schema: 1,
        blocs: [{
            cle: "x",
            champs: [{
                type: "tableau", libelle: "T",
                lignes: [{ nom: "N", cle: "n", colonnes: [{ valeur: "a", libelle: "A" }, { valeur: "b", libelle: "B" }] }]
            }]
        }]
    };
    assert.ok(validerSchema(casTableauSansEntetes).length > 0, "un « tableau » sans « entetes » doit être refusé");
    leve = false;
    let resultatTableauSansEntetes;
    try {
        resultatTableauSansEntetes = rendre(casTableauSansEntetes, contexteMoteur.document, conteneurVide());
    } catch (erreurInattendue) {
        leve = true;
    }
    assert.strictEqual(leve, false, "rendre() ne doit jamais lever (tableau sans entetes)");
    assert.strictEqual(resultatTableauSansEntetes.ok, false);
    console.log("6. deux schémas non rendables (texte en en-ligne, tableau sans entetes) : "
        + "refusés par une règle nommée, rendre() ne lève jamais");

    // --- Constat n°6 de l'audit C1-T3 : D8 — une clé facultative inconnue
    //     est ignorée avec un avertissement, jamais un refus, jamais un
    //     silence ; titre_apparence/titre_cle portés par un CHAMP (et non
    //     un bloc) sont en revanche un attribut connu à la mauvaise place,
    //     refusé nommément par la règle 14.
    const avertissements = [];
    const avertirOriginal = console.warn;
    console.warn = function (message) { avertissements.push(message); };
    let erreursAttributsInconnus;
    try {
        const schemaAvecAttributsInconnus = {
            version_schema: 1,
            blocs: [{ cle: "x", couleur: "rouge", champs: [{ cle: "y", type: "texte", libelle: "Y", onclick: "alert(1)" }] }]
        };
        erreursAttributsInconnus = validerSchema(schemaAvecAttributsInconnus);
    } finally {
        console.warn = avertirOriginal;
    }
    // assert.deepStrictEqual() compare les prototypes : erreursAttributsInconnus
    // vient du contexte vm (son propre « royaume » Array), distinct de celui
    // de ce fichier — comparer .length (un nombre, insensible au royaume)
    // plutôt que la structure, comme pour les .some()/.ok ci-dessus et
    // ailleurs dans ce fichier.
    assert.strictEqual(erreursAttributsInconnus.length, 0,
        "D8 : des attributs facultatifs inconnus ne doivent jamais être refusés (" + erreursAttributsInconnus.join(" | ") + ")");
    assert.ok(avertissements.some((m) => /couleur/.test(m)),
        "D8 : avertissement attendu pour l'attribut de bloc inconnu « couleur »");
    assert.ok(avertissements.some((m) => /onclick/.test(m)),
        "D8 : avertissement attendu pour l'attribut de champ inconnu « onclick »");

    const casTitreApparenceSurChamp = {
        version_schema: 1,
        blocs: [{ cle: "x", champs: [{ cle: "y", type: "texte", libelle: "Y", titre_apparence: "h3" }] }]
    };
    const refusTitreApparenceChamp = validerSchema(casTitreApparenceSurChamp);
    assert.ok(refusTitreApparenceChamp.some((m) => /règle 14/.test(m)),
        "titre_apparence porté par un champ : règle 14 attendue");
    console.log("7. D8 : attribut facultatif inconnu averti (jamais refusé) ; "
        + "titre_apparence/titre_cle sur un champ : refusé (règle 14)");

    // --- 8. Critère 5 : un champ ajouté au schéma apparaît sans JavaScript.
    //        Entièrement en mémoire : formulaire/schema.json n'est jamais modifié.
    const schemaAvecEssai = JSON.parse(JSON.stringify(schemaProduction));
    schemaAvecEssai.blocs.push({ cle: "essai", champs: [{ cle: "essai_texte", type: "texte", libelle: "Essai" }] });
    const conteneurEssai = conteneurVide();
    const resultatEssai = rendre(schemaAvecEssai, contexteMoteur.document, conteneurEssai);
    assert.strictEqual(resultatEssai.ok, true, "le schéma augmenté d'un bloc doit rester valide");
    const blocsEssai = collecterBlocsAvecAncetres(conteneurEssai);
    assert.strictEqual(blocsEssai.length, 29, "29ᵉ bloc attendu (28 + le bloc « essai »)");
    let essaiTrouve = false;
    (function marcher(n) {
        if (n.genre === "element") {
            if (n.getAttribute("id") === "essai_texte") essaiTrouve = true;
            n.enfants.forEach(marcher);
        }
    })(conteneurEssai);
    assert.ok(essaiTrouve, "#essai_texte doit apparaître dans le rendu");
    console.log("8. un bloc et un champ ajoutés à schema.json (en mémoire) apparaissent dans le rendu, "
        + "sans qu'aucun fichier .js ne soit modifié");

    console.log("\nTout est vert.");
} catch (erreur) {
    console.error("ÉCHEC :", erreur.message);
    process.exit(1);
}
