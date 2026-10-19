/*
 * Moteur de rendu du formulaire — valide `schema.json`, puis construit le
 * DOM du bilan à partir de cette seule description : plus aucun bloc n'est
 * écrit à la main dans `formulaire/index.html`.
 *
 * Deux fonctions nommées par le contrat C1-T3 : `validerSchema(schema)` et
 * `rendre(schema, document, conteneur)`. La troisième, `demarrerApplication`,
 * vit dans `formulaire/script.js` — ce fichier l'appelle après son rendu
 * (section « couture », plus bas), il ne la définit pas.
 *
 * Aucune couleur n'est écrite ici (les cinq tokens de `:root` restent la
 * source unique, C1-T2) et tout texte venu du schéma passe par
 * `textContent`, jamais par `innerHTML` : un schéma sera produit par
 * l'atelier C9 à partir d'un questionnaire rempli par un tiers, et un
 * libellé ne doit jamais pouvoir devenir du balisage.
 *
 * Aucun accès au DOM au niveau module, hors l'enregistrement du gestionnaire
 * `DOMContentLoaded` en bas de fichier (même piège, même parade que
 * `formulaire/script.js` : les doubles de test fournissent un
 * `document.addEventListener` qui ne rappelle jamais rien).
 *
 * ──────────────────────────────────────────────────────────────────────
 * Formes canoniques relevées dans `formulaire/index.html` (V1), une ligne
 * par couple (type, disposition) effectivement rencontré. Ce tableau est la
 * référence que `rendreBloc()` et ses fonctions sœurs reproduisent ;
 * `tests/test_comparaison_dom.js` vérifie que la sortie du moteur s'y
 * conforme (projection définie au critère 2 du contrat).
 *
 *   Bloc (disposition par défaut « empilee »)
 *     conteneur   <div id="CLE" class="bloc">            (une exception non
 *                 reproduite par le moteur : `patient_infos` est un
 *                 <section> en V1 — voir le commentaire de `rendreBloc()`)
 *     titre       voir le tableau « titre de bloc » plus bas
 *     texte/date  <label class="titre_section" for="CLE">LIBELLE:</label>
 *                 <input type="text|date" id="CLE">
 *                 <br>
 *     zone-texte  <label class="titre_section" for="CLE">LIBELLE:</label>
 *                 <textarea id="CLE" class="input-auto-grow"></textarea>
 *                 <br>
 *     case        <label class="checkbox-label"><input type="checkbox"
 *                 id="CLE"><span class="custom-checkbox"></span> LIBELLE</label>
 *                 <br>
 *     radio       un <div class="radio-group"> isolé, voir « en-ligne »
 *     image-ann.  apparence "squelette" (défaut) : <img id="CLE" ...
 *                 class="squelette dessinable"> directement dans le bloc ;
 *                 apparence "encadree" : voir « bloc encadré » plus bas
 *
 *   Bloc, disposition "en-ligne" (`form-group-inline bloc`)
 *     titre       <label class="titre_section">LIBELLE:</label>
 *     groupe      un seul <div class="checkbox-group"> si le bloc contient
 *                 au moins un champ "case", sinon <div class="radio-group"> ;
 *                 les champs "case" et les options "radio" s'y succèdent
 *                 dans l'ordre du schéma (bloc 10 « Podo » mélange les deux)
 *     case        <label class="checkbox-label"><input type="checkbox"
 *                 id="CLE"><span class="custom-checkbox"></span> LIBELLE</label>
 *     radio       <label class="radio-label"><input type="radio" id="OPT_CLE"
 *                 name="groupe-PREMIERE_OPT_CLE" value="OPT_VALEUR">
 *                 <span class="custom-radio"></span> OPT_LIBELLE</label>
 *
 *   Bloc, disposition "en-ligne-bas" (`form-group-inline-bottom bloc`)
 *     texte       <label class="titre_section" for="CLE">LIBELLE:</label>
 *                 <input type="text" id="CLE">                 (pas de <br>)
 *
 *   Bloc, disposition "atcd" (`form-group-atcd bloc`)
 *     titre       <label class="titre_section">ATCD:</label>
 *     groupe      <div class="atcd-inputs-container"> contenant, par champ,
 *                 <div class="atcd-row"><label class="atcd-sublabel"
 *                 for="CLE">LIBELLE:</label><textarea id="CLE"
 *                 class="input-auto-grow"></textarea></div>
 *
 *   Bloc, disposition "chaussures" (`chaussures-inline-group bloc`)
 *     texte       <label for="CLE">LIBELLE:</label>
 *                 <input type="text" id="CLE">            (pas de "titre_section")
 *     case        <input type="checkbox" id="CLE"> LIBELLE  (pas d'enveloppe :
 *                 en V1 le `<label>` qui précède « Usées » est vide et sans
 *                 `for`, donc sans effet — le moteur ne le reproduit pas,
 *                 voir le constat consigné dans le compte rendu de la tâche)
 *
 *   Titre de bloc (`titre_apparence`, D10)
 *     "h3"        <h3 class="Title" id="TITRE_CLE">TITRE</h3>        (pas de ":")
 *     "label_bloc"<label class="titre_section_bloc" id="TITRE_CLE">TITRE:</label>
 *     "label"     <label class="titre_section" id="TITRE_CLE">TITRE:</label>  (défaut)
 *
 *   Bloc dont l'unique champ est de type "tableau" (disposition sans objet)
 *     <table id="CLE" class="bloc">
 *       <thead><tr><th class="titre_section">LIBELLE:</th>
 *                  <th>ENTETE_0</th><th>ENTETE_1</th>…</tr></thead>
 *       <tbody>
 *         <tr><td>LIGNE.nom</td>
 *             <td><input type="radio" name="LIGNE.cle" value="COL.valeur"></td>
 *             …</tr>
 *       </tbody>
 *     </table>
 *
 *   Bloc encadré (un champ "image-annotable" porte `apparence: "encadree"`,
 *   D9 ; un seul cas en production, bloc « Plan appareillage »)
 *     <div class="appareillage-container">
 *       <div class="empreintes-box"><img id="CLE" ... class="dessinable"></div>
 *       (les autres champs du bloc, à la suite, sans label propre : leur
 *        libellé est déjà porté par le titre du bloc — D9)
 *     </div>
 * ──────────────────────────────────────────────────────────────────────
 */

