# Session des 19-20 octobre 2026 — L'adressage tranché, et un journal que l'éditeur peut lire

**Durée approximative :** deux demi-journées, à cheval sur deux jours, avec deux
interruptions par limite de session en pleine implémentation.
**Tâches concernées :** C3-T1 (livrée), C4-T1 (livrée)
**Branches :** `c3-t1-adressage`, `c4-t1-journal-technique`, intégrées dans `main`
**Commits :** `46dfafb`, `c33ed9b`, `265b91f` — non poussés

## Ce qui a été fait

La session commence par un constat de blocage : le chantier C1 n'attend plus du
code mais le terrain. C1-T3b est livrée dans le dépôt à un geste près — poser le
favori de secours sur la tablette — et C1-T4 a pour critère d'acceptation une
semaine de bilans réels sans régression. Rien de cela ne s'écrit à la machine.
Le travail utile était donc ailleurs, et c'est ce qui a orienté toute la séance.

**C3-T1 — l'adressage.** La feuille de route présentait la voie du sous-domaine
public certifié par Let's Encrypt comme celle du « zéro manipulation », et
l'autorité locale comme le pis-aller dont il fallait sortir. L'étude a renversé
ce classement, et le point que la feuille de route elle-même désignait comme
« pouvant tout invalider » s'est invalidé contre elle : un nom public qui résout
vers une adresse privée n'est pas fiable en France. Les résolveurs IPv4 de Free
le refusent, leurs IPv6 l'acceptent, et la panne est donc intermittente — le
pire mode de défaillance possible chez un praticien. Deux défauts non prévus ont
achevé la comparaison : cette voie rendait un usage purement local dépendant
d'Internet, de sorte qu'une box en panne coupe l'accès à un PC situé à deux
mètres sur le même Wi-Fi ; et elle publiait la liste des cabinets clients dans
les journaux de *Certificate Transparency*, consultables à jamais. S'y ajoute
une trajectoire que personne n'avait regardée : les certificats publics passent
à 100 jours en mars 2027 et 47 jours en mars 2029, et une autorité locale
installée à la main en est explicitement exemptée. La voie n°2 est donc retenue
délibérément, et non par défaut : zéro euro par cabinet et par an, aucun geste à
la charge du praticien. Décision écrite et sourcée dans `docs/adressage.md`.

**C4-T1 — le journal technique.** `technique.log` vit désormais à la racine du
cabinet, à côté du journal nominatif : huit événements à vocabulaire fermé, la
rotation du premier journal *partagée* et non réécrite, et un interrupteur
`journal_technique` qui rend en trente secondes le comportement d'avant la
tâche. La tension que le cadrage avait identifiée d'avance — interdire les
adresses IP dans un fichier conçu pour circuler, tout en rendant diagnosticable
à distance un changement d'adresse du PC — est tranchée par la négative, puis
contournée par l'empreinte du certificat : il porte l'adresse en
`subjectAltName`, donc il change avec elle. La praticienne apprend enfin
l'existence de ce fichier dans les quatre documents qui la concernent, avec ce
qui en fait l'intérêt : `journal.log` ne quitte jamais le cabinet,
`technique.log` le peut.

## Décisions prises

| Décision | Raison | Conséquence |
|---|---|---|
| Voie d'adressage n°2 : IP privée fixe + autorité locale | Le nom public vers adresse privée est intermittent en France ; dépendance à Internet pour un usage local ; liste clients publiée en CT ; durée des certificats publics qui tombe à 47 jours | C3-T2 change de nature et passe de L à M ; C4-T3 et C4-T5 deviennent moins optionnelles |
| Garder la voie n°1 en réserve documentée, non maintenue | Elle redevient la bonne réponse pour un client dont les appareils n'admettent pas l'installation d'une autorité | Un protocole d'essai de vingt minutes est écrit, à dérouler le jour où le cas se présente |
| Aucune adresse dans `technique.log`, pas même celle du serveur | Une exception exprimable est une exception contournable : au cabinet les deux adresses ne diffèrent que du dernier octet, en test les deux valent `127.0.0.1` | L'adresse courante relève exclusivement de C4-T3 |
| Ne pas commiter les deux `.ps1` que `git diff` affiche modifiés | Divergence latente de normalisation, antérieure à la session et sans rapport avec les tâches | Versée dans C6-T4, à corriger dans un commit isolé |
| Ne pas enchaîner sur C1-T4 | Ses critères d'acceptation exigent le terrain, pas du code | Le chantier C1 attend un passage au cabinet |

