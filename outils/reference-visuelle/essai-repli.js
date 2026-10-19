// Critère 2 du contrat C1-T3b : éprouver la fiche de secours.
//
// Le scénario est celui d'un mardi matin : une consultation commencée sur le
// moteur, le formulaire qui ne répond plus, la praticienne qui bascule sur la
// fiche de secours et termine son bilan. On vérifie que la saisie n'est pas
// perdue et que le PDF arrive bien sur le PC.
//
// Contre un vrai serveur `serveur.py`, en HTTPS, derrière authentification,
// dans un bac à sable : ni la configuration du cabinet, ni ses clés, ni son
// dossier de bilans ne sont touchés.

const fs = require("fs");
const path = require("path");
const { ouvrirChrome, pause } = require("./cdp.js");

const BASE = "https://127.0.0.1:8443";
const BAC = path.join(__dirname, "essai-repli");
const BILANS = path.join(BAC, "bilans");
const IDENTIFIANTS = Buffer.from("essai:essai-repli-2026").toString("base64");

function bilansDeposes() {
    return fs.existsSync(BILANS) ? fs.readdirSync(BILANS).filter((f) => f.endsWith(".pdf")) : [];
}

(async function () {
    let chrome;
    const etapes = [];
    const note = (ok, texte) => { etapes.push((ok ? "  OK   " : "  RATÉ ") + texte); return ok; };
    try {
        chrome = await ouvrirChrome({ port: 9333, ignorerCertificat: true });
        await chrome.cmd("Network.setExtraHTTPHeaders",
            { headers: { Authorization: "Basic " + IDENTIFIANTS } });
        await chrome.cmd("Security.enable");
        await chrome.cmd("Security.setIgnoreCertificateErrors", { ignore: true });

        const avant = bilansDeposes();

        // 1. Une consultation commence sur le moteur.
        await chrome.aller(BASE + "/index.html");
        await pause(1200);
        const rendu = await chrome.evaluer(
            `document.querySelectorAll("#form-bilan .bloc").length`);
        note(rendu === 29, "le moteur rend le formulaire derrière l'authentification ("
            + rendu + " blocs)");

        await chrome.evaluer(`(() => {
            const poser = (id, v) => { const c = document.getElementById(id);
                c.value = v; c.dispatchEvent(new Event("input", { bubbles: true })); };
            poser("nom", "Essai");
            poser("prenom", "Repli");
            poser("MDC", "Consultation interrompue : on bascule sur la fiche de secours.");
        })()`);
        await pause(2000);   // la sauvegarde différée écrit le brouillon

        // 2. Le formulaire ne répond plus : la praticienne ouvre le favori.
        await chrome.aller(BASE + "/index-v1.html");
        await pause(900);
        const secours = await chrome.evaluer(`(() => ({
            blocs: document.querySelectorAll("#form-bilan .bloc").length,
            moteur: document.getElementById("form-bilan").hasAttribute("data-moteur"),
            restaurer: !!document.getElementById("btn-restaurer")
        }))()`);
        note(secours.blocs === 29 && secours.moteur === false,
            "la fiche de secours s'ouvre, sans le moteur (" + secours.blocs + " blocs)");
        note(secours.restaurer, "elle propose de restaurer le bilan en cours");

        // 3. Elle reprend sa saisie.
        await chrome.evaluer(`(() => { const b = document.getElementById("btn-restaurer");
            if (b) b.click(); })()`);
        await pause(1500);
        const repris = await chrome.evaluer(`(() => ({
            nom: (document.getElementById("nom") || {}).value || "",
            mdc: (document.getElementById("MDC") || {}).value || ""
        }))()`);
        note(repris.nom === "Essai" && repris.mdc.indexOf("interrompue") !== -1,
            "la saisie commencée sur le moteur est reprise telle quelle");

        // 4. Elle termine et génère le bilan.
        await chrome.evaluer(`(() => {
            const c = document.getElementById("conseils");
            c.value = "Bilan terminé depuis la fiche de secours.";
            c.dispatchEvent(new Event("input", { bubbles: true }));
        })()`);
        await pause(1200);
        await chrome.evaluer(`document.getElementById("btn-export").click()`);

        let depose = null;
        for (let i = 0; i < 60; i += 1) {
            await pause(1000);
            const neufs = bilansDeposes().filter((f) => avant.indexOf(f) === -1);
            if (neufs.length) { depose = neufs[0]; break; }
        }
        note(depose !== null, "le PDF arrive dans le dossier des bilans du PC"
            + (depose ? " : " + depose : ""));
        if (depose) {
            const octets = fs.statSync(path.join(BILANS, depose)).size;
            note(octets > 50000, "le fichier déposé est un PDF complet (" + octets + " octets)");
            const tete = fs.readFileSync(path.join(BILANS, depose)).subarray(0, 5).toString();
            note(tete === "%PDF-", "il commence bien par l'en-tête d'un PDF");
        }

        // 5. Le message du moteur nomme-t-il ce chemin de secours ?
        const message = await chrome.evaluer(`(() => {
            const s = document.createElement("script"); return null; })()`);
        const sourceMoteur = fs.readFileSync(
            path.join(BAC, "formulaire/moteur/rendu.js"), "utf-8");
        note(sourceMoteur.indexOf("secours V1") !== -1
            && sourceMoteur.indexOf("index-v1.html") !== -1,
            "le message d'erreur du moteur nomme le favori et l'adresse");
    } catch (erreur) {
        etapes.push("  RATÉ  " + erreur.message);
        process.exitCode = 1;
    } finally {
        if (chrome) chrome.fermer();
    }

    console.log("Essai de la fiche de secours — scénario d'une consultation interrompue\n");
    etapes.forEach((e) => console.log(e));
    const rates = etapes.filter((e) => e.indexOf("RATÉ") !== -1).length;
    console.log("\n" + (rates === 0
        ? "Le repli fonctionne de bout en bout."
        : rates + " étape(s) en échec."));
    if (rates) process.exitCode = 1;
})();
