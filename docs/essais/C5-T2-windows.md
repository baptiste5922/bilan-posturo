# Fiche d'essai C5-T2 — le client de mise à jour, sur un vrai Windows

Contrat : `docs/contrats/C5-T2.md` (§12, « Ce que seule la VM Windows vérifie »).
**À remplir par Baptiste.** L'implémenteur n'y a rien inscrit : les champs de
résultat sont vides à dessein, et les cases de l'audit ne se cochent qu'ici.

Règles de la fiche : **patient fictif uniquement** ; **aucune adresse IP du
cabinet pilote** ; aucun contenu de `journal.log` ; aucun nom de patient. Une
adresse de la VM d'essai peut figurer, pas celle du cabinet.

La partie **A** (application locale) conditionne la livraison de C5-T2a au
prospect. La partie **B** (téléchargement, plage horaire, magasin de certificats)
sera ajoutée par C5-T2b : elle n'est pas à remplir ici.

## Fabriquer les paquets d'essai (sur le poste de développement)

**La clé d'essai ne touche jamais le dépôt.** Ni la clé privée, ni sa liste de
confiance `serveur/cles_publication.json` ne se posent dans votre dépôt de travail :
ce fichier est la racine de confiance de tout le parc, il n'est pas ignoré par Git,
et il ne se commite qu'une fois, avec la **vraie** clé, dans un commit dédié
(`docs/cle-publication.md`, §4). Tout ce qui suit se passe dans une **copie jetable
hors du dépôt**, faite par `git ls-files -z` (jamais `cp -r` : la racine du dépôt
porte les données réelles d'un cabinet). Un test (`tests.test_maj`,
`Documentation`) refuse qu'une clé nommée `…-essai` soit un jour suivie par Git.

La séquence a été déroulée telle quelle, le 12 novembre 2026, sur une copie du dépôt
(macOS, Python 3.14 avec `cryptography`) ; elle produit cinq dossiers de paquets.

```sh
# 1. Copie jetable, HORS du dépôt (dossier à effacer à la fin de l'essai).
ESSAI=$(mktemp -d)
mkdir "$ESSAI/depot" "$ESSAI/cles" "$ESSAI/paquets"
git ls-files -z | tar -c --null -T - -f - | tar -x -C "$ESSAI/depot" -f -
cd "$ESSAI/depot"          # à partir d'ici, plus rien ne touche le dépôt

# 2. Clé jetable. Le nom doit suivre « publication-AAAA… ». La clé privée est
#    écrite dans $ESSAI/cles (hors de la copie : l'outil refuse tout dossier sous
#    le dépôt, copie comprise). La sortie standard est la liste de confiance.
PHRASE='une-phrase-d-essai-de-plus-de-vingt-signes'
printf '%s\n' "$PHRASE" | python3 outils/signer-paquet.py generer-cle \
    --dossier "$ESSAI/cles" --nom publication-2026-essai --phrase-stdin \
    > serveur/cles_publication.json

# 3. Un paquet par version : monter la version, fabriquer, signer, ranger.
fabriquer() {      # $1 = version, $2 = dossier de rangement
    printf '{\n  "version": "%s"\n}\n' "$1" > formulaire/version.json
    sh outils/faire-paquet.sh cabinet-01 > /dev/null
    mkdir -p "$ESSAI/paquets/$2"
    printf '%s\n' "$PHRASE" | python3 outils/signer-paquet.py signer \
        --cle "$ESSAI/cles/publication-2026-essai-privee.pem" \
        --client cabinet-01 --version-minimale 1.1.0 --phrase-stdin \
        BilanPosturo-*.zip > "$ESSAI/paquets/$2/signature.txt"
    mv BilanPosturo-*.zip* "$ESSAI/paquets/$2/"
}

# N : le paquet à INSTALLER sur la VM (version 1.1.0, non signé : il embarque la
# liste de confiance d'essai, ce qui est tout ce que le client installé lui demande).
printf '{\n  "version": "1.1.0"\n}\n' > formulaire/version.json
sh outils/faire-paquet.sh cabinet-01 > /dev/null
mkdir "$ESSAI/paquets/n" && mv BilanPosturo-*.zip "$ESSAI/paquets/n/"

fabriquer 1.2.0 n1      # N+1, pour A1
fabriquer 1.3.0 n2      # N+2, pour A3 (remplace aussi maj.py : A4)

# N+3, volumineux (12 Mio) pour allonger la bascule : A7.
mkdir formulaire/remplissage
i=0; while [ $i -lt 60 ]; do head -c 200000 /dev/urandom > formulaire/remplissage/f$i.bin; i=$((i+1)); done
fabriquer 1.4.0 n3

# N+4, cassé exprès (le serveur sort aussitôt) : A8.
printf 'import sys\nsys.exit(1)\n' > serveur/serveur.py
fabriquer 1.5.0 n4
```

