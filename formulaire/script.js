document.addEventListener('input', function (event) {
    if (event.target.classList.contains('input-auto-grow')) {
        event.target.style.height = 'auto';
        event.target.style.height = event.target.scrollHeight + 'px';
    }
});

// Format A4 portrait, en millimètres.
const PDF_LARGEUR = 210;
const PDF_HAUTEUR = 297;
const MARGE_MM = 12;                // Marge sur les 4 bords, en millimètres réels
const TAILLE_NUMERO = 9;            // Corps du numéro de page, en points
const DELAI_DEPOT = 20000;          // ms : au-delà, on renonce au dépôt

/**
 * Convertit une couleur CSS en triplet RVB pour jsPDF.
 * getPropertyValue() rend la chaîne telle qu'elle est écrite dans la feuille
 * de style, espaces de tête compris, et non une couleur résolue : la
 * conversion est à notre charge.
 * Accepte « #RGB », « #RRGGBB », « rgb(r, g, b) » et « rgba(r, g, b, a) ».
 * Renvoie null si la valeur est vide, non reconnue, porte une composante hors
 * 0-255, ou un alpha nul (un fond totalement transparent est inutilisable :
 * mieux vaut forcer l'appelant vers son propre repli qu'aplatir en noir).
 */
function couleurEnRgb(valeur) {
    const chaine = (valeur || "").trim();

    const court = chaine.match(/^#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])$/);
    if (court) {
        return [parseInt(court[1] + court[1], 16),
                parseInt(court[2] + court[2], 16),
                parseInt(court[3] + court[3], 16)];
    }

    const long = chaine.match(/^#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$/);
    if (long) {
        return [parseInt(long[1], 16), parseInt(long[2], 16), parseInt(long[3], 16)];
    }

    // rgb() et rgba() : la forme que rend le navigateur pour le repli sur
    // document.body. Un alpha nul (transparence totale) est explicitement
    // rejeté plus bas plutôt que traité comme une couleur valide.
    const fonction = chaine.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/i);
    if (fonction) {
        if (fonction[4] !== undefined && parseFloat(fonction[4]) === 0) {
            return null;
        }
        const composantes = [parseInt(fonction[1], 10), parseInt(fonction[2], 10), parseInt(fonction[3], 10)];
        if (composantes.some(function (c) { return c > 255; })) {
            return null;
        }
        return composantes;
    }

    return null;
}

/**
 * Couleurs du document, lues sur les tokens de :root à chaque génération de
 * PDF : modifier un token change l'écran et le PDF sans recharger la page.
 * En cas d'échec de lecture, voir le repli décrit dans le contrat C1-T2.
 */
function couleursDocument() {
    const racine = getComputedStyle(document.documentElement);

    let fondCss = racine.getPropertyValue("--fond").trim();
    let fondRgb = couleurEnRgb(fondCss);
    if (!fondRgb) {
        console.warn("Jeton --fond illisible, repli sur la couleur de fond résolue du document.");
        fondCss = getComputedStyle(document.body).backgroundColor;
        fondRgb = couleurEnRgb(fondCss);
    }
    if (!fondRgb) {
        // Dernier recours, si même le repli précédent est illisible (fond
        // transparent, feuille de style absente…) : le blanc n'est pas une
        // couleur de palette, c'est un neutre déjà littéral ailleurs dans ce
        // CSS (quatorze occurrences de #FFFFFF). Le préférer au noir qu'un
        // canevas transparent aplatirait sinon au moment du JPEG : un bilan
        // illisible est pire qu'un bilan neutre. Ne jamais remplacer cette
        // valeur par une couleur d'identité : ce n'est pas son rôle.
        console.warn("Couleur de fond introuvable, repli sur le blanc neutre.");
        fondCss = "#FFFFFF";
        fondRgb = [255, 255, 255];
    }

    const texteCss = racine.getPropertyValue("--texte").trim();
    const texteRgb = couleurEnRgb(texteCss);
    if (!texteRgb) {
        console.warn("Jeton --texte illisible, numéro de page écrit sans couleur.");
    }

    return { fondCss, fondRgb, texteRgb };
}

function optionsCanvas(fond) {
    return {
        scale: 2,          // Résolution doublée pour éviter le flou du texte
        useCORS: true,     // Autorise le chargement des images du dossier images/
        backgroundColor: fond,
        logging: false,
        onclone: preparerClone
    };
}

// Styles à recopier de la textarea vers son remplaçant, pour un rendu identique
const STYLES_REPRIS = [
    "fontFamily", "fontSize", "fontWeight", "lineHeight", "color",
    "backgroundColor", "border", "borderRadius", "padding",
    "marginTop", "marginRight", "marginBottom", "marginLeft",
    "textAlign", "verticalAlign"
];

/**
 * Prépare le clone servant à la capture : masque les commandes de dessin et
 * remplace les textareas.
 * html2canvas 1.4.1 n'implémente pas la propriété CSS white-space : le contenu
 * d'une textarea est rendu comme un texte continu et les retours à la ligne
 * disparaissent. On remplace donc, dans le clone servant à la capture, chaque
 * textarea par un div où les lignes sont séparées par des <br>.
 * Le clone est un document séparé : le formulaire affiché n'est pas modifié.
 */
function preparerClone(docClone) {
    // Masquer les commandes de dessin sans les retirer : visibility conserve
    // l'espace occupé, donc les positions calculées pour la pagination restent
    // valables (display:none les décalerait)
    docClone.querySelectorAll(".sans-pdf").forEach(function (element) {
        element.style.visibility = "hidden";
    });

    const originaux = document.querySelectorAll("#form-bilan textarea");
    const clones = docClone.querySelectorAll("#form-bilan textarea");

    clones.forEach(function (zone, i) {
        const source = originaux[i];
        if (!source) return;

        const boite = source.getBoundingClientRect();
        const styles = window.getComputedStyle(source);
        const remplacant = docClone.createElement("div");

        STYLES_REPRIS.forEach(function (prop) {
            remplacant.style[prop] = styles[prop];
        });

        // Figer la géométrie : la pagination est calculée sur le document affiché
        remplacant.style.boxSizing = "border-box";
        remplacant.style.width = boite.width + "px";
        remplacant.style.height = boite.height + "px";
        remplacant.style.display = "inline-block";
        remplacant.style.overflow = "hidden";
        remplacant.style.whiteSpace = "normal";

        // Coupure par <br> et non par des div : html2canvas ne rend pas les
        // enfants de type bloc dans un parent inline-block (vérifié en A/B,
        // le texte disparaissait entièrement du PDF).
        // Tolère les fins de ligne Windows (\r\n) des tablettes
        (zone.value || "").split(/\r\n|\r|\n/).forEach(function (texte, i) {
            if (i > 0) remplacant.appendChild(docClone.createElement("br"));
            remplacant.appendChild(docClone.createTextNode(texte));
        });

        zone.parentNode.replaceChild(remplacant, zone);
    });

    return docClone;
}

/**
 * Répartit les blocs sur des pages : on empile les .bloc tant qu'ils tiennent,
 * et on coupe dans l'espace qui précède le premier bloc qui déborde.
 * Retourne les tranches { debut, fin } en pixels du canvas.
 */
function calculerPages(blocs, hauteurPagePx, hauteurTotalePx) {
    const pages = [];
    let debut = 0;
    let i = 0;

    while (i < blocs.length) {
        const limite = debut + hauteurPagePx;

        // Dernier bloc qui tient entièrement dans la page courante
        let dernier = -1;
        for (let k = i; k < blocs.length && blocs[k].bas <= limite; k++) {
            dernier = k;
        }

        if (dernier === -1) {
            // Ce bloc dépasse à lui seul la hauteur d'une page : coupe franche
            console.warn("Bloc trop haut pour une page, coupé :", blocs[i].nom);
            pages.push({ debut: debut, fin: limite });
            debut = limite;
            while (i < blocs.length && blocs[i].bas <= debut) i++;
        } else {
            // Couper juste avant le bloc suivant, en gardant l'espacement
            const suivant = dernier + 1 < blocs.length
                ? Math.min(blocs[dernier + 1].haut, limite)
                : hauteurTotalePx;
            pages.push({ debut: debut, fin: suivant });
            debut = suivant;
            i = dernier + 1;
        }
    }
    return pages;
}

async function exporterBilanPDF() {
    const { jsPDF } = window.jspdf;
    const element = document.getElementById("form-bilan");
    const bouton = document.getElementById("btn-export");

    if (!element) {
        console.error("Élément #form-bilan introuvable.");
        return;
    }

    if (bouton) bouton.style.display = "none";

    try {
        // La lecture des couleurs est dans le try : hors de lui, une
        // défaillance remonterait sans passer par le catch, donc sans
        // message, et la praticienne verrait un bouton qui ne fait rien.
        const couleurs = couleursDocument();

        // Une seule capture : tous les blocs partagent ainsi la même échelle
        const canvas = await html2canvas(element, optionsCanvas(couleurs.fondCss));

        const origine = element.getBoundingClientRect();
        const echelle = canvas.width / origine.width;

        const marge = MARGE_MM;
        const largeurUtile = PDF_LARGEUR - 2 * marge;
        const hauteurUtile = PDF_HAUTEUR - 2 * marge;

        const blocs = Array.from(element.querySelectorAll(".bloc")).map(function (b) {
            const r = b.getBoundingClientRect();
            return {
                nom: b.id || b.className,
                haut: (r.top - origine.top) * echelle,
                bas: (r.bottom - origine.top) * echelle
            };
        });

        if (blocs.length === 0) {
            console.error("Aucun élément .bloc trouvé.");
            return;
        }

        // La largeur du canvas correspond à la largeur utile : l'échelle verticale en découle
        const hauteurPagePx = canvas.width * (hauteurUtile / largeurUtile);
        const pages = calculerPages(blocs, hauteurPagePx, canvas.height);

        // Canvas tampon d'une page pleine, prérempli au fond du document
        const tampon = document.createElement("canvas");
        tampon.width = canvas.width;
        tampon.height = Math.round(hauteurPagePx);
        const ctx = tampon.getContext("2d");

        const pdf = new jsPDF("p", "mm", "a4");

        pages.forEach(function (page, index) {
            const hauteur = page.fin - page.debut;

            ctx.fillStyle = couleurs.fondCss;
            ctx.fillRect(0, 0, tampon.width, tampon.height);
            ctx.drawImage(canvas, 0, page.debut, canvas.width, hauteur,
                                  0, 0, canvas.width, hauteur);

            if (index > 0) pdf.addPage();

            // Fond beige sur toute la page : la marge n'apparaît pas en blanc
            if (couleurs.fondRgb) {
                pdf.setFillColor(couleurs.fondRgb[0], couleurs.fondRgb[1], couleurs.fondRgb[2]);
                pdf.rect(0, 0, PDF_LARGEUR, PDF_HAUTEUR, "F");
            }

            pdf.addImage(tampon.toDataURL("image/jpeg", 0.92), "JPEG",
                         marge, marge, largeurUtile, hauteurUtile);

            // Numéro de page, centré dans la marge du bas
            pdf.setFontSize(TAILLE_NUMERO);
            if (couleurs.texteRgb) {
                pdf.setTextColor(couleurs.texteRgb[0], couleurs.texteRgb[1], couleurs.texteRgb[2]);
            }
            pdf.text((index + 1) + " / " + pages.length,
                     PDF_LARGEUR / 2, PDF_HAUTEUR - marge / 2,
                     { align: "center" });
        });

        console.log("PDF généré :", pages.length, "page(s) pour", blocs.length, "blocs.");

        const nomFichier = construireNomFichier();

        // Deux copies systématiques : une sur le PC, une sur la tablette.
        // Le PDF entre d'abord dans la file, avant toute tentative d'envoi :
        // une coupure entre la génération et le dépôt ne le perdrait pas.
        const enFile = await mettreEnFile(pdf.output("blob"), nomFichier);

        // Le dépôt passe avant la copie locale pour que le déclenchement du
        // téléchargement ne perturbe pas la requête réseau.
        const depot = enFile
            ? await ecoulerFile()
            : await deposerDirectement(pdf, nomFichier);
        const local = await enregistrerSurTablette(pdf, nomFichier);

        const surTablette = local.dossier
            ? "enregistré dans le dossier « " + local.dossier + " »"
            : "téléchargé sur la tablette";

        if (depot.restants) {
            // Le bilan n'est pas perdu : il est en file et repartira seul.
            // Le message le dit, pour ne pas alarmer en fin de consultation.
            const cause = await serveurRepond()
                ? "le PC refuse le dépôt (" + (depot.motif || "cause inconnue") + ")"
                : "le serveur du cabinet ne répond pas";
            annoncer("Bilan " + surTablette + ". Envoi au PC différé : "
                   + cause + ". " + (depot.restants === 1
                        ? "Il partira automatiquement."
                        : depot.restants + " bilans partiront automatiquement."),
                     "avertissement", true);
        } else if (depot.refuses) {
            annoncer("Bilan " + surTablette + ", mais le PC a refusé le fichier ("
                   + depot.motif + "). Le transférer à la main.", "erreur", true);
        } else {
            annoncer("Bilan " + surTablette + " et déposé sur le PC : "
                   + depot.fichier, "succes");
        }

    } catch (erreur) {
        console.error("Erreur lors de la génération du PDF :", erreur);
        annoncer("La création du PDF a échoué. Rien n'a été enregistré, "
               + "votre saisie est intacte.", "erreur");
    } finally {
        if (bouton) bouton.style.display = "block";
    }
}

/** Nom de fichier construit à partir de la date et de l'identité du patient. */
function construireNomFichier() {
    const valeur = function (id) {
        const champ = document.getElementById(id);
        return champ && champ.value ? champ.value.trim() : "";
    };

    const date = valeur("date-bilan") || new Date().toISOString().slice(0, 10);
    const identite = [valeur("nom"), valeur("prenom")].filter(Boolean).join("-");

    return ["Bilan", date, identite || "sans-nom"].join("_") + ".pdf";
}

/**
 * Dépôt sans file, pour le cas où IndexedDB est indisponible (navigation
 * privée, quota saturé). Rend le même compte que ecoulerFile() afin que
 * l'appelant n'ait pas deux formes de résultat à distinguer.
 */
async function deposerDirectement(pdf, nomFichier) {
    const depot = await deposerSurLePC(pdf.output("blob"), nomFichier);
    if (depot.ok) {
        return { envoyes: 1, refuses: 0, restants: 0, motif: null,
                 fichier: depot.fichier };
    }
    // Rien ne conserve ce bilan : l'échec doit rester visible, donc il est
    // compté comme refusé plutôt que comme différé.
    return { envoyes: 0, refuses: 1, restants: 0, motif: depot.motif,
             fichier: null };
}

/**
 * Envoie le PDF au serveur du cabinet. Le nom voyage en base64 dans un en-tête
 * car un en-tête HTTP ne transporte pas fiablement les accents.
 *
 * Retourne `definitif` avec l'échec : vrai quand le serveur a examiné le
 * fichier et le refuse, cas où le réessayer ne servirait à rien.
 */
async function deposerSurLePC(blob, nomFichier) {
    // Sans délai maximal, un PC qui accepte la connexion sans jamais répondre
    // bloquerait la fin de consultation.
    const abandon = new AbortController();
    const minuterie = setTimeout(function () { abandon.abort(); }, DELAI_DEPOT);

    try {
        const reponse = await fetch("/depot", {
            method: "POST",
            headers: {
                "Content-Type": "application/pdf",
                "X-Fichier": btoa(unescape(encodeURIComponent(nomFichier)))
            },
            body: blob,
            signal: abandon.signal
        });

        if (!reponse.ok) {
            const detail = await reponse.json().catch(function () { return {}; });
            // 400 et 413 portent sur le contenu envoyé : il ne deviendra pas
            // acceptable en le renvoyant. 401 (mot de passe) et 5xx (disque
            // plein, droits) se corrigent sur le PC, donc on retente.
            return {
                ok: false,
                definitif: reponse.status === 400 || reponse.status === 413,
                motif: detail.erreur || ("code " + reponse.status)
            };
        }

        const resultat = await reponse.json();
        return { ok: true, fichier: resultat.fichier };

    } catch (erreur) {
        // fetch ne rejette que sur une panne réseau, pas sur un code d'erreur
        if (erreur.name === "AbortError") {
            return { ok: false, definitif: false,
                     motif: "le PC n'a pas répondu à temps" };
        }
        return { ok: false, definitif: false, motif: "serveur injoignable" };
    } finally {
        clearTimeout(minuterie);
    }
}

/* ===================== File d'attente des dépôts ===================== */

/*
 * Un bilan généré est un bilan qui doit arriver sur le PC, même si le serveur
 * est arrêté à cet instant — et il l'est parfois : PC redémarré pendant la
 * nuit, fenêtre du serveur fermée par mégarde. Sans file, l'échec retombait
 * sur le praticien, qui devait repérer le bandeau orange puis transférer le
 * fichier à la main ; un bandeau manqué, et le bilan restait sur la tablette.
 *
 * Chaque PDF est donc d'abord écrit dans IndexedDB, puis envoyé. Il n'est
 * retiré de la file qu'une fois le serveur accusé réception. Tant qu'il y
 * reste, il est réenvoyé : périodiquement, au retour du réseau, au
 * rechargement de la page. Une panne du serveur ne fait plus perdre de
 * bilan : elle le retarde.
 */

const RELANCE_FILE = 60000;   // ms entre deux tentatives d'écoulement

/** Promesse de l'écoulement en cours : deux tentatives simultanées
 *  déposeraient le même bilan deux fois. */
let ecoulementEnCours = null;

function transactionFile(mode, action) {
    return ouvrirBase().then(function (base) {
        return new Promise(function (resoudre, rejeter) {
            const transaction = base.transaction(MAGASIN_FILE, mode);
            const requete = action(transaction.objectStore(MAGASIN_FILE));
            requete.onsuccess = function () { resoudre(requete.result); };
            requete.onerror = function () { rejeter(requete.error); };
        });
    });
}

/** Place le PDF dans la file. Retourne son identifiant, ou null si le
 *  navigateur refuse d'écrire (navigation privée, quota saturé). */
async function mettreEnFile(blob, nomFichier) {
    try {
        return await transactionFile("readwrite", function (magasin) {
            return magasin.add({
                nom: nomFichier,
                blob: blob,
                date: new Date().toISOString()
            });
        });
    } catch (erreur) {
        console.error("Mise en file impossible :", erreur);
        return null;
    }
}

async function listerFile() {
    try {
        return await transactionFile("readonly", function (magasin) {
            return magasin.getAll();
        }) || [];
    } catch (erreur) {
        console.error("Lecture de la file impossible :", erreur);
        return [];
    }
}

function retirerDeLaFile(id) {
    return transactionFile("readwrite", function (magasin) {
        return magasin.delete(id);
    }).catch(function (erreur) {
        console.error("Retrait de la file impossible :", erreur);
    });
}

/**
 * Tente de déposer tout ce qui attend. Ne lève jamais : un échec laisse la
 * file en l'état, pour la tentative suivante.
 */
function ecoulerFile() {
    if (ecoulementEnCours) return ecoulementEnCours;
    ecoulementEnCours = ecoulerVraiment().finally(function () {
        ecoulementEnCours = null;
    });
    return ecoulementEnCours;
}

async function ecoulerVraiment() {
    const entrees = await listerFile();
    let envoyes = 0;
    let refuses = 0;
    let dernier = null;
    let motif = null;

    for (const entree of entrees) {
        const depot = await deposerSurLePC(entree.blob, entree.nom);

        if (depot.ok) {
            await retirerDeLaFile(entree.id);
            envoyes += 1;
            dernier = depot.fichier;
            continue;
        }

        if (depot.definitif) {
            // Le serveur a examiné ce fichier et le refuse : le renvoyer
            // indéfiniment ne ferait qu'encombrer la file.
            console.error("Dépôt refusé définitivement :", entree.nom, depot.motif);
            await retirerDeLaFile(entree.id);
            refuses += 1;
            motif = depot.motif;
            continue;
        }

        // Serveur injoignable : inutile d'essayer les suivants, ils
        // échoueraient de la même façon.
        motif = depot.motif;
        break;
    }

    const restants = (await listerFile()).length;
    majBarreAttente(restants);
    return { envoyes: envoyes, refuses: refuses, restants: restants,
             motif: motif, fichier: dernier };
}

/**
 * Distingue les pannes que le navigateur confond toutes en « erreur de
 * connexion ». La sonde n'est pas authentifiée : elle répond même si le mot
 * de passe est en cause.
 */
async function serveurRepond() {
    try {
        const reponse = await fetch("/sante", { cache: "no-store" });
        return reponse.ok;
    } catch (erreur) {
        return false;
    }
}

function majBarreAttente(restants) {
    const barre = document.getElementById("barre-attente");
    const texte = document.getElementById("texte-attente");
    if (!barre || !texte) return;

    if (!restants) {
        barre.hidden = true;
        return;
    }

    texte.textContent = restants === 1
        ? "1 bilan en attente d'envoi vers le PC. Il partira automatiquement."
        : restants + " bilans en attente d'envoi vers le PC. Ils partiront "
          + "automatiquement.";
    barre.hidden = false;
}

function initFileDepots() {
    const bouton = document.getElementById("btn-reessayer");
    if (bouton) {
        bouton.addEventListener("click", async function () {
            bouton.disabled = true;
            const bilan = await ecoulerFile();
            bouton.disabled = false;

            if (!bilan.restants) {
                annoncer("Tout est déposé sur le PC.", "succes");
            } else if (await serveurRepond()) {
                annoncer("Le PC répond mais refuse le dépôt ("
                       + (bilan.motif || "cause inconnue")
                       + "). Les bilans restent en attente.", "erreur", true);
            } else {
                annoncer("Le serveur du cabinet ne répond toujours pas. "
                       + "Vérifier qu'il est bien démarré sur le PC.",
                         "avertissement", true);
            }
        });
    }

    // Trois occasions de rattraper une panne passée : le rechargement de la
    // page, le retour du réseau, et le simple passage du temps.
    ecoulerFile();
    window.addEventListener("online", function () { ecoulerFile(); });
    setInterval(function () {
        if (!ecoulementEnCours) ecoulerFile();
    }, RELANCE_FILE);
}

/* ===================== Dessin au stylet ===================== */

const DESSIN_COULEUR = "#B03A2E";      // Rouge brique, lisible sur les squelettes
const DESSIN_EPAISSEUR = 2.5;          // Épaisseur du trait par défaut, en pixels CSS

// Réglages courants, modifiables par le praticien. Chaque trait mémorise la
// couleur et l'épaisseur en vigueur au moment où il est tracé : changer de
// réglage n'altère jamais les traits déjà posés.
const outil = { couleur: DESSIN_COULEUR, epaisseur: DESSIN_EPAISSEUR };
const DESSIN_RESOLUTION = 2;           // Facteur de finesse du calque
const TYPES_POINTEUR = ["pen", "mouse"]; // Ajouter "touch" pour dessiner au doigt

const zonesDessin = [];

/**
 * Les traits sont mémorisés en coordonnées normalisées (0 à 1) plutôt qu'en
 * pixels : le dessin se redessine sans déformation si l'image change de
 * taille, et l'annulation se réduit à retirer le dernier trait de la liste.
 */
function initDessin() {
    document.querySelectorAll("img.dessinable").forEach(preparerZoneDessin);
    brancherReglages();

    window.addEventListener("resize", function () {
        zonesDessin.forEach(redessiner);
    });
}

function preparerZoneDessin(image) {
    const zone = document.createElement("div");
    zone.className = "zone-dessin";
    image.parentNode.insertBefore(zone, image);
    zone.appendChild(image);

    const calque = document.createElement("canvas");
    calque.className = "calque-dessin";
    zone.appendChild(calque);

    const etat = { image: image, calque: calque, traits: [], encours: null };

    const annuler = creerBouton("Annuler", function () {
        etat.traits.pop();
        redessiner(etat);
    });
    const effacer = creerBouton("Effacer", function () {
        etat.traits = [];
        redessiner(etat);
    });

    const outils = document.createElement("div");
    outils.className = "outils-dessin sans-pdf";
    outils.appendChild(annuler);
    outils.appendChild(effacer);
    zone.appendChild(outils);

    etat.boutons = [annuler, effacer];
    brancherPointeur(etat);
    zonesDessin.push(etat);

    if (image.complete) {
        redessiner(etat);
    } else {
        image.addEventListener("load", function () { redessiner(etat); });
    }
}

function creerBouton(libelle, action) {
    const bouton = document.createElement("button");
    bouton.type = "button";
    bouton.textContent = libelle;
    bouton.addEventListener("click", action);
    return bouton;
}

function brancherPointeur(etat) {
    const calque = etat.calque;

    calque.addEventListener("pointerdown", function (event) {
        if (TYPES_POINTEUR.indexOf(event.pointerType) === -1) return;
        event.preventDefault();
        calque.setPointerCapture(event.pointerId);

        etat.encours = {
            points: [positionRelative(calque, event)],
            couleur: outil.couleur,
            epaisseur: outil.epaisseur
        };
        etat.traits.push(etat.encours);
        majBoutons(etat);
    });

    calque.addEventListener("pointermove", function (event) {
        if (!etat.encours) return;
        event.preventDefault();

        const points = etat.encours.points;
        const precedent = points[points.length - 1];
        const actuel = positionRelative(calque, event);
        points.push(actuel);

        // Tracer seulement le nouveau segment : redessiner tout à chaque
        // déplacement rendrait le tracé saccadé sur tablette
        tracerSegment(calque, precedent, actuel, etat.encours);
    });

    ["pointerup", "pointercancel", "pointerleave"].forEach(function (nom) {
        calque.addEventListener(nom, function () {
            if (!etat.encours) return;
            // Un simple appui sans déplacement : marquer un point
            if (etat.encours.points.length === 1) redessiner(etat);
            etat.encours = null;
            sauvegarderBientot();   // le dessin n'émet pas d'événement "input"
        });
    });
}

function positionRelative(calque, event) {
    const boite = calque.getBoundingClientRect();
    return {
        x: (event.clientX - boite.left) / boite.width,
        y: (event.clientY - boite.top) / boite.height
    };
}

function contexteDessin(calque, couleur, epaisseur) {
    const ctx = calque.getContext("2d");
    ctx.strokeStyle = couleur;
    ctx.fillStyle = couleur;
    ctx.lineWidth = epaisseur * DESSIN_RESOLUTION;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    return ctx;
}

function tracerSegment(calque, depuis, vers, trait) {
    const ctx = contexteDessin(calque, trait.couleur, trait.epaisseur);
    ctx.beginPath();
    ctx.moveTo(depuis.x * calque.width, depuis.y * calque.height);
    ctx.lineTo(vers.x * calque.width, vers.y * calque.height);
    ctx.stroke();
}

function redessiner(etat) {
    const calque = etat.calque;
    const boite = etat.image.getBoundingClientRect();
    if (boite.width === 0) return;

    // Redimensionner remet le calque à zéro : on retrace tout ensuite
    calque.style.width = boite.width + "px";
    calque.style.height = boite.height + "px";
    calque.width = Math.round(boite.width * DESSIN_RESOLUTION);
    calque.height = Math.round(boite.height * DESSIN_RESOLUTION);

    etat.traits.forEach(function (trait) {
        const ctx = contexteDessin(calque, trait.couleur, trait.epaisseur);
        const points = trait.points;
        if (points.length === 1) {
            ctx.beginPath();
            ctx.arc(points[0].x * calque.width, points[0].y * calque.height,
                    ctx.lineWidth / 2, 0, 2 * Math.PI);
            ctx.fill();
            return;
        }
        ctx.beginPath();
        points.forEach(function (point, i) {
            const x = point.x * calque.width;
            const y = point.y * calque.height;
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        });
        ctx.stroke();
    });

    majBoutons(etat);
}

function majBoutons(etat) {
    const vide = etat.traits.length === 0;
    etat.boutons.forEach(function (bouton) { bouton.disabled = vide; });
}

let applicationDemarree = false;

/**
 * Démarre le stylet, le brouillon, le dossier choisi et la file de dépôts.
 * Idempotente : un second appel ne fait rien, pour que le moteur de rendu
 * (formulaire/moteur/rendu.js) puisse l'appeler après son propre rendu sans
 * se soucier de ce qu'a déjà fait ce fichier.
 */
function demarrerApplication() {
    if (applicationDemarree) return;
    applicationDemarree = true;

    // Câblage du bouton d'export sans onclick= en ligne, mais seulement sur
    // la page provisoire du moteur (constat n°10, audit C1-T3 : onclick= est
    // incompatible avec la CSP à venir, C6-T1). Conditionné à data-moteur :
    // formulaire/index.html porte toujours son onclick= (index.html:26,
    // hors périmètre de cette tâche), et ajouter ce même écouteur là aussi
    // déclencherait exporterBilanPDF() deux fois par clic.
    const formulaire = document.getElementById("form-bilan");
    if (formulaire && formulaire.dataset && formulaire.dataset.moteur !== undefined) {
        const bouton = document.getElementById("btn-export");
        if (bouton) bouton.addEventListener("click", exporterBilanPDF);
    }

    initDessin();        // doit précéder : remplit zonesDessin
    initSauvegarde();    // s'appuie sur zonesDessin pour restaurer les traits
    initDossierBilans();
    initFileDepots();    // rattrape les bilans qu'une panne a laissés en attente
}

document.addEventListener("DOMContentLoaded", function () {
    // Point de couture avec le moteur de rendu (contrat C1-T3) : quand
    // #form-bilan porte l'attribut data-moteur, le formulaire n'est pas
    // encore dans le DOM à cet instant — rendu.js l'y insère plus tard et
    // appelle lui-même demarrerApplication() une fois son rendu terminé.
    // Démarrer ici rendrait zonesDessin vide (script.js:619-626) : plus
    // aucun dessin, et les traits d'un brouillon restauré tomberaient dans
    // le vide. La garde tolère l'absence de `dataset` (tests/test_file_depots.js
    // fournit un double d'élément qui n'en a pas).
    const formulaire = document.getElementById("form-bilan");
    if (formulaire && formulaire.dataset && formulaire.dataset.moteur !== undefined) {
        return;
    }
    demarrerApplication();
});

/**
 * Câble la barre de réglages : pastilles de couleur, sélecteur libre et
 * curseur d'épaisseur. Les traits déjà tracés ne sont pas affectés.
 */
function brancherReglages() {
    const pastilles = document.querySelectorAll(".pastille");
    const couleurLibre = document.getElementById("couleur-libre");
    const epaisseur = document.getElementById("epaisseur-trait");

    pastilles.forEach(function (pastille) {
        const couleur = pastille.dataset.couleur;
        pastille.style.backgroundColor = couleur;

        pastille.addEventListener("click", function () {
            outil.couleur = couleur;
            if (couleurLibre) couleurLibre.value = couleur;
            marquerPastilleActive(pastilles, couleur);
            dessinerApercu();
        });
    });

    if (couleurLibre) {
        couleurLibre.addEventListener("input", function () {
            outil.couleur = couleurLibre.value;
            marquerPastilleActive(pastilles, outil.couleur);
            dessinerApercu();
        });
    }

    if (epaisseur) {
        epaisseur.value = outil.epaisseur;
        epaisseur.addEventListener("input", function () {
            outil.epaisseur = parseFloat(epaisseur.value);
            dessinerApercu();
        });
    }

    marquerPastilleActive(pastilles, outil.couleur);
    dessinerApercu();
}

function marquerPastilleActive(pastilles, couleur) {
    pastilles.forEach(function (pastille) {
        const correspond = pastille.dataset.couleur.toLowerCase() === couleur.toLowerCase();
        pastille.classList.toggle("active", correspond);
    });
}

/** Trait témoin reflétant la couleur et l'épaisseur courantes. */
function dessinerApercu() {
    const apercu = document.getElementById("apercu-trait");
    if (!apercu) return;

    const ctx = apercu.getContext("2d");
    ctx.clearRect(0, 0, apercu.width, apercu.height);
    ctx.strokeStyle = outil.couleur;
    ctx.lineWidth = outil.epaisseur;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(8, apercu.height / 2);
    ctx.lineTo(apercu.width - 8, apercu.height / 2);
    ctx.stroke();
}

/* ===================== Sauvegarde automatique ===================== */

const CLE_BROUILLON = "bilan-posturo-brouillon";
const DELAI_SAUVEGARDE = 1200;   // ms d'inactivité avant écriture
const PERIODE_FILET = 15000;     // ms : sauvegarde périodique de sécurité

let minuterieSauvegarde = null;

/**
 * Identifiant stable d'un champ. Les boutons radio des tableaux n'ont pas
 * d'attribut id : on les distingue par leur couple name/value.
 */
function cleChamp(champ) {
    if (champ.id) return champ.id;
    if (champ.name) return champ.name + "#" + champ.value;
    return null;
}

function champsDuFormulaire() {
    return document.querySelectorAll(
        "#form-bilan input, #form-bilan textarea, #form-bilan select");
}

/** Photographie l'état complet du bilan : champs saisis et traits dessinés. */
function collecterBilan() {
    const valeurs = {};
    const coches = {};

    champsDuFormulaire().forEach(function (champ) {
        const cle = cleChamp(champ);
        if (!cle) return;

        if (champ.type === "checkbox" || champ.type === "radio") {
            coches[cle] = champ.checked;
        } else {
            valeurs[cle] = champ.value;
        }
    });

    return {
        version: 1,
        date: new Date().toISOString(),
        valeurs: valeurs,
        coches: coches,
        dessins: zonesDessin.map(function (zone) { return zone.traits; })
    };
}

/** Vrai si l'utilisateur a réellement saisi quelque chose. */
function bilanNonVide(bilan) {
    const texteSaisi = Object.keys(bilan.valeurs)
        .some(function (cle) { return bilan.valeurs[cle].trim() !== ""; });
    const caseCochee = Object.keys(bilan.coches)
        .some(function (cle) { return bilan.coches[cle]; });
    const traitTrace = bilan.dessins
        .some(function (traits) { return traits.length > 0; });

    return texteSaisi || caseCochee || traitTrace;
}

function sauvegarder() {
    try {
        const bilan = collecterBilan();
        if (!bilanNonVide(bilan)) {
            localStorage.removeItem(CLE_BROUILLON);
            return;
        }
        localStorage.setItem(CLE_BROUILLON, JSON.stringify(bilan));
    } catch (erreur) {
        // Quota dépassé ou stockage désactivé : on prévient une seule fois
        console.error("Sauvegarde impossible :", erreur);
        annoncer("La sauvegarde automatique ne fonctionne pas sur cet appareil. "
               + "Exportez régulièrement.", "erreur", true);
    }
}

/** Regroupe les frappes rapprochées en une seule écriture. */
function sauvegarderBientot() {
    clearTimeout(minuterieSauvegarde);
    minuterieSauvegarde = setTimeout(sauvegarder, DELAI_SAUVEGARDE);
}

function restaurerBilan(bilan) {
    champsDuFormulaire().forEach(function (champ) {
        const cle = cleChamp(champ);
        if (!cle) return;

        if (champ.type === "checkbox" || champ.type === "radio") {
            if (cle in bilan.coches) champ.checked = bilan.coches[cle];
        } else if (cle in bilan.valeurs) {
            champ.value = bilan.valeurs[cle];
            // Rejouer l'agrandissement automatique des zones de texte
            if (champ.classList.contains("input-auto-grow")) {
                champ.style.height = "auto";
                champ.style.height = champ.scrollHeight + "px";
            }
        }
    });

    (bilan.dessins || []).forEach(function (traits, i) {
        if (zonesDessin[i]) {
            zonesDessin[i].traits = traits;
            redessiner(zonesDessin[i]);
        }
    });
}

function effacerBilan() {
    champsDuFormulaire().forEach(function (champ) {
        if (champ.type === "checkbox" || champ.type === "radio") {
            champ.checked = false;
        } else {
            champ.value = "";
            if (champ.classList.contains("input-auto-grow")) {
                champ.style.height = "auto";
            }
        }
    });

    zonesDessin.forEach(function (zone) {
        zone.traits = [];
        redessiner(zone);
    });

    localStorage.removeItem(CLE_BROUILLON);
}

/**
 * Le brouillon n'est jamais restauré automatiquement : un bilan appartient à
 * un patient, et rouvrir la page pour le patient suivant ne doit surtout pas
 * réafficher le dossier précédent. On propose, l'utilisateur tranche.
 */
function proposerBrouillon() {
    let bilan;
    try {
        const brut = localStorage.getItem(CLE_BROUILLON);
        if (!brut) return;
        bilan = JSON.parse(brut);
    } catch (erreur) {
        localStorage.removeItem(CLE_BROUILLON);
        return;
    }

    const barre = document.getElementById("barre-brouillon");
    const texte = document.getElementById("texte-brouillon");
    if (!barre || !texte) return;

    const date = new Date(bilan.date);
    texte.textContent = "Un bilan non terminé du "
        + date.toLocaleDateString("fr-FR")
        + " à " + date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
        + " a été retrouvé.";

    barre.hidden = false;

    document.getElementById("btn-restaurer").addEventListener("click", function () {
        restaurerBilan(bilan);
        barre.hidden = true;
        annoncer("Bilan restauré.", "succes");
    });

    document.getElementById("btn-abandonner").addEventListener("click", function () {
        localStorage.removeItem(CLE_BROUILLON);
        barre.hidden = true;
    });
}

function initSauvegarde() {
    proposerBrouillon();

    // Un seul écouteur pour tout le formulaire (délégation) : fonctionne aussi
    // pour les champs ajoutés plus tard
    const formulaire = document.getElementById("form-bilan");
    if (formulaire) {
        formulaire.addEventListener("input", sauvegarderBientot);
        formulaire.addEventListener("change", sauvegarderBientot);
    }

    // Filet de sécurité : même sans frappe, l'état est réécrit régulièrement
    setInterval(sauvegarder, PERIODE_FILET);

    const nouveau = document.getElementById("btn-nouveau");
    if (nouveau) {
        nouveau.addEventListener("click", function () {
            if (confirm("Effacer le bilan en cours et repartir d'une fiche vierge ?")) {
                effacerBilan();
                annoncer("Nouvelle fiche vierge.", "succes");
            }
        });
    }
}

/* ===================== Messages à l'utilisateur ===================== */

/**
 * Remplace les alert() : un bandeau intégré à la page, qui ne bloque pas
 * l'interface et n'oblige pas à cliquer pour continuer.
 */
function annoncer(message, type, persistant) {
    const zone = document.getElementById("zone-messages");
    if (!zone) {
        console.log(message);
        return;
    }

    zone.textContent = message;
    zone.className = "message " + (type || "info");
    zone.hidden = false;

    if (!persistant) {
        clearTimeout(annoncer.minuterie);
        annoncer.minuterie = setTimeout(function () { zone.hidden = true; }, 6000);
    }
}

/* ============ Enregistrement dans un dossier de la tablette ============ */

/*
 * Une page web ne choisit pas librement où écrire sur l'appareil : le
 * navigateur impose son dossier de téléchargement. La seule exception est
 * l'API File System Access, qui permet à l'utilisateur de désigner un dossier
 * une fois pour toutes ; la page peut ensuite y écrire directement.
 *
 * Deux conditions : un navigateur Chromium (Chrome, Edge) — Safari sur iPad
 * ne l'implémente pas — et une page servie en HTTPS. Quand l'une manque, on
 * retombe sur le téléchargement classique, et c'est le dossier configuré dans
 * les réglages du navigateur qui décide.
 */

const BASE_REGLAGES = "bilan-posturo";
const MAGASIN_REGLAGES = "reglages";
const MAGASIN_FILE = "file-depots";
const CLE_DOSSIER = "dossier-bilans";
const VERSION_BASE = 2;

function dossierDisponible() {
    return typeof window.showDirectoryPicker === "function" && window.isSecureContext;
}

/**
 * Un handle de dossier ne tient pas dans localStorage : il faut IndexedDB.
 * La même base héberge la file d'attente des dépôts, qui a besoin de stocker
 * des Blob — hors de portée de localStorage également.
 */
function ouvrirBase() {
    return new Promise(function (resoudre, rejeter) {
        const requete = indexedDB.open(BASE_REGLAGES, VERSION_BASE);
        requete.onupgradeneeded = function () {
            // Les tablettes déjà en service portent une base en version 1 :
            // chaque magasin est créé seulement s'il manque.
            const base = requete.result;
            if (!base.objectStoreNames.contains(MAGASIN_REGLAGES)) {
                base.createObjectStore(MAGASIN_REGLAGES);
            }
            if (!base.objectStoreNames.contains(MAGASIN_FILE)) {
                base.createObjectStore(MAGASIN_FILE,
                                       { keyPath: "id", autoIncrement: true });
            }
        };
        requete.onsuccess = function () { resoudre(requete.result); };
        requete.onerror = function () { rejeter(requete.error); };
    });
}

function lireReglage(cle) {
    return ouvrirBase().then(function (base) {
        return new Promise(function (resoudre, rejeter) {
            const requete = base.transaction(MAGASIN_REGLAGES, "readonly")
                                .objectStore(MAGASIN_REGLAGES).get(cle);
            requete.onsuccess = function () { resoudre(requete.result || null); };
            requete.onerror = function () { rejeter(requete.error); };
        });
    });
}

function ecrireReglage(cle, valeur) {
    return ouvrirBase().then(function (base) {
        return new Promise(function (resoudre, rejeter) {
            const requete = base.transaction(MAGASIN_REGLAGES, "readwrite")
                                .objectStore(MAGASIN_REGLAGES).put(valeur, cle);
            requete.onsuccess = function () { resoudre(); };
            requete.onerror = function () { rejeter(requete.error); };
        });
    });
}

/**
 * Demande à l'utilisateur de désigner le dossier. Doit être appelé depuis un
 * clic : le navigateur refuse d'ouvrir le sélecteur sans geste explicite.
 */
async function choisirDossierBilans() {
    if (!dossierDisponible()) {
        annoncer("Ce navigateur ne permet pas de choisir le dossier. "
               + "Réglez le dossier de téléchargement dans ses paramètres.",
                 "avertissement", true);
        return;
    }

    try {
        const dossier = await window.showDirectoryPicker({ mode: "readwrite" });
        await ecrireReglage(CLE_DOSSIER, dossier);
        majEtiquetteDossier(dossier.name);
        annoncer("Les bilans seront enregistrés dans le dossier « "
               + dossier.name + " ».", "succes");
    } catch (erreur) {
        if (erreur.name !== "AbortError") {   // AbortError = simple annulation
            console.error("Choix du dossier impossible :", erreur);
            annoncer("Le dossier n'a pas pu être enregistré.", "erreur");
        }
    }
}

/** Handle mémorisé, s'il est toujours utilisable sans redemander l'accord. */
async function dossierMemorise() {
    if (!dossierDisponible()) return null;

    try {
        const dossier = await lireReglage(CLE_DOSSIER);
        if (!dossier) return null;

        // L'autorisation peut avoir été révoquée depuis le dernier usage
        const etat = await dossier.queryPermission({ mode: "readwrite" });
        return etat === "granted" ? dossier : null;
    } catch (erreur) {
        return null;
    }
}

/**
 * Écrit le PDF sur la tablette : dans le dossier choisi si possible, sinon
 * par un téléchargement classique.
 */
async function enregistrerSurTablette(pdf, nomFichier) {
    const dossier = await dossierMemorise();

    if (dossier) {
        try {
            const fichier = await dossier.getFileHandle(nomFichier, { create: true });
            const flux = await fichier.createWritable();
            await flux.write(pdf.output("blob"));
            await flux.close();
            return { ok: true, dossier: dossier.name };
        } catch (erreur) {
            // Dossier supprimé, déplacé, ou support plein : on ne perd pas
            // le bilan pour autant
            console.error("Écriture dans le dossier impossible :", erreur);
        }
    }

    pdf.save(nomFichier);
    return { ok: true, dossier: null };
}

function majEtiquetteDossier(nom) {
    const bouton = document.getElementById("btn-dossier");
    if (!bouton) return;
    bouton.textContent = nom ? "Dossier : " + nom : "Choisir le dossier…";
}

async function initDossierBilans() {
    const bouton = document.getElementById("btn-dossier");
    if (!bouton) return;

    if (!dossierDisponible()) {
        bouton.hidden = true;   // inutile d'afficher une option indisponible
        return;
    }

    bouton.addEventListener("click", choisirDossierBilans);

    const dossier = await dossierMemorise();
    majEtiquetteDossier(dossier ? dossier.name : null);
}