const VERSION_CONNUE = 1;
const TYPES_RETENUS = ["texte", "zone-texte", "date", "case", "radio", "tableau", "image-annotable"];
const DISPOSITIONS_FERMEES = ["empilee", "en-ligne", "en-ligne-bas", "atcd", "chaussures"];
const TITRE_APPARENCES_FERMEES = ["h3", "label", "label_bloc"];
const APPARENCES_IMAGE_FERMEES = ["squelette", "encadree"];
// Apparences d'une case à cocher. Par défaut la puce précède le libellé ;
// `titre_avant` place au contraire le libellé devant la case, dans son propre
// label de classe « titre_section », comme le fait la V1 pour « Empreinte
// encre » (`index-v1.html:306-311`). Sans elle, le moteur inversait l'ordre
// des deux — défaut visible au PDF, constat du 19 octobre 2026.
const APPARENCES_CASE_FERMEES = ["titre_avant"];
const TYPES_AVEC_CLE_OBLIGATOIRE = ["texte", "zone-texte", "date", "case", "image-annotable"];
const TYPES_AVEC_LIBELLE_OBLIGATOIRE = ["texte", "zone-texte", "date", "case", "tableau", "image-annotable"];
const TYPES_AVEC_DEFAUT_AUTORISE = ["texte", "zone-texte", "date", "case"];
const TYPES_AVEC_INDICATION_AUTORISEE = ["texte", "zone-texte"];

// Attributs facultatifs reconnus à chaque niveau — D8 : une clé absente de
// l'un de ces deux ensembles est ignorée avec un avertissement, jamais un
// refus, jamais un silence (amendement D8, docs/schema-formulaire.md §5.1).
// `titre_apparence` et `titre_cle` sont réservés au bloc : portés par un
// champ, ce n'est pas une extension facultative mais une erreur de
// position — la règle 14 les refuse nommément, un cran avant
// l'avertissement générique ci-dessous.
const ATTRIBUTS_BLOC_CONNUS = new Set(
    ["cle", "en_tete", "disposition", "titre", "titre_apparence", "titre_cle",
     "balise", "champs"]
);

// La balise du conteneur de bloc. `div` par défaut ; `section` existe parce
// que la V1 l'emploie pour `patient_infos`, et parce qu'un `h3` n'a pas la
// même taille par défaut selon qu'il est ou non dans une section. C'est une
// donnée du schéma, pas une table de correspondance par clé à l'intérieur du
// moteur — ce que D9 interdit (constat du 19 octobre 2026).
const BALISES_BLOC_FERMEES = ["div", "section"];
const ATTRIBUTS_CHAMP_CONNUS = new Set([
    "type", "cle", "libelle", "defaut", "indication",
    "valeurs", "entetes", "lignes", "fichier", "texte_alternatif", "apparence"
]);

/**
 * Constat n°4 de l'audit C1-T3, étendu par C1-T3b : les 21 `id` que la
 * coquille de production (`formulaire/index.html`) émet — son conteneur
 * `#form-bilan`, son bloc d'en-tête hors schéma (titre, champ de date, logo,
 * identité du cabinet), son message statique `#attente-moteur`, et toute sa
 * barre d'outils (boutons d'export/nouveau/dossier, réglages du stylet,
 * barres de brouillon et d'attente, zone de messages) — ne doivent jamais
 * être déclarés dans le schéma. Les vérifications d'unicité des règles 4 et
 * 8 ne comparent qu'entre clés DU schéma ; un schéma qui revendiquerait l'un
 * de ces `id` produirait un second élément de même `id`, et `cleChamp()`
 * (`script.js:869-873`) rendrait la même clé de brouillon aux deux — une
 * valeur écraserait l'autre en silence.
 *
 * Avant C1-T3b, seuls les cinq `id` DANS `#form-bilan` (le conteneur et son
 * en-tête) figuraient ici ; les seize autres étaient supposés protégés par
 * le seul ordre du document (la barre d'outils vit AVANT `#form-bilan`,
 * invariant du contrat) — un argument qui ne vaut de toute façon que pour
 * quinze d'entre eux : le seizième, `attente-moteur`, vit lui-même DANS
 * `#form-bilan > main` (contrat C1-T3b, section 3), là où l'invariant
 * d'ordre ne porte que sur ce qui précède `#form-bilan`. L'argument était de
 * toute façon un argument de hasard : l'ordre protège `getElementById()`
 * mais pas `label for=`, qui pointerait sur le mauvais contrôle, et un futur
 * déplacement de la barre d'outils rendrait le bouton d'export inerte sans
 * qu'aucune règle ne s'en plaigne. Les 21 `id` sont donc tous réservés ici,
 * et `tests/test_coquille.py` vérifie mécaniquement que cette liste reste
 * l'exacte image de ceux que la coquille émet réellement — ni plus, ni
 * moins — plutôt que de rester une liste qui pourrait un jour mentir.
 *
 * Les SEPT clés gelées de `docs/schema-formulaire.md` n'y figurent PAS, à
 * l'exception de `form-bilan` et `logo` : les cinq autres (`patient_infos`,
 * `patient_info_title`, `section_squelettes`,
 * `section_enregistrement_plateforme`, `image_empreintes`) sont au
 * contraire des clés que le SCHÉMA doit légitimement émettre — c'est tout
 * l'objet de D2, et `formulaire/schema.json` les porte déjà. Les interdire
 * ici casserait la production actuelle sans rien protéger de plus : un
 * conflit sur l'une d'elles serait interne au schéma, déjà couvert par les
 * règles 4 et 8. Vérifié à la rédaction du contrat C1-T3b : aucune des 82
 * clés du schéma de production ne collisionne avec aucun des 21 `id`
 * ci-dessous.
 */
const IDS_RESERVES_COQUILLE = new Set([
    "form-bilan", "date-bilan", "maintitle", "logo", "infos_podo", "attente-moteur",
    "btn-export", "btn-nouveau", "btn-dossier",
    "barre-brouillon", "texte-brouillon", "btn-restaurer", "btn-abandonner",
    "barre-attente", "texte-attente", "btn-reessayer",
    "zone-messages", "outils-globaux", "couleur-libre", "epaisseur-trait", "apercu-trait"
]);

/* ========================= Validation (section 7) ========================= */

/**
 * Applique les règles 1 à 14 de `docs/schema-formulaire.md` §7, plus les
 * vérifications internes du moteur qui ne portent pas de numéro (le type
 * `tableau` combiné à un autre champ, les clés réservées à la coquille…),
 * et retourne la liste complète des refus (jamais une exception, jamais un
 * refus partiel) : chaque message nomme la règle et la position (index de
 * bloc, index de champ, clé), jamais la valeur d'un champ de saisie. Un
 * tableau vide signifie « schéma valide, et rendable sans lever » : tout
 * schéma qui passerait cette fonction mais ferait lever `rendre()` est un
 * défaut de cette fonction, pas une limite acceptée (constat n°5, audit C1-T3).
 */
