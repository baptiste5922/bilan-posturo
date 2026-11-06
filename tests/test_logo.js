/*
 * Tests du logo propre au cabinet côté navigateur (contrat C2-T2).
 *
 * 1. appliquerLogo() : le serveur ne rend que le chemin qu'il a validé, ou
 *    "" ; #logo reçoit ce chemin, ou disparaît. Le `src` n'est réécrit que
 *    s'il diffère (la fiche de secours charge le même script.js : avec la
 *    configuration par défaut, le DOM ne doit pas bouger). Sans identité,
 *    l'image n'est pas touchée.
 * 2. logoPret() : html2canvas lit l'image telle qu'elle est à cet instant ;
 *    l'export attend donc son chargement — borné par DELAI_LOGO, pour qu'un
 *    logo qui n'arrive jamais ne bloque pas une consultation.
 *
 * Même outillage que tests/test_concurrence_export.js : contexte vm, doubles
 * écrits à la main, aucun cadre de test.
 *
 *     node tests/test_logo.js
 */

const fs = require("fs"), vm = require("vm"), assert = require("assert");
const path = require("path");

const SCRIPT = path.join(__dirname, "..", "formulaire", "script.js");

// Reprise de tests/test_concurrence_export.js : même simulation d'IndexedDB.
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
 * Le double de <img id="logo"> : attributs lus par getAttribute, écrits par
 * setAttribute (chaque appel est consigné), `complete` réglable, écouteurs
 * déclenchables à la main. Ni `src` ni `innerHTML` : le script ne doit lire ni
 * l'un ni l'autre (le navigateur rend `src` absolu).
 */
function creerLogo(srcInitial, complete) {
    return {
        // style.display vaut "" tant que rien ne l'a posé, comme dans un vrai DOM.
        id: "logo", style: { display: "" }, complete,
        attributs: { src: srcInitial },
        appelsSetAttribute: [],
        ecouteurs: {},
        getAttribute(nom) { return nom in this.attributs ? this.attributs[nom] : null; },
        setAttribute(nom, valeur) {
            this.appelsSetAttribute.push([nom, valeur]);
            this.attributs[nom] = valeur;
        },
        addEventListener(type, f, options) {
            (this.ecouteurs[type] = this.ecouteurs[type] || []).push(
                { f, une_fois: !!(options && options.once) });
        },
        declencher(type) {
            const liste = this.ecouteurs[type] || [];
            this.ecouteurs[type] = liste.filter((e) => !e.une_fois);
            liste.forEach((e) => e.f());
        },
        nombreEcouteurs() {
            return Object.keys(this.ecouteurs).reduce(
                (n, type) => n + this.ecouteurs[type].length, 0);
        }
    };
}

/**
 * Construit un contexte vm chargé avec script.js.
 *   cabinet : le corps de la réponse de /cabinet ;
 *   logo    : le double de #logo, ou null pour une page sans image ;
 *   minuteries : true pour que setTimeout ne soit jamais exécuté de lui-même
 *     (les minuteries sont consignées, le test les déclenche à la main).
 */
