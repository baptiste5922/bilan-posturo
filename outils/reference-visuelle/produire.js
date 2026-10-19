// Produit le jeu de référence d'une des deux pages du formulaire.
//
//   node produire.js v1       → remplit le bilan témoin sur index-v1.html
//   node produire.js moteur   → rejoue le même brouillon sur index.html
//
// Dans les deux cas : PDF, deux captures d'écran, et pour « v1 » le brouillon
// lui-même, qui est ce qui permet de rejouer à l'identique.

const fs = require("fs");
const path = require("path");
const { ouvrirChrome, pause } = require("./cdp.js");

const BASE = "http://127.0.0.1:8777";
const SORTIE = path.join(__dirname, "sortie");
const BROUILLON = path.join(SORTIE, "bilan-reference.json");

const cible = process.argv[2];
if (cible !== "v1" && cible !== "moteur") {
    console.error("usage : node produire.js v1|moteur");
    process.exit(2);
}

// Le bilan témoin. Aucune donnée réelle : « Témoin Référence », né le 01/01/1980.
// Les zones de texte sont longues à dessein — il faut au moins trois pages de
// PDF pour que la pagination et le numéro de page entrent dans la comparaison.
const PARAGRAPHE = [
    "Patiente témoin servant de référence visuelle avant la bascule du",
    "formulaire sur le moteur de rendu à schéma. Ce texte n'a aucune valeur",
    "clinique : il occupe la place d'un compte rendu réel afin que la",
    "pagination, les retours à la ligne et la hauteur des blocs soient",
    "exercés comme ils le seraient un jour de consultation ordinaire.",
    "La longueur compte autant que le contenu, puisque c'est elle qui",
    "détermine le nombre de pages du document produit."
].join(" ");

const TEXTES = {
    "date-bilan": "2026-10-19",
    nom: "Témoin",
    prenom: "Référence",
    date_naissance: "01/01/1980",
    metier: "profession témoin",
    sport: "marche",
    niveau_scolaire: "sans objet"
};

const ZONES = {
    MDC: "Motif de consultation témoin. " + PARAGRAPHE,
    oriente_par: "Orientation témoin, sans praticien réel.",
    "spécialistes": "Aucun spécialiste réel : champ témoin.",
    perso: "Antécédents personnels témoins. " + PARAGRAPHE,
    familliaux: "Antécédents familiaux témoins. " + PARAGRAPHE,
    elements_testes: "Éléments testés, texte témoin. " + PARAGRAPHE,
    bilan_algique: "Bilan algique témoin. " + PARAGRAPHE,
    bilan_morpho: "Bilan morphologique témoin. " + PARAGRAPHE,
    bilan_def: "Bilan des déformations, témoin. " + PARAGRAPHE,
    enregistrement_plateforme: "Enregistrement témoin sur plateforme.",
    plan_texte: "Plan d'appareillage témoin. " + PARAGRAPHE,
    recouvrement: "Recouvrement témoin.",
    conseils: "Conseils témoins au patient. " + PARAGRAPHE,
    orientation: "Orientation de fin, témoin."
};

const CASES = ["symétrique", "Isthme", "pédieux", "tibial",
               "empreinte_encre", "usee_ville"];
const RADIOS_AVEC_ID = ["SO_oui", "anterieur", "isthme_g", "gauche"];
// Les quatre lignes des deux tableaux : pas d'`id`, la clé de brouillon est
// `name + "#" + value`. C'est le chemin le plus fragile de la restauration.
const RADIOS_TABLEAU = [["test_positif", "G"], ["membre_court", "D"],
                        ["dorsal", "G"], ["lombaire", "D"]];

