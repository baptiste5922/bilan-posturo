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

Au-delà de 5 Mo, il est archivé en `journal.log.1` et un nouveau journal
commence ; trois générations sont conservées. Les appels à `/sante`, qui
arrivent en continu depuis chaque tablette allumée, n'y figurent pas.

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