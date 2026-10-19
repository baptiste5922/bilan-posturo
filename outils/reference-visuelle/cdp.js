// Pilotage de Chrome par le protocole de débogage, sans aucune dépendance.
// Node 24 expose WebSocket en global : il n'y a rien à installer.
//
// Lance Chrome, ouvre un canal sur l'onglet, et rend un objet avec deux
// fonctions : `cmd(methode, params)` et `attendre(evenement)`.

const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function pause(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

async function lireJson(url, essais = 40) {
    for (let i = 0; i < essais; i += 1) {
        try {
            const reponse = await fetch(url);
            if (reponse.ok) return await reponse.json();
        } catch (e) { /* Chrome n'écoute pas encore */ }
        await pause(250);
    }
    throw new Error("Chrome n'a pas ouvert son port de débogage : " + url);
}

/**
 * Démarre Chrome et rend un canal de pilotage.
 *
 * `largeur`/`hauteur` fixent la fenêtre : le rendu du PDF passe par
 * html2canvas, donc la taille de la zone visible change la mise en page.
 */
async function ouvrirChrome({ port = 9222, largeur = 1280, hauteur = 900,
                              dossierTelechargement, visible = false } = {}) {
    if (!fs.existsSync(CHROME)) {
        throw new Error("Google Chrome n'est pas installé dans /Applications.");
    }
    // Un Chrome déjà en écoute sur ce port est réutilisé : le tout premier
    // démarrage initialise le profil et peut dépasser la minute, ce qui avait
    // fait expirer l'essai initial.
    let dejaLa = false;
    try {
        const r = await fetch("http://127.0.0.1:" + port + "/json/version");
        dejaLa = r.ok;
    } catch (e) { dejaLa = false; }

    const profil = fs.mkdtempSync(path.join(os.tmpdir(), "profil-chrome-"));
    const arguments_ = [
        "--remote-debugging-port=" + port,
        "--user-data-dir=" + profil,
        "--no-first-run", "--no-default-browser-check",
        "--disable-background-networking", "--disable-sync",
        "--window-size=" + largeur + "," + hauteur,
        "about:blank"
    ];
    if (!visible) arguments_.unshift("--headless=new");

    const processus = dejaLa ? null : spawn(CHROME, arguments_, { stdio: "ignore" });

    // 240 essais × 250 ms = une minute de patience au premier démarrage.
    const version = await lireJson("http://127.0.0.1:" + port + "/json/version", 240);
    const onglets = await lireJson("http://127.0.0.1:" + port + "/json/list");
    const page = onglets.find((o) => o.type === "page");
    if (!page) throw new Error("aucun onglet trouvé");

    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise((ok, non) => {
        ws.addEventListener("open", ok, { once: true });
        ws.addEventListener("error", () => non(new Error("canal refusé")), { once: true });
    });

    let compteur = 0;
    const attentes = new Map();
    const guetteurs = [];

    ws.addEventListener("message", (message) => {
        const donnees = JSON.parse(message.data);
        if (donnees.id && attentes.has(donnees.id)) {
            const { ok, non } = attentes.get(donnees.id);
            attentes.delete(donnees.id);
            if (donnees.error) non(new Error(donnees.error.message));
            else ok(donnees.result);
            return;
        }
        for (let i = guetteurs.length - 1; i >= 0; i -= 1) {
            if (guetteurs[i].nom === donnees.method) {
                guetteurs[i].ok(donnees.params);
                guetteurs.splice(i, 1);
            }
        }
    });

    function cmd(methode, params = {}) {
        compteur += 1;
        const id = compteur;
        return new Promise((ok, non) => {
            attentes.set(id, { ok, non });
            ws.send(JSON.stringify({ id, method: methode, params }));
            setTimeout(() => {
                if (attentes.has(id)) {
                    attentes.delete(id);
                    non(new Error("délai dépassé sur " + methode));
                }
            }, 30000);
        });
    }

    function attendre(nom, delai = 20000) {
        return new Promise((ok, non) => {
            guetteurs.push({ nom, ok });
            setTimeout(() => non(new Error("évènement jamais reçu : " + nom)), delai);
        });
    }

    await cmd("Page.enable");
    await cmd("Runtime.enable");
    if (dossierTelechargement) {
        fs.mkdirSync(dossierTelechargement, { recursive: true });
        await cmd("Browser.setDownloadBehavior", {
            behavior: "allow", downloadPath: dossierTelechargement, eventsEnabled: true
        });
    }

    /** Évalue une expression dans la page et rend sa valeur. */
    async function evaluer(expression) {
        const r = await cmd("Runtime.evaluate", {
            expression, returnByValue: true, awaitPromise: true
        });
        if (r.exceptionDetails) {
            throw new Error("erreur dans la page : "
                + (r.exceptionDetails.exception
                    ? r.exceptionDetails.exception.description
                    : r.exceptionDetails.text));
        }
        return r.result.value;
    }

    async function aller(url) {
        const chargement = attendre("Page.loadEventFired");
        await cmd("Page.navigate", { url });
        await chargement;
        await pause(400);   // laisse les scripts de démarrage s'exécuter
    }

    function fermer() {
        try { ws.close(); } catch (e) {}
        if (processus) { try { processus.kill(); } catch (e) {} }
    }

    return { cmd, attendre, evaluer, aller, fermer, pause,
             navigateur: version["User-Agent"], profil };
}

module.exports = { ouvrirChrome, pause };
