/*
 * Test de l'inventaire du formulaire (docs/schema-formulaire.md), produit
 * par la tâche C1-T1.
 *
 * Ce document fige le vocabulaire du moteur de rendu (C1-T3, basculé en
 * production par C1-T3b) : un champ oublié dans l'inventaire, ou une clé qui
 * diverge du brouillon `localStorage` réel (cleChamp(), script.js:863-867),
 * ne se verrait qu'en production, après coup, sur le poste de la
 * praticienne. Ce test recompte donc mécaniquement, à chaque exécution, tout
 * ce que la spécification présente comme normatif — les clés de brouillon,
 * le nombre de blocs, l'ordre et le nombre des images annotables, l'ensemble
 * des `id` gelés — plutôt que de figer ces nombres en constantes qui
 * dériveraient du HTML réel sans que rien ne le signale (défaut relevé à
 * l'audit).
 *
 * Depuis la bascule (C1-T3b), `formulaire/index.html` est une coquille qui
 * ne porte plus les 29 blocs à la main : le témoin indépendant des groupes 1
 * et 7 devient `formulaire/index-v1.html`, la V1 gelée (son intégrité, empreinte
 * SHA-256 comprise, est sous la garde de `tests/test_coquille.py`). Un test
 * qui dériverait sa référence du schéma qu'il contrôle ne contrôlerait rien.
 * Le groupe 6 lit désormais l'union des `id` de la coquille et de ceux
 * qu'émet le schéma ; le groupe 8, nouveau, vérifie que la coquille ne
 * contient plus que l'en-tête.
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

const CHEMIN_V1 = path.join(__dirname, "..", "formulaire", "index-v1.html");
const CHEMIN_COQUILLE = path.join(__dirname, "..", "formulaire", "index.html");
const CHEMIN_CSS = path.join(__dirname, "..", "formulaire", "style.css");
const CHEMIN_JS = path.join(__dirname, "..", "formulaire", "script.js");
const CHEMIN_SPEC = path.join(__dirname, "..", "docs", "schema-formulaire.md");
const CHEMIN_SCHEMA = path.join(__dirname, "..", "formulaire", "schema.json");

function lireNormalise(chemin) {
    return fs.readFileSync(chemin, "utf-8").replace(/\r\n/g, "\n");
}

const htmlV1 = lireNormalise(CHEMIN_V1);
const htmlCoquille = lireNormalise(CHEMIN_COQUILLE);
const css = lireNormalise(CHEMIN_CSS);
const js = lireNormalise(CHEMIN_JS);
const spec = lireNormalise(CHEMIN_SPEC);

/**
 * Le sous-arbre `#form-bilan` d'un texte HTML donné, hors barre d'outils.
 * Localise le conteneur par motif plutôt que par littéral exact
 * (`<div id="form-bilan">`) : la coquille de production porte désormais
 * `data-moteur` sur ce même `div` (`<div id="form-bilan" data-moteur>`),
 * qu'un littéral exact ne reconnaîtrait plus. Lève toujours si le motif est
 * introuvable — jamais un sous-arbre vide passé sous silence.
 */
function corpsFormulaire(texte, nomFichier) {
    const motif = /<div\s+id="form-bilan"[^>]*>/;
    const m = motif.exec(texte);
    if (!m) {
        throw new Error(`« #form-bilan » introuvable dans ${nomFichier}`);
    }
    return texte.slice(m.index);
}

// R2 (audit C1-T1) : compte les appels à lireAttribut() pour pouvoir nommer
// une position (numéro d'occurrence) dans le message de refus, sans jamais
// recopier le contenu lu — ce journal est public, et formulaire/index.html
// est un fichier **client** depuis C1-T3b.
let compteurLectureAttribut = 0;

/**
 * Lit un attribut sous ses trois formes réelles du fichier : guillemets
 * doubles, apostrophes, ou sans guillemet (anomalie A6, `index-v1.html:309`).
 * Si le nom d'attribut est présent mais sous une forme qu'aucune des trois
 * ne reconnaît, le test refuse explicitement plutôt que d'ignorer
 * silencieusement l'attribut — un faux vert y coûterait un bilan perdu. Le
 * message nomme l'attribut et le numéro d'occurrence, jamais le texte lu.
 */
