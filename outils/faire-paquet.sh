#!/bin/sh
# Construit l'archive à installer sur le PC du cabinet.
# N'inclut QUE ce qui est nécessaire : ni secrets, ni données patient,
# ni node_modules.
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
cp -R formulaire serveur "$PAQUET/"

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

echo "Archive créée : $PAQUET.zip"
unzip -l "$PAQUET.zip" | tail -3
