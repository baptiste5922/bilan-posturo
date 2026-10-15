/*
 * Test de l'inventaire du formulaire (docs/schema-formulaire.md), produit
 * par la tâche C1-T1.
 *
 * Ce document fige le vocabulaire du futur moteur de rendu (C1-T3) : un
 * champ oublié dans l'inventaire, ou une clé qui diverge du brouillon
 * `localStorage` réel (cleChamp(), script.js:863-867), ne se verrait qu'en
 * production, après coup, sur le poste de la praticienne. Ce test recompte
 * donc mécaniquement, à chaque exécution, tout ce que la spécification
 * présente comme normatif — les clés de brouillon, le nombre de blocs,
 * l'ordre et le nombre des images annotables, l'ensemble des `id` gelés —
 * plutôt que de figer ces nombres en constantes qui dériveraient du HTML
 * réel sans que rien ne le signale (défaut relevé à l'audit).
 *
 * Les fichiers lus sont normalisés en fin de ligne `\n` dès la lecture : le
 * reste du fichier peut donc écrire ses motifs sans jamais répéter `\r?\n`,
 * et le résultat ne dépend pas de la convention de fin de ligne du poste
 * qui exécute la suite (CRLF sur un clone Windows par défaut, LF ailleurs —
 * défaut relevé à l'audit, aucun `.gitattributes` ne le garantit).
 *
 *     node tests/test_inventaire_formulaire.js
 */

const fs = require("fs");
const path = require("path");

const CHEMIN_HTML = path.join(__dirname, "..", "formulaire", "index.html");
const CHEMIN_CSS = path.join(__dirname, "..", "formulaire", "style.css");
const CHEMIN_JS = path.join(__dirname, "..", "formulaire", "script.js");
const CHEMIN_SPEC = path.join(__dirname, "..", "docs", "schema-formulaire.md");

function lireNormalise(chemin) {
    return fs.readFileSync(chemin, "utf-8").replace(/\r\n/g, "\n");
}

const html = lireNormalise(CHEMIN_HTML);
const css = lireNormalise(CHEMIN_CSS);
const js = lireNormalise(CHEMIN_JS);
const spec = lireNormalise(CHEMIN_SPEC);

/** Le sous-arbre `#form-bilan`, hors barre d'outils (lignes 26-63, section 1). */
function corpsFormulaire() {
    const debut = html.indexOf('<div id="form-bilan">');
    if (debut === -1) {
        throw new Error("« #form-bilan » introuvable dans formulaire/index.html");
    }
    return html.slice(debut);
}

/**
 * Lit un attribut sous ses trois formes réelles du fichier : guillemets
 * doubles, apostrophes, ou sans guillemet (anomalie A6, `index.html:309`).
 * Si le nom d'attribut est présent mais sous une forme qu'aucune des trois
 * ne reconnaît, le test refuse explicitement plutôt que d'ignorer
 * silencieusement l'attribut — un faux vert y coûterait un bilan perdu.
 */
function lireAttribut(attributs, nom) {
    const present = new RegExp("\\b" + nom + "\\s*=", "i");
    if (!present.test(attributs)) return undefined;
    const motif = new RegExp(
        "\\b" + nom + "\\s*=\\s*(?:\"([^\"]*)\"|'([^']*)'|([^\\s\"'=<>`]+))", "i"
    );
    const m = attributs.match(motif);
    if (!m) {
        throw new Error(
            `attribut « ${nom} » de forme non reconnue (ni "...", ni '...', ni sans guillemet) ` +
            `dans : ${attributs.trim()}`
        );
    }
    return m[1] !== undefined ? m[1] : (m[2] !== undefined ? m[2] : m[3]);
}

/**
 * Identifiant stable d'un champ — reproduit cleChamp() (script.js:863-867) :
 * l'id du champ s'il existe, sinon name + "#" + value, sinon aucune clé. Un
 * attribut `nom=` (anomalie A1) n'est pas un `name` et ne doit jamais être lu
 * ici : lireAttribut() exige le nom exact, pas une approximation.
 */
