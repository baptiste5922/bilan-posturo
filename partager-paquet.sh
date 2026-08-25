PORT=9000
PARTAGE=$(mktemp -d)

ARCHIVE=$(ls -t BilanPosturo-*.zip 2>/dev/null | head -1)
if [ -z "$ARCHIVE" ]; then
    echo "Aucune archive trouvée. Lancez d'abord ./faire-paquet.sh"
    exit 1
fi

cp "$ARCHIVE" "$PARTAGE/"

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
[ -z "$IP" ] && IP="<adresse-de-ce-mac>"

echo "Depuis le navigateur du PC du cabinet, ouvrez :"
echo
echo "    http://$IP:$PORT/$ARCHIVE"
echo
echo "Ctrl+C pour arrêter le partage une fois le fichier récupéré."
echo

python3 -m http.server "$PORT" --directory "$PARTAGE"
