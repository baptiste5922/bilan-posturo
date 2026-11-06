#!/bin/sh
# Construit l'archive à installer sur le PC du cabinet.
# N'inclut QUE ce qui est nécessaire : ni secrets, ni données patient,
# ni node_modules.
#
#     sh outils/faire-paquet.sh <client>        (par exemple : cabinet-01)
#
# Le client est un argument OBLIGATOIRE, sans valeur par défaut : le schéma du
# formulaire qui part dans l'archive est celui de clients/<client>/schema.json
# (C1-T4a). Un défaut livrerait par mégarde le formulaire du cabinet pilote à
# un autre cabinet. Le nom de l'archive, lui, ne change pas.
#
# `set -e` : sans lui, une copie qui échoue laissait le script continuer,
# zipper, puis annoncer « Archive créée ». Le paquet partait au cabinet
# amputé — du texte de licence, par exemple, que BUSL exige sur chaque
# copie. Un défaut qui s'annonce comme un succès est le pire des deux.
set -e
#
# Les scripts livrés à la racine du paquet (installer-demarrage.ps1,
# demarrer-serveur.bat) prennent pour racine LEUR PROPRE DOSSIER, à côté de
# serveur/ et formulaire/. Ce n'est pas une supposition :
# tests/test_scripts_installation.py fabrique le paquet par ce script, l'extrait,
# et évalue le calcul de racine de chaque script à l'endroit où l'archive le
# dépose. Déplacer un script dans le paquet fait rougir ce test.

# Se placer à la racine du projet, quel que soit le dossier d'appel.
cd "$(dirname "$0")/.." || exit 1