Chaque dossier `n1` à `n4` contient `BilanPosturo-AAAA-MM-JJ.zip`, son
`.manifeste.json` et son `.manifeste.sig` : **les trois doivent rester côte à côte**
quand on les copie sur la VM, sous le même nom. Relire `signature.txt` (la liste
des fichiers signés) ; contrôler un paquet comme le fera le cabinet :

```sh
python3 outils/signer-paquet.py verifier --cles serveur/cles_publication.json \
    --version-installee 1.1.0 --client cabinet-01 \
    "$ESSAI/paquets/n1/BilanPosturo-AAAA-MM-JJ.zip"      # PAQUET ACCEPTÉ 1.2.0
```

Sur la VM : installer le paquet `n` selon `docs/LISEZMOI.txt`. Sa liste de confiance
`serveur\cles_publication.json` est celle d'essai : c'est elle qui jugera N+1.
**Ne copiez jamais la clé privée** (`$ESSAI/cles`) sur la VM. L'essai fini, effacez
`$ESSAI` et la VM.

---

## A. Essai sur une VM Windows propre

### Préparation

- Windows 10 ou 11, sans installation antérieure de l'application.
- Python 3.9 ou plus, avec « Add python.exe to PATH ».
- Paquet N (dossier `n`, voir plus haut), installé dans `C:\BilanPosturo` selon
  `docs/LISEZMOI.txt`, tâche `BilanPosturo` installée.
- `config.json` complété : `"mise_a_jour": { "client": "cabinet-01" }`.
- Les paquets signés N+1 à N+4 (dossiers `n1` à `n4`), avec leurs trois fichiers.
- Une session **administrateur**, et un second compte **utilisateur standard**.

| Champ | Valeur |
|---|---|
| Date de l'essai | |
| Version de Windows (`winver`) | |
| Version de Python (`python --version`) | |
| Version N / N+1 / N+2 | 1.1.0 / 1.2.0 / 1.3.0 (si fabriqués comme ci-dessus) |
| Opérateur | |

### A1. Application en console administrateur

```powershell
cd C:\BilanPosturo
python serveur\maj.py appliquer C:\essai\n1\BilanPosturo-AAAA-MM-JJ.zip
echo $LASTEXITCODE
python serveur\maj.py etat
```

Attendu : code `0` ; `etat` donne `repos`, `appliquee`, la version N+1 ;
`https://localhost:8000/etat` (authentifié) montre la ligne « Mise à jour » ;
`technique.log` porte `ARRET motif=mise-a-jour` puis `MAJ_APPLIQUEE`.

| Résultat | |
|---|---|

### A2. Droits de `C:\BilanPosturo` et de `mise-a-jour\`

```powershell
icacls C:\BilanPosturo
icacls C:\BilanPosturo\mise-a-jour
icacls C:\BilanPosturo\serveur\serveur.py
```

