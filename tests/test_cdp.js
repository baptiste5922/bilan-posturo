/*
 * Tests du refus d'un port occupé par outils/reference-visuelle/cdp.js
 * (C1-T6b, point 1 : R2 de l'audit de C1-T6).
 *
 * Un Chrome laissé en écoute par un essai précédent tourne à une fenêtre
 * inconnue : `--window-size` n'a alors aucun effet, et un verdict « au pixel »
 * produit là-dedans ne prouve rien. `ouvrirChrome` refuse donc tout port qui
 * répond. Ces cas n'ont besoin d'aucun Chrome : un petit serveur HTTP local
 * tient le rôle du port occupé, et le refus survient avant tout le reste, ce
 * qui permet de les jouer sous Linux, Windows et macOS, donc en CI.
 *
 *     node tests/test_cdp.js
 */

const assert = require("assert");
const fs = require("fs");
const http = require("http");
const net = require("net");
const os = require("os");
const path = require("path");

const { ouvrirChrome, portEstOccupe } = require(path.join(__dirname, "..", "outils", "reference-visuelle", "cdp.js"));

let nbCas = 0;
const echecs = [];
async function cas(nom, fn) {
    nbCas += 1;
    try {
        await fn();
        console.log("ok - " + nom);
    } catch (erreur) {
        echecs.push(nom);
        console.log("ECHEC - " + nom + "\n    " + String(erreur.message).split("\n").join("\n    "));
    }
}

/** Un serveur local qui répond `statut` à toute requête ; rend serveur et port. */
function occuperUnPort(statut) {
    return new Promise((ok) => {
        const serveur = http.createServer((requete, reponse) => {
            reponse.writeHead(statut, { "Content-Type": "application/json" });
            reponse.end("{}");
        });
        serveur.listen(0, "127.0.0.1", () => ok({ serveur, port: serveur.address().port }));
    });
}

function fermerServeur(serveur) {
    return new Promise((ok) => {
        serveur.close(ok);
        // Les connexions keep-alive de fetch retardent la fermeture : on les coupe.
        if (typeof serveur.closeAllConnections === "function") serveur.closeAllConnections();
    });
}

/**
 * Un serveur qui accepte la connexion et ne répond jamais : le cas que « le
 * port répond » ne couvre pas. Il tient le port aussi sûrement qu'un autre.
 */
function occuperUnPortMuet() {
    return new Promise((ok) => {
        const sockets = new Set();
        const serveur = net.createServer((socket) => {
            sockets.add(socket);
            socket.on("error", () => {});
            socket.on("close", () => sockets.delete(socket));
        });
        serveur.listen(0, "127.0.0.1", () => ok({
            serveur, port: serveur.address().port,
            fermer: () => new Promise((fini) => {
                sockets.forEach((s) => s.destroy());
                serveur.close(fini);
            })
        }));
    });
}

/** Un port que personne n'écoute : on en réserve un, puis on le rend. */
function portLibre() {
    return new Promise((ok) => {
        const serveur = net.createServer();
        serveur.listen(0, "127.0.0.1", () => {
            const port = serveur.address().port;
            serveur.close(() => ok(port));
        });
    });
}

function compterProfils() {
    return fs.readdirSync(os.tmpdir()).filter((n) => n.startsWith("profil-chrome-")).length;
}

/**
 * Appelle `ouvrirChrome` sur le port et rend le rejet. Un succès, ou un
 * dépassement de 5 s, est un échec du cas : le refus doit être immédiat.
 */
async function rejetDe(port) {
    let minuteur;
    const delai = new Promise((_, non) => {
        minuteur = setTimeout(() => non(new Error("aucun refus en 5 s : cdp.js a continué sur un port occupé")), 5000);
    });
    try {
        const canal = await Promise.race([ouvrirChrome({ port }), delai]);
        try { canal.fermer(); } catch (e) { /* rien à fermer */ }
        throw new Error("ouvrirChrome a réussi sur un port occupé");
    } catch (erreur) {
        return erreur;
    } finally {
        clearTimeout(minuteur);
    }
}

(async () => {
    await cas("un port qui répond 200 sur /json/version est refusé", async () => {
        const { serveur, port } = await occuperUnPort(200);
        try {
            const erreur = await rejetDe(port);
            assert.ok(String(erreur.message).includes("Le port " + port + " est déjà occupé"),
                "message inattendu : " + erreur.message);
        } finally {
            await fermerServeur(serveur);
        }
    });

    await cas("un port qui répond 404 est refusé aussi", async () => {
        const { serveur, port } = await occuperUnPort(404);
        try {
            const erreur = await rejetDe(port);
            assert.ok(String(erreur.message).includes("Le port " + port + " est déjà occupé"),
                "message inattendu : " + erreur.message);
        } finally {
            await fermerServeur(serveur);
        }
    });

    await cas("aucun profil temporaire créé avant le refus", async () => {
        const { serveur, port } = await occuperUnPort(200);
        try {
            const avant = compterProfils();
            const erreur = await rejetDe(port);
            assert.ok(String(erreur.message).includes("est déjà occupé"), "message inattendu : " + erreur.message);
            assert.strictEqual(compterProfils(), avant, "un profil profil-chrome-* a été créé avant le refus");
        } finally {
            await fermerServeur(serveur);
        }
    });

    await cas("un port qui accepte la connexion sans jamais répondre est refusé, en moins de 5 s", async () => {
        const muet = await occuperUnPortMuet();
        try {
            const debut = Date.now();
            const erreur = await rejetDe(muet.port);
            assert.ok(String(erreur.message).includes("Le port " + muet.port + " est déjà occupé"),
                "message inattendu : " + erreur.message);
            assert.ok(Date.now() - debut < 5000, "refus trop lent");
        } finally {
            await muet.fermer();
        }
    });

    await cas("un port dont la connexion est refusée est déclaré libre", async () => {
        const port = await portLibre();
        assert.strictEqual(await portEstOccupe(port), false, "le port " + port + " est libre");
    });

    console.log("\n" + nbCas + " cas joués, " + echecs.length + " en échec.");
    if (echecs.length > 0) {
        console.log("Échecs : " + echecs.join(" ; "));
        process.exit(1);
    }
    console.log("Tout est vert.");
})().catch((erreur) => {
    console.error(erreur);
    process.exit(1);
});