function validerSchema(schema) {
    const erreurs = [];

    if (schema === null || typeof schema !== "object" || Array.isArray(schema)) {
        erreurs.push("règle 1 : le document racine doit être un objet JSON.");
        return erreurs;
    }

    const clesRacine = Object.keys(schema);
    const clesRacineInattendues = clesRacine.filter(function (c) {
        return c !== "version_schema" && c !== "blocs";
    });
    if (clesRacineInattendues.length > 0) {
        erreurs.push("règle 1 : clé(s) racine inconnue(s) refusée(s) : " + clesRacineInattendues.join(", "));
    }
    if (!("version_schema" in schema)) {
        erreurs.push("règle 1 : la clé racine « version_schema » est absente.");
    }
    if (!("blocs" in schema)) {
        erreurs.push("règle 1 : la clé racine « blocs » est absente.");
    }

    if ("version_schema" in schema) {
        if (!Number.isInteger(schema.version_schema)) {
            erreurs.push("règle 2 : « version_schema » doit être un entier.");
        } else if (schema.version_schema !== VERSION_CONNUE) {
            erreurs.push("règle 2 : version de schéma inconnue du moteur : " + schema.version_schema);
        }
    }

    if (!("blocs" in schema)) return erreurs;

    if (!Array.isArray(schema.blocs) || schema.blocs.length === 0) {
        erreurs.push("règle 3 : « blocs » doit être un tableau non vide.");
        return erreurs;
    }

    const clesBlocVues = new Set();
    const clesChampVues = new Set();
    let blocEnTeteVu = false;

    schema.blocs.forEach(function (bloc, indexBloc) {
        if (bloc === null || typeof bloc !== "object" || Array.isArray(bloc)) {
            erreurs.push("règle 3 : le bloc d'index " + indexBloc + " n'est pas un objet.");
            return;
        }

        if (typeof bloc.cle !== "string" || bloc.cle === "") {
            erreurs.push("règle 4 : le bloc d'index " + indexBloc + " n'a pas de « cle » non vide.");
        } else if (IDS_RESERVES_COQUILLE.has(bloc.cle)) {
            erreurs.push("sécurité du moteur : « cle » de bloc réservée à la coquille (index " + indexBloc + ") : " + bloc.cle);
        } else if (clesBlocVues.has(bloc.cle)) {
            erreurs.push("règle 4 : « cle » de bloc dupliquée (index " + indexBloc + ") : " + bloc.cle);
        } else {
            clesBlocVues.add(bloc.cle);
        }

        if ("disposition" in bloc && DISPOSITIONS_FERMEES.indexOf(bloc.disposition) === -1) {
            erreurs.push("règle 5 : disposition inconnue au bloc d'index " + indexBloc + " : " + bloc.disposition);
        }

        if (bloc.en_tete === true) {
            if (indexBloc !== 0) {
                erreurs.push("règle 6 : « en_tete » ne peut être porté que par le premier bloc (vu à l'index " + indexBloc + ").");
            }
            if (blocEnTeteVu) {
                erreurs.push("règle 6 : plusieurs blocs portent « en_tete » (index " + indexBloc + ").");
            }
            blocEnTeteVu = true;
        }

        if ("balise" in bloc && BALISES_BLOC_FERMEES.indexOf(bloc.balise) === -1) {
            erreurs.push("règle 15 : « balise » inconnue au bloc d'index " + indexBloc
                + " : " + bloc.balise + " (attendu : " + BALISES_BLOC_FERMEES.join(", ") + ")");
        }
        if ("titre_apparence" in bloc && TITRE_APPARENCES_FERMEES.indexOf(bloc.titre_apparence) === -1) {
            erreurs.push("règle 14 : « titre_apparence » inconnue au bloc d'index " + indexBloc + " : " + bloc.titre_apparence);
        }
        if ("titre_cle" in bloc) {
            if (typeof bloc.titre_cle !== "string" || bloc.titre_cle === "") {
                erreurs.push("règle 14 : « titre_cle » doit être une chaîne non vide au bloc d'index " + indexBloc + ".");
            } else if (IDS_RESERVES_COQUILLE.has(bloc.titre_cle)) {
                erreurs.push("sécurité du moteur : « titre_cle » réservée à la coquille au bloc d'index " + indexBloc + " : " + bloc.titre_cle);
            }
        }

        // D8 : un attribut facultatif inconnu du bloc est ignoré avec un
        // avertissement, jamais un refus, jamais un silence.
        avertirAttributsInconnus(bloc, ATTRIBUTS_BLOC_CONNUS, "bloc d'index " + indexBloc);

        if (!Array.isArray(bloc.champs)) {
            erreurs.push("règle 3 : « champs » du bloc d'index " + indexBloc + " doit être un tableau.");
            return;
        }

        bloc.champs.forEach(function (champ, indexChamp) {
            validerChamp(champ, indexBloc, indexChamp, clesChampVues, erreurs);
        });

        verifierCompatibiliteBloc(bloc, indexBloc, erreurs);
    });

    return erreurs;
}

/**
 * D8 : avertit, sans jamais refuser ni se taire, pour toute clé de `objet`
 * absente de `connues`. N'est jamais appelée sur la racine du document : la
 * règle 1 y ferme le jeu des clés, sans exception (D8).
 */
function avertirAttributsInconnus(objet, connues, etiquette) {
    Object.keys(objet).forEach(function (cle) {
        if (!connues.has(cle)) {
            console.warn("Attribut facultatif inconnu, ignoré (" + etiquette + ") : " + cle);
        }
    });
}

