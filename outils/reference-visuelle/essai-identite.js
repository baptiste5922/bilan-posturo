// Critères de rendu réel du contrat C2-T1 : l'identité du cabinet dans
// l'en-tête, et le refus d'exporter un bilan anonyme.
//
// Deux scénarios, contre un vrai serveur `serveur.py` en HTTPS, derrière
// authentification, dans un bac à sable dont le `config.json` porte une
// identité fictive :
//
//   A. Identité configurée : l'en-tête affiche les lignes que rend
//      GET /cabinet, et le PDF déposé porte cet en-tête en première page.
//   B. Route /cabinet injoignable (bloquée par Chrome) : en-tête vide,
//      bandeau d'avertissement, saisie et brouillon intacts, export refusé
//      avec un message, aucun PDF déposé, file de dépôts vide.
//
// Le bac à sable se construit en copiant les fichiers suivis par
// `git ls-files -z` (jamais `cp -r` : CLAUDE.md), puis en y lançant
// `generer_autorite.py 127.0.0.1` et `serveur.py` — jamais depuis le dépôt.
//
//   ESSAI_BASE=https://127.0.0.1:8444 \
//   ESSAI_BILANS=/chemin/du/bac/bilans \
//   ESSAI_IDENTIFIANTS=utilisateur:mot-de-passe \
//   ESSAI_SORTIE=/dossier/des/captures \
//   node outils/reference-visuelle/essai-identite.js
//
// La première page du PDF est extraite telle que jsPDF l'a écrite (flux
// JPEG) dans ESSAI_SORTIE : c'est elle qu'on regarde pour l'en-tête, aucun
// programme ne sachant lire du texte dans une image.

const fs = require("fs");
const path = require("path");
const { ouvrirChrome, pause } = require("./cdp.js");

const BASE = process.env.ESSAI_BASE || "https://127.0.0.1:8444";
const BILANS = process.env.ESSAI_BILANS;
const IDENTIFIANTS = Buffer.from(process.env.ESSAI_IDENTIFIANTS || "").toString("base64");
const SORTIE = process.env.ESSAI_SORTIE || path.join(__dirname, "sortie");

if (!BILANS || !process.env.ESSAI_IDENTIFIANTS) {
    console.error("ESSAI_BILANS et ESSAI_IDENTIFIANTS sont obligatoires (voir l'en-tête du fichier).");
    process.exit(2);
}

function bilansDeposes() {
    return fs.existsSync(BILANS) ? fs.readdirSync(BILANS).filter((f) => f.endsWith(".pdf")) : [];
}

/** Le premier flux JPEG d'un PDF jsPDF : l'image de la première page. */
function premierePage(cheminPdf) {
    const donnees = fs.readFileSync(cheminPdf);
    const texte = donnees.toString("latin1");
    const i = texte.indexOf("/DCTDecode");
    if (i === -1) return null;
    let debut = texte.indexOf("stream", i) + "stream".length;
    if (texte[debut] === "\r") debut += 1;
    if (texte[debut] === "\n") debut += 1;
    const fin = texte.indexOf("endstream", debut);
    return donnees.subarray(debut, fin);
}

async function capturer(chrome, nom, selecteur) {
    const zone = await chrome.evaluer(`(() => {
        const r = document.querySelector(${JSON.stringify(selecteur)}).getBoundingClientRect();
        return { x: r.left + scrollX, y: r.top + scrollY, width: r.width, height: r.height };
    })()`);
    const image = await chrome.cmd("Page.captureScreenshot",
        { format: "png", clip: Object.assign(zone, { scale: 1 }), captureBeyondViewport: true });
    const chemin = path.join(SORTIE, nom);
    fs.writeFileSync(chemin, Buffer.from(image.data, "base64"));
    return chemin;
}

/** Nombre d'entrées dans la file de dépôts IndexedDB de la page. */
const FILE_DEPOTS = `new Promise((ok) => {
    const r = indexedDB.open("bilan-posturo");
    r.onsuccess = () => {
        const base = r.result;
        if (!base.objectStoreNames.contains("file-depots")) { base.close(); ok(0); return; }
        const c = base.transaction("file-depots").objectStore("file-depots").count();
        c.onsuccess = () => { base.close(); ok(c.result); };
        c.onerror = () => { base.close(); ok(-1); };
    };
    r.onerror = () => ok(-1);
})`;

function saisir(valeurs) {
    return `(() => {
        const valeurs = ${JSON.stringify(valeurs)};
        Object.keys(valeurs).forEach((id) => {
            const c = document.getElementById(id);
            c.value = valeurs[id];
            c.dispatchEvent(new Event("input", { bubbles: true }));
        });
    })()`;
}

