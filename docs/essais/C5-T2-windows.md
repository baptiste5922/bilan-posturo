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

**Clés d'essai.** Cet essai n'utilise **jamais** la vraie clé de publication.
Sur le poste de développement, fabriquer une clé jetable
(`python3 outils/signer-paquet.py generer-cle --dossier <dossier hors dépôt> --nom publication-essai`),
signer deux paquets d'essai avec elle (`signer`, version N+1 puis N+2), et poser
sa partie *publique* dans `serveur\cles_publication.json` de la VM
(`docs/cle-publication.md`). Ne pas copier la clé privée sur la VM.

---

## A. Essai sur une VM Windows propre

### Préparation

- Windows 10 ou 11, sans installation antérieure de l'application.
- Python 3.9 ou plus, avec « Add python.exe to PATH ».
- Paquet N produit par `sh outils/faire-paquet.sh cabinet-01`, installé dans
  `C:\BilanPosturo` selon `docs/LISEZMOI.txt`, tâche `BilanPosturo` installée.
- `config.json` complété : `"mise_a_jour": { "client": "cabinet-01" }`.
- Deux paquets signés N+1 et N+2 (numéros de version supérieurs, par exemple en
  bumpant `formulaire/version.json`) et leurs `.manifeste.json` / `.manifeste.sig`.
- Une session **administrateur**, et un second compte **utilisateur standard**.

| Champ | Valeur |
|---|---|
| Date de l'essai | |
| Version de Windows (`winver`) | |
| Version de Python (`python --version`) | |
| Version N / N+1 / N+2 | |
| Opérateur | |

### A1. Application en console administrateur

```powershell
cd C:\BilanPosturo
python serveur\maj.py appliquer C:\essai\BilanPosturo-N1.zip
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

Créer une tâche de test qui lance la commande sous SYSTEM, puis la démarrer :

```powershell
schtasks /Create /TN BilanPosturo-essai-maj /RU SYSTEM /SC ONCE /ST 23:59 /TR "python C:\BilanPosturo\serveur\maj.py appliquer C:\essai\BilanPosturo-N2.zip" /F
schtasks /Run /TN BilanPosturo-essai-maj
```

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

| Intervalle ARRET → DEMARRAGE | |
|---|---|
| Une relance a-t-elle été nécessaire ? | |

### A6. Dépôt depuis un navigateur pendant `appliquer`

Depuis un navigateur de la VM, exporter un bilan d'essai (patient fictif) **pendant**
que `appliquer` est lancé sur un nouveau paquet N+3 (avec `--calme-minutes 0`).
Attendu : si le dépôt est en cours à la demande d'arrêt, `appliquer` sort en code
`3` (`ARRET_REFUSE`, motif `depot-en-cours` dans `mise-a-jour\arret.reponse`) ; le
PDF arrive intact dans `bilans\`. Rejouer `appliquer` après le dépôt.

| Résultat | |
|---|---|

### A7. Coupure pendant la bascule

Lancer `appliquer` d'un paquet N+3 volumineux (ajouter des fichiers dans `docs\`
pour allonger la bascule), **débrancher la VM** (arrêt brutal) pendant
`etat` = `bascule`, puis redémarrer. Attendu : à la reconnexion, `python
serveur\maj.py etat` dit `bascule` ; `python serveur\maj.py reprendre` ramène
chaque fichier à l'état d'avant, `/sante` répond, la version n'est **pas** écartée.

| Résultat | |
|---|---|

### A8. Un paquet cassé revient seul

Appliquer un paquet N+4 dont `serveur\serveur.py` sort immédiatement (fabriqué
exprès). Attendu : au bout d'une minute, `MAJ_RETOUR cause=SANTE_MUETTE
resultat=ok`, serveur d'avant relancé, `/etat` dit `revenue`, et un second
`appliquer` du même paquet rend `VERSION_ECARTEE` sans arrêter le serveur.

| Résultat | |
|---|---|

### Synthèse

| Critère | Fait | Remarque |
|---|---|---|
| A1 à A8 remplis | | |
| Aucune anomalie bloquante | | |