function validerChamp(champ, indexBloc, indexChamp, clesChampVues, erreurs) {
    const position = "bloc " + indexBloc + ", champ " + indexChamp;

    if (champ === null || typeof champ !== "object" || Array.isArray(champ)) {
        erreurs.push("règle 7 : le champ du " + position + " n'est pas un objet.");
        return;
    }

    if (typeof champ.type !== "string" || TYPES_RETENUS.indexOf(champ.type) === -1) {
        erreurs.push("règle 7 : type de champ inconnu au " + position + " : " + champ.type);
        return;
    }

    if (TYPES_AVEC_CLE_OBLIGATOIRE.indexOf(champ.type) !== -1) {
        verifierCleUnique(champ.cle, position, clesChampVues, erreurs);
    }

    if (champ.type === "radio") {
        if (!Array.isArray(champ.valeurs) || champ.valeurs.length < 2) {
            erreurs.push("règle 9 : « valeurs » du " + position + " doit compter au moins deux options.");
        } else {
            champ.valeurs.forEach(function (option, indexOption) {
                const positionOption = position + ", option " + indexOption;
                if (!option || typeof option !== "object" || !option.cle || !option.valeur || !option.libelle) {
                    erreurs.push("règle 9 : option incomplète au " + positionOption + " (cle, valeur et libelle sont requis).");
                } else {
                    verifierCleUnique(option.cle, positionOption, clesChampVues, erreurs);
                }
            });
        }
    }

    if (champ.type === "tableau") {
        if (!Array.isArray(champ.entetes) || champ.entetes.length === 0 ||
            champ.entetes.some(function (e) { return typeof e !== "string" || e === ""; })) {
            // Sans ce contrôle, creerTable() lève un TypeError sur
            // `champ.entetes.forEach` (constat n°5, audit C1-T3) : un
            // schéma qui aurait dû être refusé ici faisait lever rendre().
            erreurs.push("règle 10 : « entetes » du " + position + " doit être un tableau non vide de chaînes non vides.");
        }
        if (!Array.isArray(champ.lignes) || champ.lignes.length === 0) {
            erreurs.push("règle 10 : « lignes » du " + position + " doit compter au moins une entrée.");
        } else {
            champ.lignes.forEach(function (ligne, indexLigne) {
                const positionLigne = position + ", ligne " + indexLigne;
                if (!ligne || typeof ligne !== "object" || !ligne.nom || !ligne.cle ||
                    !Array.isArray(ligne.colonnes) || ligne.colonnes.length < 2) {
                    erreurs.push("règle 10 : ligne incomplète au " + positionLigne + " (nom, cle et au moins deux colonnes sont requis).");
                    return;
                }
                ligne.colonnes.forEach(function (colonne, indexColonne) {
                    if (!colonne || typeof colonne !== "object" || !colonne.valeur || !colonne.libelle) {
                        erreurs.push("règle 10 : colonne incomplète au " + positionLigne + ", colonne " + indexColonne + ".");
                    }
                });
            });
        }
    }

    if ("defaut" in champ && TYPES_AVEC_DEFAUT_AUTORISE.indexOf(champ.type) === -1) {
        erreurs.push("règle 11 : « defaut » n'est pas autorisé sur le type « " + champ.type + " » au " + position + ".");
    }

    if ("indication" in champ && TYPES_AVEC_INDICATION_AUTORISEE.indexOf(champ.type) === -1) {
        erreurs.push("règle 11 : « indication » n'est pas autorisé sur le type « " + champ.type + " » au " + position + ".");
    }

    if ("apparence" in champ) {
        // Deux types seulement portent une apparence, chacun avec son jeu fermé.
        if (champ.type === "image-annotable") {
            if (APPARENCES_IMAGE_FERMEES.indexOf(champ.apparence) === -1) {
                erreurs.push("règle 13 : « apparence » inconnue au " + position + " : " + champ.apparence);
            }
        } else if (champ.type === "case") {
            if (APPARENCES_CASE_FERMEES.indexOf(champ.apparence) === -1) {
                erreurs.push("règle 13 : « apparence » inconnue au " + position
                    + " : " + champ.apparence + " (attendu : "
                    + APPARENCES_CASE_FERMEES.join(", ") + ")");
            }
        } else {
            erreurs.push("règle 13 : « apparence » n'est pas autorisé sur le type « " + champ.type + " » au " + position + ".");
        }
    }

    if (TYPES_AVEC_LIBELLE_OBLIGATOIRE.indexOf(champ.type) !== -1 &&
        (typeof champ.libelle !== "string" || champ.libelle === "")) {
        erreurs.push("règle 12 : « libelle » est obligatoire au " + position + ".");
    }

    // Règle 14 (étendue) : titre_apparence/titre_cle ne vivent qu'au niveau
    // du bloc (section 5.2). Portés par un champ, ce n'est pas un attribut
    // facultatif inconnu (D8) mais un attribut CONNU à la mauvaise place :
    // refusé nommément, et non pas seulement averti.
    if ("titre_apparence" in champ || "titre_cle" in champ) {
        erreurs.push("règle 14 : « titre_apparence »/« titre_cle » ne sont valides que sur un bloc, pas sur un champ, au " + position + ".");
    }

    // Au-delà des 14 règles numérotées : un `image-annotable` sans chemin
    // d'image ne casse pas la validation au sens de la section 7, mais
    // rendrait un <img> sans source — ou, pire, une requête sortante vers
    // un hôte arbitraire (constat n°8, audit C1-T3) si le chemin n'est pas
    // contraint. Signalé séparément, pas comme une « règle 15 » — la liste
    // de la section 7 est fermée.
    if (champ.type === "image-annotable") {
        if (typeof champ.fichier !== "string" || champ.fichier === "") {
            erreurs.push("sécurité du moteur : « fichier » est requis pour l'image-annotable du " + position + ".");
        } else if (!cheminImageAutorise(champ.fichier)) {
            erreurs.push(
                "sécurité du moteur : « fichier » doit être un chemin relatif sous images/, sans « .. », " +
                "sans antislash ni schéma d'URL, au " + position + "."
            );
        }
        if (typeof champ.texte_alternatif !== "string" || champ.texte_alternatif === "") {
            erreurs.push("sécurité du moteur : « texte_alternatif » est requis pour l'image-annotable du " + position + ".");
        }
    }

    // D8 : attributs facultatifs inconnus du champ, avertis sans être
    // refusés — titre_apparence/titre_cle sont déjà couverts ci-dessus par
    // un refus nommé, donc exclus d'un second avertissement redondant.
    const connuesIciAussi = new Set(ATTRIBUTS_CHAMP_CONNUS);
    connuesIciAussi.add("titre_apparence");
    connuesIciAussi.add("titre_cle");
    avertirAttributsInconnus(champ, connuesIciAussi, position);
}

/**
 * Chemin d'image autorisé (constat n°8, audit C1-T3) : relatif, sous
 * `images/`, sans traversée de répertoire ni schéma d'URL — la même
 * discipline qu'`assainir_nom()` côté serveur (`serveur/serveur.py`), et
 * pour la même raison : un schéma sera produit par l'atelier C9, et un
 * champ de configuration ne doit jamais devenir un chemin d'exécution.
 */
function cheminImageAutorise(chemin) {
    if (typeof chemin !== "string" || chemin === "") return false;
    if (chemin.indexOf("..") !== -1) return false;
    if (chemin.indexOf("\\") !== -1) return false;
    if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(chemin)) return false; // schéma d'URL (http:, data:…)
    if (chemin.indexOf("//") === 0) return false;               // protocole relatif (//hôte/chemin)
    if (chemin.charAt(0) === "/") return false;
    return /^images\/[A-Za-z0-9._-]+\.(?:png|jpe?g|svg)$/i.test(chemin);
}

