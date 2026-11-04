/*
 * Sérialise le rendu d'un schéma par un moteur donné : charge `rendu.js` dans
 * un contexte `vm` avec le double de DOM de `dom-minimal.js` (comme
 * `tests/test_comparaison_dom.js`), rend le schéma dans un conteneur, puis
 * imprime `serialiser()` de ce conteneur sur la sortie standard.
 *
 *     node tests/outils/serialiser-rendu.js <rendu.js> <schema.json>
 *
 * C'est l'outil qui produit `tests/donnees/rendu-schema-production.txt`, et
 * qui permet de le reproduire à partir du moteur d'un autre commit (C1-T6).
 * Code de retour 1 si le schéma est refusé : on ne sérialise jamais un rendu
 * qui n'a pas eu lieu.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const dom = require("./dom-minimal.js");

function serialiserRendu(cheminMoteur, cheminSchema) {
    // `warn` est muet : les avertissements d'attributs inconnus ne font pas
    // partie du rendu, et la sortie standard ne doit porter que lui.
    const contexte = { console: { warn() {}, error() {}, log() {} } };
    vm.createContext(contexte);
    contexte.document = Object.assign(dom.creerDocument(), { addEventListener() {} });
    vm.runInContext(fs.readFileSync(cheminMoteur, "utf-8"), contexte, { filename: "rendu.js" });

    const schema = JSON.parse(fs.readFileSync(cheminSchema, "utf-8"));
    const conteneur = contexte.document.createElement("main");
    const resultat = contexte.rendre(schema, contexte.document, conteneur);
    if (!resultat.ok) {
        throw new Error("schéma refusé : " + resultat.erreurs.join(" | "));
    }
    return JSON.stringify(dom.serialiser(conteneur), null, 1) + "\n";
}

module.exports = { serialiserRendu };

if (require.main === module) {
    if (process.argv.length !== 4) {
        process.stderr.write("usage : node serialiser-rendu.js <rendu.js> <schema.json>\n");
        process.exit(2);
    }
    try {
        process.stdout.write(serialiserRendu(path.resolve(process.argv[2]), path.resolve(process.argv[3])));
    } catch (erreur) {
        process.stderr.write(erreur.message + "\n");
        process.exit(1);
    }
}
