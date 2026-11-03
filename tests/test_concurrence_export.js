/*
 * Tests de concurrence autour de l'identité du cabinet et de l'export
 * (constats moyens n°1 et n°2, revue C2-T1).
 *
 * 1. Un chargement de /cabinet resté en vol depuis le chargement de la page
 *    ne doit jamais effacer, en aboutissant tardivement, une identité
 *    confirmée entre-temps par un appel plus récent (chargerCabinet(),
 *    cabinetGeneration) — sans quoi un PDF peut sortir sans en-tête et être
 *    tout de même déposé, sans aucun message d'erreur.
 * 2. exporterBilanPDF() ne doit jamais être réentrante : un second appel
 *    pendant qu'un premier est en cours doit être ignoré, pas dédoublé en
 *    un second bilan déposé.
 *
 * SCRIPT_A_TESTER permet de rejouer ces deux essais contre une copie
 * antérieure du fichier (preuve qu'ils échouaient avant le correctif) :
 *
 *     node tests/test_concurrence_export.js
 *     SCRIPT_A_TESTER=/chemin/vers/l-ancien-script.js node tests/test_concurrence_export.js
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");

const SCRIPT = process.env.SCRIPT_A_TESTER
    ? path.resolve(process.env.SCRIPT_A_TESTER)
    : path.join(__dirname, "..", "formulaire", "script.js");

// Reprise exacte de tests/test_file_depots.js : même simulation d'IndexedDB,
// pas une seconde version qui diverge.
function faireIndexedDB() {
    const magasins = {};
    const sequences = {};
    let versionBase = 0;
    const ok = (resultat) => {
        const r = { result: resultat };
        setTimeout(() => r.onsuccess && r.onsuccess(), 0);
        return r;
    };
    const objectStore = (nom) => ({
        add(valeur) {
            sequences[nom] = (sequences[nom] || 0) + 1;
            const id = sequences[nom];
            magasins[nom].set(id, Object.assign({ id }, valeur));
            return ok(id);
        },
        put(valeur, cle) { magasins[nom].set(cle, valeur); return ok(undefined); },
        get(cle) { return ok(magasins[nom].get(cle)); },
        getAll() { return ok([...magasins[nom].values()]); },
        delete(cle) { magasins[nom].delete(cle); return ok(undefined); }
    });
    return {
        _magasins: magasins,
        open(nom, version) {
            const requete = {
                result: {
                    objectStoreNames: { contains: (n) => n in magasins },
                    createObjectStore(n) { magasins[n] = new Map(); return objectStore(n); },
                    transaction: (n) => ({ objectStore })
                }
            };
            setTimeout(() => {
                if (version > versionBase) { versionBase = version; requete.onupgradeneeded(); }
                requete.onsuccess();
            }, 0);
            return requete;
        }
    };
}

/** Un élément DOM minimal, mais suffisant pour tout le chemin d'export :
 *  valeur de champ, visibilité, texte, et un appendChild qui agrège le
 *  texte des enfants dans le parent — assez pour relire #infos_podo après
 *  appliquerCabinet() sans implémenter un arbre DOM complet. */
function creerElement(id) {
    return {
        id, value: "", hidden: true, textContent: "", className: "",
        style: {}, classList: { contains: () => false },
        children: [],
        appendChild(enfant) {
            this.children.push(enfant);
            this.textContent += enfant.textContent || "";
        },
        addEventListener(type, f) { this["on" + type] = f; },
        getBoundingClientRect() { return { top: 0, bottom: 100, left: 0, right: 100, width: 100, height: 100 }; },
        querySelectorAll() { return [this]; }
    };
}

/**
 * Construit un contexte vm chargé avec script.js. `fetchCabinet` répond aux
 * requêtes vers "/cabinet" ; "/depot" et "/sante" ont une réponse fixe, le
 * strict nécessaire pour qu'un export aboutisse jusqu'au dépôt.
 */
