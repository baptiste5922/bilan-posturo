// Compare deux PDF produits par jsPDF, page par page, sans dépendance.
//
//   node comparer-pdf.js sortie/V1-reference.pdf sortie/C1-T3-moteur.pdf
//
// Ce que le programme sait voir, et que l'œil voit mal : le nombre de pages, le
// format exact, et surtout la **matrice de placement** de l'image de chaque
// page — position et dimensions au centième de point. Un bloc décalé, une marge
// perdue, une page de plus : tout cela se lit ici.
//
// Ce qu'il ne sait pas voir : le contenu des images rasterisées. Deux images de
// même taille et même position peuvent différer en couleur. Il rend donc aussi
// la taille de chaque flux, dont un écart important signale un rendu différent.

const fs = require("fs");
const zlib = require("zlib");

function lire(chemin) {
    return fs.readFileSync(chemin);
}

/** Les objets d'un PDF non chiffré : « N 0 obj … endobj ». */
function objets(donnees) {
    const texte = donnees.toString("latin1");
    const trouves = new Map();
    const motif = /(\d+)\s+0\s+obj([\s\S]*?)endobj/g;
    let m;
    while ((m = motif.exec(texte)) !== null) {
        trouves.set(Number(m[1]), { corps: m[2], debut: m.index });
    }
    return trouves;
}

/** Le flux d'un objet, décompressé si besoin. */
function flux(donnees, objet) {
    const texte = objet.corps;
    const i = texte.indexOf("stream");
    if (i === -1) return null;
    let debut = i + "stream".length;
    if (texte[debut] === "\r") debut += 1;
    if (texte[debut] === "\n") debut += 1;
    const fin = texte.indexOf("endstream", debut);
    if (fin === -1) return null;
    const brut = Buffer.from(texte.slice(debut, fin), "latin1");
    if (/\/Filter\s*\/FlateDecode/.test(texte.slice(0, i))) {
        try { return zlib.inflateSync(brut); } catch (e) { return brut; }
    }
    return brut;
}

