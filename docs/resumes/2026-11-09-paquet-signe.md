# Session du 8-9 novembre 2026 — Un paquet de mise à jour que le cabinet sait authentifier

**Durée approximative :** une journée, de part et d'autre de minuit, à la
suite de la session du 8 novembre (`2026-11-08-requetes-malformees.md`).
**Tâches concernées :** C5-T1.
**Branche :** `c5-t1-signature`, fusionnée en avance rapide sur `main` et
poussée.
**Commits :** `9cdc88e..f33cb2b`. `main` est à `f33cb2b`. La CI de la branche
(run `42523857725`) puis celle de `main` (run `42588831325`) sont vertes sur
les 7 jobs.

## Ce qui a été fait

**Mode de travail.** Inchangé : commits et poussées sans demander. Baptiste a
demandé où en était la feuille de route, puis a lancé C5-T1, qui a enchaîné
contrat, implémentation, audit, correction, réaudit, revue, fusion et poussée.

**C5-T1 — Format de paquet et signature Ed25519. Livrée.**

- **Vérifier sans dépendance.** La bibliothèque standard de Python n'a pas
  Ed25519, et tout ce qui tourne au cabinet n'utilise qu'elle. La vérification
  est donc écrite en Python pur d'après la RFC 8032, dans
  `serveur/signature_ed25519.py` (170 lignes, une seule fonction publique,
  `verifier`, qui ne lève jamais). Elle est plus stricte qu'OpenSSL : S ≥ L,
  encodages non canoniques et points d'ordre faible sont refusés. Environ 4 ms
  par vérification sous le 3.9 du Mac. Elle ne manipule aucun secret, d'où
  l'absence d'exigence de temps constant ; signer reste le rôle de
  `cryptography`, sur le poste de l'éditeur seulement.
- **Le format.** Un manifeste JSON et sa signature de 64 octets sont posés à
  côté de l'archive. Le manifeste porte la version, la version minimale, le
  client, l'empreinte de l'archive entière et celle de chaque fichier.
  `serveur/paquet_signe.py` vérifie dans un ordre imposé : taille, signature
  sur les octets exacts, JSON strict, versions, client, chemins, empreinte de
  l'archive, et seulement alors `zipfile`, sur le même descripteur. Rien n'est
  extrait. Vingt codes de refus fermés, sans chemin.
- **Les clés.** La liste des clés de confiance (`serveur/cles_publication.json`,
  quatre au plus, pour pouvoir changer de clé) est celle déjà installée, jamais
  celle du paquet entrant. Le dépôt n'en porte aucune : générer la vraie clé
  est le geste de Baptiste, décrit dans `docs/cle-publication.md`.
- **L'outil de l'éditeur.** `outils/signer-paquet.py` a trois sous-commandes,
  `generer-cle`, `signer` et `verifier`. Il refuse une clé sous la racine du
  dépôt, n'écrase jamais rien, écrit la clé chiffrée en 0600, refuse de signer
  avec une clé absente de la liste embarquée, et revérifie le résultat avec le
  code du cabinet avant de le laisser sortir. `faire-paquet.sh` ne signe pas :
  la CI fabrique toujours un paquet non signé.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| Vérification Ed25519 en Python pur au cabinet | Stdlib seule ; aucune autre voie (OpenSSL par `ctypes`, HMAC, Authenticode, GPG, bibliothèque vendorisée) n'était à la fois sans dépendance et auditable | 170 lignes de code cryptographique écrit à la main, gardées par les vecteurs RFC, un croisement avec `cryptography` et vingt mutations |
| Manifeste et signature à côté de l'archive, empreinte de l'archive dans le manifeste | Authentifier avant d'analyser quoi que ce soit | Trois fichiers à publier par version ; `.gitignore` les ignore |
| La liste installée juge, jamais celle du paquet | Sinon un attaquant embarque sa propre clé | À reporter tel quel dans le contrat de C5-T2 |
| Pas de révocation de clé | Hors de portée sans canal de confiance supplémentaire | Une compromission demande une intervention sur chaque PC ; écrit dans la fiche |
| Phrase de passe d'au moins 20 caractères | `cryptography` ne chiffre la clé qu'avec 2 048 tours PBKDF2 pour ce format | Parade proportionnée retenue par l'audit, plutôt qu'un autre format |
| Champ de nom 0x7075 refusé explicitement | Python 3.12 et plus le lisent, 3.9 l'ignore : le verdict dépendait de la version installée | Même verdict sur toutes les versions |
| D9 (paquet par client ou générique) non tranchée | Ne bloque pas C5-T1 ; le format garde un champ `client` et refuse tout format inconnu | À trancher avant C5-T3 : des paquets par client publiés exposeraient la liste des clients |
| Effort M → L, tâche non découpée | Le contrat tenait en un seul morceau cohérent | — |

## État des tests

