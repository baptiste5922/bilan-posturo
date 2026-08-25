#!/bin/sh
# Construit l'archive à installer sur le PC du cabinet.
# N'inclut QUE ce qui est nécessaire : ni secrets, ni données patient,
# ni node_modules.

PAQUET="BilanPosturo-$(date +%Y-%m-%d)"
rm -rf "$PAQUET" "$PAQUET.zip"
mkdir -p "$PAQUET"

cp index.html style.css script.js serveur.py generer_autorite.py \
   demarrer-serveur.bat \
   Mode_emploi.md LISEZMOI.txt USER-GUIDE.md READ-ME-FIRST.txt "$PAQUET/"
cp -R lib images "$PAQUET/"

# Retirer les fichiers parasites de macOS
find "$PAQUET" -name '.DS_Store' -delete
find "$PAQUET" -name '._*' -delete

zip -r -q -X "$PAQUET.zip" "$PAQUET"
rm -rf "$PAQUET"

echo "Archive créée : $PAQUET.zip"
unzip -l "$PAQUET.zip" | tail -3