function verifierCleUnique(cle, position, clesChampVues, erreurs) {
    if (typeof cle !== "string" || cle === "") {
        erreurs.push("règle 8 : « cle » manquante ou vide au " + position + ".");
        return;
    }
    if (IDS_RESERVES_COQUILLE.has(cle)) {
        erreurs.push("sécurité du moteur : « cle » réservée à la coquille au " + position + " : " + cle);
        return;
    }
    if (clesChampVues.has(cle)) {
        erreurs.push("règle 8 : « cle » de champ dupliquée (" + position + ") : " + cle);
    } else {
        clesChampVues.add(cle);
    }
}

/**
 * Constat n°3 de l'audit C1-T3 : sans ce contrôle, un champ "tableau"
 * combiné à un autre champ dans le même bloc (le cas du bloc-tableau
 * exempté ci-dessous mis à part), ou un champ "radio"/"tableau" dans une
 * disposition qui ne sait pas le rendre, atterrissait avec un attribut
 * dérivé de `champ.cle` alors que ce type n'en porte pas — `id="undefined"`,
 * littéralement, partagé par tous les champs fautifs du même type : la
 * dernière valeur saisie écraserait les autres au brouillon. Cette
 * fonction referme la combinatoire type × disposition à ce que les
 * fonctions de rendu savent effectivement construire.
 */
const TYPES_COMPATIBLES_PAR_DISPOSITION = {
    "empilee": ["texte", "zone-texte", "date", "case", "radio", "image-annotable"],
    "en-ligne": ["case", "radio"],
    "en-ligne-bas": ["texte", "zone-texte", "date"],
    "atcd": ["texte", "zone-texte", "date"],
    "chaussures": ["texte", "case"]
};

function verifierCompatibiliteBloc(bloc, indexBloc, erreurs) {
    if (!Array.isArray(bloc.champs)) return;

    // Cas spécial : un bloc dont l'unique champ est "tableau" devient le
    // <table> lui-même (rendreBloc()) — exempté de la combinatoire ci-dessous.
    if (bloc.champs.length === 1 && bloc.champs[0] && bloc.champs[0].type === "tableau") {
        return;
    }

    const encadree = bloc.champs.some(function (c) {
        return c && c.type === "image-annotable" && c.apparence === "encadree";
    });

    const dispositionConnue = !("disposition" in bloc) || DISPOSITIONS_FERMEES.indexOf(bloc.disposition) !== -1;
    const disposition = bloc.disposition || "empilee";

    bloc.champs.forEach(function (champ, indexChamp) {
        if (!champ || typeof champ.type !== "string") return; // déjà refusé par la règle 7/3
        const position = "bloc " + indexBloc + ", champ " + indexChamp;

        if (champ.type === "tableau") {
            erreurs.push("sécurité du moteur : le type « tableau » n'est valide que comme unique champ de son bloc (" + position + ").");
            return;
        }

        if (encadree) {
            // D9 : à côté d'une image "encadree", les autres champs n'ont
            // pas de label propre et passent par creerControleSaisie(),
            // qui ne sait construire que texte/zone-texte/date.
            if (champ.type !== "image-annotable" && ["texte", "zone-texte", "date"].indexOf(champ.type) === -1) {
                erreurs.push("sécurité du moteur : type « " + champ.type + " » incompatible avec un bloc encadré, apparence « encadree » (" + position + ").");
            }
            return;
        }

        if (!dispositionConnue) return; // déjà refusé par la règle 5, pas la peine d'ajouter du bruit

        const compatibles = TYPES_COMPATIBLES_PAR_DISPOSITION[disposition] || TYPES_COMPATIBLES_PAR_DISPOSITION.empilee;
        if (compatibles.indexOf(champ.type) === -1) {
            erreurs.push("sécurité du moteur : type « " + champ.type + " » incompatible avec la disposition « " + disposition + " » (" + position + ").");
        }
    });
}

/* ============================ Rendu (section 6) ============================ */

const CLASSES_DISPOSITION = {
    "en-ligne": "form-group-inline",
    "en-ligne-bas": "form-group-inline-bottom",
    "atcd": "form-group-atcd",
    "chaussures": "chaussures-inline-group"
};

/**
 * Construit l'arbre entier dans un fragment détaché et ne l'insère dans
 * `conteneur` qu'une fois la construction terminée sans erreur, et ne lève
 * jamais (constat n°5, audit C1-T3) : tout schéma qui passe
 * `validerSchema()` doit être rendable, et une défaillance interne
 * imprévue est rattrapée et rendue comme un refus nommé plutôt que de
 * remonter comme une exception non interceptée.
 *
 * `conteneur` est l'élément qui doit recevoir directement les blocs — en
 * production, le `<main>` de la coquille (`formulaire/index.html`),
 * **pas** `#form-bilan` lui-même : en V1, les 28 blocs du corps vivent DANS
 * `<main>` (`main { padding: 10px }`, `style.css:23`), pas après lui
 * (constat n°1, audit C1-T3). C'est l'appelant qui résout `<main>` dans
 * `#form-bilan` (`demarrerMoteur()` plus bas, avec `querySelector` — une
 * méthode que le double DOM de `tests/outils/dom-minimal.js` n'expose pas,
 * et qu'aucun chemin testé par ce fichier n'emprunte).
 *
 * Retourne `{ ok: true }` si le rendu a eu lieu, ou `{ ok: false, erreurs }`
 * si la validation (ou une défaillance interne) a refusé le document — dans
 * ce cas, `conteneur` n'est pas touché.
 */
function rendre(schema, document, conteneur) {
    const erreurs = validerSchema(schema);
    if (erreurs.length > 0) {
        return { ok: false, erreurs: erreurs };
    }

    // Décision de conception (section 7 du contrat, « name des groupes de
    // radios ») : le moteur vérifie à la construction qu'aucun `name`
    // synthétisé pour un groupe de radios ne collisionne avec le `name`
    // d'une ligne de tableau — sans quoi deux groupes de boutons radio sans
    // rapport partageraient l'exclusivité du navigateur.
    const collisions = nomsEnCollision(schema);
    if (collisions.length > 0) {
        return {
            ok: false,
            erreurs: collisions.map(function (nom) {
                return "sécurité du moteur : le nom synthétisé « " + nom + " » collisionne avec une ligne de tableau.";
            })
        };
    }

    // Filet de sécurité (constat n°5) : validerSchema() et
    // verifierCompatibiliteBloc() couvrent tout ce qui est connu
    // aujourd'hui, mais la construction ne doit jamais faire remonter une
    // exception au navigateur — cette garantie porte sur l'ensemble de ce
    // fichier, pas seulement sur les deux cas déjà découverts par l'audit.
    // Rien n'est inséré dans `conteneur` tant que la construction n'est pas
    // allée jusqu'au bout sans lever.
    try {
        const fragment = document.createDocumentFragment();
        schema.blocs.forEach(function (bloc) {
            rendreBloc(document, fragment, bloc);
        });
        conteneur.appendChild(fragment);
    } catch (erreur) {
        return {
            ok: false,
            erreurs: ["sécurité du moteur : construction interrompue (" + erreur.message + "), rien n'a été inséré."]
        };
    }

    return { ok: true, erreurs: [] };
}

