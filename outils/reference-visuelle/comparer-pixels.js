// Compare les pixels des pages, par vignettes décodées.
//
// Le JPEG de l'export est regénéré à chaque fois (qualité 92 %), donc les
// octets diffèrent toujours : comparer les fichiers ne dit rien. En décodant
// puis en réduisant à 64×94, le bruit de compression se moyenne et seules les
// différences structurelles — un bloc déplacé, une couleur changée, un trait
// manquant — subsistent.
const fs = require("fs");

// TIFF non compressé produit par sips : on cherche l'offset des données brutes
// plutôt que de lire l'en-tête, en prenant les N derniers octets utiles.
function pixels(chemin, largeur, hauteur) {
    const d = fs.readFileSync(chemin);
    const attendus = largeur * hauteur * 3;
    if (d.length < attendus) throw new Error(chemin + " : trop court");
    return d.subarray(d.length - attendus);   // les données sont en fin de fichier
}

const L = 64, H = 94;
let pireEcart = 0, pirePage = 0;
const lignes = [];

for (let i = 1; i <= 6; i += 1) {
    const a = pixels(`vignettes/v1-${i}.tiff`, L, H);
    const b = pixels(`vignettes/mo-${i}.tiff`, L, H);
    let somme = 0, max = 0, differents = 0;
    for (let k = 0; k < a.length; k += 1) {
        const e = Math.abs(a[k] - b[k]);
        somme += e;
        if (e > max) max = e;
        if (e > 12) differents += 1;          // 12/255 ≈ 5 %, au-delà du bruit
    }
    const moyen = somme / a.length;
    const pourcent = (differents / a.length) * 100;
    lignes.push(`  page ${i} : écart moyen ${moyen.toFixed(2)}/255, `
        + `maximum ${max}, ${pourcent.toFixed(2)} % de composantes au-delà de 5 %`);
    if (moyen > pireEcart) { pireEcart = moyen; pirePage = i; }
}

console.log("Comparaison des pixels, vignettes " + L + "×" + H + " :");
lignes.forEach((l) => console.log(l));
console.log("");
if (pireEcart < 3) {
    console.log("Verdict : les six pages sont visuellement identiques.");
    console.log("L'écart résiduel est du niveau du bruit de compression JPEG.");
} else {
    console.log("Verdict : écart visuel réel, le plus marqué page " + pirePage + ".");
    process.exitCode = 1;
}
