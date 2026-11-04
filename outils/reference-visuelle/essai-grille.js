// Rendu réel du type `grille` (contrat C1-T6, étape 10), dans Chrome piloté
// contre un vrai serveur `serveur.py` en HTTPS, derrière authentification.
//
// Les tests sur double de DOM ne voient ni la mise en page, ni le PDF : cet
// essai vérifie sept choses que seul un navigateur montre.
//
//   1. le moteur a rendu sans erreur (`#attente-moteur` retiré, aucun message) ;
//   2. chaque cellule non neutralisée existe sous sa clé dérivée, aucune
//      cellule neutralisée ne contient de contrôle, et son fond est `--fond` ;
//   3. chaque grille tient en largeur dans `#form-bilan`, ses en-têtes de colonnes
//      surplombant leurs cellules ;
//   4. la saisie (deux cases d'une même ligne, `WWWWWWWW` tapé dans une cellule
//      de texte court, neuvième caractère refusé) arrive dans le brouillon,
//      sous la bonne clé, dans `coches` et `valeurs` ;
//   5. après rechargement et « Restaurer », les mêmes états reviennent ;
//   6. la zone de texte de tête est remplie jusqu'à ce que la dernière grille
//      chevauche la limite de la page 1 : `calculerPages()` (celle de la page)
//      la range alors entière sur une seule page ;
//   7. l'export dépose un PDF dans `bilans/` du bac, et chaque page en est
//      extraite en JPEG dans ESSAI_SORTIE, pour le contrôle à l'œil.
//
// Les clés attendues sont DÉRIVÉES du schéma d'essai (ESSAI_SCHEMA), jamais
// recopiées ici : la règle de dérivation est celle de la spécification, §6.
//
// Le bac à sable se construit par `git ls-files -z -- serveur formulaire`
// (jamais `cp -r` : CLAUDE.md), `formulaire/schema.json` du bac remplacé par
// ESSAI_SCHEMA, `generer_autorite.py 127.0.0.1` et `serveur.py` lancés DANS le
// bac — jamais depuis le dépôt, qui écraserait les fichiers réels du cabinet.
//
//   ESSAI_BASE=https://127.0.0.1:8444 \
//   ESSAI_BILANS=/chemin/du/bac/bilans \
//   ESSAI_IDENTIFIANTS=utilisateur:mot-de-passe \
//   ESSAI_SORTIE=/dossier/hors/depot \
//   ESSAI_SCHEMA=tests/donnees/schema-v2-grilles-fictives.json \
//   node outils/reference-visuelle/essai-grille.js
//
// Code de sortie 0 si les sept lignes sont « OK ».

const fs = require("fs");
const path = require("path");
const { ouvrirChrome, pause } = require("./cdp.js");

const BASE = process.env.ESSAI_BASE || "https://127.0.0.1:8444";
const BILANS = process.env.ESSAI_BILANS;
const IDENTIFIANTS_BRUTS = process.env.ESSAI_IDENTIFIANTS;
const SORTIE = process.env.ESSAI_SORTIE;
const SCHEMA = process.env.ESSAI_SCHEMA;
const PORT_CHROME = parseInt(process.env.ESSAI_PORT_CHROME || "9335", 10);

if (!BILANS || !IDENTIFIANTS_BRUTS || !SORTIE || !SCHEMA) {
    console.error("ESSAI_BILANS, ESSAI_IDENTIFIANTS, ESSAI_SORTIE et ESSAI_SCHEMA sont obligatoires "
        + "(voir l'en-tête du fichier). ESSAI_SORTIE doit être HORS du dépôt.");
    process.exit(2);
}
const IDENTIFIANTS = Buffer.from(IDENTIFIANTS_BRUTS).toString("base64");

/* ------------------------- Attendus, dérivés du schéma ------------------------- */

const schema = JSON.parse(fs.readFileSync(SCHEMA, "utf-8"));

/** La règle de dérivation de la spécification (§6) : grille, ligne, colonne. */
function cleCellule(grille, ligne, colonne) {
    return grille.cle + "__" + ligne.cle + "__" + colonne.cle;
}

