# Session du 8 novembre 2026 — Plus de silence sur une requête malformée, et un en-tête `Server` muet

**Durée approximative :** une demi-journée, à la suite de la session du
7 novembre (`2026-11-07-racine-web-refusee.md`).
**Tâches concernées :** C6-T5.
**Branche :** `c6-t5-requetes-malformees`, fusionnée en avance rapide sur
`main` et poussée.
**Commits :** `7d0a972..af8b8c3`. `main` est à `af8b8c3`. La CI de la branche
(run `42470497173`) puis celle de `main` (run `42472428565`) sont vertes sur
les 7 jobs.

## Ce qui a été fait

**Mode de travail.** Inchangé : commits et poussées sans demander. C6-T5 a
enchaîné contrat, implémentation, audit, revue, fusion et poussée. Le serveur
`http.server` du port 8777 (PID 77897), resté de la session précédente, a été
arrêté à la demande de Baptiste.

**C6-T5 — Une requête malformée reçoit un code, pas un silence. Livrée.**

- **La mesure d'abord.** Le planificateur a envoyé 51 requêtes brutes à un
  serveur en bac à sable, sous 3.14 puis sous le 3.9 du Mac. L'octet nul
  recevait déjà un code depuis C6-T6, mais un silence subsistait sous 3.9 :
  `/%ed%a0%80.html`, une demi-paire de substitution une fois décodée, faisait
  lever à `open()` une `UnicodeEncodeError` que la bibliothèque ne rattrape
  pas. La mesure a aussi trouvé la version de Python dans l'en-tête `Server`
  de toutes les réponses, et des caractères de contrôle bruts dans
  `journal.log`. L'effort est passé de S à M.
- **Deux barrières pour le silence.**
  - `confiner_fichier_servi` refuse un chemin que `os.fsencode` ne sait pas
    encoder. Le motif `forme-invalide` couvre aussi l'octet nul (qui donnait
    `hors-racine`).
  - Un filet dans `send_head` rend 404 sur une `ValueError`, et seulement
    celle-là. L'audit a vérifié, en lisant `http.server` de 3.9 et 3.14, que
    toute `ValueError` qu'un client peut provoquer survient avant
    `send_response`.
- **Une seule forme du chemin.** Le filtre d'extension et le confinement lisent
  la même chaîne, `fichier = self.translate_path(chemin)`, celle que
  `send_head` ouvrira. La garde AST `test_g2` a été réécrite, plus stricte.
  Effet voulu : des formes encodées du même fichier (`/index%2ehtml`,
  `/script.j%73`, `/index.html/.`) sont servies ; aucun fichier nouveau ne
  l'est.
- **Le reste.**
  - Un chemin qui ne commence pas par `/` reçoit 400, après
    l'authentification : sans identifiants, la même 401 quel que soit le
    chemin.
  - `list_directory` rend toujours 404, quelle que soit la version de Python.
  - `Server: bilan-posturo`, `sys_version` vide, `version_string` surchargée.
  - `log_message` échappe C0, DEL et C1, pas la barre oblique inverse, pour
    garder lisibles les chemins Windows. Une requête non analysée (414, 505)
    est classée `route=autre` dans `technique.log`, au lieu de `formulaire`.
- **Documentation.** Le README (surface exposée, en-têtes, dépannage), la
  feuille de route (bloc de C6-T5, notes de C6-T6 et C6-T7 soldées) et un
  erratum en pied de contrat. Le mode d'emploi ne change pas : aucun message
  visible ne change.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| Le 400 d'un chemin non absolu vient après l'authentification | Ne pas offrir à un client sans identifiants un oracle sur l'analyse du chemin | Les codes protocolaires de la bibliothèque (414, 431, 501, 505) restent, eux, avant l'authentification, comme avant |