**Avant :** 473 tests Python (7 sautés sur le Mac) et 16 suites Node.
**Après :** **671 tests Python** (7 sautés), verts aussi sous `python3 -O`, et
16 suites Node inchangées. Trois suites nouvelles :
`tests/test_signature_ed25519.py` (vecteurs RFC 8032 reproduits à l'octet,
encodages non canoniques, croisement avec `cryptography` dans les trois sens),
`tests/test_paquet_signe.py` (chaque code de refus derrière une signature
valide, fuzz de 300 archives re-signées) et `tests/test_signer_paquet.py`
(bout en bout sur le paquet réel). La garde « stdlib seule » couvre désormais
tous les `serveur/*.py`, `generer_autorite.py` exempté par son nom. Sous le
3.9.6 du Mac, sans `cryptography`, les suites de vérification passent.
66 mises en échec dans `docs/audits/C5-T1-mises-en-echec.md`.

## Constats de sécurité

- **Audit : CONFORME SOUS RÉSERVE au premier passage, CONFORME au réaudit.**
  Aucun moyen trouvé de faire accepter un paquet sans la clé privée. Quatre
  constats, tous corrigés :
  - **moyen** : une entrée au nom brut propre renommée `../../…` par un champ
    0x7075 n'était refusée que sous Python ≥ 3.12, et la garde qui l'arrêtait
    n'était éprouvée par aucun test ;
  - **faibles** : phrase de passe de 12 caractères alors que la fiche en
    demandait 20 ; fichier partiel laissé si une écriture échouait ; fichier et
    dossier de même nom acceptés, impossibles à extraire sous Windows.
- **Revue : À LIVRER**, deux remarques importantes corrigées : la fiche faisait
  signer un paquet portant la version installée (refusé à la première commande
  réelle), et les manifestes signés n'étaient pas ignorés par Git. Mineurs
  laissés en l'état, avec leur raison, dans `docs/revues/C5-T1.md`.
- **Observations sans correction** : clé publique à composante de torsion
  acceptée (inexploitable, la liste est choisie par l'éditeur) ; le détail
  d'un refus contient un chemin, C5-T2 ne devra journaliser que le code.

## Ce qui reste en suspens

- **Geste de Baptiste : générer et sauvegarder la vraie clé de publication**,
  d'après `docs/cle-publication.md`. Sans elle, `signer` refuse.
- **D9** : paquet par client ou générique, avant C5-T3. Touche D-O1.
- **Mesures de Baptiste :** A13 de C1-T5, M-A et M-B de C9-T2 ; D-O1 et D-O2.
- **Tâche C7 de l'outillage de test**, à ouvrir : les deux courses sous macOS,
  la dérivation des routes dupliquée, et désormais `port_libre()`
  (« Address already in use » isolé sur macOS, run `42514993341`).
- **`cp -R` de `faire-paquet.sh`** emporte les fichiers non suivis, que le
  manifeste signe fidèlement : une tâche pour copier par `git ls-files`.
- **Hérité :** essai de C3-T3a sur une VM Windows ; à la visite de C1-T4b,
  `demarrer-serveur.bat` et A5 de C6-T5.

## Prochaine étape recommandée

Côté Baptiste : générer la clé de publication, en suivant
`docs/cle-publication.md`. Côté code : `/lancer-tache C5-T2`, le client de
mise à jour, dont le contrat doit reprendre les points reportés par l'audit
(bloc C5-T1 de `docs/ROADMAP.md`).

## À savoir pour la prochaine session

- **`zipfile` réécrit `\` en `/` sous Windows, à l'écriture comme à la
  lecture.** Un test qui veut un antislash dans un nom d'entrée doit l'écrire
  dans les octets du zip ; un contrôle de chemin doit juger `orig_filename`.
  Les deux jobs Windows du premier run l'ont montré.
- **Un champ supplémentaire peut renommer une entrée, selon la version de
  Python.** 0x7075 (*Unicode Path*) est appliqué par 3.12 et plus, ignoré par
  3.9. Toute garde qui dépend de `filename` doit être éprouvée sur les deux.
- **Une empreinte globale masque les gardes qui la suivent.** Pour éprouver une
  garde du zip, il faut recalculer et re-signer le manifeste (D8 du contrat) ;
  sinon tout s'arrête à `ARCHIVE_DIFFERENTE` et la garde n'est jamais testée.
  C'est ce qui a fait survivre huit mutations au premier passage.
- **Une fiche se joue comme du code.** La revue a trouvé que la première
  commande réelle de la fiche aurait échoué : la relire en déroulant chaque
  commande sur l'état réel du dépôt.
- **`tests/test_confidentialite_prospect.py` lit tout `.json` de
  `tests/donnees/` comme un schéma** : des données de test étrangères vont dans
  `tests/donnees/externes/`. La garde a aussi pris une chaîne d'octets de test
  pour un numéro de téléphone : reformuler, ne pas assouplir.
- **`… | tail` rend le code de `tail`.** Pour lire le verdict d'une suite
  lancée en arrière-plan, rediriger vers un fichier et chercher `Ran`/`OK`.