# Tout contrôle de l'argument a lieu AVANT la première copie : un refus ne
# laisse ni dossier ni archive. Le motif ancré interdit `/` et `..` : le client
# entre dans un chemin (clients/$CLIENT/schema.json).
clients_disponibles() {
    for schema in clients/*/schema.json; do
        [ -f "$schema" ] || continue
        nom=${schema#clients/}
        echo "  ${nom%/schema.json}"
    done
}

if [ "$#" -ne 1 ]; then
    echo "ERREUR : un seul argument attendu, le client (par exemple : sh outils/faire-paquet.sh cabinet-01)." >&2
    echo "Clients disponibles :" >&2
    clients_disponibles >&2
    exit 2
fi
CLIENT="$1"
# `case` d'abord : il juge la chaîne ENTIÈRE, retours à la ligne compris, là où
# `grep` ne juge que ligne par ligne (« cabinet-01<saut>../x » passerait).
case "$CLIENT" in
    *[!a-z0-9-]*) CLIENT_VALIDE=non ;;
    *) CLIENT_VALIDE=oui ;;
esac
if [ "$CLIENT_VALIDE" != oui ] || ! printf '%s\n' "$CLIENT" | grep -Eq '^cabinet-[0-9]{2,}$'; then
    echo "ERREUR : nom de client invalide. Attendu : cabinet-NN (par exemple cabinet-01)." >&2
    echo "Clients disponibles :" >&2
    clients_disponibles >&2
    exit 2
fi
if [ ! -f "clients/$CLIENT/schema.json" ]; then
    echo "ERREUR : le client $CLIENT n'existe pas (clients/$CLIENT/schema.json manque)." >&2
    echo "Clients disponibles :" >&2
    clients_disponibles >&2
    exit 2
fi

# Un logo client est une donnée identifiante : il se pose sur le PC du cabinet,
# sous formulaire/images/cabinet/, jamais dans le paquet (C2-T2). `cp -R
# formulaire` copie tout le dossier de travail, fichiers non suivis compris :
# un logo oublié ici partirait chez tous les clients suivants. Refus AVANT la
# première copie, et avant d'effacer un paquet précédent.
if [ -e formulaire/images/cabinet ]; then
    echo "ERREUR : formulaire/images/cabinet existe dans l'arbre source." >&2
    echo "Un logo client se pose au cabinet, jamais dans le paquet : retirez ce dossier de l'atelier, puis recommencez." >&2
    exit 2
fi

PAQUET="BilanPosturo-$(date +%Y-%m-%d)"
rm -rf "$PAQUET" "$PAQUET.zip"
mkdir -p "$PAQUET"

cp demarrer-serveur.bat "$PAQUET/"
# Scripts d'installation du démarrage automatique : ils s'exécutent au
# cabinet, pas ici, et doivent donc voyager avec le paquet.
cp installer-demarrage.ps1 desinstaller-demarrage.ps1 "$PAQUET/"
cp -R formulaire serveur "$PAQUET/"
# Le schéma du client remplace celui de formulaire/ (son miroir, gardé égal par
# tests/test_schema_client.js). Le dossier clients/ lui-même ne voyage jamais :
# le schéma d'un client ne doit pas partir chez un autre.
cp "clients/$CLIENT/schema.json" "$PAQUET/formulaire/schema.json"

# Depuis C1-T3b, le formulaire de production EST le moteur : index.html est
# une coquille qui rend son corps au chargement depuis schema.json. Un
# paquet qui livrerait la coquille sans moteur ni schéma livrerait un
# formulaire VIDE au cabinet, le lendemain de l'installation — c'est pourquoi
# formulaire/moteur/rendu.js et formulaire/schema.json rejoignent la boucle
# `obligatoire` plus bas, aux côtés de formulaire/index-v1.html (la fiche de
# secours gelée) : leur présence est vérifiée dans l'archive elle-même, pas
# seulement supposée parce que `cp -R formulaire` les a copiés.

# Le code passe en Business Source License 1.1 : chaque copie doit porter le
# Notice de la licence (exigence propre à BUSL), et TIERS.md l'accompagne
# pour l'attribution des bibliothèques vendorisées dans formulaire/lib/.
cp LICENSE TIERS.md "$PAQUET/"

# Les fiches d'installation restent à la racine du paquet : c'est la première
# chose à lire en dézippant. Les guides d'usage quotidien vont dans docs/.
cp docs/LISEZMOI.txt docs/READ-ME-FIRST.txt "$PAQUET/"
mkdir -p "$PAQUET/docs"
cp docs/Mode_emploi.md docs/USER-GUIDE.md "$PAQUET/docs/"

# Retirer les fichiers parasites de macOS
find "$PAQUET" -name '.DS_Store' -delete
find "$PAQUET" -name '._*' -delete
find "$PAQUET" -name '__pycache__' -type d -exec rm -rf {} +

zip -r -q -X "$PAQUET.zip" "$PAQUET"
rm -rf "$PAQUET"

# Le contrôle porte sur la présence effective des pièces obligatoires, et non
# sur les dernières lignes du listing : LICENSE et TIERS.md sont triés en tête
# et n'y figuraient jamais, si bien que leur absence passait inaperçue.
# Depuis C1-T3b, formulaire/index.html (la coquille), formulaire/index-v1.html
# (la fiche de secours), formulaire/moteur/rendu.js et formulaire/schema.json
# rejoignent la liste : un paquet qui en manquerait livrerait un formulaire
# vide au cabinet, exactement comme un paquet sans LICENSE le livrerait hors
# de ses conditions d'usage.
for obligatoire in "$PAQUET/LICENSE" "$PAQUET/TIERS.md" \
                   "$PAQUET/formulaire/index.html" "$PAQUET/formulaire/index-v1.html" \
                   "$PAQUET/formulaire/moteur/rendu.js" "$PAQUET/formulaire/schema.json" \
                   "$PAQUET/formulaire/version.json"; do
    if ! unzip -l "$PAQUET.zip" "$obligatoire" > /dev/null 2>&1; then
        # L'archive incomplète est effacée, comme pour le contrôle du schéma plus
        # bas : un BilanPosturo-*.zip laissé sur le disque a l'air d'un paquet
        # valide, et c'est celui que l'on emporterait au cabinet.
        rm -f "$PAQUET.zip"
        echo "ERREUR : $obligatoire manque dans l'archive." >&2
        echo "Le paquet ne doit pas partir incomplet : ni sans licence, ni sans moteur de rendu ni schéma." >&2
        echo "L'archive a été effacée." >&2
        exit 1
    fi
done

# Ce que contient l'archive est ce que le client a décrit, octet pour octet :
# le contrôle relit l'archive elle-même, pas la copie qui l'a fabriquée.
if ! unzip -p "$PAQUET.zip" "$PAQUET/formulaire/schema.json" | cmp -s - "clients/$CLIENT/schema.json"; then
    rm -f "$PAQUET.zip"
    echo "ERREUR : le formulaire/schema.json de l'archive n'est pas celui de clients/$CLIENT/schema.json." >&2
    echo "L'archive a été effacée : le paquet ne doit pas partir avec le schéma d'un autre." >&2
    exit 1
fi

echo "Archive créée : $PAQUET.zip (client : $CLIENT)"
unzip -l "$PAQUET.zip"