(async function () {
    let chrome;
    const etapes = [];
    const note = (ok, texte) => { etapes.push((ok ? "  OK   " : "  RATÉ ") + texte); return ok; };
    fs.mkdirSync(SORTIE, { recursive: true });
    try {
        chrome = await ouvrirChrome({ port: 9334 });
        await chrome.cmd("Network.enable");
        await chrome.cmd("Network.setCacheDisabled", { cacheDisabled: true });
        await chrome.cmd("Network.setExtraHTTPHeaders",
            { headers: { Authorization: "Basic " + IDENTIFIANTS } });
        await chrome.cmd("Security.enable");
        await chrome.cmd("Security.setIgnoreCertificateErrors", { ignore: true });

        // ---------------- A. Identité configurée ----------------
        etapes.push("A. Identité configurée");
        const avantA = bilansDeposes();
        await chrome.aller(BASE + "/index.html");
        await pause(2000);

        // Les lignes attendues sont dérivées de la route, jamais recopiées.
        const cabinet = await chrome.evaluer(`fetch("/cabinet").then((r) => r.json())`);
        const attendues = [cabinet.praticien, cabinet.adresse,
            cabinet.courriel ? "mail: " + cabinet.courriel : "",
            cabinet.telephone ? "tel: " + cabinet.telephone : ""].filter(Boolean);
        const lignes = await chrome.evaluer(
            `Array.from(document.querySelectorAll("#infos_podo p")).map((p) => p.textContent)`);
        note(attendues.length === 4 && JSON.stringify(lignes) === JSON.stringify(attendues),
            "l'en-tête affiche les quatre lignes de GET /cabinet : " + JSON.stringify(lignes));
        note(true, "capture de l'en-tête : " + await capturer(chrome, "C2-T1-entete-ecran.png", "header"));

        await chrome.evaluer(saisir({ nom: "Essai", prenom: "Identite" }));
        await pause(1200);
        await chrome.evaluer(`document.getElementById("btn-export").click()`);
        let depose = null;
        for (let i = 0; i < 60 && !depose; i += 1) {
            await pause(1000);
            depose = bilansDeposes().filter((f) => avantA.indexOf(f) === -1)[0] || null;
        }
        note(depose !== null, "le PDF arrive dans le dossier des bilans : " + depose);
        if (depose) {
            const cheminPdf = path.join(BILANS, depose);
            note(fs.readFileSync(cheminPdf).subarray(0, 5).toString() === "%PDF-",
                "il commence par l'en-tête d'un PDF");
            const page = premierePage(cheminPdf);
            if (note(page !== null, "la première page est une image JPEG extraite")) {
                const chemin = path.join(SORTIE, "C2-T1-pdf-page1.jpg");
                fs.writeFileSync(chemin, page);
                etapes.push("       → à regarder : " + chemin);
            }
        }

        // ---------------- B. Route /cabinet injoignable ----------------
        etapes.push("B. Route /cabinet injoignable");
        await chrome.cmd("Network.setBlockedURLs", { urls: ["*/cabinet*"] });
        const avantB = bilansDeposes();
        await chrome.aller(BASE + "/index.html");
        await pause(2500);

        const entete = await chrome.evaluer(`document.getElementById("infos_podo").textContent.trim()`);
        note(entete === "", "l'en-tête reste vide");
        const bandeau = await chrome.evaluer(`(() => { const z = document.getElementById("zone-messages");
            return { visible: !z.hidden, texte: z.textContent.trim() }; })()`);
        note(bandeau.visible && bandeau.texte.length > 0,
            "un bandeau d'avertissement s'affiche : « " + bandeau.texte + " »");

        await chrome.evaluer(saisir({ nom: "Essai", prenom: "Injoignable",
            MDC: "Saisie faite pendant que le PC ne répond pas." }));
        await pause(2500);   // la sauvegarde différée écrit le brouillon
        const saisie = await chrome.evaluer(`document.getElementById("MDC").value`);
        note(saisie.indexOf("PC ne répond pas") !== -1, "le formulaire reste saisissable");
        const brouillon = await chrome.evaluer(`(() => { for (let i = 0; i < localStorage.length; i += 1) {
            if ((localStorage.getItem(localStorage.key(i)) || "").indexOf("Injoignable") !== -1) return true; }
            return false; })()`);
        note(brouillon, "le brouillon continue d'être écrit");

        const fileAvant = await chrome.evaluer(FILE_DEPOTS);
        await chrome.evaluer(`document.getElementById("btn-export").click()`);
        await pause(9000);   // seconde tentative de chargement de l'identité comprise
        const refus = await chrome.evaluer(`document.getElementById("zone-messages").textContent.trim()`);
        note(refus.indexOf("ne répond pas") !== -1, "l'export est refusé avec un message : « " + refus + " »");
        note(bilansDeposes().filter((f) => avantB.indexOf(f) === -1).length === 0, "aucun PDF n'est déposé");
        const fileApres = await chrome.evaluer(FILE_DEPOTS);
        note(fileApres === fileAvant && fileApres === 0,
            "aucune entrée dans la file de dépôts (" + fileAvant + " → " + fileApres + ")");
        const bouton = await chrome.evaluer(`getComputedStyle(document.getElementById("btn-export")).display`);
        note(bouton !== "none", "le bouton d'export réapparaît pour réessayer");
        note(true, "capture : " + await capturer(chrome, "C2-T1-injoignable.png", "body"));
    } catch (erreur) {
        etapes.push("  RATÉ  " + erreur.message);
        process.exitCode = 1;
    } finally {
        if (chrome) chrome.fermer();
    }

    console.log("Essai C2-T1 — identité du cabinet en rendu réel\n");
    etapes.forEach((e) => console.log(e));
    const rates = etapes.filter((e) => e.indexOf("RATÉ") !== -1).length;
    console.log("\n" + (rates === 0 ? "Les deux critères tiennent en rendu réel." : rates + " étape(s) en échec."));
    if (rates) process.exitCode = 1;
})();
