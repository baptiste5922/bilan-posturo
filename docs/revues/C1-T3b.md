# Revue C1-T3b — Basculer le formulaire de production sur le moteur

**Date :** 2026-10-15  **Verdict :** À LIVRER
**Tests :** `npm test` → 81 Python (dont les 6 nouveaux de `test_coquille.py`),
7 scénarios de file, 8 groupes de palette, 8 groupes d'inventaire, 8 groupes
de comparaison DOM — tous verts, exécutés par moi. `python3 -m unittest
discover -s tests` → 81/81 OK. `python3 -m pyflakes serveur/ tests/` → aucune
sortie.

Rappel du périmètre : les critères 1 (préalable étape 0), 2 (repli éprouvé,
humain) et 11 (PDF superposable, humain) sont hors de portée de cette passe
et ne sont pas comptés ci-dessous comme des manquements — c'est consigné,
honnêtement et sans détour, dans `docs/audits/C1-T3b-mises-en-echec.md`.

## Critères d'acceptation

| Critère | Vérifié par | Résultat |
|---|---|---|
| 1. Préalable levé | `ls docs/references-visuelles/` | Non levé, hors de portée (assumé) |
| 2. Repli éprouvé avant bascule (humain) | — | Non fait ici, hors de portée (assumé) |
| 3. V1 octet pour octet | `shasum -a 256 formulaire/index-v1.html` | Conforme (`589eee33…958a6e`) |
| 4. La coquille ne contient que l'en-tête | `node tests/test_inventaire_formulaire.js` (8 groupes verts, groupe 8), `diff` des en-têtes | Conforme |
| 5. Protection des clés gelées (7, pas 5 ni 0) | groupe 6 de l'inventaire, mise en échec n°1 relue dans le journal | Conforme |
| 6. Les 21 `id` réservés, liste non menteuse | `python3 -m unittest tests.test_coquille`, mises en échec n°4, `node tests/test_comparaison_dom.js` | Conforme |
| 7. Le paquet contient le moteur | `python3 -m unittest tests.test_paquet`, lecture de `outils/faire-paquet.sh` | Conforme |
| 8. DOM de production ≡ V1 | `node tests/test_comparaison_dom.js` (8 groupes verts, 29 blocs) | Conforme |
| 9. Page provisoire disparue sans référence morte | `test ! -f formulaire/index-moteur.html`, `grep -rn "index-moteur" . --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=docs` | **Presque** — le grep rend une ligne, `CLAUDE.md:96` (voir remarque mineure) |
| 10. Serveur, surface, gardes | suite complète, lecture de `tests.yml` et du journal des mises en échec | Conforme |
| 11. PDF superposable (humain) | — | Non fait ici, hors de portée (assumé) |
| 12. Aucune régression, un seul commit | `npm test`, `git diff --stat HEAD~1 -- tests/test_file_depots.js tests/test_palette.js` (vide) ; commit unique pas encore fait (attend les étapes humaines) | Conforme en l'état actuel, le commit unique reste à faire par Baptiste à l'étape 12 |

## Remarques

### Important — Commentaire devenu faux à `formulaire/script.js:793-797`
**Où :** `formulaire/script.js:793-797`
**Problème :** le commentaire dit « `formulaire/index.html` porte toujours
son `onclick=` (index.html:26, hors périmètre de cette tâche) ». C'est
désormais **faux** au sens strict : depuis la bascule, `formulaire/index.html`
est la coquille et **n'a plus** d'`onclick=` (vérifié : `grep 'id="btn-export"'
formulaire/index.html` ne contient pas `onclick`) — c'est
`formulaire/index-v1.html`, jamais nommé ici, qui le porte. Le code reste
correct (la garde teste `data-moteur`, qui distingue bien les deux pages),
mais quiconque lira ce commentaire pour comprendre pourquoi la garde existe
sera orienté vers le mauvais fichier. C'est précisément le genre de dérive
que C1-T4 (suppression d'`index-v1.html`) devra trancher, et un commentaire
qui pointe déjà vers le mauvais fichier aujourd'hui rend ce travail plus
difficile, pas plus facile.
**Attendu :** une ligne corrigée (« c'est `formulaire/index-v1.html` qui
porte encore son `onclick=` d'origine ») à la prochaine tâche qui touche
`script.js` — l'implémenteur l'a lui-même signalé sans la corriger, à raison
puisque `script.js` n'est pas dans les fichiers touchés de ce contrat ; ne
pas laisser traîner au-delà de C1-T4.

### Mineur — `CLAUDE.md` nomme encore la page provisoire disparue
**Où :** `CLAUDE.md:96`
**Problème :** la commande exacte du critère 9
(`grep -rn "index-moteur" . --exclude-dir=.git --exclude-dir=node_modules
--exclude-dir=docs`) n'est **pas** vide : elle trouve « Le moteur ne se
visite que par `formulaire/index-moteur.html` ». `CLAUDE.md` est hors de ma
compétence de revue et hors du périmètre de ce contrat — il n'est maintenu
que par `/cloture-projet`, et il n'était pas raisonnable que l'implémenteur
le modifie ici. Mais la mention restera fausse jusqu'à la prochaine clôture.
**Attendu :** à signaler à la prochaine exécution de `/cloture-projet`, pour
qu'elle mette à jour la section « pièges connus » en conséquence. Aucune
conséquence en production — ce fichier ne part jamais au cabinet.

## Ce qui est bien fait

- **Discipline de périmètre sur `formulaire/moteur/rendu.js`.** Le diff
  intégral du fichier ne touche que `IDS_RESERVES_COQUILLE`, ses commentaires
  et le texte d'`afficherErreurMoteur()` — vérifié ligne par ligne. Rien
  d'autre n'a bougé dans un fichier audité et revu, exactement comme
  l'exigeait la section 4 du contrat.
- **Non-circularité des tests réellement respectée.** `tests/test_coquille.py`
  et les groupes 1, 6, 7, 8 de `tests/test_inventaire_formulaire.js` gardent
  `formulaire/index-v1.html` comme témoin indépendant des 29 blocs et des 45
  champs, jamais le schéma qu'ils contrôlent par ailleurs — c'était le risque
  que le contrat redoutait le plus, et ce n'est pas arrivé. Le groupe 6 en
  particulier redevient vert *avec contenu* (7 `id` exigés) plutôt que vert à
  vide, et le groupe 7 rend l'exception `date-bilan` non vacante.
- **L'inversion du paquet (`outils/faire-paquet.sh`, `tests/test_paquet.py`)
  vérifie l'archive elle-même**, pas seulement l'absence des anciens `rm` —
  exactement la discipline que le contrat demandait pour le risque le plus
  grave (« formulaire vide au cabinet »).
- **Le journal des mises en échec est honnête et complet** :
  `docs/audits/C1-T3b-mises-en-echec.md` documente, avec commande et sortie,
  les six scénarios de l'étape 11, et refuse explicitement de simuler les
  étapes humaines (0, 3, 12) plutôt que de les cocher sans les faire. C'est
  exactement la rigueur que ce contrat, plus que tout autre, exigeait.

## Documentation à mettre à jour

- Aucune action requise de ma part ici : `docs/Mode_emploi.md`,
  `docs/USER-GUIDE.md` et `README.md` sont à jour et conformes à la section 10
  du contrat (encadré de quatre lignes, aide-mémoire, arborescence). Le
  français reste la source, l'anglais la traduction fidèle.
- `CLAUDE.md` (hors de ma compétence) reste à corriger à la prochaine
  `/cloture-projet` — voir remarque mineure ci-dessus.
