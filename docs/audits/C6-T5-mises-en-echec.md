# C6-T5 — Journal des mises en échec

Rédigé par l'implémenteur, le 8 novembre 2026. L'audit de sécurité de la tâche
(`docs/audits/C6-T5.md`) est écrit à part, par l'auditeur.

## Protocole

- **Copie jetable** hors du dépôt, faite par
  `git ls-files -z --cached --others --exclude-standard`, fichier par fichier
  (Python, `shutil.copy2`), puis initialisée en dépôt Git **sans origine** pour
  que `test_u12` de `test_liens_servis` dispose d'un index. Le harnais refuse de
  continuer si `config.json`, une clé, `journal.log`, `technique.log` ou
  `bilans/` se retrouve dans la copie. Aucun fichier réel du cabinet n'y figure.
  Un premier essai sans index Git a montré `test_u12` rouge au témoin : c'est la
  copie qui manquait d'index, pas un défaut du code ; le harnais a été corrigé
  avant toute mutation.
- **Sauvegarde** de `serveur/serveur.py` hors du dépôt avant la première
  mutation. Aucune mutation n'a jamais touché le dépôt : elles se jouent toutes
  sur la copie, dont le fichier est réécrit à l'identique après chaque
  mutation. À la fin, `git status` et `git diff` du dépôt étaient vides.
- **Une mutation = un remplacement de texte exact** dans `serveur/serveur.py` de
  la copie. Le harnais exige que le motif soit trouvé **exactement une fois** et
  que le fichier change.
- **Témoin sans mutation** joué avant les mutations, pour chaque mode.
- **Code de sortie lu sur la commande de test elle-même** (`subprocess.run(...)
  .returncode` du processus `python -m unittest`, jamais après un autre
  processus). Le harnais est un script Python, non des fonctions shell
  `A() { … "$@"; }` : la contrainte visée (ne jamais mettre une commande dans
  une variable sous zsh) est respectée, puisque les arguments partent en liste.
- **Tests joués** : `python3 [-O] -W error::ResourceWarning -m unittest
  tests.test_requetes_malformees tests.test_liens_servis` (63 tests). Les listes
  rouges sont comparées au témoin du même mode : seuls les rouges **nouveaux**
  comptent.
- **Modes** : 3.14.3 (macOS) pour toutes ; `-O` en plus pour M1 à M4 ; 3.9.6
  (`/usr/bin/python3`) en plus pour M5 et M6, les certificats du bac à sable
  étant fabriqués par 3.14 (`BILAN_PYTHON_CERTIFICATS`, voir l'en-tête de
  `tests/test_requetes_malformees.py`) parce que `cryptography` manque en 3.9.
  Le harnais est lancé en arrière-plan ; les modules joués n'incluent pas
  `ServeurArret`, le seul test qui dépend de SIGINT (piège connu de
  `CLAUDE.md`). La suite complète sous `-O` a, elle, été jouée au premier plan.
- **Témoin 3.9.6 : un rouge antérieur**, `test_u8_jonction_simulee_invisible_a_islink`
  (déjà rouge sur `b8010fd`, vérifié sur une extraction de ce commit ; c'est
  l'un des deux tests de jonction que `CLAUDE.md` signale pour le Python 3.9.6
  de macOS). Il est présent au témoin comme à chaque mutant et ne compte pas.

## Les tests contre le code d'avant (`b8010fd`)