function charger(fetchCabinet) {
    const elements = {};
    const element = (id) => (elements[id] = elements[id] || creerElement(id));

    let appelsJsPDF = 0;
    let depots = 0;

    const pdfFactice = () => ({
        addPage() {}, setFillColor() {}, rect() {}, addImage() {},
        setFontSize() {}, setTextColor() {}, text() {},
        output() { return "blob-factice"; },
        save() {}
    });

    const canvasFactice = (largeur, hauteur) => ({
        width: largeur, height: hauteur,
        getContext() { return { fillStyle: "", fillRect() {}, drawImage() {} }; },
        toDataURL() { return "data:image/jpeg;base64,"; }
    });

    const contexte = {
        console,
        setTimeout, clearTimeout, setInterval: () => 0,
        Promise, Date, JSON, Math,
        AbortController: class { constructor() { this.signal = {}; } abort() {} },
        getComputedStyle() { return { getPropertyValue: () => "#FFFFFF", backgroundColor: "#FFFFFF" }; },
        html2canvas() { return Promise.resolve(canvasFactice(100, 100)); },
        fetch(url, options) {
            const chemin = String(url).split("?")[0];
            if (chemin === "/cabinet") return fetchCabinet(url, options);
            if (chemin === "/depot") {
                depots += 1;
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ ok: true, fichier: "Bilan_test.pdf" })
                });
            }
            if (chemin === "/sante") return Promise.resolve({ ok: true });
            return Promise.reject(new Error("fetch non simulé pour " + url));
        },
        document: {
            addEventListener() {},
            getElementById: element,
            documentElement: {}, body: {},
            createElement(tag) {
                if (tag === "canvas") return canvasFactice(0, 0);
                return { tagName: tag, textContent: "" };
            },
            querySelectorAll: () => [],
            querySelector: () => null
        },
        window: {
            addEventListener() {},
            isSecureContext: true,
            showDirectoryPicker: undefined,   // force le repli pdf.save()
            jspdf: {
                jsPDF: function () { appelsJsPDF += 1; return pdfFactice(); }
            }
        },
        navigator: { onLine: true },
        localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
        indexedDB: faireIndexedDB(),
        btoa: (s) => Buffer.from(s, "binary").toString("base64"),
        unescape, encodeURIComponent
    };
    vm.createContext(contexte);
    vm.runInContext(fs.readFileSync(SCRIPT, "utf8"), contexte);
    contexte._elements = elements;
    contexte._appelsJsPDF = () => appelsJsPDF;
    contexte._depots = () => depots;
    return contexte;
}

function remplir(c, valeurs) {
    Object.keys(valeurs).forEach(function (id) {
        c._elements[id] = c._elements[id] || creerElement(id);
        c._elements[id].value = valeurs[id];
    });
}

const CABINET_BON = {
    praticien: "Dr Témoin", adresse: "1 rue du Test",
    courriel: "", telephone: "", convention_nommage: ""
};

