# Bilan posturologique — mode d'emploi

Système de saisie des bilans sur tablette, avec enregistrement automatique sur
le PC du cabinet.

---

## 1. Chaque matin — rien à faire

Le serveur démarre avec le PC et se relance tout seul s'il s'arrête. Aucune
fenêtre à ouvrir, rien à laisser tourner.

### Vérifier qu'il répond, en cas de doute

Depuis la tablette ou depuis le PC, ouvrir :

```
https://192.168.1.13:8000/sante
```

La réponse `{"etat":"ok"}` signifie que le serveur tourne. C'est la seule
vérification utile : elle répond même sans identifiant.

### Le relancer à la main

Si la tablette n'arrive pas à se connecter, sur le PC, dans PowerShell :

```powershell
Start-ScheduledTask -TaskName BilanPosturo
```

Pour voir un éventuel message d'erreur, double-cliquer plutôt sur
`demarrer-serveur.bat` : le serveur s'exécute alors dans une fenêtre visible.

| Message | Que faire |
|---|---|
| `Port 8000 indisponible` | Le serveur tourne déjà, il n'y a rien à faire. |
| `certificat.pem introuvable` | Voir la section Maintenance. |
| `config.json absent` | Voir la section Maintenance. |
| `Refus de démarrer : le dossier formulaire mène…` | Voir la section Maintenance ; ne pas déplacer ni remplacer le dossier `formulaire` par un raccourci. |

---

## 2. Pendant la consultation — remplir le bilan

Sur la **tablette**, toucher le raccourci **Bilan posturo** sur l'écran
d'accueil.

Au premier lancement de la journée, la tablette demande un identifiant et un
mot de passe : ce sont ceux du cabinet, à saisir une seule fois par session.

Remplir le formulaire. Les annotations au stylet sur les schémas de squelette
et les empreintes sont enregistrées dans le PDF final.

> **Le brouillon est sauvegardé automatiquement.** Si la tablette s'éteint ou
> que Chrome se ferme, la saisie est proposée à la reprise au lancement
> suivant.

> **Si le formulaire ne s'affiche pas, ou qu'un message rouge le dit,**
> toucher le favori **« Formulaire — secours V1 »** — ou, s'il a disparu,
> ajouter `index-v1.html` à la fin de l'adresse habituelle. C'est le même
> formulaire, le même brouillon, le même dépôt ; la saisie en cours est
> reprise.

---

## 3. En fin de consultation — générer le bilan

Toucher le bouton de génération du PDF en bas du formulaire. Deux choses se
produisent :

1. Le PDF part vers le PC et arrive dans `C:\Bilan_entrants`
2. Une copie est téléchargée sur la tablette

Un bandeau de couleur confirme le résultat :

- **Vert** — le bilan est arrivé sur le PC. Tout va bien.
- **Orange** — le serveur du cabinet ne répondait pas. Le bilan est conservé
  sur la tablette et **partira tout seul** dès que le serveur répondra. Il n'y
  a rien à refaire, et surtout pas à regénérer le PDF.
- **Rouge** — la création du PDF a échoué, ou le PC a refusé le fichier. La
  saisie n'est pas perdue : réessayer.

Tant qu'un bilan attend, un bandeau reste affiché en haut de la page et
indique combien il en reste. Le bouton **Réessayer maintenant** force une
tentative sans attendre.

> **Ce qui garde les bilans en attente, c'est la page ouverte.** Les bilans
> sont conservés dans la tablette et survivent à une fermeture de Chrome,
> mais l'envoi ne reprend qu'au rechargement du formulaire. En fin de journée,
> laisser la page ouverte jusqu'à disparition du bandeau.

---

## 4. En fin de journée — classer les bilans

C'est l'étape à ne pas oublier. Elle prend deux minutes.

### Sur le PC

Ouvrir `C:\Bilan_entrants` : les bilans de la journée s'y trouvent, nommés
`Bilan_2026-08-22_Dupont-Lea.pdf`.