function charger(cabinet, logo, minuteries) {
    const elements = {};
    const element = (id) => {
        if (id === "logo") return logo;
        return (elements[id] = elements[id] || creerElement(id));
    };

    const evenements = [];
    const timers = [];
    let numeroTimer = 0;
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
        setTimeout: minuteries
            ? (f, ms) => { const id = ++numeroTimer; timers.push({ id, f, ms }); return id; }
            : setTimeout,
        clearTimeout: minuteries
            ? (id) => { const i = timers.findIndex((t) => t.id === id); if (i >= 0) timers.splice(i, 1); }
            : clearTimeout,
        setInterval: () => 0,
        Promise, Date, JSON, Math,
        AbortController: class { constructor() { this.signal = {}; } abort() {} },
        getComputedStyle() { return { getPropertyValue: () => "#FFFFFF", backgroundColor: "#FFFFFF" }; },
        html2canvas() {
            evenements.push("html2canvas");
            return Promise.resolve(canvasFactice(100, 100));
        },
        fetch(url) {
            const chemin = String(url).split("?")[0];
            if (chemin === "/cabinet") {
                return Promise.resolve({ ok: true, json: () => Promise.resolve(cabinet) });
            }
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
            jspdf: { jsPDF: function () { return pdfFactice(); } }
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
    contexte._evenements = evenements;
    contexte._timers = timers;
    contexte._depots = () => depots;
    contexte._delaiLogo = () => vm.runInContext("DELAI_LOGO", contexte);
    return contexte;
}

const IDENTITE = { praticien: "Dr Témoin", adresse: "1 rue du Test",
                   courriel: "", telephone: "", convention_nommage: "" };

/** Charge l'identité puis l'applique, comme demarrerApplication(). */
async function demarrer(cabinet, logo, minuteries) {
    const c = charger(cabinet, logo, minuteries);
    await c.chargerCabinet();
    c.appliquerCabinet();
    return c;
}

const ticks = async (n) => { for (let i = 0; i < n; i++) await new Promise((r) => setImmediate(r)); };

(async () => {
    // ===================================================================
    // 1. appliquerLogo
    // ===================================================================

    // 1a. Un logo déclaré : #logo reçoit ce src, et n'est pas masqué.
    {
        const logo = creerLogo("images/favicon.jpeg", true);
        logo.style.display = "none";   // l'état antérieur ne doit pas survivre
        await demarrer(Object.assign({}, IDENTITE, { logo: "images/cabinet/l.png" }), logo);
        assert.strictEqual(logo.attributs.src, "images/cabinet/l.png",
            "#logo doit recevoir le chemin rendu par /cabinet");
        assert.strictEqual(logo.style.display, "",
            "un logo déclaré ne doit pas rester masqué");
        assert.deepStrictEqual(logo.appelsSetAttribute, [["src", "images/cabinet/l.png"]],
            "un seul setAttribute, sur src");
        console.log("1a. un logo déclaré est appliqué à #logo (src, style.display vide)");
    }

    // 1b. "" : pas de logo, l'image est masquée et son src n'est pas touché.
    {
        const logo = creerLogo("images/favicon.jpeg", true);
        await demarrer(Object.assign({}, IDENTITE, { logo: "" }), logo);
        assert.strictEqual(logo.style.display, "none",
            "un logo vide doit masquer #logo (style.display, pas hidden)");
        assert.strictEqual(logo.attributs.src, "images/favicon.jpeg",
            "le src ne doit pas changer quand le logo est vide");
        assert.strictEqual(logo.appelsSetAttribute.length, 0,
            "aucun setAttribute quand le logo est vide");
        console.log("1b. un logo vide masque #logo sans toucher son src");
    }

    // 1c. Une valeur qui n'est pas une chaîne, ou une clé absente : pas de logo.
    {
        for (const valeur of [undefined, null, 42, ["x"], { a: 1 }, true]) {
            const logo = creerLogo("images/favicon.jpeg", true);
            const cabinet = Object.assign({}, IDENTITE);
            if (valeur !== undefined) cabinet.logo = valeur;
            await demarrer(cabinet, logo);
            assert.strictEqual(logo.style.display, "none",
                "logo = " + JSON.stringify(valeur) + " : l'image doit être masquée");
            assert.strictEqual(logo.appelsSetAttribute.length, 0,
                "logo = " + JSON.stringify(valeur) + " : aucun setAttribute");
        }
        console.log("1c. une valeur qui n'est pas une chaîne vaut « pas de logo »");
    }

    // 1d. Src déjà égal : setAttribute n'est PAS appelé (inertie du DOM par
    //     défaut — c'est ce qui protège la fiche de secours).
    {
        const logo = creerLogo("images/favicon.jpeg", true);
        await demarrer(Object.assign({}, IDENTITE, { logo: "images/favicon.jpeg" }), logo);
        assert.strictEqual(logo.appelsSetAttribute.length, 0,
            "src déjà égal : setAttribute ne doit pas être appelé");
        assert.deepStrictEqual(logo.style, { display: "" },
            "src déjà égal : le style de l'image ne doit pas être touché");
        console.log("1d. src déjà égal : aucun setAttribute, style intact");
    }

    // 1e. Sans identité utilisable : l'image n'est pas touchée.
    {
        for (const cabinet of [
            Object.assign({}, IDENTITE, { praticien: "", logo: "images/cabinet/l.png" }),
            Object.assign({}, IDENTITE, { praticien: "   ", logo: "" })
        ]) {
            const logo = creerLogo("images/favicon.jpeg", true);
            await demarrer(cabinet, logo);
            assert.deepStrictEqual(logo.style, { display: "" },
                "sans identité, le style de l'image ne doit pas être touché");
            assert.strictEqual(logo.attributs.src, "images/favicon.jpeg");
            assert.strictEqual(logo.appelsSetAttribute.length, 0);
        }
        // Et /cabinet injoignable : cabinet reste null, rien ne bouge non plus.
        const logo = creerLogo("images/favicon.jpeg", true);
        const c = charger(IDENTITE, logo);
        c.appliquerCabinet();
        assert.deepStrictEqual(logo.style, { display: "" });
        assert.strictEqual(logo.appelsSetAttribute.length, 0);
        console.log("1e. sans identité utilisable, #logo n'est pas touché");
    }

    // 1f. Une page sans #logo : ni levée, ni attente.
    {
        const c = await demarrer(Object.assign({}, IDENTITE, { logo: "images/cabinet/l.png" }), null);
        await c.logoPret();
        console.log("1f. une page sans #logo ne lève pas et n'attend pas");
    }

    // ===================================================================
    // 2. Attente du logo avant la capture
    // ===================================================================

    // 2a. Image pas complète : html2canvas n'est appelé qu'APRÈS « load ».
    for (const evenementFin of ["load", "error"]) {
        const logo = creerLogo("images/favicon.jpeg", false);
        // Minuteries consignées et jamais exécutées : seul l'événement peut
        // libérer l'attente, jamais le délai de secours.
        const c = await demarrer(Object.assign({}, IDENTITE, { logo: "images/cabinet/l.png" }), logo, true);

        const export_ = c.exporterBilanPDF();
        await ticks(10);
        assert.strictEqual(c._evenements.length, 0,
            "logo non chargé : html2canvas ne doit pas être appelé avant « "
            + evenementFin + " »");

        c._evenements.push(evenementFin);
        logo.declencher(evenementFin);
        const abandon = new Promise((r) => setTimeout(() => r("bloque"), 1000));
        const issue = await Promise.race([export_.then(() => "termine"), abandon]);
        assert.strictEqual(issue, "termine",
            "l'événement « " + evenementFin + " » doit libérer l'export sans attendre le délai");
        assert.deepStrictEqual(c._evenements, [evenementFin, "html2canvas"],
            "html2canvas doit suivre l'événement « " + evenementFin + " »");
        assert.strictEqual(c._depots(), 1, "l'export doit aller jusqu'au dépôt");
        console.log("2a. logo non chargé : la capture attend l'événement « "
                  + evenementFin + " »");
    }

    // 2b. Aucun événement : après DELAI_LOGO la capture part quand même.
    {
        const logo = creerLogo("images/favicon.jpeg", false);
        const c = await demarrer(Object.assign({}, IDENTITE, { logo: "images/cabinet/l.png" }), logo, true);
        assert.strictEqual(c._delaiLogo(), 3000, "DELAI_LOGO = 3000 ms (contrat C2-T2)");

        const export_ = c.exporterBilanPDF();
        await ticks(10);
        assert.strictEqual(c._evenements.length, 0,
            "logo non chargé, délai non écoulé : pas de capture");
        const minuterie = c._timers.find((t) => t.ms === c._delaiLogo());
        assert.ok(minuterie, "une minuterie de DELAI_LOGO doit borner l'attente");

        minuterie.f();   // le délai s'écoule
        await export_;
        assert.deepStrictEqual(c._evenements, ["html2canvas"],
            "après DELAI_LOGO, la capture part sans l'événement");
        assert.strictEqual(c._depots(), 1, "l'export n'est pas bloqué par un logo qui n'arrive pas");

        // Un « load » tardif ne relance rien et ne lève pas.
        logo.declencher("load");
        console.log("2b. aucun événement : la capture part après DELAI_LOGO, l'export aboutit");
    }

    // 2c. Rien à attendre : image complète, ou masquée.
    {
        const logoComplet = creerLogo("images/favicon.jpeg", true);
        const c1 = await demarrer(Object.assign({}, IDENTITE, { logo: "images/favicon.jpeg" }), logoComplet, true);
        await c1.logoPret();
        assert.ok(!c1._timers.some((t) => t.ms === c1._delaiLogo()),
            "image complète : aucune minuterie d'attente");
        assert.strictEqual(logoComplet.nombreEcouteurs(), 0,
            "image complète : aucun écouteur posé");

        const logoMasque = creerLogo("images/favicon.jpeg", false);
        const c2 = await demarrer(Object.assign({}, IDENTITE, { logo: "" }), logoMasque, true);
        await c2.logoPret();
        assert.ok(!c2._timers.some((t) => t.ms === c2._delaiLogo()),
            "image masquée : aucune minuterie d'attente");
        assert.strictEqual(logoMasque.nombreEcouteurs(), 0,
            "image masquée : aucun écouteur posé");
        console.log("2c. image complète ou masquée : on n'attend pas");
    }

    // 2d. Le délai s'arrête avec l'événement : pas de minuterie résiduelle.
    {
        const logo = creerLogo("images/favicon.jpeg", false);
        const c = await demarrer(Object.assign({}, IDENTITE, { logo: "images/cabinet/l.png" }), logo, true);
        const attente = c.logoPret();
        assert.ok(c._timers.some((t) => t.ms === c._delaiLogo()));
        logo.declencher("load");
        await attente;
        assert.ok(!c._timers.some((t) => t.ms === c._delaiLogo()),
            "la minuterie doit être annulée dès que le logo est chargé");
        console.log("2d. la minuterie d'attente est annulée une fois le logo chargé");
    }

    console.log("\nTout est vert.");
})().catch((erreur) => {
    console.error(erreur);
    process.exit(1);
});