(async () => {
    // ===================================================================
    // 1. Un chargement abandonné tardivement ne doit pas effacer une
    //    identité confirmée par un appel plus récent.
    // ===================================================================
    {
        let rejeterAppelA;
        let numeroAppel = 0;
        const c = charger((url) => {
            numeroAppel += 1;
            if (numeroAppel === 1) {
                // Appel A (chargement de page) : reste en vol tant que le
                // test ne décide pas de son issue — exactement la panne
                // réseau du scénario de l'audit, sans dépendre d'une vraie
                // minuterie de 5 s pour la reproduire.
                return new Promise((ok, non) => { rejeterAppelA = non; });
            }
            // Appel B (retentative depuis l'export) : répond tout de suite.
            return Promise.resolve({
                ok: true, json: () => Promise.resolve(CABINET_BON)
            });
        });

        const promesseA = c.chargerCabinet();       // génération 1, en vol
        await new Promise((r) => setImmediate(r));  // laisse A s'installer

        const promesseB = c.chargerCabinet();        // génération 2
        await promesseB;
        c.appliquerCabinet();
        assert.strictEqual(c.identiteUtilisable(), true,
            "l'appel B doit rendre l'identité exploitable");
        const enteteApresB = c._elements["infos_podo"].textContent;
        assert.ok(enteteApresB.indexOf("Dr Témoin") !== -1,
            "l'en-tête doit porter l'identité confirmée par B");

        // L'appel A s'abandonne maintenant (c'est ce qui arriverait à t=5s
        // dans la réalité) : son catch interne s'exécute, et le code
        // d'avant le correctif en profitait pour écraser `cabinet`.
        rejeterAppelA(new Error("AbortError simulé"));
        await promesseA;
        c.appliquerCabinet();   // ce que fait le .then(appliquerCabinet) de demarrerApplication()

        assert.strictEqual(c.identiteUtilisable(), true,
            "l'abandon tardif de l'appel A ne doit pas effacer l'identité confirmée par B");
        const enteteFinal = c._elements["infos_podo"].textContent;
        assert.ok(enteteFinal.indexOf("Dr Témoin") !== -1,
            "l'en-tête doit rester rempli après l'abandon tardif de A : " + JSON.stringify(enteteFinal));

        console.log("1. un chargement de /cabinet abandonné tardivement ne vide plus "
                  + "une identité déjà confirmée par un appel plus récent");
    }

    // ===================================================================
    // 2. exporterBilanPDF() n'est pas réentrante.
    // ===================================================================
    {
        // /cabinet répond tout de suite, mais seulement après un micro-délai
        // (setImmediate) : assez pour laisser le temps à un second clic
        // d'arriver pendant l'attente, si rien ne le bloque.
        const c = charger((url) => new Promise((ok) => {
            setImmediate(() => ok({
                ok: true, json: () => Promise.resolve(CABINET_BON)
            }));
        }));

        remplir(c, { "date-bilan": "2026-10-21", "nom": "Doublon", "prenom": "Test" });

        // Deux clics rapprochés, sans attendre le premier : c'est exactement
        // le scénario de l'audit (page ouverte depuis moins de 5 s, ou PC
        // lent ; rien ne bouge à l'écran pendant l'attente).
        const p1 = c.exporterBilanPDF();
        const p2 = c.exporterBilanPDF();
        await Promise.all([p1, p2]);

        assert.strictEqual(c._appelsJsPDF(), 1,
            "un double clic ne doit produire qu'UN SEUL PDF, pas deux ("
            + c._appelsJsPDF() + " instancié(s))");
        assert.strictEqual(c._depots(), 1,
            "un double clic ne doit déposer qu'UN SEUL bilan sur le PC, pas deux ("
            + c._depots() + " dépôt(s))");

        console.log("2. exporterBilanPDF() n'est pas réentrante : un double clic ne produit "
                  + "qu'un seul PDF et qu'un seul dépôt");
    }

    // ===================================================================
    // 3. Même garantie quand l'identité est DÉJÀ chargée.
    // ===================================================================
    // L'essai 2 ne suffit pas à lui seul : l'identité n'y étant pas encore
    // chargée, chaque appel lance son propre chargerCabinet(), et le numéro
    // de génération de l'essai 1 rend périmé le résultat du premier — qui
    // renonce alors à l'export. Retirer le drapeau exportEnCours laissait
    // donc l'essai 2 vert.
    // Ici, aucune attente ne précède le travail : seul le drapeau sépare
    // deux appels enchaînés de deux bilans déposés.
    {
        const c = charger(() => Promise.resolve({
            ok: true, json: () => Promise.resolve(CABINET_BON)
        }));
        await c.chargerCabinet();
        c.appliquerCabinet();
        assert.strictEqual(c.identiteUtilisable(), true,
            "préalable : l'identité doit être chargée avant le double appel");

        remplir(c, { "date-bilan": "2026-10-21", "nom": "Doublon", "prenom": "Charge" });

        const p1 = c.exporterBilanPDF();
        const p2 = c.exporterBilanPDF();
        await Promise.all([p1, p2]);

        assert.strictEqual(c._appelsJsPDF(), 1,
            "identité chargée : un double appel ne doit produire qu'UN SEUL PDF ("
            + c._appelsJsPDF() + " instancié(s))");
        assert.strictEqual(c._depots(), 1,
            "identité chargée : un double appel ne doit déposer qu'UN SEUL bilan ("
            + c._depots() + " dépôt(s))");

        console.log("3. identité déjà chargée : un double appel ne produit toujours "
                  + "qu'un seul PDF et qu'un seul dépôt");
    }

    // ===================================================================
    // 4. Le drapeau se relâche : un export refusé n'en bloque pas un autre.
    // ===================================================================
    // Sans le `exportEnCours = false` du finally, le premier refus (PC
    // éteint) rendrait tous les clics suivants muets jusqu'au rechargement
    // de la page, PC revenu ou non.
    {
        let pcAllume = false;
        const c = charger(() => pcAllume
            ? Promise.resolve({ ok: true, json: () => Promise.resolve(CABINET_BON) })
            : Promise.reject(new Error("PC injoignable")));

        remplir(c, { "date-bilan": "2026-10-21", "nom": "Reprise", "prenom": "Test" });

        await c.exporterBilanPDF();
        assert.strictEqual(c._appelsJsPDF(), 0, "PC éteint : aucun PDF ne doit être produit");
        assert.strictEqual(c._depots(), 0, "PC éteint : aucun dépôt ne doit partir");

        pcAllume = true;
        await c.exporterBilanPDF();
        assert.strictEqual(c._appelsJsPDF(), 1,
            "PC revenu : le second export doit produire un PDF, pas être ignoré");
        assert.strictEqual(c._depots(), 1,
            "PC revenu : le second export doit déposer le bilan");

        console.log("4. un export refusé (PC éteint) n'empêche pas l'export suivant, "
                  + "une fois le PC revenu");
    }

    console.log("\nTout est vert.");
})().catch((erreur) => {
    console.error(erreur);
    process.exit(1);
});