function nomsEnCollision(schema) {
    const nomsTableau = new Set();
    const nomsRadio = new Set();
    schema.blocs.forEach(function (bloc) {
        (bloc.champs || []).forEach(function (champ) {
            if (champ.type === "tableau") {
                (champ.lignes || []).forEach(function (ligne) {
                    if (ligne && ligne.cle) nomsTableau.add(ligne.cle);
                });
            }
            if (champ.type === "radio" && Array.isArray(champ.valeurs) && champ.valeurs[0]) {
                nomsRadio.add("groupe-" + champ.valeurs[0].cle);
            }
        });
    });
    return [...nomsRadio].filter(function (nom) { return nomsTableau.has(nom); });
}

function rendreBloc(document, fragment, bloc) {
    // Un bloc dont l'unique champ est de type "tableau" devient lui-même un
    // <table> : la disposition ne s'y applique pas (docs/schema-formulaire.md
    // §2, note des blocs 11 et 12 — « bloc et champ se confondent »).
    if (bloc.champs.length === 1 && bloc.champs[0].type === "tableau") {
        fragment.appendChild(creerTable(document, bloc));
        return;
    }

    const apparenceEncadree = bloc.champs.some(function (c) {
        return c.type === "image-annotable" && c.apparence === "encadree";
    });

    const conteneur = document.createElement(bloc.balise || "div");
    conteneur.setAttribute("id", bloc.cle);
    const classeDisposition = CLASSES_DISPOSITION[bloc.disposition];
    if (classeDisposition) conteneur.classList.add(classeDisposition);
    conteneur.classList.add("bloc");

    if (bloc.titre) conteneur.appendChild(creerTitreBloc(document, bloc));

    if (apparenceEncadree) {
        conteneur.appendChild(creerGroupeEncadre(document, bloc.champs));
    } else if (bloc.disposition === "en-ligne") {
        conteneur.appendChild(creerGroupeEnLigne(document, bloc.champs));
    } else if (bloc.disposition === "atcd") {
        conteneur.appendChild(creerGroupeAtcd(document, bloc.champs));
    } else if (bloc.disposition === "chaussures") {
        bloc.champs.forEach(function (champ) { rendreChampChaussure(document, conteneur, champ); });
    } else if (bloc.disposition === "en-ligne-bas") {
        bloc.champs.forEach(function (champ) { rendreChampEnLigneBas(document, conteneur, champ); });
    } else {
        bloc.champs.forEach(function (champ) { rendreChampEmpile(document, conteneur, champ); });
    }

    fragment.appendChild(conteneur);
}

function creerTitreBloc(document, bloc) {
    const apparence = bloc.titre_apparence || "label";
    let el;
    if (apparence === "h3") {
        el = document.createElement("h3");
        el.classList.add("Title");
        el.textContent = bloc.titre;
    } else if (apparence === "label_bloc") {
        el = document.createElement("label");
        el.classList.add("titre_section_bloc");
        el.textContent = bloc.titre;
    } else {
        el = document.createElement("label");
        el.classList.add("titre_section");
        el.textContent = bloc.titre;
    }
    if (bloc.titre_cle) el.setAttribute("id", bloc.titre_cle);
    return el;
}

/** Les champs "empilee" par défaut : label, contrôle, <br> — sauf case et
 *  radio, qui portent déjà leur propre libellé, et image-annotable, qui n'a
 *  pas de label du tout (bloc 8, apparence "squelette"). */
function rendreChampEmpile(document, parent, champ) {
    if (champ.type === "image-annotable") {
        parent.appendChild(creerImage(document, champ, ["squelette", "dessinable"]));
        return;
    }
    if (champ.type === "case") {
        parent.appendChild(creerCaseEnveloppee(document, champ));
        parent.appendChild(document.createElement("br"));
        return;
    }
    if (champ.type === "radio") {
        parent.appendChild(creerGroupeEnLigne(document, [champ]));
        return;
    }

    const label = document.createElement("label");
    label.classList.add("titre_section");
    label.setAttribute("for", champ.cle);
    label.textContent = (champ.libelle || "");
    parent.appendChild(label);
    // Le HTML de la V1 sépare le label de son contrôle par un retour à la
    // ligne, qui se rend comme une espace : sans elle, le champ remonte de
    // quelques pixels vers la gauche. L'écart est petit mais réel, et il se
    // répète sur chaque champ de chaque page.
    separer(document, parent);
    parent.appendChild(creerControleSaisie(document, champ));
    parent.appendChild(document.createElement("br"));
}

function rendreChampEnLigneBas(document, parent, champ) {
    const label = document.createElement("label");
    label.classList.add("titre_section");
    label.setAttribute("for", champ.cle);
    label.textContent = (champ.libelle || "");
    parent.appendChild(label);
    separer(document, parent);
    parent.appendChild(creerControleSaisie(document, champ));
}

/** Disposition "chaussures" : labels sans classe, aucun <br>.
 *
 * Les éléments sont séparés par une espace, comme ils le sont dans le HTML
 * écrit à la main. Ce n'est pas cosmétique : entre éléments en ligne, l'espace
 * du source est signifiante — c'est elle qui offre au navigateur ses points de
 * coupure. Sans elle, le moteur laissait « Type : » orphelin en fin de première
 * ligne et renvoyait son champ seul à la ligne suivante, là où la V1 garde le
 * libellé et son champ ensemble (constat du 19 octobre 2026,
 * `docs/references-visuelles/CONSTAT-2026-10-19.md`).
 */
function rendreChampChaussure(document, parent, champ) {
    separer(document, parent);
    if (champ.type === "case") {
        // La V1 ouvre la case par un <label> vide (`index-v1.html:317`) : vide
        // ou non, il occupe le flux en ligne et participe à la coupure.
        const enveloppe = document.createElement("label");
        enveloppe.classList.add("checkbox-label-simple");
        parent.appendChild(enveloppe);
        const entree = document.createElement("input");
        entree.setAttribute("type", "checkbox");
        entree.setAttribute("id", champ.cle);
        parent.appendChild(entree);
        parent.appendChild(document.createTextNode(" " + (champ.libelle || "")));
        return;
    }
    const label = document.createElement("label");
    label.setAttribute("for", champ.cle);
    label.textContent = (champ.libelle || "");
    parent.appendChild(label);
    separer(document, parent);
    parent.appendChild(creerControleSaisie(document, champ));
}