const grilles = [];
let zoneDeTete = null;                        // premier champ zone-texte avant la dernière grille
schema.blocs.forEach(function (bloc) {
    bloc.champs.forEach(function (champ) {
        if (champ.type === "zone-texte" && !zoneDeTete && grilles.length === 0) zoneDeTete = champ.cle;
        if (champ.type !== "grille") return;
        grilles.push({
            bloc: bloc.cle,
            cle: champ.cle,
            colonnes: champ.colonnes.map(function (c) { return { cle: c.cle, nature: c.nature }; }),
            lignes: champ.lignes.map(function (l) {
                return { cle: l.cle, neutralisees: l.neutralisees || [] };
            }),
            cellules: champ.lignes.map(function (l) {
                return champ.colonnes.map(function (c) {
                    return {
                        cle: cleCellule(champ, l, c),
                        nature: c.nature,
                        neutre: (l.neutralisees || []).indexOf(c.cle) !== -1
                    };
                });
            })
        });
    });
});
if (grilles.length < 3 || !zoneDeTete) {
    console.error("ESSAI_SCHEMA doit porter une zone de texte de tête puis au moins trois grilles.");
    process.exit(2);
}
const derniere = grilles[grilles.length - 1];

// Saisie : deux cases d'une même ligne de la grille 1, un texte court de la grille 2.
const grille1 = grilles[0], grille2 = grilles[1];
const ligneDeCases = grille1.cellules.find(function (ligne) {
    return ligne.filter(function (c) { return !c.neutre && c.nature === "case"; }).length >= 2;
});
const casesACocher = ligneDeCases.filter(function (c) { return !c.neutre && c.nature === "case"; }).slice(0, 2);
const celluleTexte = [].concat.apply([], grille2.cellules)
    .filter(function (c) { return !c.neutre && c.nature === "texte-court"; })[0];
if (casesACocher.length !== 2 || !celluleTexte) {
    console.error("Le schéma d'essai ne permet pas la saisie demandée (deux cases d'une ligne, un texte court).");
    process.exit(2);
}

/* ------------------------------------ Outils ------------------------------------ */

function bilansDeposes() {
    return fs.existsSync(BILANS) ? fs.readdirSync(BILANS).filter((f) => f.endsWith(".pdf")) : [];
}

/** Tous les flux JPEG d'un PDF jsPDF : l'image de chaque page, dans l'ordre. */
function pagesJpeg(cheminPdf) {
    const donnees = fs.readFileSync(cheminPdf);
    const texte = donnees.toString("latin1");
    const pages = [];
    let i = texte.indexOf("/DCTDecode");
    while (i !== -1) {
        let debut = texte.indexOf("stream", i) + "stream".length;
        if (texte[debut] === "\r") debut += 1;
        if (texte[debut] === "\n") debut += 1;
        const fin = texte.indexOf("endstream", debut);
        pages.push(donnees.subarray(debut, fin));
        i = texte.indexOf("/DCTDecode", fin);
    }
    return pages;
}

const BROUILLON = `(() => JSON.parse(localStorage.getItem("bilan-posturo-brouillon") || "null"))()`;

