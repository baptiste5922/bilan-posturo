/*
 * Double minimal du DOM, sans dépendance : `jsdom` est indisponible en
 * intégration continue (aucun `npm ci` n'y est exécuté, tests.yml:36-52).
 *
 * N'expose **exactement** que ce qu'un moteur de rendu construit par
 * `createElement`/`textContent` est en droit d'utiliser : `createElement`,
 * `createTextNode`, `createDocumentFragment` sur le document, et
 * `appendChild`, `setAttribute`, `getAttribute`, `classList.add`,
 * `textContent` sur les nœuds. Pas de `querySelector`, pas d'`innerHTML` :
 * ce que ce double n'offre pas, `formulaire/moteur/rendu.js` n'a pas le
 * droit de l'utiliser — si un test échoue ici avec « n'est pas une
 * fonction », c'est le signal recherché, pas un défaut du double.
 *
 * `serialiser(noeud)` rend l'arbre inspectable : un objet simple (balise,
 * attributs triés, enfants), que `tests/test_comparaison_dom.js` compare
 * ensuite à la projection tirée de `formulaire/index.html`.
 *
 * Exécuté seul (`node tests/outils/dom-minimal.js`), ce fichier ne fait
 * rien : aucun effet de bord au niveau module, seulement des définitions.
 *
 *     node -e "const d = require('./tests/outils/dom-minimal.js');
 *              const doc = d.creerDocument();
 *              const racine = doc.createElement('div');
 *              const enfant = doc.createElement('span');
 *              enfant.setAttribute('id', 'x');
 *              enfant.appendChild(doc.createTextNode('bonjour'));
 *              racine.appendChild(enfant);
 *              console.log(JSON.stringify(d.serialiser(racine), null, 2));"
 */

const TEXTE = "texte";
const ELEMENT = "element";
const FRAGMENT = "fragment";

function creerNoeudTexte(valeur) {
    return { genre: TEXTE, valeur: String(valeur) };
}

/** Concatène le texte de tous les descendants, comme le ferait un vrai nœud. */
function texteDe(noeud) {
    if (noeud.genre === TEXTE) return noeud.valeur;
    return noeud.enfants.map(texteDe).join("");
}

function creerElement(balise) {
    const attributs = new Map();
    const classes = new Set();
    const enfants = [];

    const noeud = {
        genre: ELEMENT,
        balise: String(balise),
        enfants,
        _attributs: attributs,
        _classes: classes,

        appendChild(enfant) {
            // Un fragment n'est jamais lui-même un nœud du document final :
            // l'insérer en déplace les enfants, comme le fait un vrai DOM.
            if (enfant.genre === FRAGMENT) {
                enfant.enfants.forEach(function (e) { enfants.push(e); });
                enfant.enfants.length = 0;
            } else {
                enfants.push(enfant);
            }
            return enfant;
        },

        setAttribute(nom, valeur) {
            if (nom === "class") {
                classes.clear();
                String(valeur).split(/\s+/).filter(Boolean)
                    .forEach(function (c) { classes.add(c); });
            } else {
                attributs.set(nom, String(valeur));
            }
        },

        getAttribute(nom) {
            if (nom === "class") {
                return classes.size ? [...classes].join(" ") : null;
            }
            return attributs.has(nom) ? attributs.get(nom) : null;
        },

        classList: {
            add() {
                Array.prototype.slice.call(arguments)
                    .forEach(function (c) { classes.add(c); });
            }
        }
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
        genre: FRAGMENT,
        enfants,
        appendChild(enfant) {
            if (enfant.genre === FRAGMENT) {
                enfant.enfants.forEach(function (e) { enfants.push(e); });
                enfant.enfants.length = 0;
            } else {
                enfants.push(enfant);
            }
            return enfant;
        }
    };
}

function creerDocument() {
    return {
        createElement: creerElement,
        createTextNode: creerNoeudTexte,
        createDocumentFragment: creerFragment
    };
}

/** Rend un nœud inspectable : balise, attributs triés, enfants récursifs. */
function serialiser(noeud) {
    if (noeud.genre === TEXTE) {
        return { texte: noeud.valeur };
    }
    if (noeud.genre === FRAGMENT) {
        return { fragment: true, enfants: noeud.enfants.map(serialiser) };
    }
    const attributs = {};
    [...noeud._attributs.keys()].sort().forEach(function (nom) {
        attributs[nom] = noeud._attributs.get(nom);
    });
    if (noeud._classes.size) {
        attributs["class"] = [...noeud._classes].sort().join(" ");
    }
    return { balise: noeud.balise, attributs, enfants: noeud.enfants.map(serialiser) };
}

module.exports = { creerDocument, serialiser };
