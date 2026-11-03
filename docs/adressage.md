# Adressage et certificat : la voie retenue

> **Objet.** Trancher, pour la V2, comment une tablette atteint le serveur du
> cabinet en HTTPS sans avertissement de sécurité. C'est la tâche **C3-T1** de
> `docs/ROADMAP.md`, et elle est bloquante : se tromper ici fait refaire
> l'installateur entier.
>
> **Document de décision interne.** Il remplace toute discussion antérieure sur
> le sujet. Ce qui est écrit ici se corrige vers l'avant, par un autre document
> daté ; il ne se renégocie pas au moment de coder.

**Date :** 19 octobre 2026
**Niveau de process :** Direct — étude et décision, aucune ligne de code.

---

## 1. La décision, en une page

**Voie retenue : n°2 — adresse IP privée fixe + autorité de certification
locale.** C'est l'existant, conservé délibérément, et non par défaut.

**Coût récurrent par cabinet : 0 €.** Pas de domaine, pas de compte DNS, pas de
VPS, pas d'autorité publique. Le seul coût est du support occasionnel, estimé
en §6.

**Gestes à la charge du praticien : aucun**, ni à l'installation ni à l'usage.
Les deux gestes techniques — fixer le bail DHCP dans la box, installer le
certificat racine sur la tablette — sont faits **par l'installateur, une fois,
sur place ou en prise en main à distance**. Ils ne reviennent jamais en usage
normal. Un seul événement les rappelle : le remplacement de la box par
l'opérateur, traité en §6.

**Ce qui a fait basculer la décision** n'est aucun des deux critères attendus
(ni le coût, ni le nombre de gestes), mais deux constats de fiabilité :

1. **Un nom public qui résout vers une adresse privée n'est pas fiable en
   France.** Les résolveurs IPv4 de Free refusent cette résolution — c'est
   constaté, pas supposé (§3.1). La voie n°1 échangeait un geste
   d'installation, fait une fois, contre une dépendance permanente au résolveur
   DNS du réseau *et* de l'appareil.
2. **La voie n°1 rend un usage purement local dépendant d'Internet.** Box en
   panne, le nom ne résout plus, et la tablette n'atteint plus un PC situé à
   deux mètres sur le même Wi-Fi. Pour un produit dont l'argument est
   « local-first », c'est une régression de fiabilité qu'aucune économie de
   geste ne rachète.

S'y ajoute un argument de durée : les certificats publics tombent à **100 jours
en mars 2027 et 47 jours en mars 2029** (§3.4). Une autorité locale installée à
la main est explicitement exemptée de cette trajectoire.

---

## 2. Ce que le cabinet pilote prouve déjà

La voie n°2 tourne en production depuis août 2026, pour la totalité des bilans
d'un cabinet. Ce n'est pas une hypothèse à instruire : c'est la seule des trois
voies dont on possède une preuve d'usage réel.

Ce qu'elle établit :