async function remplir(chrome) {
    const rapport = await chrome.evaluer(`(() => {
        const manquants = [];
        const poser = (id, valeur) => {
            const champ = document.getElementById(id);
            if (!champ) { manquants.push(id); return; }
            champ.value = valeur;
            champ.dispatchEvent(new Event("input", { bubbles: true }));
            champ.dispatchEvent(new Event("change", { bubbles: true }));
        };
        const textes = ${JSON.stringify(TEXTES)};
        const zones = ${JSON.stringify(ZONES)};
        Object.keys(textes).forEach((id) => poser(id, textes[id]));
        Object.keys(zones).forEach((id) => poser(id, zones[id]));

        ${JSON.stringify(CASES)}.forEach((id) => {
            const c = document.getElementById(id);
            if (!c) { manquants.push(id); return; }
            if (!c.checked) c.click();
        });
        ${JSON.stringify(RADIOS_AVEC_ID)}.forEach((id) => {
            const r = document.getElementById(id);
            if (!r) { manquants.push(id); return; }
            if (!r.checked) r.click();
        });
        ${JSON.stringify(RADIOS_TABLEAU)}.forEach(([nom, valeur]) => {
            const r = document.querySelector(
                'input[type=radio][name="' + nom + '"][value="' + valeur + '"]');
            if (!r) { manquants.push(nom + "#" + valeur); return; }
            if (!r.checked) r.click();
        });
        return { manquants };
    })()`);
    if (rapport.manquants.length) {
        throw new Error("champs introuvables : " + rapport.manquants.join(", "));
    }
}

/** Trace un trait sur chacun des quatre schémas, par évènements de pointeur.
 *
 * Deux pièges, tous deux payés à la première tentative : les coordonnées de
 * `Input.dispatchMouseEvent` sont relatives à la **zone affichée**, pas au
 * document — une planche située à 1600 px de haut ne reçoit donc rien tant
 * qu'on n'a pas défilé jusqu'à elle ; et `zonesDessin` est une variable de
 * module, invisible depuis l'extérieur, si bien que seul le brouillon peut
 * témoigner de ce qui a réellement été tracé.
 */
async function dessiner(chrome) {
    const nombre = await chrome.evaluer(
        `document.querySelectorAll("canvas.calque-dessin").length`);
    if (nombre !== 4) {
        throw new Error("attendu 4 zones de dessin, trouvé " + nombre);
    }

    for (let i = 0; i < nombre; i += 1) {
        const z = await chrome.evaluer(`(() => {
            const c = document.querySelectorAll("canvas.calque-dessin")[${i}];
            c.scrollIntoView({ block: "center" });
            const r = c.getBoundingClientRect();
            return { x: r.x, y: r.y, w: r.width, h: r.height };
        })()`);
        await pause(350);
        const apres = await chrome.evaluer(`(() => {
            const c = document.querySelectorAll("canvas.calque-dessin")[${i}];
            const r = c.getBoundingClientRect();
            return { x: r.x, y: r.y, w: r.width, h: r.height };
        })()`);
        if (apres.y < 0 || apres.y + apres.h > 900) {
            throw new Error("planche " + (i + 1) + " hors de la zone affichée après défilement");
        }

        // Un trait oblique, différent sur chaque planche : une permutation des
        // images se verrait alors à l'œil comme à la comparaison.
        const depart = { x: apres.x + apres.w * 0.25,
                         y: apres.y + apres.h * (0.20 + i * 0.12) };
        const arrivee = { x: apres.x + apres.w * 0.75,
                          y: apres.y + apres.h * (0.70 - i * 0.08) };

        await chrome.cmd("Input.dispatchMouseEvent", {
            type: "mousePressed", x: depart.x, y: depart.y,
            button: "left", clickCount: 1, pointerType: "mouse"
        });
        const pas = 12;
        for (let k = 1; k <= pas; k += 1) {
            await chrome.cmd("Input.dispatchMouseEvent", {
                type: "mouseMoved",
                x: depart.x + (arrivee.x - depart.x) * (k / pas),
                y: depart.y + (arrivee.y - depart.y) * (k / pas),
                button: "left", pointerType: "mouse"
            });
            await pause(15);
        }
        await chrome.cmd("Input.dispatchMouseEvent", {
            type: "mouseReleased", x: arrivee.x, y: arrivee.y,
            button: "left", clickCount: 1, pointerType: "mouse"
        });
        await pause(120);
    }

    await chrome.evaluer(`window.scrollTo(0, 0)`);
    return nombre;
}

async function exporterPdf(chrome, nomAttendu) {
    const avant = new Set(fs.readdirSync(SORTIE));
    await chrome.evaluer(`document.getElementById("btn-export").click()`);

    // Le dépôt sur le PC n'existe pas ici : il expire au bout de 20 s
    // (DELAI_DEPOT), puis le PDF est téléchargé en repli — c'est le chemin
    // `enregistrerSurTablette()`, appelé quel que soit le sort du dépôt.
    for (let i = 0; i < 90; i += 1) {
        await pause(1000);
        const nouveaux = fs.readdirSync(SORTIE)
            .filter((f) => !avant.has(f) && f.endsWith(".pdf"));
        if (nouveaux.length) {
            const source = path.join(SORTIE, nouveaux[0]);
            const taille1 = fs.statSync(source).size;
            await pause(700);
            if (fs.statSync(source).size === taille1 && taille1 > 1000) {
                fs.renameSync(source, path.join(SORTIE, nomAttendu));
                return { fichier: nomAttendu, octets: taille1, nomOrigine: nouveaux[0] };
            }
        }
    }
    throw new Error("aucun PDF téléchargé après 90 s");
}

