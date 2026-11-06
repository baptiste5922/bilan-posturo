// Empreinte de chaque page d'un PDF produit par jsPDF, et comparaison stricte.
//
//   node empreintes-pages.js bilan.pdf
//       une ligne par flux /DCTDecode :  page N  <sha256>  <octets>
//
//   node empreintes-pages.js reference.pdf candidat.pdf
//       même nombre de pages exigé, puis même empreinte page à page.
//       Sortie 0 si tout est égal, 1 sinon, en nommant les pages qui diffèrent.
//
// Pourquoi ce programme existe (C1-T4a) : `comparer-pixels.js` rend son verdict
// sur un écart MOYEN inférieur à 3/255 — une tolérance, qui laisse passer un
// pixel faux sur une vignette de 64×94. Ici, AUCUN seuil : deux pages sont
// égales si leurs octets JPEG le sont. Cela suppose que l'export soit
// déterministe (même navigateur, même largeur, même brouillon, caches
// désactivés) ; c'est mesuré, pas supposé : un PDF contre un second export du
// même brouillon doit rendre 0, et un trait de plus doit rendre 1.
//
// Comme `comparer-pdf.js`, la page N est la N-ième image dans l'ordre des
// objets du PDF : jsPDF ajoute une image par page, dans l'ordre. Aucune
// dépendance.

const fs = require("fs");
const crypto = require("crypto");

/** Les flux /DCTDecode d'un PDF non chiffré, dans l'ordre des objets. */
function fluxDeImages(chemin) {
    const donnees = fs.readFileSync(chemin);
    // latin1 : un octet = un caractère, donc les positions du texte sont celles
    // du tampon, et les octets d'un flux se relisent sans perte.
    const texte = donnees.toString("latin1");
    const images = [];
    const motif = /(\d+)\s+0\s+obj([\s\S]*?)endobj/g;
    let m;
    while ((m = motif.exec(texte)) !== null) {
        const corps = m[2];
        const entete = corps.slice(0, corps.indexOf("stream") === -1 ? corps.length : corps.indexOf("stream"));
        if (!/\/Filter\s*\[?\s*\/DCTDecode/.test(entete)) continue;
        let debut = m.index + m[0].indexOf("stream", m[1].length) + "stream".length;
        if (texte[debut] === "\r") debut += 1;
        if (texte[debut] === "\n") debut += 1;
        const longueur = (entete.match(/\/Length\s+(\d+)(?!\s+\d+\s+R)/) || [])[1];
        let fin;
        if (longueur !== undefined) {
            fin = debut + Number(longueur);
        } else {
            fin = texte.indexOf("endstream", debut);
            if (fin === -1) throw new Error(chemin + " : flux sans fin dans l'objet " + m[1]);
            while (fin > debut && (texte[fin - 1] === "\n" || texte[fin - 1] === "\r")) fin -= 1;
        }
        images.push({ objet: Number(m[1]), flux: donnees.subarray(debut, fin) });
    }
    images.sort((a, b) => a.objet - b.objet);
    return images.map((image, rang) => ({
        page: rang + 1,
        sha256: crypto.createHash("sha256").update(image.flux).digest("hex"),
        octets: image.flux.length
    }));
}

function main(arguments_) {
    if (arguments_.length < 1 || arguments_.length > 2) {
        console.error("usage : node empreintes-pages.js bilan.pdf [autre.pdf]");
        return 2;
    }
    const a = fluxDeImages(arguments_[0]);
    if (a.length === 0) {
        console.error(arguments_[0] + " : aucun flux /DCTDecode — ce n'est pas un export du formulaire.");
        return 2;
    }

    if (arguments_.length === 1) {
        a.forEach((p) => console.log("page " + p.page + "  " + p.sha256 + "  " + p.octets));
        return 0;
    }

    const b = fluxDeImages(arguments_[1]);
    if (b.length === 0) {
        console.error(arguments_[1] + " : aucun flux /DCTDecode — ce n'est pas un export du formulaire.");
        return 2;
    }
    if (a.length !== b.length) {
        console.log("DIFFÈRENT : " + a.length + " page(s) contre " + b.length);
        return 1;
    }
    const differentes = [];
    a.forEach((p, i) => { if (p.sha256 !== b[i].sha256) differentes.push(p.page); });
    if (differentes.length > 0) {
        console.log("DIFFÈRENT : " + differentes.length + " page(s) sur " + a.length
            + " — page(s) " + differentes.join(", "));
        return 1;
    }
    console.log("IDENTIQUE : " + a.length + " page(s), empreintes égales page à page");
    return 0;
}

process.exitCode = main(process.argv.slice(2));