/** Insère une espace entre deux éléments en ligne, s'il y a déjà quelque chose. */
function separer(document, parent) {
    if (parent.childNodes && parent.childNodes.length > 0) {
        parent.appendChild(document.createTextNode(" "));
    }
}

/** Contrôle de saisie seul (texte, date ou zone-texte), sans label ni <br>. */
function creerControleSaisie(document, champ) {
    if (champ.type === "zone-texte") {
        const zone = document.createElement("textarea");
        zone.setAttribute("id", champ.cle);
        zone.classList.add("input-auto-grow");
        if (champ.indication) zone.setAttribute("placeholder", champ.indication);
        return zone;
    }
    const entree = document.createElement("input");
    entree.setAttribute("type", champ.type === "date" ? "date" : "text");
    entree.setAttribute("id", champ.cle);
    if (champ.indication) entree.setAttribute("placeholder", champ.indication);
    return entree;
}

/** Case à cocher enveloppée dans son label, forme des blocs "en-ligne"/"empilee". */
function creerCaseEnveloppee(document, champ) {
    if (champ.apparence === "titre_avant") {
        // Forme de la V1 : un label enveloppe, le titre, puis la case.
        const enveloppe = document.createElement("label");
        enveloppe.classList.add("checkbox-group");
        const titre = document.createElement("label");
        titre.classList.add("titre_section");
        titre.setAttribute("for", champ.cle);
        titre.textContent = (champ.libelle || "");
        enveloppe.appendChild(titre);
        const caseACocher = document.createElement("input");
        caseACocher.setAttribute("type", "checkbox");
        caseACocher.classList.add("custom-checkbox");
        caseACocher.setAttribute("id", champ.cle);
        enveloppe.appendChild(caseACocher);
        enveloppe.appendChild(document.createElement("br"));
        return enveloppe;
    }
    const label = document.createElement("label");
    label.classList.add("checkbox-label");
    const entree = document.createElement("input");
    entree.setAttribute("type", "checkbox");
    entree.setAttribute("id", champ.cle);
    label.appendChild(entree);
    const puce = document.createElement("span");
    puce.classList.add("custom-checkbox");
    label.appendChild(puce);
    label.appendChild(document.createTextNode(" " + (champ.libelle || "")));
    return label;
}

/**
 * Le groupe partagé des blocs "en-ligne" : un seul <div>, "checkbox-group"
 * si le bloc contient au moins un champ "case" (même mélangé à du radio,
 * cas du bloc « Podo »), sinon "radio-group".
 */
function creerGroupeEnLigne(document, champs) {
    const contientCase = champs.some(function (c) { return c.type === "case"; });
    const groupe = document.createElement("div");
    groupe.classList.add(contientCase ? "checkbox-group" : "radio-group");

    champs.forEach(function (champ) {
        if (champ.type === "case") {
            groupe.appendChild(creerCaseEnveloppee(document, champ));
            return;
        }
        if (champ.type !== "radio") {
            throw new Error("type de champ non pris en charge dans un groupe en-ligne : " + champ.type);
        }
        const nomGroupe = "groupe-" + champ.valeurs[0].cle;
        champ.valeurs.forEach(function (option) {
            const label = document.createElement("label");
            label.classList.add("radio-label");
            const entree = document.createElement("input");
            entree.setAttribute("type", "radio");
            entree.setAttribute("id", option.cle);
            entree.setAttribute("name", nomGroupe);
            entree.setAttribute("value", option.valeur);
            label.appendChild(entree);
            const puce = document.createElement("span");
            puce.classList.add("custom-radio");
            label.appendChild(puce);
            label.appendChild(document.createTextNode(" " + (option.libelle || "")));
            groupe.appendChild(label);
        });
    });

    return groupe;
}

/** Disposition "atcd" : un <div class="atcd-row"> par champ, label + textarea. */
function creerGroupeAtcd(document, champs) {
    const conteneur = document.createElement("div");
    conteneur.classList.add("atcd-inputs-container");
    champs.forEach(function (champ) {
        const ligne = document.createElement("div");
        ligne.classList.add("atcd-row");
        const label = document.createElement("label");
        label.classList.add("atcd-sublabel");
        label.setAttribute("for", champ.cle);
        label.textContent = (champ.libelle || "");
        ligne.appendChild(label);
        ligne.appendChild(creerControleSaisie(document, champ));
        conteneur.appendChild(ligne);
    });
    return conteneur;
}

/**
 * Bloc encadré (D9, apparence "encadree") : l'image rejoint une
 * "empreintes-box" et les champs suivants du même bloc n'ont pas de label
 * propre — leur libellé est déjà porté par le titre du bloc.
 */
function creerGroupeEncadre(document, champs) {
    const conteneur = document.createElement("div");
    conteneur.classList.add("appareillage-container");
    champs.forEach(function (champ) {
        if (champ.type === "image-annotable") {
            const boite = document.createElement("div");
            boite.classList.add("empreintes-box");
            boite.appendChild(creerImage(document, champ, ["dessinable"]));
            conteneur.appendChild(boite);
        } else {
            conteneur.appendChild(creerControleSaisie(document, champ));
        }
    });
    return conteneur;
}

function creerImage(document, champ, classes) {
    const img = document.createElement("img");
    img.setAttribute("src", champ.fichier);
    img.setAttribute("alt", champ.texte_alternatif);
    img.setAttribute("id", champ.cle);
    classes.forEach(function (c) { img.classList.add(c); });
    return img;
}

