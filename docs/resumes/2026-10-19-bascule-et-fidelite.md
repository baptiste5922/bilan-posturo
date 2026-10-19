# Session du 19 octobre 2026 — La bascule, et ce que le rendu réel a révélé

**Durée approximative :** une longue session, étalée sur le 16 puis le 19 octobre
**Tâches concernées :** C1-T3b (bascule), prolongement de C1-T3
**Branche :** `main`  **Commits :** `d1cb356`, `0339f17`, `daf60aa`, `3fc0045`

## Ce qui a été fait

Le formulaire de production est passé au moteur. `formulaire/index.html` n'est
plus les 388 lignes de HTML tenues à la main : c'est une coquille de 118 lignes
que `formulaire/moteur/rendu.js` remplit depuis `formulaire/schema.json`. La V1
est conservée octet pour octet dans `formulaire/index-v1.html`, servie — c'est
le repli de niveau 1, et le témoin qui garde les clés de brouillon dans les
tests maintenant que la coquille n'a plus les 45 champs.

Puis, et c'est l'essentiel de la session, **les deux vérifications que la
bascule exigeait ont enfin été menées**, dans un vrai navigateur. Elles ne
devaient pas être automatisables : elles l'ont été. Google Chrome a été installé
sur le poste et piloté par le protocole de débogage, sans aucune dépendance —
Node 24 expose `WebSocket` nativement. Un bilan témoin de six pages a été saisi
sur la V1, son brouillon rejoué sur le moteur, et les deux PDF comparés de trois
façons : structure du document, pixels, puis l'œil sur ce que les deux premières
signalaient.

**La comparaison a trouvé cinq écarts de rendu réels**, tous corrigés depuis, et
tous invisibles aux 115 tests alors au vert :

1. le moteur ajoutait « : » à chaque libellé, alors que le formulaire emploie
   deux conventions — 29 libellés collés, 8 avec l'espace typographique
   française ;
2. il omettait les espaces que le HTML écrit à la main place entre un libellé et
   son champ, ce qui décalait **chaque champ de chaque page** de quelques
   pixels ;
3. il inversait le libellé et la case d'« Empreinte encre » ;
4. il ne reproduisait pas le `<label>` vide qui ouvre les blocs chaussures,
   laissant « Type : » orphelin en fin de ligne ;
5. il n'affichait **pas du tout** le titre « Déjà SO: », laissant deux boutons
   « Oui / Non » sans intitulé — le seul des cinq qu'un praticien aurait vu au
   premier coup d'œil.

Enfin la fiche de secours a été éprouvée de bout en bout, contre un **vrai**
`serveur.py` en HTTPS, derrière authentification, dans un bac à sable : une
saisie commencée sur le moteur se reprend sur la fiche de secours, et le PDF
arrive dans le dossier des bilans.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| **Le moteur n'invente plus ni ponctuation ni structure** : le schéma porte le texte exact qui s'affiche | Toute règle typographique appliquée par le moteur est une divergence en puissance, et elle s'est matérialisée sur 8 libellés | 38 libellés et titres alignés sur le texte réel ; `libelle` est désormais ce qui est rendu, à l'octet près |
| Les deux formes qui ne se déduisaient pas deviennent des **données à valeurs fermées** : `balise` au niveau du bloc, `apparence: titre_avant` sur une case | D9 interdit une table de correspondance par clé **à l'intérieur du moteur** ; un attribut fermé n'est pas une exception, c'est une description | Deux règles de validation de plus (15 et 13 étendue), pas de spécifique client dans le code commun |
| Le seuil du comparateur d'images est ramené à **zéro** | Mesure faite : deux exports successifs de la même page sont rigoureusement identiques. La compression est déterministe, donc rien ne peut être mis sur le compte du bruit | Tout écart non nul est traité comme un défaut |
| **Ne pas versionner** les PDF et captures de référence | Ils portent l'en-tête du cabinet en image, hors de portée de la garde qui ne lit que du texte — or C2-T1 doit justement retirer ces coordonnées du dépôt | Ils vivent dans `~/bilan-posturo-references/` ; seuls le brouillon témoin et l'outillage sont versionnés |
| Réécrire l'historique local plutôt que corriger par-dessus | Le journal de mises en échec contenait le courriel du cabinet, et rien n'était encore poussé | Le commit du moteur a changé d'empreinte ; aucune coordonnée n'est entrée dans l'historique public |
| Fusionner la bascule **avant** les vérifications humaines | Pousser ne livre rien au cabinet : le déploiement passe par un paquet fabriqué et installé à la main | La fenêtre entre la fusion et la livraison est précisément celle où la bascule est sans danger |

## État des tests

Avant la session : 103. Après : **115** — 81 Python (dont `test_coquille.py` et
`test_paquet.py`, nouveaux), 7 Node (file), 8 (palette), 8 (inventaire),
8 (comparaison de DOM), 4 (démarrage du moteur, nouveau).