| La forme unique est celle de `translate_path`, empruntée et non recodée | Le filtre doit juger exactement ce que le disque ouvrira | Des formes encodées du même fichier sont servies ; erratum au contrat, qui n'en annonçait qu'une |
| Aucun événement technique nouveau | La 400 se lit déjà dans `REPONSE … code=400` | `EVENEMENTS_TECHNIQUES` inchangé |
| `\` non échappé dans le journal | L'échapper doublerait chaque séparateur des chemins Windows | L'échappement n'est pas parfaitement réversible, ce qui est acceptable pour un journal lu par un humain |
| Doubles lignes `REPONSE code=0`, en-tête `Host` absent, réponse sans ligne d'état sur requête illisible : hors périmètre | Défauts antérieurs, sans silence ni divulgation | Consignés dans le contrat |
| Test de casse du filtre d'extension hors Windows, factorisation de la dérivation des routes : reportés | Ni l'un ni l'autre ne tient en une ligne ; la factorisation toucherait une garde de sécurité | Versés dans le bloc de C6-T5 (la factorisation en C7) |

## État des tests

**Avant :** 448 tests Python (7 sautés sur le Mac) et 16 suites Node.
**Après :** **473 tests Python** (7 sautés), verts aussi sous `python3 -O`, et
16 suites Node. `tests/test_requetes_malformees.py` est nouveau : table de 54
requêtes, en-tête `Server` sur toutes les routes dérivées de l'AST, index de
dossier, journaux. Dans `tests/test_liens_servis.py`, `test_g2` est réécrit et
`test_u10` attend `forme-invalide`. Mutations M1 à M11 et M9b consignées dans
`docs/audits/C6-T5-mises-en-echec.md`, M5 et M6 rejouées sous 3.9 (M6 fait
revenir le silence) ; l'auditeur en a rejoué six autres, dont quatre sous `-O`.

## Constats de sécurité

- **Audit : CONFORME au premier passage**, aucun constat. Trois observations :
  les formes équivalentes servies sont plus nombreuses que le contrat ne
  l'annonçait (même fichier, aucune exposition) ; le filet de `send_head` ne
  peut pas répondre après un `send_response` ; la variable de test
  `BILAN_PYTHON_CERTIFICATS` ne touche que la fabrication des certificats.
- **Revue : À LIVRER**, six remarques mineures, aucune bloquante. La
  documentation a été faite ; le reste est écarté avec sa raison dans
  `docs/revues/C6-T5.md`.

## Ce qui reste en suspens

- **Avant C1-T4b :** rejouer le test du service ordinaire (A5) sur la liste
  réelle des fichiers du formulaire de la praticienne : un nom inhabituel
  pourrait ne plus être servi sous la forme décodée. Et, à la visite, lancer
  une fois `demarrer-serveur.bat` (C6-T7).
- **Mesures de Baptiste :** A13 de C1-T5, M-A et M-B de C9-T2.
- **D-O1 et D-O2** : à trancher avant le premier client hors pilote.
- **Une tâche C7 à ouvrir** : les deux courses de l'outillage de test sous
  macOS, et la dérivation des routes dupliquée entre deux tests.
- **Hérité :** essai de C3-T3a sur une VM Windows ; C6-T1 à T3.

## Prochaine étape recommandée

La mesure de C9-T2 par Baptiste, en suivant `docs/essais/C9-T2-fabrication.md` :
elle seule débloque la fabrication du premier client hors pilote. Côté code,
ouvrir la tâche C7 de l'outillage de test.

## À savoir pour la prochaine session

- **Un silence peut n'exister que sous une version de Python.** Le défaut ne
  se reproduisait que sous 3.9 ; un test vert sous 3.14 ne prouvait rien. Le
  3.9 du Mac (`/usr/bin/python3`) n'a pas `cryptography` : fabriquer les
  certificats avec 3.14 et lancer le serveur en 3.9 (variable
  `BILAN_PYTHON_CERTIFICATS` de `tests/test_requetes_malformees.py`).
- **Sous Windows, `os.fsencode` accepte une demi-paire isolée** (PEP 529,
  `surrogatepass`). Une attente qui en dépend se dérive d'un essai
  `os.fsencode`, ancrée sous POSIX.
- **Un journal ouvert en mode texte se termine par `\r\n` sous Windows** :
  découper sur `\n` après lecture, pas sur `os.linesep`.
- **Une mutation qui ne mord pas n'est pas forcément un trou.** M9 retirait
  l'application de l'échappement, que `test_u5` ne garde pas (il éprouve la
  table) ; d'autres tests la gardent. L'auditeur a cru X9 non couverte, mais
  `test_i9` la voit sous Windows seulement. Lire quel test garde quoi avant de
  conclure.
- **Un audit corrige le contrat autant que le code.** Ici, rien à corriger
  dans le code, mais deux énoncés du contrat démentis par la mesure : erratum
  plutôt que réécriture.