/** Bloc dont l'unique champ est "tableau" : le bloc devient le <table> lui-même. */
function creerTable(document, bloc) {
    const champ = bloc.champs[0];
    const table = document.createElement("table");
    table.setAttribute("id", bloc.cle);
    table.classList.add("bloc");

    const thead = document.createElement("thead");
    const trEntete = document.createElement("tr");
    const thTitre = document.createElement("th");
    thTitre.classList.add("titre_section");
    thTitre.textContent = (champ.libelle || "");
    trEntete.appendChild(thTitre);
    champ.entetes.forEach(function (texte) {
        const th = document.createElement("th");
        th.textContent = texte;
        trEntete.appendChild(th);
    });
    thead.appendChild(trEntete);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    champ.lignes.forEach(function (ligne) {
        const tr = document.createElement("tr");
        const tdNom = document.createElement("td");
        tdNom.textContent = ligne.nom;
        tr.appendChild(tdNom);
        ligne.colonnes.forEach(function (colonne) {
            const td = document.createElement("td");
            const entree = document.createElement("input");
            entree.setAttribute("type", "radio");
            entree.setAttribute("name", ligne.cle);
            entree.setAttribute("value", colonne.valeur);
            td.appendChild(entree);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    return table;
}

/* ===================== Point d'entrée dans le navigateur ===================== */

/**
 * Le texte du dernier filet, partagé entre `afficherErreurMoteur()` et son
 * repli indépendant de `formulaire/script.js` : une seule chaîne à tenir à
 * jour, jamais deux qui pourraient diverger.
 */
const MESSAGE_REPLI =
    "Le formulaire n'a pas pu être chargé. Utilisez le favori "
  + "« Formulaire — secours V1 » (adresse : index-v1.html) "
  + "pour continuer la consultation.";

/**
 * Récupère `schema.json`, valide, rend dans `<main>` — jamais directement
 * dans `#form-bilan` (constat n°1, audit C1-T3 : en V1 les 28 blocs vivent
 * DANS `<main>`, pas après lui) —, puis cède la main à
 * `demarrerApplication()` (définie par `formulaire/script.js`, chargé avant
 * ce fichier) : c'est le point de couture du contrat — sans cet appel,
 * `zonesDessin` resterait vide et plus aucun dessin ni brouillon restauré ne
 * fonctionnerait (`script.js:619-626`).
 *
 * Constat élevé (audit C1-T3b) : la coquille charge DEUX scripts, chacun
 * retéléchargé à chaque ouverture (`Cache-Control: no-store`,
 * `serveur.py:400`). Si `formulaire/script.js` manque ou arrive tronqué
 * alors que `rendu.js` et `schema.json` arrivent intacts, `rendre()`
 * réussit mais `demarrerApplication` n'existe pas : retirer
 * `#attente-moteur` dans ce cas donnerait un formulaire d'apparence
 * normale où rien n'écrit de brouillon, où le stylet ne marque pas et où
 * `#btn-export` n'est câblé par personne — silencieusement. Le message de
 * repli ne doit donc disparaître QUE si `demarrerApplication` a réellement
 * pu être appelée ; dans le cas contraire, c'est un chemin d'échec comme un
 * autre, et il doit en avoir l'air.
 */
function demarrerMoteur() {
    const formulaire = document.getElementById("form-bilan");
    const zoneRendu = formulaire && typeof formulaire.querySelector === "function"
        ? formulaire.querySelector("main")
        : null;

    if (!zoneRendu) {
        // #form-bilan ou <main> introuvable : le silence n'est jamais une
        // réponse acceptable (constat n°9, audit C1-T3).
        afficherErreurMoteur();
        return;
    }

    fetch("schema.json", { credentials: "same-origin" })
        .then(function (reponse) {
            if (reponse.status === 401) {
                throw new Error("authentification refusée");
            }
            if (!reponse.ok) {
                throw new Error("réponse " + reponse.status);
            }
            return reponse.json();
        })
        .then(function (schema) {
            const resultat = rendre(schema, document, zoneRendu);
            if (!resultat.ok) {
                console.error("Schéma refusé :", resultat.erreurs);
                afficherErreurMoteur();
                return;
            }
            if (typeof demarrerApplication !== "function") {
                // formulaire/script.js n'a pas chargé (ou a chargé
                // tronqué) : NE PAS retirer #attente-moteur, sans quoi le
                // formulaire semblerait fonctionnel sans l'être (constat
                // élevé, audit C1-T3b). C'est un échec comme un autre.
                afficherErreurMoteur();
                return;
            }
            // Le rendu a réussi ET l'application a réellement démarré : le
            // message d'attente statique de la coquille (formulaire/index.html,
            // #attente-moteur) n'a plus lieu d'être.
            const attente = document.getElementById("attente-moteur");
            if (attente && typeof attente.remove === "function") attente.remove();
            demarrerApplication();
        })
        .catch(function (erreur) {
            console.error("Chargement du formulaire impossible :", erreur);
            afficherErreurMoteur();
        });
}

/**
 * Message persistant, qui dirige vers la fiche de secours (contrat,
 * section 11). Appelée depuis tous les chemins d'échec de
 * `demarrerMoteur()`, y compris quand `#form-bilan`/`<main>` sont
 * introuvables (constat n°9, audit C1-T3), ou quand `demarrerApplication`
 * n'existe pas (constat élevé, audit C1-T3b) : le silence n'est jamais une
 * réponse acceptable.
 *
 * Deux chemins, l'un n'excluant pas l'autre :
 *  1. `annoncer()` (définie par `formulaire/script.js`), quand ce fichier a
 *     chargé — un bandeau en plus du message statique.
 *  2. Un repli qui ne dépend d'AUCUN fichier JavaScript autre que
 *     celui-ci : `#attente-moteur` existe déjà dans le HTML statique de la
 *     coquille sans aucun script, et ce chemin se contente d'y écrire le
 *     même texte et de le rendre visible — précisément le cas où
 *     `formulaire/script.js` est le fichier manquant, donc où `annoncer()`
 *     elle-même est indisponible.
 */
function afficherErreurMoteur() {
    if (typeof annoncer === "function") {
        annoncer(MESSAGE_REPLI, "erreur", true);
    }
    const attente = document.getElementById("attente-moteur");
    if (attente) {
        if (typeof attente.textContent !== "undefined") attente.textContent = MESSAGE_REPLI;
        attente.hidden = false;
    }
    // Troisième canal, et le seul qui vive HORS de #form-bilan : #zone-messages
    // (formulaire/index.html:67). Les deux canaux précédents tombent ensemble
    // quand `script.js` manque ET que #form-bilan ou <main> est introuvable,
    // puisque #attente-moteur habite précisément le nœud surveillé — chemin
    // n°9 du réaudit C1-T3b. Un filet ne doit pas dépendre de ce qu'il
    // surveille. On n'écrit ici que faute d'`annoncer` : quand il existe, il a
    // déjà posé le message dans cette même zone, et le réécrire le dupliquerait.
    if (typeof annoncer !== "function") {
        const zone = document.getElementById("zone-messages");
        if (zone) {
            if (typeof zone.textContent !== "undefined") zone.textContent = MESSAGE_REPLI;
            zone.hidden = false;
        }
    }
}

if (typeof document !== "undefined" && typeof document.addEventListener === "function") {
    document.addEventListener("DOMContentLoaded", demarrerMoteur);
}