Les déplacer vers le dossier de classement définitif (par patient, par année —
selon l'organisation du cabinet). `C:\Bilan_entrants` doit être **vide** en fin
de journée : c'est ce qui permet de voir d'un coup d'œil ce qui reste à
classer.

### Sur la tablette

Les copies téléchargées s'accumulent dans **Téléchargements**. Elles font
double emploi avec celles du PC.

Ouvrir l'application **Fichiers** → **Téléchargements**, sélectionner les PDF
commençant par `Bilan_`, et les supprimer.

> **Pourquoi supprimer ?** Ces copies contiennent des données de santé. Une
> tablette est plus facilement perdue ou volée qu'un PC fixe : moins elle en
> conserve, mieux c'est. La copie de référence est celle du PC.

À faire une fois par semaine au minimum.

---

## 5. Vérification hebdomadaire

Le vendredi, contrôler que le nombre de bilans classés correspond au nombre de
consultations de la semaine.

Un écart ne peut plus venir d'un envoi manqué : un bilan que le serveur n'a pas
reçu reste en file sur la tablette, visible dans le bandeau d'attente. Ouvrir
le formulaire suffit à relancer l'envoi.

Si un bilan manque malgré tout, la copie locale se trouve dans les
Téléchargements de la tablette et peut être transférée à la main.

---

## Maintenance — pour Baptiste

### Le démarrage automatique

Installé une fois pour toutes, en administrateur :

```powershell
.\installer-demarrage.ps1
```

Il crée la tâche planifiée `BilanPosturo` (démarrage du PC, compte SYSTEM,
relance automatique jusqu'à cinq fois) et la règle de pare-feu. Pour revenir
au lancement manuel : `.\desinstaller-demarrage.ps1`.

Avant une installation à distance, faire passer le contrôle seul : il vérifie
l'emplacement du script, `config.json` et `pythonw.exe`, puis s'arrête avant
la tâche planifiée et le pare-feu, sans rien modifier.

```powershell
.\installer-demarrage.ps1 -Verifier   # contrôle seul, ne modifie rien
```

```powershell
Get-ScheduledTask -TaskName BilanPosturo          # état
Get-ScheduledTaskInfo -TaskName BilanPosturo      # dernier résultat, heure
Stop-ScheduledTask  -TaskName BilanPosturo        # arrêt
Start-ScheduledTask -TaskName BilanPosturo        # relance
```

La tâche tourne sous `pythonw.exe`, sans console : tout ce que le serveur a à
dire est dans `journal.log`. Après une modification de `config.json` ou du
certificat, il faut arrêter puis relancer la tâche.

Conséquence du compte SYSTEM : `dossier_pdf` doit être un chemin local absolu
ou un chemin UNC (`\\serveur\partage\...`). Un lecteur réseau mappé sur la
session du praticien n'existe pas pour SYSTEM.

### L'adresse du PC a changé

Symptôme : la tablette affiche `ERR_CONNECTION_TIMED_OUT` ou un avertissement
de sécurité, alors que rien n'a été modifié. Une erreur
`ERR_CONNECTION_REFUSED` désigne au contraire un PC joignable dont le serveur
est arrêté : c'est la tâche planifiée qu'il faut regarder, pas l'adresse.

```powershell
ipconfig | findstr IPv4
python serveur/generer_autorite.py <la_nouvelle_IP>
python serveur/serveur.py
```

L'autorité de certification est réutilisée : **rien à réinstaller sur la
tablette**. Penser ensuite à corriger le raccourci de l'écran d'accueil.

Pour éviter que cela se reproduise, réserver l'adresse en DHCP statique dans
l'interface de la box (associer l'adresse MAC du Wi-Fi à `192.168.1.13`).

### Changer le mot de passe

```powershell
python serveur/serveur.py --config
```

### Le certificat serveur expire

Validité 825 jours. Le regénérer avant la date d'expiration :

```powershell
python serveur/generer_autorite.py 192.168.1.13
```

L'autorité, elle, est valable 10 ans.

### Consulter le journal

`C:\BilanPosturo\journal.log` conserve chaque requête et chaque erreur.
Y chercher `TLS refusé` ou `Traceback` en cas de problème inexpliqué.

Il est archivé en `journal.log.1` et un nouveau journal commence dès qu'il
dépasse 5 Mo, **ou** dès que sa première ligne a plus d'un mois (30 jours).
Les archives plus anciennes sont décalées (`.2`, `.3`, …) et **aucune ligne
n'est conservée plus de six mois** : une archive est supprimée dès que sa
première ligne a plus de six mois (180 jours) moins un jour. La vérification
a lieu au démarrage du serveur, à chaque nouvelle archive, à l'écriture du
journal (au plus une fois par jour) et, serveur en marche, toutes les six
heures même si plus rien ne s'écrit. Un serveur arrêté ne purge rien avant son
prochain démarrage. Au plus sept générations d'archives
coexistent en régime normal. La suppression est définitive, et elle se fait
archive par archive : une ligne récente peut donc disparaître jusqu'à un mois
avant ses six mois, si elle partage son archive avec une ligne plus ancienne.
**Exception, la première fois :** au premier démarrage après la mise à jour,
tout l'historique d'avant devient une seule archive, qui part en bloc quand sa
première ligne atteint la limite. Les lignes les plus récentes de cette
archive peuvent alors partir jusqu'à plusieurs mois avant leurs six mois.
Les appels à `/sante`, qui arrivent en continu depuis chaque
tablette allumée, n'y figurent pas.

La durée se règle dans `config.json`, par la ligne
`"conservation_journaux_mois"` (entier de 1 à 120, **6 par défaut**) ; une
valeur invalide est ignorée et remplacée par 6. Elle vaut pour les deux
journaux. Relancer le serveur après modification.

### Quelle version est installée ?

Elle s'affiche en tout petit au bas du formulaire, sur la tablette
(« Bilan posturo — version 1.1.0 »), et sur chaque ligne `DEMARRAGE` de
`technique.log` (`version=1.1.0`). Le numéro vit dans un seul fichier,
`formulaire/version.json` : c'est la première chose que demande l'assistance.

### Le second journal, celui qu'on peut envoyer

Un deuxième fichier, `C:\BilanPosturo\technique.log`, vit à côté du premier.
Il note les démarrages, les arrêts et les incidents techniques (certificat,
authentification, dépôts), mais **jamais une adresse, jamais un nom de
fichier, jamais rien qui tienne de vos patientes et patients**. C'est la
différence entre les deux : `journal.log` ne doit jamais quitter le cabinet ;
`technique.log` le peut, par courriel, à l'assistance, pour un diagnostic à
distance sans qu'aucune donnée de santé ne sorte du PC.

Il tourne et se purge exactement comme l'autre journal : archivé au-delà de
5 Mo ou d'un mois, et plus aucune ligne conservée au-delà de six mois
(`"conservation_journaux_mois"`, voir plus haut). Une seule durée vaut pour
les deux fichiers.

Pour le désactiver (il ne devrait pas y avoir de raison, mais le retour en
arrière existe) : ouvrir `config.json` à la racine, ajouter ou mettre à
`false` la ligne `"journal_technique"`, enregistrer, relancer le serveur. Le
fichier déjà écrit peut rester tel quel ; il n'est simplement plus alimenté.

### La page d'état

Une page de diagnostic, en lecture seule, pour nommer un incident en une
minute pendant une séance d'assistance. Sur le PC du cabinet, dans un
navigateur : `https://localhost:8000/etat` (remplacer `8000` par le port de
`config.json`), avec l'identifiant et le mot de passe habituels. Sans eux, la
page répond « non autorisé » comme tout le reste : seule la sonde de santé
`/sante` est ouverte à tous.

Elle dit, ligne à ligne :

- **Version** — la même que celle du pied de formulaire et de `technique.log` ;
- **Serveur démarré le** — la date du dernier démarrage (la ligne `ARRET` du
  journal n'est presque jamais écrite : cette date la remplace) ;
- **Dernier bilan reçu** — « aucun depuis le démarrage » tant que rien n'est
  arrivé ; la valeur est perdue à chaque redémarrage ;
- **Espace libre** du disque qui porte le dossier des PDF ;
- **Certificat valable jusqu'au** — avec les jours restants, et la mention
  « à renouveler » sous 30 jours (voir « Le certificat serveur expire ») ;
- **Empreinte du certificat** — la même que celle des lignes `DEMARRAGE` de
  `technique.log` ;
- **Adresse du PC et certificat** — `conforme` (le certificat couvre une
  adresse que le PC porte), `adresse changée` (il n'en couvre aucune que le PC
  porte en ce moment : soit l'adresse a changé, et il faut suivre « L'adresse
  du PC a changé » plus haut ; soit une interface réseau est débranchée, Wi-Fi
  coupé ou câble arraché sous Windows, et il suffit de la rebrancher puis de
  recharger la page) ou `indéterminé` (rien à comparer : le certificat ne
  porte que `localhost`, ou il n'a pas pu être lu) ;
- **Identité du cabinet** — « non renseignée » signifie que l'export des
  bilans est refusé : lancer `python serveur/serveur.py --config` ;
- les **30 dernières lignes de `technique.log`**.

Rien de ce qui s'y lit n'identifie une patiente, un patient, un fichier ou une
adresse : elle peut être photographiée ou copiée dans un courriel, comme
`technique.log`. Elle n'écrit rien et ne déclenche rien.

Pour la lire par un programme, la demander avec l'en-tête
`Accept: application/json`.

Pour la désactiver : dans `config.json`, ajouter ou mettre à `false` la ligne
`"page_etat"`, puis arrêter et relancer la tâche planifiée. `/etat` répond
alors comme avant son existence (« non autorisé » sans identifiants, « type de
fichier non servi » avec).

### Fichiers à ne jamais diffuser

- `autorite-cle.pem` — permet de fabriquer de faux certificats
- `cle.pem` — clé du serveur
- `config.json` — contient l'empreinte du mot de passe

À exclure de tout dépôt Git.

---

## Aide-mémoire

| | |
|---|---|
| Adresse tablette | `https://192.168.1.13:8000` |
| Arrivée des bilans | `C:\Bilan_entrants` |
| Dossier du projet | `C:\BilanPosturo` |
| Démarrer | `demarrer-serveur.bat` |
| Arrêter | Fermer la fenêtre noire, ou `Ctrl+C` |
| Secours | favori *Formulaire — secours V1*, ou `index-v1.html` |