/*
 * Mini-analyseur HTML, extrait de `tests/test_comparaison_dom.js` (C1-T4a)
 * pour que `tests/test_schema_client.js` lise lui aussi un fragment de HTML
 * écrit à la main, sans le recopier.
 *
 * Ce n'est pas un analyseur HTML général : il lit le HTML de CE dépôt, bien
 * formé, sans commentaire ni CDATA à l'intérieur de `#form-bilan`. Il
 * construit un arbre dans le double DOM de `dom-minimal.js` — le même type de
 * nœud que celui que produit `rendre()`.
 *
 * Exécuté seul, ce fichier ne fait rien : aucun effet de bord au niveau module.
 */

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

module.exports = { analyserAttributs, analyserHtml, extraireElement };