async function capturer(chrome, prefixe) {
    const hauteurTotale = await chrome.evaluer(
        `Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)`);
    const sorties = [];
    for (const [rang, position] of [[1, 0], [2, Math.max(0, hauteurTotale - 900)]]) {
        await chrome.evaluer(`window.scrollTo(0, ${position})`);
        await pause(500);
        const { data } = await chrome.cmd("Page.captureScreenshot", { format: "png" });
        const nom = prefixe + "-ecran-" + rang + ".png";
        fs.writeFileSync(path.join(SORTIE, nom), Buffer.from(data, "base64"));
        sorties.push(nom);
    }
    await chrome.evaluer(`window.scrollTo(0, 0)`);
    return sorties;
}

(async function () {
    fs.mkdirSync(SORTIE, { recursive: true });
    let chrome;
    try {
        chrome = await ouvrirChrome({ dossierTelechargement: SORTIE });

        if (cible === "v1") {
            await chrome.aller(BASE + "/index-v1.html");
            await remplir(chrome);
            const zones = await dessiner(chrome);
            console.log("rempli, " + zones + " planches annotées");
            await pause(2000);   // laisse la sauvegarde différée s'écrire

            const brut = await chrome.evaluer(
                `localStorage.getItem("bilan-posturo-brouillon")`);
            if (!brut) throw new Error("aucun brouillon en localStorage");
            fs.writeFileSync(BROUILLON, brut);
            const relu = JSON.parse(brut);
            console.log("brouillon : " + Object.keys(relu.valeurs || {}).length
                + " valeurs, " + Object.keys(relu.coches || {}).length + " cases, "
                + (relu.dessins || []).length + " planches, "
                + (relu.dessins || []).reduce((n, d) => n + d.length, 0) + " traits");

            const captures = await capturer(chrome, "V1-reference");
            const pdf = await exporterPdf(chrome, "V1-reference.pdf");
            console.log("PDF : " + pdf.fichier + " (" + pdf.octets + " octets, "
                + "nom produit par le formulaire : " + pdf.nomOrigine + ")");
            console.log("captures : " + captures.join(", "));
        } else {
            if (!fs.existsSync(BROUILLON)) {
                throw new Error("bilan-reference.json manquant : produire « v1 » d'abord");
            }
            const brut = fs.readFileSync(BROUILLON, "utf-8");
            await chrome.aller(BASE + "/index.html");
            await chrome.evaluer(
                `localStorage.setItem("bilan-posturo-brouillon", ${JSON.stringify(brut)})`);
            await chrome.aller(BASE + "/index.html");
            await pause(800);

            const restaure = await chrome.evaluer(`(() => {
                const b = document.getElementById("btn-restaurer");
                if (!b) return "bouton Restaurer absent";
                b.click();
                return "cliqué";
            })()`);
            await pause(1500);
            const etat = await chrome.evaluer(`(() => ({
                restaure: ${JSON.stringify(restaure)},
                nom: (document.getElementById("nom") || {}).value || "",
                mdc: ((document.getElementById("MDC") || {}).value || "").length,
                tableau: !!document.querySelector(
                    'input[type=radio][name="test_positif"][value="G"]:checked'),
                traits: window.zonesDessin
                    ? window.zonesDessin.reduce((n, z) => n + z.traits.length, 0) : -1
            }))()`);
            console.log("restauration : " + JSON.stringify(etat));

            const captures = await capturer(chrome, "C1-T3-moteur");
            const pdf = await exporterPdf(chrome, "C1-T3-moteur.pdf");
            console.log("PDF : " + pdf.fichier + " (" + pdf.octets + " octets)");
            console.log("captures : " + captures.join(", "));
        }
    } catch (erreur) {
        console.error("ÉCHEC :", erreur.message);
        process.exitCode = 1;
    } finally {
        if (chrome) chrome.fermer();
    }
})();