function lireAttribut(attributs, nom) {
    compteurLectureAttribut++;
    const present = new RegExp("\\b" + nom + "\\s*=", "i");
    if (!present.test(attributs)) return undefined;
    const motif = new RegExp(
        "\\b" + nom + "\\s*=\\s*(?:\"([^\"]*)\"|'([^']*)'|([^\\s\"'=<>`]+))", "i"
    );
    const m = attributs.match(motif);
    if (!m) {
        throw new Error(
            `attribut « ${nom} » de forme non reconnue (ni "...", ni '...', ni sans guillemet), ` +
            `occurrence numéro ${compteurLectureAttribut} de lireAttribut()`
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

/** Les clés de brouillon réellement dérivables d'un corps #form-bilan donné. */
function clesDuFormulaire(corps) {
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
function blocsHtml(corps) {
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
function imagesHtml(corps) {
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
function idsReferences(texte, nomFichier) {
    const ids = new Set();
    const motif = /#([A-Za-z_][\w-]*)/g;
    let m;
    while ((m = motif.exec(texte)) !== null) {
        const jeton = m[1];
        const estCouleur = /^[0-9a-fA-F]+$/.test(jeton) && [3, 4, 6, 8].includes(jeton.length);
        if (!estCouleur) ids.add(jeton);
    }

    // R1 (audit C1-T1) : les deux styles de citation littérale réellement
    // utilisés dans ce dépôt (guillemets doubles, apostrophes) sont
    // reconnus. Un argument qui n'est ni l'un ni l'autre, mais qui est un
    // simple identifiant (`getElementById(id)`, script.js:340, un paramètre
    // de fonction) ne porte aucun `id` littéral : rien à ajouter, à juste
    // titre. Toute AUTRE forme (gabarit littéral, concaténation, guillemet
    // mal fermé…) fait refuser le test plutôt que d'être ignorée en
    // silence — un `id` qui ne passerait que par cette forme deviendrait
    // invisible à la dérivation des clés gelées.
    const motifAppel = /getElementById\(\s*([^)]*?)\s*\)/g;
    const motifIdentifiant = /^[A-Za-z_$][A-Za-z0-9_$]*$/;
    let numeroAppel = 0;
    while ((m = motifAppel.exec(texte)) !== null) {
        numeroAppel++;
        const argument = m[1];
        const double = argument.match(/^"([^"]*)"$/);
        const simple = argument.match(/^'([^']*)'$/);
        if (double) {
            ids.add(double[1]);
        } else if (simple) {
            ids.add(simple[1]);
        } else if (motifIdentifiant.test(argument)) {
            // Argument dynamique (variable, paramètre) : aucun id littéral.
        } else {
            throw new Error(
                `getElementById() d'une forme non reconnue (ni "...", ni '...', ni identifiant) ` +
                `dans ${nomFichier}, occurrence numéro ${numeroAppel}`
            );
        }
    }
    return ids;
}

/** Tous les `id` présents dans un corps #form-bilan donné. */
function idsPresentsDansLeFormulaire(corps) {
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
 * Les `id` qu'émet le moteur de rendu à partir de `formulaire/schema.json` :
 * la `cle` de chaque bloc (y compris un bloc `tableau`, `rendu.js:827`), son
 * `titre_cle` quand il en porte un (`rendu.js:648`), la `cle` de chaque
 * champ pour tout type qui en pose une en `id` (texte, zone-texte, date,
 * case, image-annotable — `rendu.js:693,709,716,727,818`), et la `cle` de
 * chaque option d'un champ `radio` (`rendu.js:760`). Les lignes d'un champ
 * `tableau` ne reçoivent jamais d'`id` — seul leur `name` synthétisé les
 * distingue (`rendu.js`, aucun `setAttribute("id", …)` sur ce chemin) — donc
 * rien n'y est ajouté pour ce type.
 *
 * Distincte de clesDuSchemaJson() plus bas, qui dérive les clés DE
 * BROUILLON (forme `ligne.cle + "#" + colonne.valeur` pour un tableau) : un
 * `id` du DOM et une clé de `localStorage` ne sont pas la même chose pour ce
 * type précis.
 */
function idsEmisParLeSchema() {
    const schema = JSON.parse(lireNormalise(CHEMIN_SCHEMA));
    const ids = new Set();
    schema.blocs.forEach(function (bloc) {
        if (bloc.cle) ids.add(bloc.cle);
        if (bloc.titre_cle) ids.add(bloc.titre_cle);
        (bloc.champs || []).forEach(function (champ) {
            if (champ.type === "radio") {
                (champ.valeurs || []).forEach(function (option) {
                    if (option.cle) ids.add(option.cle);
                });
            } else if (champ.type === "tableau") {
                // Les lignes de tableau ne reçoivent jamais d'id (voir le
                // commentaire de la fonction) : rien à ajouter.
            } else if (champ.cle) {
                ids.add(champ.cle);
            }
        });
    });
    return ids;
}

/**
 * L'ensemble des `id` que la spécification doit déclarer gelés : présents
 * dans le formulaire ET référencés par script.js ou style.css. Depuis la
 * bascule (C1-T3b), « présents dans le formulaire » est l'UNION des `id` de
 * la coquille (`#form-bilan` d'`index.html`, barre d'outils comprise hors
 * de cette union puisqu'elle en est exclue) et des `id` qu'émet le schéma
 * (`idsEmisParLeSchema()`) : aucun des deux seuls ne suffit — la coquille
 * n'en porte plus que 6 (`form-bilan`, `maintitle`, `logo`, `date-bilan`,
 * `infos_podo`, `attente-moteur`), et le schéma ne modélise jamais le
 * conteneur `form-bilan` lui-même. La barre d'outils (btn-export,
 * barre-brouillon…) reste hors de #form-bilan et se trouve donc naturellement
 * écartée par cette intersection, sans liste d'exclusion à maintenir à la main.
 */
function idsGelesAttendus(corpsCoquille) {
    const references = new Set([
        ...idsReferences(css, "formulaire/style.css"),
        ...idsReferences(js, "formulaire/script.js")
    ]);
    const presents = new Set([
        ...idsPresentsDansLeFormulaire(corpsCoquille),
        ...idsEmisParLeSchema()
    ]);
    return [...references].filter(function (id) { return presents.has(id); });
}

/**
 * Les clés de brouillon dérivables de `formulaire/schema.json`, par les
 * mêmes règles que `cleChamp()` : la `cle` du champ pour tout type qui en
 * porte une, la `cle` de chaque option pour `radio`, et `ligne.cle + "#" +
 * colonne.valeur` pour chaque colonne de `tableau` — exactement la forme
 * que produit un champ sans `id` dans `cleChamp()`.
 */
function clesDuSchemaJson() {
    const schema = JSON.parse(lireNormalise(CHEMIN_SCHEMA));
    const cles = new Set();
    schema.blocs.forEach(function (bloc) {
        (bloc.champs || []).forEach(function (champ) {
            if (champ.type === "image-annotable") {
                // Les images ne passent pas par cleChamp() (script.js:863-867,
                // #form-bilan input/textarea/select uniquement) : leurs traits
                // sont indexés par position (D7), pas par clé de brouillon.
                return;
            }
            if (champ.type === "radio") {
                (champ.valeurs || []).forEach(function (option) { cles.add(option.cle); });
            } else if (champ.type === "tableau") {
                (champ.lignes || []).forEach(function (ligne) {
                    (ligne.colonnes || []).forEach(function (colonne) {
                        cles.add(ligne.cle + "#" + colonne.valeur);
                    });
                });
            } else if (champ.cle) {
                cles.add(champ.cle);
            }
        });
    });
    return cles;
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
    // Témoin indépendant des 29 blocs, 45 champs et 4 images : la V1 gelée
    // (formulaire/index-v1.html), dont l'intégrité — empreinte SHA-256
    // comprise — est sous la garde de tests/test_coquille.py. Un test qui
    // dériverait sa référence du schéma qu'il contrôle ne contrôlerait rien
    // (contrat C1-T3b, section 7).
    const corpsV1 = corpsFormulaire(htmlV1, "formulaire/index-v1.html");
    // La coquille de production : le seul fichier HTML servi à la tablette
    // depuis la bascule. Les groupes 6 et 8 la lisent directement.
    const corpsCoquille = corpsFormulaire(htmlCoquille, "formulaire/index.html");

    // 1. Bijection entre les clés dérivables du HTML V1 et celles citées dans l'inventaire,
    //    et recomptage mécanique des blocs et des images (plus de constantes figées).
    const clesHtml = clesDuFormulaire(corpsV1);
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

    const blocs = blocsHtml(corpsV1);
    if (blocs.length !== 29) {
        throw new Error(`formulaire/index-v1.html compte ${blocs.length} bloc(s) (.bloc), 29 attendus`);
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

    const images = imagesHtml(corpsV1);
    if (images.length !== 4) {
        throw new Error(`formulaire/index-v1.html compte ${images.length} image(s) dessinable(s), 4 attendues`);
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
        `1. bijection clés HTML (index-v1.html) <-> inventaire (${clesHtml.size} clés, ${lignesChamps} champs) ; ` +
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

    // 6. Les clés gelées (id dont dépendent script.js/style.css) sont toutes déclarées,
    //    ET toutes encore présentes : l'union coquille + schéma ne doit ni en
    //    taire une nouvelle, ni en avoir perdu une déclarée (contrat C1-T3b,
    //    étape 7 — sans quoi le groupe passerait "vert à vide" dès que la
    //    coquille ne porte plus que l'en-tête).
    const attendus = idsGelesAttendus(corpsCoquille);
    const cites = clesGeleesCitees();
    const geleesNonDeclarees = attendus.filter(function (id) { return !cites.has(id); });
    if (geleesNonDeclarees.length > 0) {
        throw new Error(`id gelé(s) référencé(s) par script.js ou style.css mais absent(s) de la liste « Clés gelées » : ${geleesNonDeclarees.join(", ")}`);
    }
    const geleesDisparues = [...cites].filter(function (id) { return !attendus.includes(id); });
    if (geleesDisparues.length > 0) {
        throw new Error(`id gelé(s) déclaré(s) dans la liste « Clés gelées » mais plus émis ni par la coquille (formulaire/index.html) ni par formulaire/schema.json : ${geleesDisparues.join(", ")}`);
    }
    if (attendus.length !== 7) {
        throw new Error(`${attendus.length} id(s) gelé(s) exigé(s) trouvé(s) (${attendus.join(", ")}), 7 attendus (conteneur #form-bilan compris)`);
    }
    console.log(`6. clés gelées exhaustives (${attendus.length} id attendus, conteneur #form-bilan compris)`);

    // 7. Bijection clés du HTML (V1 gelée) <-> clés de formulaire/schema.json (C1-T3).
    //    `date-bilan` est la seule clé du HTML que schema.json ne porte pas :
    //    son bloc d'en-tête reste écrit en dur, hors du schéma (section 4 du
    //    contrat C1-T3b — l'en-tête sort en configuration avec C2-T1, pas ici).
    //    C'est la seule différence tolérée ; toute autre fait échouer ce test
    //    en la nommant, et renommer une clé dans schema.json (p. ex.
    //    « familliaux » en « familiaux ») la fait apparaître ici.
    const clesSchema = clesDuSchemaJson();
    const manquantesDuSchema = [...clesHtml].filter(function (c) { return c !== "date-bilan" && !clesSchema.has(c); });
    const enTropDansSchema = [...clesSchema].filter(function (c) { return !clesHtml.has(c); });
    if (manquantesDuSchema.length > 0) {
        throw new Error(`clé(s) du formulaire absente(s) de formulaire/schema.json : ${manquantesDuSchema.join(", ")}`);
    }
    if (enTropDansSchema.length > 0) {
        throw new Error(`clé(s) de formulaire/schema.json absente(s) du formulaire : ${enTropDansSchema.join(", ")}`);
    }
    // L'exception « date-bilan » ne doit pas être un laissez-passer
    // inconditionnel : si cette clé disparaissait un jour de la coquille,
    // elle resterait acceptée ci-dessus sans que rien ne le remarque. Cette
    // assertion rend l'exception non vacante.
    if (!idsPresentsDansLeFormulaire(corpsCoquille).has("date-bilan")) {
        throw new Error(`« date-bilan » est exceptée de la bijection HTML <-> schema.json, mais n'est plus présente dans la coquille (formulaire/index.html)`);
    }
    console.log(`7. bijection clés HTML <-> formulaire/schema.json (${clesSchema.size} clés, « date-bilan » exceptée)`);

    // 8. La coquille de production ne contient plus que l'en-tête : rien
    //    n'empêche sinon de recopier un bloc à la main dans index.html, ce
    //    qui réintroduirait exactement le verrou que C1 existe pour lever
    //    (contrat C1-T3b, étape 7, point 5).
    const blocsCoquille = blocsHtml(corpsCoquille);
    if (blocsCoquille.length !== 1) {
        throw new Error(`#form-bilan de formulaire/index.html compte ${blocsCoquille.length} élément(s) de classe « bloc » (${blocsCoquille.join(", ")}), 1 attendu (l'en-tête)`);
    }
    const imagesCoquille = imagesHtml(corpsCoquille);
    if (imagesCoquille.length !== 0) {
        throw new Error(`#form-bilan de formulaire/index.html compte ${imagesCoquille.length} image(s) dessinable(s), 0 attendue`);
    }
    const clesCoquille = clesDuFormulaire(corpsCoquille);
    if (clesCoquille.size !== 1 || !clesCoquille.has("date-bilan")) {
        throw new Error(`#form-bilan de formulaire/index.html compte ${clesCoquille.size} champ(s) de saisie (${[...clesCoquille].join(", ")}), 1 attendu : date-bilan`);
    }
    // <main> ne doit contenir que le paragraphe statique #attente-moteur —
    // ni un bloc recopié à la main, ni un second message, rien d'autre.
    const motifMain = /<main[^>]*>/;
    const mDebutMain = motifMain.exec(corpsCoquille);
    if (!mDebutMain) {
        throw new Error("« <main> » introuvable dans #form-bilan de formulaire/index.html");
    }
    const motifBalisesMain = /<(\/?)main\b[^>]*>/g;
    motifBalisesMain.lastIndex = mDebutMain.index;
    let profondeurMain = 0;
    let finMain = -1;
    let mBaliseMain;
    while ((mBaliseMain = motifBalisesMain.exec(corpsCoquille)) !== null) {
        if (mBaliseMain[1] === "/") {
            profondeurMain--;
            if (profondeurMain === 0) { finMain = motifBalisesMain.lastIndex; break; }
        } else {
            profondeurMain++;
        }
    }
    if (finMain === -1) {
        throw new Error("balise fermante « </main> » introuvable dans formulaire/index.html");
    }
    const interieurMain = corpsCoquille
        .slice(mDebutMain.index + mDebutMain[0].length, finMain - "</main>".length)
        .replace(/<!--[\s\S]*?-->/g, "");
    const balisesDansMain = [...interieurMain.matchAll(/<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g)]
        .map(function (m) { return m[1].toLowerCase(); });
    if (balisesDansMain.length !== 1 || balisesDansMain[0] !== "p" || !/<p\s+id="attente-moteur"/.test(interieurMain)) {
        throw new Error(
            `<main> de formulaire/index.html ne se réduit pas au seul paragraphe #attente-moteur ` +
            `(balise(s) trouvée(s) : ${balisesDansMain.join(", ") || "aucune"})`
        );
    }
    console.log("8. la coquille (formulaire/index.html) ne contient que l'en-tête : "
        + "1 bloc, 0 image, 1 champ (date-bilan), <main> réduit à #attente-moteur");

    console.log("\nTout est vert.");
} catch (erreur) {
    console.error("ÉCHEC :", erreur.message);
    process.exit(1);
}
