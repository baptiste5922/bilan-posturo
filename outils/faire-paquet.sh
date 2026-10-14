#!/bin/sh
# Construit l'archive à installer sur le PC du cabinet.
# N'inclut QUE ce qui est nécessaire : ni secrets, ni données patient,
# ni node_modules.
#
# `set -e` : sans lui, une copie qui échoue laissait le script continuer,
# zipper, puis annoncer « Archive créée ». Le paquet partait au cabinet
# amputé — du texte de licence, par exemple, que BUSL exige sur chaque
# copie. Un défaut qui s'annonce comme un succès est le pire des deux.
set -e
#
# L'archive reproduit l'arborescence du dépôt : les scripts calculent leurs
# chemins à partir de leur propre emplacement, et fonctionnent donc au
# cabinet exactement comme ici.

# Se placer à la racine du projet, quel que soit le dossier d'appel.
cd "$(dirname "$0")/.." || exit 1

PAQUET="BilanPosturo-$(date +%Y-%m-%d)"
rm -rf "$PAQUET" "$PAQUET.zip"
mkdir -p "$PAQUET"

cp demarrer-serveur.bat "$PAQUET/"
# Scripts d'installation du démarrage automatique : ils s'exécutent au
# cabinet, pas ici, et doivent donc voyager avec le paquet.
cp installer-demarrage.ps1 desinstaller-demarrage.ps1 "$PAQUET/"
cp -R formulaire serveur "$PAQUET/"

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
for obligatoire in "$PAQUET/LICENSE" "$PAQUET/TIERS.md"; do
    if ! unzip -l "$PAQUET.zip" "$obligatoire" > /dev/null 2>&1; then
        echo "ERREUR : $obligatoire manque dans l'archive." >&2
        echo "Le paquet ne doit pas être livré sans son texte de licence." >&2
        exit 1
    fi
done

echo "Archive créée : $PAQUET.zip"
unzip -l "$PAQUET.zip"
