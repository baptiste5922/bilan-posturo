/*
 * Tests de calculerPages() (formulaire/script.js) : la répartition des blocs
 * du formulaire sur les pages A4 du PDF.
 *
 * La fonction est pure : elle est extraite telle quelle du fichier de
 * production (accolades comptées), jamais recopiée ici, pour que le test
 * porte toujours sur le code qui tourne au cabinet.
 *
 *     node tests/test_pagination.js
 *     SCRIPT_A_TESTER=/copie/mutée/script.js node tests/test_pagination.js
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");

const SCRIPT = process.env.SCRIPT_A_TESTER
    ? path.resolve(process.env.SCRIPT_A_TESTER)
    : path.join(__dirname, "..", "formulaire", "script.js");

function extraireFonction(source, nom) {
    const debut = source.indexOf("function " + nom + "(");
    assert.ok(debut !== -1, nom + "() introuvable dans " + SCRIPT);
    let i = source.indexOf("{", debut), profondeur = 0;
    for (; i < source.length; i += 1) {
        if (source[i] === "{") profondeur += 1;
        if (source[i] === "}" && --profondeur === 0) break;
    }
    return source.slice(debut, i + 1);
}

const avertissements = [];
const contexte = { console: { warn: (...a) => avertissements.push(a.join(" ")) } };
vm.createContext(contexte);
vm.runInContext(extraireFonction(fs.readFileSync(SCRIPT, "utf8"), "calculerPages")
    + "\nthis.calculerPages = calculerPages;", contexte);
const calculerPages = contexte.calculerPages;

const PAGE = 1000;
const bloc = (nom, haut, bas) => ({ nom, haut, bas });
// Sortie du contexte vm → objets d'un autre royaume : on compare en JSON.
const egal = (obtenu, attendu, message) =>
    assert.strictEqual(JSON.stringify(obtenu), JSON.stringify(attendu), message);

/** Invariants communs à tout découpage. */
function verifierInvariants(pages, blocs, total, cas) {
    assert.ok(pages.length > 0, cas + " : au moins une page");
    assert.strictEqual(pages[0].debut, 0, cas + " : la première page commence en haut");
    for (let p = 1; p < pages.length; p += 1) {
        assert.strictEqual(pages[p].debut, pages[p - 1].fin,
            cas + " : les pages se suivent sans trou ni recouvrement (page " + (p + 1) + ")");
    }
    assert.strictEqual(pages[pages.length - 1].fin, total, cas + " : la dernière page finit au bas du document");
    pages.forEach((page, p) => {
        const derniere = p === pages.length - 1;
        if (!derniere) {
            assert.ok(page.fin - page.debut <= PAGE, cas + " : la page " + (p + 1) + " tient dans une page");
        } else {
            // La dernière page peut dépasser d'une marge vide, jamais d'un bloc.
            const limite = page.debut + PAGE;
            blocs.forEach((b) => assert.ok(b.haut >= limite || b.bas <= limite || b.bas - b.haut > PAGE,
                cas + " : aucun bloc ne déborde de la dernière page (" + b.nom + ")"));
        }
    });
}

let nbCas = 0;
function cas(nom, fn) { fn(); nbCas += 1; console.log("ok - " + nom); }

cas("blocs qui tiennent tous sur une page", () => {
    const blocs = [bloc("a", 0, 300), bloc("b", 320, 600)];
    const pages = calculerPages(blocs, PAGE, 640);
    egal(pages, [{ debut: 0, fin: 640 }]);
    verifierInvariants(pages, blocs, 640, "une page");
});

cas("coupe dans l'espace qui précède le premier bloc qui déborde", () => {
    const blocs = [bloc("a", 0, 500), bloc("b", 520, 900), bloc("c", 930, 1400)];
    const pages = calculerPages(blocs, PAGE, 1450);
    egal(pages, [{ debut: 0, fin: 930 }, { debut: 930, fin: 1450 }],
        "la coupe tombe au haut de c, jamais au milieu de c");
    verifierInvariants(pages, blocs, 1450, "coupe");
});

cas("bloc qui tombe pile sur la coupe : il reste sur la page", () => {
    const blocs = [bloc("a", 0, 600), bloc("pile", 620, 1000), bloc("c", 1000, 1300)];
    const pages = calculerPages(blocs, PAGE, 1320);
    egal(pages, [{ debut: 0, fin: 1000 }, { debut: 1000, fin: 1320 }],
        "un bloc dont le bas égale la limite tient sur la page");
    verifierInvariants(pages, blocs, 1320, "pile sur la coupe");
});

cas("bloc plus haut qu'une page : coupe franche, puis reprise", () => {
    avertissements.length = 0;
    const blocs = [bloc("a", 0, 200), bloc("geant", 220, 2600), bloc("z", 2620, 2800)];
    const pages = calculerPages(blocs, PAGE, 2850);
    egal(pages, [
        { debut: 0, fin: 220 },
        { debut: 220, fin: 1220 },
        { debut: 1220, fin: 2220 },
        { debut: 2220, fin: 2850 }
    ], "le bloc géant est coupé par pages pleines, puis la suite reprend");
    assert.ok(avertissements.some((a) => a.indexOf("geant") !== -1),
        "la coupe d'un bloc est signalée en console, avec son nom");
    verifierInvariants(pages, blocs, 2850, "bloc géant");
});

cas("dernier bloc : la dernière page va jusqu'au bas du document", () => {
    const blocs = [bloc("a", 0, 400), bloc("dernier", 420, 800)];
    const pages = calculerPages(blocs, PAGE, 830);
    egal(pages, [{ debut: 0, fin: 830 }], "la marge sous le dernier bloc reste dans le PDF");
    verifierInvariants(pages, blocs, 830, "dernier bloc");
});

cas("liste vide : aucune page, sans lever", () => {
    // Le formulaire a toujours au moins un bloc ; une liste vide ne doit
    // simplement pas boucler ni lever. exporterBilanPDF() ne l'atteint pas.
    egal(calculerPages([], PAGE, 1200), []);
});

cas("hauteur totale nulle : une page de hauteur nulle, sans lever ni boucler", () => {
    const blocs = [bloc("a", 0, 0)];
    egal(calculerPages(blocs, PAGE, 0), [{ debut: 0, fin: 0 }]);
});

console.log("\n" + nbCas + " cas verts.");