/** Décrit un PDF : pages, format, et par page les opérations de placement. */
function decrire(chemin) {
    const donnees = lire(chemin);
    const tous = objets(donnees);
    const pages = [];

    for (const [numero, objet] of tous) {
        if (!/\/Type\s*\/Page[^s]/.test(objet.corps)) continue;
        const boite = (objet.corps.match(/\/MediaBox\s*\[([^\]]*)\]/) || [])[1];
        const contenu = (objet.corps.match(/\/Contents\s+(\d+)\s+0\s+R/) || [])[1];
        pages.push({ numero, boite: (boite || "").trim().split(/\s+/).map(Number),
                     contenu: contenu ? Number(contenu) : null });
    }
    pages.sort((a, b) => a.numero - b.numero);

    const decrites = pages.map((page, rang) => {
        const objetContenu = page.contenu !== null ? tous.get(page.contenu) : null;
        const brut = objetContenu ? flux(donnees, objetContenu) : null;
        const texte = brut ? brut.toString("latin1") : "";

        // « a b c d e f cm » : mise à l'échelle et translation.
        const matrices = [];
        const motifCm = /([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+cm/g;
        let m;
        while ((m = motifCm.exec(texte)) !== null) {
            matrices.push(m.slice(1, 7).map(Number));
        }
        // Les textes posés par `setTextColor`/`text` : numéro de page.
        const textes = [];
        const motifTj = /\((?:[^()\\]|\\.)*\)\s*Tj/g;
        while ((m = motifTj.exec(texte)) !== null) textes.push(m[0]);
        // Couleurs de remplissage : « r g b rg » et niveaux de gris « g ».
        const couleurs = [];
        const motifRg = /([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg/g;
        while ((m = motifRg.exec(texte)) !== null) couleurs.push(m.slice(1, 4).map(Number));

        return { rang: rang + 1, boite: page.boite, octetsContenu: texte.length,
                 matrices, textes, couleurs };
    });

    // Les images, dans l'ordre des objets.
    const images = [];
    for (const [numero, objet] of tous) {
        if (!/\/Subtype\s*\/Image/.test(objet.corps)) continue;
        const l = (objet.corps.match(/\/Width\s+(\d+)/) || [])[1];
        const h = (objet.corps.match(/\/Height\s+(\d+)/) || [])[1];
        const taille = (objet.corps.match(/\/Length\s+(\d+)/) || [])[1];
        images.push({ numero, largeur: Number(l), hauteur: Number(h),
                      octets: Number(taille) });
    }
    images.sort((a, b) => a.numero - b.numero);

    return { chemin, pages: decrites, images, octets: donnees.length };
}

function arrondi(x) { return Math.round(x * 100) / 100; }

function comparer(a, b) {
    const ecarts = [];
    const note = (quoi) => ecarts.push(quoi);

    if (a.pages.length !== b.pages.length) {
        note("nombre de pages : " + a.pages.length + " contre " + b.pages.length);
        return ecarts;   // inutile d'aller plus loin
    }
    if (a.images.length !== b.images.length) {
        note("nombre d'images : " + a.images.length + " contre " + b.images.length);
    }

    a.pages.forEach((pa, i) => {
        const pb = b.pages[i];
        const n = "page " + pa.rang + " : ";
        if (JSON.stringify(pa.boite) !== JSON.stringify(pb.boite)) {
            note(n + "format " + pa.boite.join(" ") + " contre " + pb.boite.join(" "));
        }
        if (pa.matrices.length !== pb.matrices.length) {
            note(n + pa.matrices.length + " matrice(s) de placement contre "
                 + pb.matrices.length);
        }
        const commun = Math.min(pa.matrices.length, pb.matrices.length);
        for (let k = 0; k < commun; k += 1) {
            const ma = pa.matrices[k].map(arrondi);
            const mb = pb.matrices[k].map(arrondi);
            if (JSON.stringify(ma) !== JSON.stringify(mb)) {
                note(n + "placement n°" + (k + 1) + " : [" + ma.join(", ")
                     + "] contre [" + mb.join(", ") + "]");
            }
        }
        if (JSON.stringify(pa.textes) !== JSON.stringify(pb.textes)) {
            note(n + "textes posés : " + JSON.stringify(pa.textes)
                 + " contre " + JSON.stringify(pb.textes));
        }
        if (JSON.stringify(pa.couleurs) !== JSON.stringify(pb.couleurs)) {
            note(n + "couleurs de remplissage : " + JSON.stringify(pa.couleurs)
                 + " contre " + JSON.stringify(pb.couleurs));
        }
    });

    a.images.forEach((ia, i) => {
        const ib = b.images[i];
        if (!ib) return;
        if (ia.largeur !== ib.largeur || ia.hauteur !== ib.hauteur) {
            note("image n°" + (i + 1) + " : " + ia.largeur + "×" + ia.hauteur
                 + " contre " + ib.largeur + "×" + ib.hauteur);
        }
        const ecart = Math.abs(ia.octets - ib.octets) / Math.max(1, ia.octets);
        if (ecart > 0.02) {
            note("image n°" + (i + 1) + " : " + (ecart * 100).toFixed(1)
                 + " % d'écart de taille (" + ia.octets + " contre " + ib.octets
                 + ") — au-delà du bruit de compression attendu");
        }
    });

    return ecarts;
}

const [cheminA, cheminB] = process.argv.slice(2);
if (!cheminA || !cheminB) {
    console.error("usage : node comparer-pdf.js <référence.pdf> <candidat.pdf>");
    process.exit(2);
}

const a = decrire(cheminA);
const b = decrire(cheminB);

console.log("Référence : " + cheminA + " — " + a.pages.length + " pages, "
    + a.images.length + " images, " + a.octets + " octets");
console.log("Candidat  : " + cheminB + " — " + b.pages.length + " pages, "
    + b.images.length + " images, " + b.octets + " octets");
console.log("");

const ecarts = comparer(a, b);
if (!ecarts.length) {
    console.log("Aucun écart mesurable : même pagination, même format, mêmes");
    console.log("placements au centième de point, mêmes textes et mêmes couleurs.");
    console.log("Reste à l'œil le contenu des images rasterisées.");
} else {
    console.log("ÉCARTS (" + ecarts.length + ") :");
    ecarts.forEach((e) => console.log("  - " + e));
    process.exitCode = 1;
}