## État des tests

**116 au départ** (81 Python + 35 Node), **134 à l'arrivée** (99 Python + 35
Node), tous verts — et désormais vérifiés **aussi sous `python3 -O`**, ce qui
n'était pas fait auparavant.

Ce qui est couvert de nouveau : la non-identification du journal technique sur
l'intégralité du fichier et à la fin de tous les échanges ; les chemins
hostiles, y compris un nom de patient porté par la seule URL ; l'échec
d'écriture survenant au renommage, seul cas où l'erreur système porte le nom du
patient ; le code de réponse réel ; l'arrêt du serveur ; l'interrupteur de
retour arrière ; et un `technique.log` réenregistré dans un autre encodage.

## Constats de sécurité

**C3-T1** — process Direct, aucun audit : une étude ne s'audite pas.

**C4-T1** — audit en deux passes. La première rend **CONFORME SOUS RÉSERVE** :
une élevée, deux moyennes, quatre faibles. L'élevée valait sa gravité :
`verdict_certificat()` ne rattrapait qu'`OSError` autour d'une lecture en UTF-8,
or `UnicodeDecodeError` dérive de `ValueError` — et c'était sa propre ligne de
démarrage, avec son « é », qui fournissait l'octet fautif. Un fichier conçu pour
circuler finit réenregistré en ANSI par quelqu'un ; le serveur mourait alors au
démarrage suivant, sous `pythonw` en SYSTEM, sans console et sans un mot. La
seconde passe rend **CONFORME**, zéro constat au-dessus de faible.

Reportés, tous faibles et hors périmètre : le doublement des lignes `REPONSE`
(vers C4-T2), les fragments de nom de trois caractères, un test sans effet si
l'utilisateur est privilégié, et la ligne `ARRET` qui n'existera presque jamais
au cabinet puisque `TerminateProcess` n'exécute pas le `finally` (vers C4-T3 et
C4-T4).

## Ce qui reste en suspens

- **Le geste du cabinet**, inchangé depuis la veille : poser le favori
  « Formulaire — secours V1 » sur la tablette et l'ouvrir une fois. Il demande
  l'appareil. Tant qu'il n'est pas fait, rien ne part au cabinet et C1-T4 ne peut
  pas commencer.
- **La divergence de normalisation des deux `.ps1`** : à corriger par un
  `git add --renormalize` isolé, jamais mêlé à une tâche, et à vérifier contre le
  test qui exige CRLF et BOM sur le disque. Versée dans C6-T4.
- **Le flake de `ServeurArret`**, un échec sur soixante : cause mesurée, risque
  en production nul, critère de discrimination écrit. Versé dans C7-T5.
- **La contradiction sur l'adresse dans `/etat`**, introduite par
  `docs/adressage.md` et inscrite sur C4-T3 : la feuille de route lui interdit
  toute adresse IP, le document de décision attend qu'il affiche l'adresse
  courante. À arbitrer dans son contrat, pas par omission.

## Prochaine étape recommandée

`/lancer-tache C4-T3` — la page de diagnostic authentifiée. Elle est la moitié
de ce qui rend le coût récurrent de la voie d'adressage retenue traitable à
distance, elle s'appuie directement sur le journal livré aujourd'hui, et son
contrat devra trancher la contradiction ci-dessus.