function cleDepuisAttributs(attributs) {
    const id = lireAttribut(attributs, "id");
    if (id) return id;
    const nom = lireAttribut(attributs, "name");
    if (nom) {
        const valeur = lireAttribut(attributs, "value") || "";
        return nom + "#" + valeur;
    }
    return null;
}

/** Les clés de brouillon réellement dérivables du formulaire aujourd'hui. */
function clesDuFormulaire() {
    const corps = corpsFormulaire();
    const cles = new Set();
    const motif = /<(input|textarea|select)\b([^>]*)>/gi;
    let m;
    while ((m = motif.exec(corps)) !== null) {
        const cle = cleDepuisAttributs(m[2]);
        if (cle) cles.add(cle);
    }
    return cles;
}

/**
 * Tous les éléments dont la classe contient « bloc », dans l'ordre du DOM,
 * avec leur `id` ou `null` : c'est l'unité de pagination (script.js:234-239,
 * `b.id || b.className`), recomptée ici plutôt que supposée égale à 29.
 */
function blocsHtml() {
    const corps = corpsFormulaire();
    const blocs = [];
    const motif = /<([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>/g;
    let m;
    while ((m = motif.exec(corps)) !== null) {
        const classe = lireAttribut(m[2], "class") || "";
        if (!classe.split(/\s+/).includes("bloc")) continue;
        blocs.push(lireAttribut(m[2], "id") || null);
    }
    return blocs;
}

/**
 * Toutes les images `dessinable`, dans l'ordre du DOM, avec leur `id` et leur
 * texte alternatif : les traits de stylet sont stockés par index
 * (script.js:893, 941-946 ; peuplement DOM script.js:620), donc le nombre et
 * l'ordre réels de ces images sont ce que D7 rend normatif — pas une
 * constante du test.
 */
function imagesHtml() {
    const corps = corpsFormulaire();
    const images = [];
    const motif = /<img\b([^>]*)>/g;
    let m;
    while ((m = motif.exec(corps)) !== null) {
        const classe = lireAttribut(m[1], "class") || "";
        if (!classe.split(/\s+/).includes("dessinable")) continue;
        images.push({ id: lireAttribut(m[1], "id") || null, alt: lireAttribut(m[1], "alt") || "" });
    }
    return images;
}

/**
 * Identifiants `#id` référencés par une feuille de style ou un script, en
 * écartant les couleurs hexadécimales (`#cec1a3`, `#A08A5A`…) qui partagent
 * la même syntaxe : une couleur n'est composée que de chiffres hexadécimaux
 * (0-9, a-f) et fait 3, 4, 6 ou 8 caractères ; aucun `id` de ce dépôt ne
 * remplit les deux conditions à la fois (« form-bilan », « logo »… portent
 * des lettres hors a-f ou une longueur différente).
 */
function idsReferences(texte) {
    const ids = new Set();
    const motif = /#([A-Za-z_][\w-]*)/g;
    let m;
    while ((m = motif.exec(texte)) !== null) {
        const jeton = m[1];
        const estCouleur = /^[0-9a-fA-F]+$/.test(jeton) && [3, 4, 6, 8].includes(jeton.length);
        if (!estCouleur) ids.add(jeton);
    }
    const motifGetElementById = /getElementById\(\s*"([^"]+)"\s*\)/g;
    while ((m = motifGetElementById.exec(texte)) !== null) ids.add(m[1]);
    return ids;
}

/** Tous les `id` présents dans #form-bilan, pour restreindre idsReferences() au périmètre du schéma. */
function idsPresentsDansLeFormulaire() {
    const corps = corpsFormulaire();
    const ids = new Set();
    const motif = /<[a-zA-Z][a-zA-Z0-9]*\b([^>]*)>/g;
    let m;
    while ((m = motif.exec(corps)) !== null) {
        const id = lireAttribut(m[1], "id");
        if (id) ids.add(id);
    }
    return ids;
}

/**
 * L'ensemble des `id` que la spécification doit déclarer gelés : présents
 * dans le formulaire ET référencés par script.js ou style.css. La barre
 * d'outils (btn-export, barre-brouillon…) est hors de #form-bilan et se
 * trouve donc naturellement écartée par cette intersection, sans liste
 * d'exclusion à maintenir à la main.
 */
function idsGelesAttendus() {
    const references = new Set([...idsReferences(css), ...idsReferences(js)]);
    const presents = idsPresentsDansLeFormulaire();
    return [...references].filter(function (id) { return presents.has(id); });
}

/** Extrait le texte entre un titre de section et le prochain titre de même rang ou plus large. */
function extraireSection(texte, titre, rangTitreSuivant) {
    const debut = texte.indexOf(titre);
    if (debut === -1) {
        throw new Error(`section « ${titre} » introuvable dans la spécification`);
    }
    const reste = texte.slice(debut + titre.length);
    const suivant = reste.match(rangTitreSuivant);
    return suivant ? reste.slice(0, suivant.index) : reste;
}

/**
 * Lit le tableau d'inventaire (section 3) ligne par ligne et renvoie les
 * clés citées : un ensemble pour les champs (la bijection ne dépend pas de
 * leur ordre), un tableau ordonné pour les images (D7 rend leur ordre
 * normatif, donc leur position dans le tableau compte).
 */
function clesDeLaSpecification() {
    const section = extraireSection(spec, "## 3. Inventaire détaillé", /\n## /);
    const clesChamps = new Set();
    const ordreImages = [];
    let lignesChamps = 0;

    section.split("\n").forEach(function (ligne) {
        if (!ligne.trim().startsWith("|")) return;
        const colonnes = ligne.split("|").map(function (c) { return c.trim(); });
        // Une ligne de donnée commence toujours par un numéro de bloc, une
        // fois la cellule vide de bord de ligne retirée (colonnes[0] === "").
        if (!/^\d+$/.test(colonnes[1] || "")) return;

        const colCle = colonnes[3] || "";
        const colType = colonnes[4] || "";
        const cles = [];
        const motif = /`([^`]+)`/g;
        let m;
        while ((m = motif.exec(colCle)) !== null) cles.push(m[1]);

        if (colType.trim() === "image-annotable") {
            cles.forEach(function (c) { ordreImages.push(c); });
        } else {
            lignesChamps++;
            cles.forEach(function (c) { clesChamps.add(c); });
        }
    });

    return { clesChamps, ordreImages, lignesChamps };
}

/** Les `id` cités dans la liste à puces « Clés gelées » de la section 2. */
function clesGeleesCitees() {
    const section = extraireSection(spec, "## 2. Les 29 blocs", /\n## /);
    const cles = new Set();
    section.split("\n").forEach(function (ligne) {
        const m = ligne.match(/^- `([^`]+)`/);
        if (m) cles.add(m[1]);
    });
    return cles;
}

/** Le compte et la liste annoncés par la phrase « Les N blocs sans id… » de la section 2. */
function blocsSansIdAnnonces() {
    const section = extraireSection(spec, "## 2. Les 29 blocs", /\n## /);
    const m = section.match(/les\s+\*\*(\d+)\*\*\s+blocs sans `id` sont[^.]*\./i);
    if (!m) {
        throw new Error("la phrase « Les N blocs sans id… » est introuvable dans la section 2");
    }
    const compte = parseInt(m[1], 10);
    const numeros = [...m[0].matchAll(/`(\d+)`/g)].map(function (x) { return parseInt(x[1], 10); });
    return { compte, numeros };
}

/** Isole chaque bloc ```json de la spécification et le fait analyser par JSON.parse. */
function exemplesJson() {
    const motif = /```json\n([\s\S]*?)```/g;
    const exemples = [];
    let m;
    while ((m = motif.exec(spec)) !== null) {
        let valeur;
        try {
            valeur = JSON.parse(m[1]);
        } catch (erreur) {
            throw new Error(`un bloc \`\`\`json de la spécification ne parse pas : ${erreur.message}`);
        }
        exemples.push(valeur);
    }
    return exemples;
}

/** Récolte récursivement toutes les valeurs de l'attribut "type" dans un ensemble d'exemples. */
function typesCites(exemples) {
    const types = new Set();
    function parcourir(valeur) {
        if (Array.isArray(valeur)) {
            valeur.forEach(parcourir);
        } else if (valeur && typeof valeur === "object") {
            Object.keys(valeur).forEach(function (cle) {
                if (cle === "type" && typeof valeur[cle] === "string") types.add(valeur[cle]);
                parcourir(valeur[cle]);
            });
        }
    }
    exemples.forEach(parcourir);
    return types;
}

/** Justification d'un type écarté : le texte entre son nom et le prochain tiret ou la fin de section. */
function justificationDuRetrait(sectionTypesEcartes, nom) {
    const motif = new RegExp(
        "-\\s*\\*\\*`" + nom + "`\\*\\*\\s*—\\s*([\\s\\S]*?)(?=\\n-\\s*\\*\\*`|\\n\\n|$)"
    );
    const m = sectionTypesEcartes.match(motif);
    if (!m) return null;
    return m[1].replace(/\s+/g, " ").trim();
}

try {
    // 1. Bijection entre les clés dérivables du HTML et celles citées dans l'inventaire,
    //    et recomptage mécanique des blocs et des images (plus de constantes figées).
    const clesHtml = clesDuFormulaire();
    const { clesChamps, ordreImages, lignesChamps } = clesDeLaSpecification();

    const manquantes = [...clesHtml].filter(function (c) { return !clesChamps.has(c); });
    const enTrop = [...clesChamps].filter(function (c) { return !clesHtml.has(c); });
    if (manquantes.length > 0) {
        throw new Error(`clé(s) du formulaire absente(s) de l'inventaire : ${manquantes.join(", ")}`);
    }
    if (enTrop.length > 0) {
        throw new Error(`clé(s) citée(s) par l'inventaire mais absente(s) du formulaire : ${enTrop.join(", ")}`);
    }
    if (lignesChamps !== 45) {
        throw new Error(`l'inventaire compte ${lignesChamps} ligne(s) de champ, 45 attendues`);
    }

    const blocs = blocsHtml();
    if (blocs.length !== 29) {
        throw new Error(`formulaire/index.html compte ${blocs.length} bloc(s) (.bloc), 29 attendus`);
    }
    const sansIdReels = blocs
        .map(function (id, i) { return id === null ? i + 1 : null; })
        .filter(function (x) { return x !== null; });
    const { compte: compteAnnonce, numeros: numerosAnnonces } = blocsSansIdAnnonces();
    if (compteAnnonce !== sansIdReels.length || JSON.stringify(numerosAnnonces) !== JSON.stringify(sansIdReels)) {
        throw new Error(
            `la spécification annonce ${compteAnnonce} bloc(s) sans id (${numerosAnnonces.join(", ")}), ` +
            `le HTML en a réellement ${sansIdReels.length} (${sansIdReels.join(", ")})`
        );
    }

    const images = imagesHtml();
    if (images.length !== 4) {
        throw new Error(`formulaire/index.html compte ${images.length} image(s) dessinable(s), 4 attendues`);
    }
    if (ordreImages.length !== 4) {
        throw new Error(`l'inventaire compte ${ordreImages.length} ligne(s) d'image, 4 attendues`);
    }
    // D7 : l'ordre est normatif. Les trois premières images n'ont pas d'id dans
    // le HTML (section 3) ; leur texte alternatif suffit à vérifier leur rang.
    const motifsAttendus = [
        { motif: /gauche/i, nom: "gauche" },
        { motif: /droite/i, nom: "droite" },
        { motif: /dos/i, nom: "dos" }
    ];
    motifsAttendus.forEach(function (attendu, i) {
        if (images[i].id !== null || !attendu.motif.test(images[i].alt)) {
            throw new Error(`la ${i + 1}e image dessinable du HTML n'est pas celle attendue (« ${attendu.nom} »)`);
        }
        if (!attendu.motif.test(ordreImages[i])) {
            throw new Error(
                `ordre des images (D7) : la position ${i + 1} de l'inventaire devrait désigner ` +
                `l'image « ${attendu.nom} », trouvé « ${ordreImages[i]} »`
            );
        }
    });
    if (images[3].id !== "image_empreintes") {
        throw new Error(`la 4e image dessinable du HTML n'a pas l'id "image_empreintes" (trouvé "${images[3].id}")`);
    }
    if (ordreImages[3] !== "image_empreintes") {
        throw new Error(
            `ordre des images (D7) : la position 4 de l'inventaire devrait être "image_empreintes", ` +
            `trouvé "${ordreImages[3]}"`
        );
    }
    console.log(
        `1. bijection clés HTML <-> inventaire (${clesHtml.size} clés, ${lignesChamps} champs) ; ` +
        `${blocs.length} blocs et ${images.length} images recomptés dans le HTML, ordre des images vérifié`
    );

    // 2. La version du format figure dès l'en-tête.
    const sixPremieresLignes = spec.split("\n").slice(0, 6).join("\n");
    if (!/version du format/i.test(sixPremieresLignes)) {
        throw new Error("la version du format n'apparaît pas dans les six premières lignes");
    }
    console.log("2. version du format dans l'en-tête");

    // 3. Chaque type retenu a au moins un exemple JSON valide.
    const exemples = exemplesJson();
    const types = typesCites(exemples);
    const typesRetenus = ["texte", "zone-texte", "date", "case", "radio", "tableau", "image-annotable"];
    const typesSansExemple = typesRetenus.filter(function (t) { return !types.has(t); });
    if (typesSansExemple.length > 0) {
        throw new Error(`type(s) sans exemple JSON valide : ${typesSansExemple.join(", ")}`);
    }
    console.log(`3. un exemple JSON valide par type (${exemples.length} blocs analysés)`);

    // 4. Aucun type écarté n'est employé comme valeur de "type" dans un exemple.
    const typesEcartes = ["nombre", "liste", "paragraphe"];
    const typesEcartesUtilises = typesEcartes.filter(function (t) { return types.has(t); });
    if (typesEcartesUtilises.length > 0) {
        throw new Error(`type(s) écarté(s) employé(s) dans un exemple : ${typesEcartesUtilises.join(", ")}`);
    }
    console.log("4. aucun type écarté employé dans un exemple");

    // 5. Les trois retraits sont justifiés par au moins 40 caractères chacun.
    const sectionEcartes = extraireSection(spec, "### 4.2 Types écartés", /\n#{2,3} /);
    typesEcartes.forEach(function (nom) {
        const justification = justificationDuRetrait(sectionEcartes, nom);
        if (justification === null) {
            throw new Error(`le type écarté « ${nom} » n'est pas nommé dans la section « Types écartés »`);
        }
        if (justification.length < 40) {
            throw new Error(`le type écarté « ${nom} » n'a pas 40 caractères de justification (${justification.length} trouvés)`);
        }
    });
    console.log("5. les trois retraits sont justifiés (au moins 40 caractères chacun)");

    // 6. Les clés gelées (id dont dépendent script.js/style.css) sont toutes déclarées.
    const attendus = idsGelesAttendus();
    const cites = clesGeleesCitees();
    const geleesManquantes = attendus.filter(function (id) { return !cites.has(id); });
    if (geleesManquantes.length > 0) {
        throw new Error(`id gelé(s) référencé(s) par script.js ou style.css mais absent(s) de la liste « Clés gelées » : ${geleesManquantes.join(", ")}`);
    }
    console.log(`6. clés gelées exhaustives (${attendus.length} id attendus, conteneur #form-bilan compris)`);

    console.log("\nTout est vert.");
} catch (erreur) {
    console.error("ÉCHEC :", erreur.message);
    process.exit(1);
}