Ce qui est couvert de nouveau : la coquille et l'empreinte de la fiche de
secours ; la présence obligatoire du moteur et du schéma dans le paquet livré ;
le fait que le message de repli ne disparaisse qu'après le démarrage réel de
l'application ; et la liste des 21 `id` réservés, vérifiée mécaniquement dans
les deux sens.

## Constats de sécurité

Audit de C1-T3b : **NON CONFORME** au premier passage — 1 élevée, 2 moyennes,
4 faibles — puis **CONFORME SOUS RÉSERVE** après correction des huit constats.

Le constat élevé méritait la boucle. La coquille charge deux fichiers
JavaScript au lieu d'un, sans cache, sur le Wi-Fi d'une tablette. Si
`script.js` arrivait tronqué pendant que le moteur arrivait bien, le message
d'attente était **retiré sur la foi du rendu**, pas du démarrage : la
praticienne voyait un formulaire d'apparence normale qui n'écrivait aucun
brouillon, dont le stylet ne marquait pas et dont « Générer le PDF » ne faisait
rien, **sans un mot**. Une heure de saisie perdue au rechargement. C'est pire
qu'un écran blanc, qui au moins renvoie au favori de secours.

Deux fuites de données personnelles ont été interceptées **avant publication** :
l'adresse postale et le courriel du cabinet recopiés dans trois documents, dont
le rapport d'audit lui-même. Rien n'était parti sur GitHub.

Reporté : **C6-T5** (un chemin malformé ferme la connexion sans réponse, défaut
antérieur à ces tâches), et une note sur C2-T1 — deux fichiers HTML portent
l'identité en dur, pas un seul.

## Ce qui reste en suspens

- **Poser le favori « Formulaire — secours V1 » sur la tablette et l'ouvrir une
  fois.** C'est le seul geste de tout le chantier qu'aucune machine ne fera : il
  demande l'appareil. Le chemin qu'il emprunte, lui, est éprouvé.
- **C2-T1** : les coordonnées du cabinet sont en dur dans `index.html` **et**
  `index-v1.html`, dans un dépôt public.
- **C6-T5**, ouverte le 15 octobre.
- `formulaire/index-v1.html` devra disparaître en **C1-T4**, après une campagne
  de bilans réels. Tant qu'il est là, il sert de témoin aux tests : sa
  suppression devra leur trouver une autre ancre.

## Prochaine étape recommandée

`/lancer-tache C2-T1` — sortir l'identité du cabinet du HTML. C'est la dernière
chose qui empêche de dire que le dépôt public ne contient aucune donnée
personnelle, et elle débloque le `theme.json` que C1-T3 a délibérément laissé de
côté.

## À savoir pour la prochaine session

**Le rendu réel voit ce qu'aucun test ne voit.** 115 tests verts, un audit
CONFORME, une revue À LIVRER — et cinq défauts de rendu quand même. Trois
d'entre eux tiennent à des détails que personne n'aurait pensé à tester : une
espace entre deux balises, un `<label>` vide, un deux-points collé. La leçon
n'est pas qu'il fallait plus de tests, mais qu'il fallait **regarder**.

**La répartition d'un écart dit quelle sorte de défaut chercher.** Un écart
concentré en haut de page désignait un élément précis ; un écart réparti sur
toute la hauteur désignait un décalage systématique. C'est cette lecture qui a
guidé l'enquête, bien plus que la moyenne.

**Se méfier de ses propres tolérances.** Le premier verdict automatique disait
« identiques, le reste est du bruit JPEG ». C'était faux : le bruit réel,
mesuré, est nul. Une tolérance inventée pour expliquer un écart est exactement
ce qui fait passer un défaut pour du bruit — le travers reproché aux agents tout
au long de ces tâches, reproduit ici par l'orchestrateur lui-même.

**Chrome se pilote sans rien installer de plus.** Node 24 expose `WebSocket` :
`outils/reference-visuelle/` contient de quoi rejouer toute la comparaison et
l'essai du repli. Deux pièges payés : les coordonnées de
`Input.dispatchMouseEvent` sont relatives à la **zone affichée**, donc il faut
défiler jusqu'à l'élément avant de cliquer ; et Chrome met en cache les
ressources, si bien qu'un PDF régénéré après correction ressortait identique à
l'octet près — `Network.setCacheDisabled` est indispensable.

**Danger permanent : les fichiers réels du cabinet sont à la racine du dépôt.**
`config.json`, `cle.pem`, `autorite-cle.pem`, `journal.log` et `bilans/` y
vivent, ignorés par Git mais bien présents. `serveur.py` et
`generer_autorite.py` calculent leur racine depuis leur propre emplacement :
les lancer depuis le dépôt **écrase ces fichiers**. Tout essai doit se faire sur
une copie, dans un bac à sable — c'est ainsi que l'essai du repli a été mené.

**Les fins de ligne, pour la troisième fois.** Les deux travaux `windows-latest`
ont échoué sur l'empreinte d'un fichier pourtant intact, `actions/checkout`
convertissant les `\n` en `\r\n`. La cause racine est traitée : le dépôt a enfin
un `.gitattributes`.