Les tests de `tests/test_requetes_malformees.py` et `tests/test_liens_servis.py`
(version finale) joués contre le `serveur.py` de `b8010fd` :
105 échecs et 3 erreurs de test, dans tous les tests annoncés « échoue
aujourd'hui » par le contrat : `test_s1`, `test_s2`, `test_s3`, `test_e2`,
`test_e4`, `test_e5`, `test_e7`, `test_u1`, `test_u2`, `test_u3` (erreur : la
`ValueError` sort), `test_u4`, `test_u5` (erreur : `ECHAPPEMENT_CONTROLE`
n'existe pas), `test_j1`, `test_j2`, `test_g2` réécrit, `test_u10_l_octet_nul…`.
Verts aujourd'hui comme annoncé : `test_e1`, `test_e6`, `test_e8`, `test_a1`,
`test_j3`. `test_e3` passe sous 3.14 et **échoue sous 3.9.6** (6 sous-cas : la
connexion fermée sans un octet, mesurée de nouveau) :

    BILAN_PYTHON_CERTIFICATS=python3 /usr/bin/python3 -m unittest \
      tests.test_requetes_malformees.RequetesMalformees.test_e3_demi_paire_isolee_404
    AssertionError: b'' is not true : silence : aucune réponse à GET /%ed%a0%80.html (None)
    FAILED (failures=6)

Trois tests ajoutés au contrat (`test_u3b`, `test_u6`, `test_u7`/`test_u7b`,
`test_j2b`) ont leurs propres rouges au même commit.

## Résultats des mutations

Tous les témoins rendent `rc=0` (3.14, 3.14 `-O`) ; 3.9 rend `rc=1` à cause du
seul `test_u8` antérieur. Toutes les mutations rendent `rc=1`.

| Id | Mutation | Mode | Tests rouges nouveaux | Attendu |
|---|---|---|---|---|
| M1 | surcharge de `version_string` supprimée | 3.14 et `-O` | `test_s1`, `test_s2`, `test_s3` | conforme |
| M2 | `splitext(chemin)` au lieu de `splitext(fichier)` | 3.14 et `-O` | `test_g2`, `test_e4`, `test_e5`, `test_e7` | conforme (`test_e5` et `test_e7` en plus) |
| M3 | le 400 de l'étape 3.3 supprimé | 3.14 et `-O` | `test_e2`, `test_e7`, `test_g2`, `test_s1` | conforme |
| M4 | le 400 placé avant `authentifie()` | 3.14 et `-O` | `test_a1`, `test_e7`, `test_g2` | conforme |
| M5 | contrôle `os.fsencode` supprimé | 3.14 | `test_u1`, `test_j2b` | conforme |
| M5 | idem | 3.9 | `test_u1` seul ; **`test_e3` reste vert**, le filet de `send_head` rattrape la `ValueError` | conforme (« test_e3 vert avec M5 seule ») |
| M6 | M5 et filet de `send_head` supprimés | 3.14 | `test_u1`, `test_u3`, `test_j2b` | conforme |
| M6 | idem | 3.9 | `test_e3`, `test_e7`, `test_s1`, `test_u1`, `test_u3`, `test_j2b` : **le silence revient** | conforme |
| M7 | surcharge de `list_directory` supprimée | 3.14 | `test_u4` | conforme |
| M8 | règle « route autre » supprimée (`if commande:` → `if True:`) | 3.14 | `test_j1`, `test_u7` | conforme |
| M9 | `.translate(ECHAPPEMENT_CONTROLE)` retiré de `log_message` | 3.14 | `test_j2`, `test_u6` | écart : **`test_u5` ne rougit pas**, voir note 1 |
| M9b *(ajoutée)* | table `ECHAPPEMENT_CONTROLE` vidée (`str.maketrans({})`) | 3.14 | `test_u5`, `test_u6`, `test_j2` | — : celle qui éprouve `test_u5` |
| M10 | `\` échappé aussi (`0x5c` ajouté à la table) | 3.14 | `test_u5` | conforme |
| M11 | `hors-racine` remis pour l'octet nul | 3.14 | `test_u10_l_octet_nul_est_refuse…`, `test_u2`, `test_j2`, `test_j2b` | conforme |

### Notes

1. **M9 ne fait pas rougir `test_u5`**, contrairement au tableau du contrat.
   `test_u5` éprouve la table `ECHAPPEMENT_CONTROLE` (ses 9 bornes et le chemin
   Windows témoin) ; or M9 laisse la table intacte et retire seulement son
   application dans `log_message`. L'application est gardée par `test_u6` (unitaire
   sur `log_message`, simulé) et `test_j2` (le vrai serveur). M9b est ajoutée pour
   que la table elle-même soit éprouvée : `test_u5`, `test_u6` et `test_j2`
   rougissent. Aucune tolérance ajoutée ; trois gardes tiennent le comportement.
2. **M6 sous 3.14 laisse `test_e3` vert** : `realpath` y lève sur la demi-paire,
   et `confiner_sous_racine` l'attrape en `hors-racine`. C'est le comportement
   mesuré par le contrat ; c'est pour cela que M6 est jouée sous 3.9, où `test_e3`
   rougit, et que `test_u1` (qui remplace `realpath`) mord sur toute version.
3. **`test_e7` rougit sous M6 / 3.9** par la ligne `GET /%ed%a0%80.html`, et
   `test_s1` par la même ligne (réponse vide, nommée « silence »), sans erreur de
   test : un silence est un échec nommé.
4. **M2 fait aussi rougir `test_e5`** : `/journal.log%2f.html` redevient 404 au
   lieu de 403 sur la forme brute. `test_e4` rougit comme annoncé
   (`/index%2ehtml` redevient 403).

## Critères d'acceptation

Commandes jouées sur la branche à `deb0295` (code) et ce commit (audit).
[S] = `python3 -W error::ResourceWarning -m unittest tests.test_requetes_malformees tests.test_liens_servis -v`.

| Critère | Commande | Résultat |
|---|---|---|
| A1 | [S], `test_e1` | ok sous 3.14 et 3.9 : 404, corps identique à `/absent.html`, `GET` et `HEAD`, quatre cibles |
| A2 | [S], `test_e1` | ok : `/x%00.log` 403 ; octet nul brut 404 |
| A3 | [S], `test_e3`, `test_e7` | ok sous 3.14 et 3.9 : `/%ed%a0%80.html` 404 en `GET` et `HEAD` ; aucune réponse vide dans la table, ni sur les trois lignes illisibles (code lu dans le corps) |
| A4 | [S], `test_e7` | ok : 54 lignes de la table et 3 lignes illisibles, 8 codes (200, 400, 401, 403, 404, 414, 431, 501), table dérivée du seul `table_a4()` |
| A5 | [S], `test_e8` | ok : 8 fichiers en 200 aux octets identiques à ceux du bac ; `/index.html` encore 200 après toute la table |
| A6 | [S], `test_e6` | ok : sept formes, `GET` et `HEAD`, 301, 403 ou 404 ; aucun `Directory listing` |
| A7 | [S], `test_s1`, `test_s2`, `test_s3` | ok : `Server: bilan-posturo` sur chaque réponse de la table et sur les routes dérivées de l'AST (`/sante`, `/cabinet`, `/etat`), avec et sans identifiants, `GET`, `HEAD`, `POST /depot` ; aucun `Python/\d` ni `platform.python_version()` |
| A8 | `python3 -m unittest tests.test_liens_servis.GardesStructurelles -v` | 5 tests ok ; rouge sous M2, M3 et M4 (voir plus haut) |
| A9 | [S], `test_j1`, `test_j2`, `test_j2b`, `test_j3` | ok : `REPONSE methode=autre route=autre code=414` (et 505, 400), aucune ligne `route=formulaire code=414` ; `lecture refusée motif=forme-invalide` pour `/x%00.json` et `/%ed%a0%80.html` ; aucune ligne du journal ne porte de caractère `0x00-0x1f` ni `0x7f-0x9f` hors du saut de ligne, `\x1b[31m` en clair ; `technique.log` sans chemin ni adresse. Sous Windows, la demi-paire n'est journalisée `forme-invalide` que si `os.fsencode` la refuse (elle s'encode, PEP 529) : voir « Intégration continue » |
| A10 | `python3 -m unittest tests.test_integration -k seule_sante` ; [S], `test_j3` | ok : `Ran 1 test … OK` ; `/sante` sans identifiants n'ajoute aucun octet aux deux journaux. Le test n'a pas été modifié |
| A11 | `git diff b8010fd -- serveur/serveur.py \| grep -E '^\+(import\|from)'` | aucune sortie (code 1) |
| A12 | `git diff b8010fd -- tests/ serveur/ \| grep -E '^\+\s*assert '` ; `python3 -O -W error::ResourceWarning -m unittest discover -s tests` | aucune sortie (code 1) ; `-O` : 473 tests, `OK (skipped=7)` au premier plan |
| A13 | `python3 -W error::ResourceWarning -m unittest discover -s tests` ; `npm test` (arrière-plan) | 473 tests, `OK (skipped=7)` ; `npm test` : code 0, 473 tests Python et toutes les suites Node vertes. CI : voir ci-dessous |
| A14 | ce journal | M1 à M11 (et M9b) : témoin vert, test rouge, code de sortie du processus de test ; M5 et M6 sous 3.9 |
| A15 | `git diff --stat b8010fd -- formulaire/` | vide |

Sous 3.9.6 : [S] rend `FAILED (failures=1, skipped=12)`, l'échec étant le seul
`test_u8` antérieur à la tâche (voir le protocole). Les 12 sauts sont les
tests qui exigent des liens symboliques, une jonction ou Windows.

## Intégration continue

Deux runs, lancés par `env -u GITHUB_TOKEN gh workflow run tests.yml --ref
c6-t5-requetes-malformees`.

**Run `42470153484`** (branche à `deb0295`) : **échec**, deux causes, aucune
n'est un test instable.

- `test (windows-latest, 3.9)` : **panne d'infrastructure**, pas de code.
  `actions/setup-python@v5` a échoué au téléchargement de Python 3.9.13 (« Unexpected
  HTTP response: 504 », trois essais), avant que le moindre test de la tâche ne
  soit joué.
- `test (windows-latest, 3.13)` : deux tests de la tâche rouges, **par erreur
  d'attente de mes tests sous Windows**, pas par défaut du serveur :
  - `test_j2` : `AssertionError: True is not false : caractère de contrôle brut
    '\r' dans "… lecture refusée motif=forme-invalide chemin='/x\\x1b[31m\\x00.html'\r"`.
    Le journal est ouvert en mode texte et se termine par `\r\n` sous Windows : ce
    `\r` est le terminateur du système, non un caractère du client. L'échappement
    avait bien fonctionné (`\x1b[31m\x00` en clair). Le test remplace maintenant
    `os.linesep` par `\n` avant de découper ; un `\r` venu du client resterait
    visible (il est écrit devant son propre terminateur).
  - `test_j2b` : `AssertionError: 1 != 2`. Sous Windows (PEP 529,
    `surrogatepass`), une demi-paire isolée **s'encode** : `os.fsencode` ne lève
    pas, la 404 d'un absent répond, aucun motif n'est journalisé. Le contrat
    (A9) attend `forme-invalide` pour `/%ed%a0%80.html` sans distinguer les
    systèmes, alors que sa propre D5 dit le contraire pour Windows. Le test dérive
    maintenant le nombre attendu d'un essai `os.fsencode` (2 sous POSIX, ancré ;
    1 sous Windows). Le code du serveur n'a pas changé.

**Run `42470497173`** (branche à `8348e30`, après la correction des deux
attentes) : **succès**, 7 jobs sur 7 : `scripts-windows`, `lint`,
`test (ubuntu-latest, 3.9)`, `test (ubuntu-latest, 3.13)`,
`test (macos-latest, 3.13)`, `test (windows-latest, 3.9)`,
`test (windows-latest, 3.13)`.

Après ce second run : `python3 -W error::ResourceWarning -m unittest discover
-s tests` et la même commande sous `-O`, au premier plan : 473 tests,
`OK (skipped=7)` ; `python3 -m pyflakes serveur/ tests/` : rien. `npm test`
a été joué au commit du code (`deb0295`) : code 0, toutes les suites Node vertes
(la correction qui a suivi ne touche que `tests/test_requetes_malformees.py`).
La série de mutations ci-dessus a été rejouée en entier sur le code final : mêmes
listes rouges.