(async function () {
    let chrome;
    const lignes = [];
    let rates = 0;
    const verdict = (numero, ok, titre, detail) => {
        if (!ok) rates += 1;
        lignes.push((ok ? "  OK   " : "  RATÉ ") + numero + ". " + titre);
        (detail || []).forEach((d) => lignes.push("         · " + d));
        return ok;
    };

    fs.mkdirSync(SORTIE, { recursive: true });
    try {
        chrome = await ouvrirChrome({ port: PORT_CHROME });
        await chrome.cmd("Network.enable");
        await chrome.cmd("Network.setCacheDisabled", { cacheDisabled: true });
        await chrome.cmd("Network.setExtraHTTPHeaders", { headers: { Authorization: "Basic " + IDENTIFIANTS } });
        await chrome.cmd("Security.enable");
        await chrome.cmd("Security.setIgnoreCertificateErrors", { ignore: true });

        // Vide le brouillon d'un essai précédent : on part d'un formulaire neuf.
        await chrome.aller(BASE + "/index.html");
        await chrome.evaluer(`localStorage.clear()`);
        await chrome.aller(BASE + "/index.html");
        await pause(1500);

        // ---------------- 1. Le moteur a rendu sans erreur ----------------
        const etat1 = await chrome.evaluer(`(() => {
            const zone = document.getElementById("zone-messages");
            return {
                attente: document.getElementById("attente-moteur") !== null,
                message: zone && !zone.hidden ? zone.textContent.trim() : "",
                tables: document.querySelectorAll("#form-bilan table.bloc.grille").length
            };
        })()`);
        verdict(1, !etat1.attente && etat1.message === "" && etat1.tables === grilles.length,
            "le moteur a rendu : #attente-moteur retiré, aucun message d'erreur, " + etat1.tables + " grilles",
            etat1.message ? ["message affiché : " + etat1.message] : []);

        // ---------------- 2. Cellules, clés dérivées, neutralisées ----------------
        const etat2 = await chrome.evaluer(`(() => {
            const grilles = ${JSON.stringify(grilles)};
            const fautes = [];
            let controles = 0, neutralisees = 0;
            const sonde = document.createElement("div");
            sonde.style.backgroundColor = "var(--fond)";
            document.body.appendChild(sonde);
            const fond = getComputedStyle(sonde).backgroundColor;
            sonde.remove();
            grilles.forEach((g) => {
                const table = document.getElementById(g.bloc);
                if (!table) { fautes.push(g.bloc + " : table introuvable"); return; }
                const rangees = table.tBodies[0].rows;
                if (rangees.length !== g.lignes.length) fautes.push(g.cle + " : " + rangees.length + " lignes rendues");
                g.cellules.forEach((ligne, i) => ligne.forEach((c, j) => {
                    const td = rangees[i] && rangees[i].cells[1 + j];
                    if (!td) { fautes.push(c.cle + " : cellule absente"); return; }
                    if (c.neutre) {
                        neutralisees += 1;
                        if (!td.classList.contains("grille-neutralisee")) fautes.push(c.cle + " : neutralisée sans classe");
                        if (td.querySelector("*") !== null) fautes.push(c.cle + " : neutralisée avec un contrôle");
                        if (document.getElementById(c.cle)) fautes.push(c.cle + " : un id existe pour une neutralisée");
                        if (getComputedStyle(td).backgroundColor !== fond) fautes.push(c.cle + " : fond différent de --fond");
                    } else {
                        const el = document.getElementById(c.cle);
                        if (!el || !td.contains(el)) { fautes.push(c.cle + " : contrôle absent de sa cellule"); return; }
                        controles += 1;
                        const type = c.nature === "case" ? "checkbox" : "text";
                        if (el.tagName !== "INPUT" || el.type !== type) fautes.push(c.cle + " : type " + el.type + ", " + type + " attendu");
                        if (el.name) fautes.push(c.cle + " : name présent");
                        if (c.nature === "texte-court" && (el.maxLength !== 8 || el.getAttribute("autocomplete") !== "off"))
                            fautes.push(c.cle + " : maxlength/autocomplete");
                    }
                }));
                const nbInput = table.querySelectorAll("input").length;
                const attendus = g.cellules.reduce((s, l) => s + l.filter((c) => !c.neutre).length, 0);
                if (nbInput !== attendus) fautes.push(g.cle + " : " + nbInput + " contrôles, " + attendus + " attendus");
            });
            return { fautes, controles, neutralisees };
        })()`);
        verdict(2, etat2.fautes.length === 0,
            "chaque cellule active existe sous sa clé dérivée (" + etat2.controles + " contrôles), "
            + etat2.neutralisees + " neutralisées sans contrôle et au fond --fond",
            etat2.fautes.slice(0, 10));

        // ---------------- 3. Largeur ----------------
        const etat3 = await chrome.evaluer(`(() => {
            const form = document.getElementById("form-bilan");
            const droite = form.getBoundingClientRect().right;
            const parGrille = ${JSON.stringify(grilles.map((g) => g.bloc))}.map((id) => {
                const r = document.getElementById(id).getBoundingClientRect();
                return { id, largeur: Math.round(r.width), depasse: r.right > droite + 0.5 };
            });
            // Chaque en-tête de colonne doit surplomber les cellules de sa colonne :
            // si le coin cesse d'être une cellule de tableau, son rowspan tombe et
            // la seconde rangée d'en-têtes se décale d'une colonne (constaté au
            // premier essai réel, C1-T6).
            const decalages = [];
            ${JSON.stringify(grilles.map((g) => g.bloc))}.forEach((id) => {
                const table = document.getElementById(id);
                const entetes = table.tHead.rows[table.tHead.rows.length - 1].cells;
                const decale = table.tHead.rows.length === 1 ? 1 : 0;
                const premiere = table.tBodies[0].rows[0].cells;
                for (let j = 0; j < premiere.length - 1; j += 1) {
                    const h = entetes[j + decale], c = premiere[j + 1];
                    if (!h) { decalages.push(id + " colonne " + j + " : en-tête absent"); continue; }
                    const ecart = Math.abs((h.getBoundingClientRect().left + h.getBoundingClientRect().right) / 2
                        - (c.getBoundingClientRect().left + c.getBoundingClientRect().right) / 2);
                    if (ecart > 2) decalages.push(id + " colonne " + j + " : en-tête décalé de " + Math.round(ecart) + " px");
                }
            });
            return { scroll: form.scrollWidth, client: form.clientWidth, parGrille, decalages };
        })()`);
        verdict(3, etat3.scroll <= etat3.client && etat3.parGrille.every((g) => !g.depasse) && etat3.decalages.length === 0,
            "chaque grille tient dans #form-bilan (scrollWidth " + etat3.scroll + " <= clientWidth "
            + etat3.client + ") et ses en-têtes surplombent leurs colonnes",
            etat3.parGrille.map((g) => g.id + " : " + g.largeur + " px" + (g.depasse ? " — DÉBORDE" : ""))
                .concat(etat3.decalages.slice(0, 5)));

        // ---------------- 4. Saisie, brouillon ----------------
        const cibleTexte = celluleTexte.cle;
        await chrome.evaluer(`(() => {
            ${JSON.stringify(casesACocher.map((c) => c.cle))}.forEach((id) => {
                const el = document.getElementById(id);
                el.scrollIntoView({ block: "center" });
                el.click();
            });
        })()`);
        await chrome.evaluer(`(() => {
            const el = document.getElementById(${JSON.stringify(cibleTexte)});
            el.scrollIntoView({ block: "center" });
            el.focus();
        })()`);
        await pause(200);
        // Neuf W : la saisie réelle doit s'arrêter à huit (maxlength).
        await chrome.cmd("Input.insertText", { text: "WWWWWWWWW" });
        await pause(2500);   // la sauvegarde différée écrit le brouillon
        const etat4 = await chrome.evaluer(`(() => {
            const el = document.getElementById(${JSON.stringify(cibleTexte)});
            return {
                valeur: el.value,
                coupe: el.scrollWidth > el.clientWidth,
                brouillon: ${BROUILLON}
            };
        })()`);
        const b4 = etat4.brouillon || { coches: {}, valeurs: {} };
        const ok4 = etat4.valeur === "WWWWWWWW"
            && !etat4.coupe
            && casesACocher.every((c) => b4.coches[c.cle] === true)
            && b4.valeurs[cibleTexte] === "WWWWWWWW"
            && !(cibleTexte in b4.coches)
            && casesACocher.every((c) => !(c.cle in b4.valeurs));
        verdict(4, ok4,
            "saisie : deux cases d'une ligne et « WWWWWWWW » (le 9e caractère refusé, rien de coupé) "
            + "arrivent dans coches / valeurs du brouillon",
            ["texte saisi : " + JSON.stringify(etat4.valeur) + ", débordement du champ : " + etat4.coupe]);

        // ---------------- 5. Rechargement, « Restaurer » ----------------
        await chrome.aller(BASE + "/index.html");
        await pause(1500);
        const bouton = await chrome.evaluer(`(() => {
            const b = document.getElementById("btn-restaurer");
            if (!b || b.offsetParent === null) return "absent";
            b.click();
            return "cliqué";
        })()`);
        await pause(1200);
        const etat5 = await chrome.evaluer(`(() => {
            const coches = ${JSON.stringify(casesACocher.map((c) => c.cle))};
            const cochees = Array.from(document.querySelectorAll("table.grille input[type=checkbox]"))
                .filter((e) => e.checked).map((e) => e.id).sort();
            const textes = Array.from(document.querySelectorAll("table.grille input[type=text]"))
                .filter((e) => e.value !== "").map((e) => e.id + "=" + e.value).sort();
            return { cochees, textes, coches };
        })()`);
        const attenduCochees = casesACocher.map((c) => c.cle).sort();
        verdict(5, bouton === "cliqué"
            && JSON.stringify(etat5.cochees) === JSON.stringify(attenduCochees)
            && JSON.stringify(etat5.textes) === JSON.stringify([cibleTexte + "=WWWWWWWW"]),
            "après rechargement et « Restaurer », les mêmes cases et la même valeur reviennent, et rien d'autre",
            ["bouton Restaurer : " + bouton, "cases cochées : " + etat5.cochees.length + ", textes : " + etat5.textes.length]);

        // ---------------- 6. Pagination ----------------
        const etat6 = await chrome.evaluer(`(() => {
            const form = document.getElementById("form-bilan");
            const zone = document.getElementById(${JSON.stringify(zoneDeTete)});
            const derniere = document.getElementById(${JSON.stringify(derniere.bloc)});
            const largeurUtile = PDF_LARGEUR - 2 * MARGE_MM, hauteurUtile = PDF_HAUTEUR - 2 * MARGE_MM;
            const origine = () => form.getBoundingClientRect();
            const page = () => origine().width * (hauteurUtile / largeurUtile);
            const position = () => {
                const o = origine(), r = derniere.getBoundingClientRect();
                return { haut: r.top - o.top, bas: r.bottom - o.top };
            };
            // Remplir la zone ligne à ligne jusqu'à ce que la dernière grille passe la limite.
            let lignes = 0;
            for (; lignes < 400; lignes += 1) {
                zone.value = "Ligne de remplissage fictive.\\n".repeat(lignes);
                zone.dispatchEvent(new Event("input", { bubbles: true }));
                if (position().bas > page()) break;
            }
            const p = position();
            const chevauche = p.haut < page() && p.bas > page();
            const blocs = Array.from(form.querySelectorAll(".bloc")).map((b) => {
                const r = b.getBoundingClientRect(), o = origine();
                return { nom: b.id || b.className, haut: r.top - o.top, bas: r.bottom - o.top };
            });
            const pages = calculerPages(blocs, page(), form.getBoundingClientRect().height);
            const contenue = pages.filter((q) => p.haut >= q.debut - 0.5 && p.bas <= q.fin + 0.5);
            return {
                lignes, chevauche, limite: Math.round(page()), haut: Math.round(p.haut), bas: Math.round(p.bas),
                nbPages: pages.length, contenueDansUnePage: contenue.length === 1,
                hauteurGrille: Math.round(p.bas - p.haut)
            };
        })()`);
        verdict(6, etat6.chevauche && etat6.contenueDansUnePage,
            "la dernière grille (" + derniere.cle + "), à sa place naturelle, chevauche la limite de la page 1 "
            + "et calculerPages() la range entière sur une seule page",
            ["limite de page " + etat6.limite + " px ; grille de " + etat6.haut + " à " + etat6.bas
                + " px (" + etat6.hauteurGrille + " px de haut) ; " + etat6.lignes + " lignes de remplissage ; "
                + etat6.nbPages + " pages prévues"]);
        await pause(1500);

        // ---------------- 7. Export, PDF, pages en JPEG ----------------
        const avant = bilansDeposes();
        await chrome.evaluer(`window.scrollTo(0, 0)`);
        await chrome.evaluer(`(() => {
            const nom = document.getElementById("nom"), prenom = document.getElementById("prenom");
            [[nom, "Essai"], [prenom, "Grille"]].forEach(([c, v]) => {
                if (c) { c.value = v; c.dispatchEvent(new Event("input", { bubbles: true })); }
            });
        })()`);
        await pause(300);
        await chrome.evaluer(`document.getElementById("btn-export").click()`);
        let depose = null;
        for (let i = 0; i < 90 && !depose; i += 1) {
            await pause(1000);
            depose = bilansDeposes().filter((f) => avant.indexOf(f) === -1)[0] || null;
        }
        let ok7 = depose !== null;
        const detail7 = [];
        if (ok7) {
            await pause(1500);   // laisse le serveur finir l'écriture atomique
            const donnees = fs.readFileSync(path.join(BILANS, depose));
            ok7 = donnees.subarray(0, 5).toString() === "%PDF-";
            const pages = pagesJpeg(path.join(BILANS, depose));
            ok7 = ok7 && pages.length >= 2;
            pages.forEach((p, k) => {
                const chemin = path.join(SORTIE, "C1-T6-pdf-page-" + (k + 1) + ".jpg");
                fs.writeFileSync(chemin, p);
            });
            detail7.push("PDF déposé : " + depose + " (" + donnees.length + " octets), " + pages.length
                + " pages extraites dans " + SORTIE);
        }
        verdict(7, ok7, "l'export dépose un PDF dans bilans/ du bac, et ses pages sont extraites en JPEG", detail7);
        await chrome.evaluer(`localStorage.clear()`);
    } catch (erreur) {
        rates += 1;
        lignes.push("  RATÉ  " + erreur.message);
    } finally {
        if (chrome) chrome.fermer();
    }

    console.log("Essai C1-T6 — type grille en rendu réel\n");
    lignes.forEach((l) => console.log(l));
    console.log("\n" + (rates === 0 ? "Les sept vérifications tiennent en rendu réel." : rates + " vérification(s) en échec."));
    process.exitCode = rates === 0 ? 0 : 1;
})();