## À savoir pour la prochaine session

**Le motif « un garde-fou non mis en échec ne garde rien » s'est présenté quatre
fois sur la seule C4-T1.** C'est l'enseignement de la séance, et il coûte cher
chaque fois : le premier test anti-fuite ne mordait pas sur `str(erreur)`, parce
que l'échec d'écriture survient au `mkstemp`, dont le chemin porte le fichier
temporaire et non le nom du patient ; rien n'ancrait les lignes `REPONSE`, par
lesquelles la détection passe, de sorte que la garde pouvait maigrir en silence ;
la garde finale reposait sur des `assert` nus et s'évaporait sous `python -O` ;
et la liste des noms à vérifier, tenue à la main, manquait déjà un dépôt présent
dans le dépôt. Aucun de ces quatre n'a été trouvé par la suite de tests : trois
par mutation volontaire, un par la revue. Le dernier s'est refermé en dérivant
les noms du contenu réel de `bilans/` plutôt qu'en les énumérant — refuser la
correction au cas particulier est ce qui a payé.

**Un agent interrompu laisse son chantier ouvert.** Deux limites de session ont
coupé l'implémenteur en pleine procédure de mutation volontaire. La première
fois, il a laissé **une fuite d'adresse IP active dans le code** : la mutation
était en place et le code n'était pas commité. La règle qui en sort : copier le
fichier hors du dépôt avant toute mutation et restaurer par `cp`, jamais par
`git checkout`, qui aurait effacé les 235 lignes d'implémentation non commitées.
Et au retour d'un agent interrompu, la première chose à vérifier est l'absence
de mutation résiduelle, avant toute autre question.

**`grep` est aliasé vers `ugrep --ignore-files` dans cet environnement.** Mes
premières recherches sont revenues vides sur un fichier qui contenait pourtant
le motif, et j'ai cru pendant plusieurs minutes que l'implémentation avait été
effacée. C'est `git status` qui a révélé la contradiction. Passer par
`/usr/bin/grep` pour tout contrôle dont la réponse décide de quelque chose.

**Une copie de bac à sable par `tar` ou `cp -r` emporte les données réelles du
cabinet.** L'auditeur l'a fait et s'est retrouvé avec les clés privées, la
configuration, le journal et un PDF de bilan réel dans son dossier de travail ;
il l'a déclaré et purgé de lui-même. Vérifié : les originaux sont intacts, et
aucune copie ne subsiste — toutes les clés trouvées dans les bacs ont des
empreintes distinctes de la vraie. La bonne voie est `git ls-files -z`, que le
dépôt connaissait déjà, mais pour une autre raison (l'échappement des noms non
ASCII). Le contrat disait « copier le dépôt » sans dire comment, et aucun
garde-fou mécanique ne l'empêche.

**Se méfier des explications commodes, y compris des siennes.** L'implémenteur a
rangé un échec intermittent sous « instabilité connue du harnais », alors que
l'entrée de `CLAUDE.md` visait une autre classe de test. J'ai avancé à mon tour
une hypothèse — le verrou du journal tenu pendant l'arrêt — que l'auditeur a
écartée par la mesure : la cause est le tube `stdout=PIPE` qui se remplit, et
`journaliser()` écrit sur `stderr` **hors** du verrou. Trois explications
plausibles, une seule mesurée. Et je n'avais pas capturé la sortie de l'échec que
j'avais moi-même observé, donc je ne pouvais pas le rattacher à la cause : un
échec intermittent se capture au moment où il tombe, sinon il ne compte pas.

**Deux critères du contrat de C4-T1 étaient faux**, et le code avait raison : un
`grep -c` qui comptait une mention en docstring préexistante, et un décompte de
tests annoncé à sept pour une classe qui en a six. Vérifier un critère chiffré
contre le dépôt avant de le graver — un critère faux fait corriger du code qui
n'a rien.