Attendu : `mise-a-jour\` ne liste que `SYSTEM` et `Administrateurs` (aucun héritage).
**Point d'audit à relever** : qui peut écrire dans `C:\BilanPosturo` lui-même et dans
`serveur\` ? Si un utilisateur standard le peut, n'importe quel programme de sa
session peut remplacer `serveur.py`, exécuté en SYSTEM. C'est antérieur à C5-T2
mais un client de mise à jour le rend plus visible : à ouvrir en C6 si c'est le cas.

Vérifier aussi que le compte **standard** lit `docs\Mode_emploi.md` et
`demarrer-serveur.bat` **après** la mise à jour (les temporaires naissent à côté de
leur destination pour hériter des droits du dossier : erratum 1 du contrat).

| Résultat (droits de `mise-a-jour\`) | |
|---|---|
| Qui écrit dans `C:\BilanPosturo` et `serveur\` | |
| L'utilisateur standard lit les fichiers remplacés | |

### A3. Sous le compte SYSTEM

Créer une tâche de test qui lance la commande sous SYSTEM, puis la démarrer. Le
compte SYSTEM n'a pas le `PATH` de votre session (une installation de Python « pour
moi seulement » n'y est pas) : on donne le chemin **absolu** de `python.exe`, comme
l'installateur du produit le fait pour `pythonw.exe`.

```powershell
$python = (Get-Command python).Source     # ex. C:\Python313\python.exe
schtasks /Create /TN BilanPosturo-essai-maj /RU SYSTEM /SC ONCE /ST 23:59 /TR "$python C:\BilanPosturo\serveur\maj.py appliquer C:\essai\n2\BilanPosturo-AAAA-MM-JJ.zip" /F
schtasks /Run /TN BilanPosturo-essai-maj
```

(Le chemin de `python.exe` ne doit pas contenir d'espace, sans quoi il faudrait
protéger les guillemets de `/TR` ; réinstaller Python dans `C:\Python313` au besoin.)

Attendu : mise à jour N+2 appliquée, `maj.py etat` donne `appliquee`. Supprimer la
tâche ensuite (`schtasks /Delete /TN BilanPosturo-essai-maj /F`).

| Résultat | |
|---|---|

### A4. `maj.py` remplacé pendant qu'il s'exécute (D12)

Le paquet N+2 remplace `serveur\maj.py`. Contrôler dans A3 que le processus en
cours **n'a pas échoué** et que `technique.log` porte bien `MAJ_APPLIQUEE` (et non
`MAJ_RETOUR`). Si Windows refusait le remplacement (`PermissionError`), noter le
nombre de tentatives observées (cinq maximum, espacées de 0,5 s).

| Résultat | |
|---|---|

### A5. Tâche `IgnoreNew` et redémarrage

Pendant A1 ou A3, relever l'intervalle entre `ARRET motif=mise-a-jour` et le
`DEMARRAGE` suivant dans `technique.log`. Un `/Run` lancé pendant que l'ancienne
instance finit de quitter est **ignoré sans erreur** : le client attend 1 s après
l'arrêt, et relance la tâche toutes les 5 s tant que `/sante` reste muette. Noter
si une relance a été nécessaire (le journal de la tâche, Observateur
d'événements › Planificateur de tâches).

Relever aussi **le code de sortie de `schtasks /Run` sur la tâche du serveur déjà en
marche** (le client le rappelle toutes les 5 s tant que `/sante` est muette, et un
serveur lent à démarrer est une tâche en marche) :

```powershell
schtasks /Run /TN BilanPosturo
echo $LASTEXITCODE
```

Le client n'en dépend pas (une erreur de cette relance est avalée : elle ne défait
jamais une version saine), mais le code permet de le confirmer. Le test automatisé
`tests.test_maj_windows` l'imprime aussi dans le journal de la CI, sur une tâche
jetable : relevé le 12 novembre 2026 sous `windows-latest`, **code 0** (le second
`/Run` d'une tâche en marche est ignoré sans erreur). À confirmer ici sur la tâche
du serveur.

| Intervalle ARRET → DEMARRAGE | |
|---|---|
| Une relance a-t-elle été nécessaire ? | |
| Code de `schtasks /Run` sur la tâche en marche | |

### A6. Dépôt depuis un navigateur pendant `appliquer`

Depuis un navigateur de la VM, exporter un bilan d'essai (patient fictif) **pendant**
que `appliquer` est lancé sur un nouveau paquet N+3 (avec `--calme-minutes 0`).
Attendu : si le dépôt est en cours à la demande d'arrêt, `appliquer` sort en code
`3` (`ARRET_REFUSE`, motif `depot-en-cours` dans `mise-a-jour\arret.reponse`) ; le
PDF arrive intact dans `bilans\`. Rejouer `appliquer` après le dépôt.

| Résultat | |
|---|---|

### A7. Coupure pendant la bascule

Lancer `appliquer` du paquet N+3 (dossier `n3`, volumineux : 12 Mio de fichiers dans
`formulaire\remplissage\`, pour allonger la bascule), **débrancher la VM** (arrêt brutal) pendant
`etat` = `bascule`, puis redémarrer. Attendu : à la reconnexion, `python
serveur\maj.py etat` dit `bascule` ; `python serveur\maj.py reprendre` ramène
chaque fichier à l'état d'avant, `/sante` répond, la version n'est **pas** écartée.

| Résultat | |
|---|---|

### A8. Un paquet cassé revient seul

Appliquer le paquet N+4 (dossier `n4`) dont `serveur\serveur.py` sort immédiatement. Attendu : au bout d'une minute, `MAJ_RETOUR cause=SANTE_MUETTE
resultat=ok`, serveur d'avant relancé, `/etat` dit `revenue`, et un second
`appliquer` du même paquet rend `VERSION_ECARTEE` sans arrêter le serveur.

| Résultat | |
|---|---|

### Synthèse

| Critère | Fait | Remarque |
|---|---|---|
| A1 à A8 remplis | | |
| Aucune anomalie bloquante | | |