- Chrome sur Android **fait confiance à une autorité installée par
  l'utilisateur** pour la navigation, et le formulaire s'ouvre sans
  avertissement. (Les applications Android, elles, ignorent les autorités
  utilisateur depuis Android 7 ; le formulaire n'est pas une application.)
- Un certificat serveur portant l'adresse IP en `subjectAltName` est accepté
  (`serveur/generer_autorite.py:144-170`).
- L'installation de la racine est désagréable mais faisable : elle est enfouie
  dans les réglages Android et affiche un avertissement de surveillance
  réseau. **C'est un geste d'installateur, pas un geste de praticien.**

Ce qu'elle n'établit pas, et qui reste à traiter en C3-T3 : que ce geste tienne
sur une tablette gérée par un tiers, et que l'IP fixe survive au remplacement
de la box.

---

## 3. Les trois voies, instruites

### 3.1 Voie n°1 — sous-domaine réel + Let's Encrypt par challenge DNS-01

L'idée : `cabinet-exemple.cabinets-exemple.fr` résout vers `192.168.1.13`, le
certificat est émis par Let's Encrypt via un enregistrement TXT
`_acme-challenge` public. La tablette fait confiance nativement : zéro
manipulation de certificat.

Le mécanisme est correct. DNS-01 ne vérifie **pas** l'enregistrement A : un nom
peut donc être certifié alors qu'il résout vers une adresse privée et que le
serveur est injoignable depuis Internet. Le cabinet n'est pas exposé.

**Ce qui l'invalide — le point que la feuille de route désignait comme pouvant
tout invalider, et qui tombe :**

La protection anti-rebinding DNS n'est pas une menace théorique, c'est un
comportement répandu et déjà observé chez un opérateur français majeur. Les
résolveurs IPv4 de Free **refusent de résoudre un nom public vers une adresse
RFC1918** ; les mêmes résolveurs interrogés en IPv6 l'acceptent, ce qui rend la
panne intermittente et incompréhensible pour un praticien. C'est, au passage,
le pire mode de défaillance possible : pas une erreur franche, une
inconsistance.

Le mécanisme est documenté comme recommandation de sécurité générale, pas comme
un bug : un résolveur retire des réponses publiques les adresses privées, parce
qu'une réponse publique ne devrait jamais en contenir. `dnsmasq`
(`--stop-dns-rebind`), Unbound (`private-address`), pfSense et la plupart des
résolveurs filtrants l'implémentent. Les box d'opérateur interceptent par
ailleurs les requêtes DNS du réseau local, ce qui empêche de contourner leur
résolveur sans reconfigurer chaque appareil.

Les contournements existent et ils sont tous mauvais :

| Contournement | Pourquoi il ne tient pas |
|---|---|
| Changer les DNS de la box pour `1.1.1.1` ou `8.8.8.8`, qui ne filtrent pas | Dépend du modèle de box — la Livebox ne le permet pas toujours — et se perd au remplacement de la box. Modifie un réglage réseau du cabinet pour notre seul confort. |
| Régler le **DNS privé** d'Android (DoT) vers un résolveur non filtrant | Réglage **global de l'appareil**, pas par réseau : il suit la tablette partout. C'est exactement le « geste à la charge du praticien » qu'on voulait supprimer, et il est réversible par inadvertance — avec, à la clé, une panne le lendemain matin. |
| Résolution locale (enregistrement DNS dans la box, fichier `hosts`) | Les box d'opérateur ne permettent généralement pas d'ajouter un enregistrement arbitraire, et Android n'a pas de fichier `hosts` modifiable sans root. |

**Deux défauts supplémentaires, indépendants du DNS :**

- **Dépendance à Internet pour un usage local.** Sans accès Internet, le nom ne
  résout plus et le formulaire devient inatteignable, alors que les deux
  appareils sont sur le même réseau. La voie n°2 continue de fonctionner box
  débranchée.
- **Publication de la liste des clients.** Tout certificat Let's Encrypt est
  versé aux journaux de *Certificate Transparency*, publics et indexés :
  `cabinet-exemple.cabinets-exemple.fr` y resterait consultable à jamais, révélant
  l'existence et la localisation de chaque cabinet client. Aucune donnée de
  santé ne fuit, mais la liste commerciale et la cartographie du parc, oui. Un
  certificat *wildcard* par cabinet masquerait le sous-domaine ; c'est une
  atténuation, pas une annulation.

**Coût si on l'avait retenue :** un domaine ~12 €/an pour tout le parc, un
compte DNS automatisable (Cloudflare gratuit), et un serveur `acme-dns`
hébergé — ~60 €/an de VPS. Soit ~1,50 €/cabinet/an à cinquante cabinets. Le
coût direct n'est pas le problème ; le coût d'une installation qui échoue sur
place l'est.

**Ce qu'il faut lui reconnaître.** La voie n°1 a une bonne réponse au problème
des identifiants DNS, et elle est à retenir si la réserve du §7 s'active :
`acme-dns`. Le cabinet ne reçoit pas les identifiants du domaine maître — qui,
dupliqués sur cinquante PC, exposeraient la zone entière — mais seulement de
quoi écrire **un unique enregistrement TXT déjà délégué publiquement**. Un
`CNAME` posé une fois suffit. Limite connue : un seul `CNAME` par nom, donc un
seul client ACME par cabinet, ce qui nous va.

### 3.2 Voie n°2 — IP privée fixe + autorité locale — **retenue**

L'existant, décrit en §2. Son coût apparent est l'installation de la racine ;
ses avantages réels sont ailleurs :

- **Aucune dépendance externe.** Ni Internet, ni DNS, ni autorité publique, ni
  compte tiers. Le cabinet fonctionne isolé.
- **Aucune limite de durée imposée.** Voir §3.4.
- **Aucun secret d'API DNS sur le poste d'un client.** C'est un risque entier
  que la voie n°1 introduisait et que celle-ci n'a pas.
- **Rien de public.** Aucun nom de cabinet n'est publié où que ce soit.
- **Le renouvellement devient hors ligne et trivial.** La clé de l'autorité est
  déjà sur le PC : réémettre le certificat serveur ne demande ni réseau, ni
  compte, ni challenge. C'est ce qui reconfigure C3-T2 (§5).

Ses deux vraies faiblesses, assumées et outillées :

1. **L'IP doit rester stable**, ce qui dépend d'une box que l'on ne connaît pas
   à l'avance. C'est le sujet réel de l'installateur, bien davantage que le
   certificat.
2. **La racine locale doit être installée sur chaque appareil.** Un appareil
   supplémentaire, c'est un geste supplémentaire. Acceptable à un ou deux
   appareils par cabinet ; bloquant sur une flotte gérée en MDM (§7).

### 3.3 Voie n°3 — mDNS `.local`

**Écartée, et non réinstruite.** Aucune garantie de résolution par Chrome sous
Android. La feuille de route demandait de ne pas la réouvrir sans élément
nouveau ; il n'y en a aucun.

### 3.4 Durée de validité : l'argument qui n'était pas prévu

Le CA/Browser Forum a adopté la réduction progressive de la durée des
certificats publics (scrutin SC-081v3) :

| Date | Durée maximale d'un certificat **public** |
|---|---|
| 15 mars 2026 | 200 jours *(déjà en vigueur)* |
| 15 mars 2027 | 100 jours |
| 15 mars 2029 | 47 jours |

Retenir la voie n°1 nous attachait à cette cadence : à l'horizon 2029, un
renouvellement automatisé tous les 47 jours, dépendant d'Internet et d'un
compte DNS, sur chaque PC de cabinet, chaque échec étant un cabinet à l'arrêt
un matin.

Cette trajectoire **ne s'applique pas** à une autorité locale : la limite
historique de 398 jours, comme celles qui la suivent, ne vise que les autorités
présentes par défaut dans le navigateur. Chrome documente explicitement
l'exemption des autorités exploitées localement et installées à la main. Les
825 jours de `JOURS_SERVEUR` restent donc valides — et le commentaire du code
qui les justifie par « la limite acceptée par les navigateurs récents » mérite
d'être reformulé : ce n'est pas la limite des navigateurs, c'est le choix d'une
autorité privée qui n'y est pas soumise.

---

## 4. Gestes restant à la charge du praticien

Le critère d'acceptation demandait cette liste, « idéalement vide ».

**En usage normal : vide.** Le praticien ouvre un favori.

**À l'installation : vide pour lui**, deux gestes pour l'installateur —
fixer le bail DHCP dans la box, installer la racine sur la tablette.

**Un seul événement le sollicite :** le remplacement de la box par l'opérateur,
qui perd le bail fixe. Le formulaire devient inatteignable, et le geste attendu
du praticien se réduit à un appel. Le reste se fait à distance (§6).

---

## 5. Ce que cette décision change dans la feuille de route

- **C3-T2 — Renouvellement du certificat** change de nature et d'effort. Elle
  était écrite autour d'un client ACME DNS-01 (effort L) ; elle devient une
  réémission **hors ligne** depuis l'autorité locale déjà présente : plus de
  challenge, plus de compte DNS, plus de secret d'API à protéger, plus de
  dépendance réseau. Deux déclencheurs, et le second est le vrai sujet :
  l'approche de l'expiration, et **le changement d'adresse IP du PC**. Les
  critères « renouvelé sans intervention », « échec visible à distance avant
  l'expiration » et « le serveur ne démarre jamais sans certificat valide »
  restent entiers. Le point 4 de son périmètre — garder le secret de l'API DNS
  hors du dépôt — devient sans objet.
- **C3-T3 — Installateur** garde son périmètre, avec un ordre de priorité
  clarifié : l'IP fixe et l'installation de la racine sont ses deux vrais
  livrables, pas des détails de fin de procédure. Son critère « la tablette
  atteint le formulaire sans avertissement de sécurité » est atteignable tel
  quel.
- **C3-T4 — Recette** doit vérifier explicitement deux points que cette
  décision rend critiques : que le bail DHCP est bien fixé dans la box (et non
  seulement que l'adresse est la bonne aujourd'hui), et que la racine est
  installée sur **tous** les appareils du cabinet, pas seulement celui qui a
  servi à l'essai.
- **C4-T3 et C4-T5** gagnent en importance : le diagnostic à distance est ce
  qui rend la faiblesse n°1 de la voie n°2 supportable (§6).
- Aucune autre tâche n'est touchée. Rien dans `serveur/` ne change du fait de
  cette décision seule.

---

## 6. Le coût réel : le remplacement de la box

C'est le seul coût récurrent de la voie retenue, et il faut l'écrire plutôt que
de le découvrir.

**Événement.** L'opérateur remplace la box ; le bail DHCP fixe disparaît ; le
PC prend une autre adresse. Le favori de la tablette ne répond plus. Le
certificat serveur, lui, ne porte plus la bonne adresse : il faut le réémettre.

**Fréquence estimée.** Une box est remplacée tous quatre à cinq ans, soit
~0,2 incident par cabinet et par an.

**Traitement.** Il se fait entièrement à distance, à deux conditions qui sont
déjà des tâches de la feuille de route :

- le réseau privé de support (**C4-T5**) ne dépend pas de l'adresse du LAN : il
  reste joignable précisément quand l'adresse locale a changé ;
- la page de diagnostic (**C4-T3**) affiche l'adresse courante et la validité du
  certificat, donc l'incident se nomme en une minute au lieu de se deviner.

Avec ces deux-là, l'intervention est : refixer le bail, réémettre le certificat
(automatique après C3-T2), vérifier le favori. **Sans elles**, c'est un
déplacement — et c'est pourquoi cette décision rend C4-T3 et C4-T5 moins
optionnelles qu'elles n'en avaient l'air.

**Coût annuel équivalent :** de l'ordre de quelques euros par cabinet et par
an, contre un déplacement — plusieurs dizaines d'euros et un créneau — si le
support à distance n'existe pas.

---

## 7. La réserve, et quand elle s'active

La voie n°2 a une limite nette : **elle suppose qu'on puisse installer une
autorité sur les appareils du cabinet.** Le jour où un client s'y refuse ou ne
le peut pas — tablette gérée par un prestataire, flotte sous MDM, politique
d'entreprise, plusieurs praticiens avec leurs appareils personnels — elle ne
s'applique plus, et la voie n°1 redevient la bonne réponse **pour ce client**.

Dans ce cas, et seulement dans ce cas : un domaine dédié, `acme-dns` hébergé
par l'atelier, un `CNAME` posé une fois par cabinet, des certificats *wildcard*
pour ne pas publier le nom du client, et le DNS privé de l'appareil réglé vers
un résolveur non filtrant si celui du réseau filtre. C'est une voie de
repli documentée, pas un second chemin principal : la maintenir réellement
testée coûterait plus que ce qu'elle rapporte avant qu'un client ne la réclame.

**Avant de l'activer, l'essai qui tranche** — vingt minutes, à faire sur le
réseau du client concerné, et pas ailleurs :

1. Faire résoudre, depuis la tablette **sur le Wi-Fi du cabinet**, un nom
   public pointant vers une adresse RFC1918. Un nom de test suffit.
2. Vérifier la réponse en IPv4 **et** en IPv6 : le constat Free montre que les
   deux peuvent différer, et qu'une réponse correcte sur l'une ne garantit rien.
3. Recommencer avec le DNS privé d'Android désactivé, puis activé.
4. Débrancher la liaison Internet de la box et refaire l'essai : c'est le
   scénario de panne, et il doit être connu avant de vendre, pas après.

Un seul de ces quatre essais qui échoue disqualifie la voie n°1 chez ce client.

---

## 8. Sources

Les faits de ce document, et où les revérifier.

- Protection anti-rebinding comme pratique recommandée des résolveurs, et
  plages filtrées (RFC1918, loopback, link-local) :
  [pfSense — DNS Rebinding Protections](https://docs.netgate.com/pfsense/en/latest/services/dns/rebinding.html),
  [Control D — DNS Rebind Protection](https://docs.controld.com/docs/dns-rebind-option),
  [DNS rebinding (Wikipédia)](https://en.wikipedia.org/wiki/DNS_rebinding).
- **Constat sur un opérateur français** — les résolveurs IPv4 de Free refusent
  un nom public vers une IPv4 privée, les IPv6 l'acceptent :
  [Univers Freebox — résoudre une entrée avec une IPv4 privée](https://forum.universfreebox.com/viewtopic.php?t=49057).
  Interception des requêtes DNS du réseau local par la box, et limites de la
  Livebox : [Livebox limitée, aidons-la avec Dnsmasq](https://www.metal3d.org/blog/2025/livebox-limit%C3%A9e-aidons-la-avec-dnsmasq/).
- DNS-01 ne vérifie pas l'enregistrement A, donc certifie un nom résolvant en
  privé ; et le renouvellement manuel n'est pas automatisable :
  [Let's Encrypt Community — home server with private IP](https://community.letsencrypt.org/t/home-server-with-private-ip-address/184666),
  [Set up Let's Encrypt on an intranet website](https://davidaugustat.com/web/set-up-lets-encrypt-on-intranet-website).
- `acme-dns` : identifiants limités à un unique enregistrement délégué, et la
  limite d'un seul `CNAME` par nom :
  [EFF — Securing the automation of ACME DNS challenge validation](https://www.eff.org/deeplinks/2018/02/technical-deep-dive-securing-automation-acme-dns-challenge-validation),
  [draft-ietf-acme-dns-account-label](https://datatracker.ietf.org/doc/html/draft-ietf-acme-dns-account-label).
- Réduction de la durée des certificats publics (SC-081v3), calendrier 200 /
  100 / 47 jours :
  [SSL.com — SSL certificate validity changes](https://www.ssl.com/article/ssl-certificate-validity-changes-what-you-need-to-know/),
  [Sectigo — 200-day certificates](https://www.sectigo.com/blog/200-day-certificate-expiration-begins).
- Exemption des autorités locales installées à la main :
  [Chromium — Certificate Lifetimes](https://chromium.googlesource.com/chromium/src/+/HEAD/net/docs/certificate_lifetimes.md),
  [Chrome Root Store — FAQ](https://chromium.googlesource.com/chromium/src/+/main/net/data/ssl/chrome_root_store/faq.md).
