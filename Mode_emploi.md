# Bilan posturologique — mode d'emploi

Système de saisie des bilans sur tablette, avec enregistrement automatique sur
le PC du cabinet.

---

## 1. Chaque matin — démarrer le serveur

Sur le **PC**, ouvrir le dossier `C:\BilanPosturo`, puis double-cliquer sur
`demarrer-serveur.bat`.

Une fenêtre noire s'ouvre et affiche :

```
Serveur HTTPS démarré.
  Sur ce PC  : https://localhost:8000
  Tablette   : https://192.168.1.13:8000
  Dépôt      : C:\Bilan_entrants
```

**Laisser cette fenêtre ouverte toute la journée.** La fermer arrête le
serveur : la tablette ne pourra plus envoyer de bilan.

La réduire dans la barre des tâches ne pose aucun problème.

### Si un message d'erreur apparaît

| Message | Que faire |
|---|---|
| `Port 8000 indisponible` | Le serveur tourne déjà. Chercher l'autre fenêtre noire. |
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
- **Orange** — le bilan est sur la tablette mais **pas** sur le PC. Vérifier
  que la fenêtre noire est toujours ouverte, puis regénérer le PDF.
- **Rouge** — la création du PDF a échoué. La saisie n'est pas perdue :
  réessayer.

> **Ne jamais quitter la page sur un bandeau orange ou rouge** sans avoir
> vérifié que le bilan est bien arrivé.

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
consultations de la semaine. Un écart signale un bandeau orange passé
inaperçu.

En cas de bilan manquant, vérifier les Téléchargements de la tablette : la
copie locale s'y trouve probablement, et peut être transférée manuellement sur
le PC.

---

## Maintenance — pour Baptiste

### L'adresse du PC a changé

Symptôme : la tablette affiche une erreur de connexion ou un avertissement de
sécurité, alors que rien n'a été modifié.

```powershell
ipconfig | findstr IPv4
python generer_autorite.py <la_nouvelle_IP>
python serveur.py
```

L'autorité de certification est réutilisée : **rien à réinstaller sur la
tablette**. Penser ensuite à corriger le raccourci de l'écran d'accueil.

Pour éviter que cela se reproduise, réserver l'adresse en DHCP statique dans
l'interface de la box (associer l'adresse MAC du Wi-Fi à `192.168.1.13`).

### Changer le mot de passe

```powershell
python serveur.py --config
```

### Le certificat serveur expire

Validité 825 jours. Le regénérer avant la date d'expiration :

```powershell
python generer_autorite.py 192.168.1.13
```

L'autorité, elle, est valable 10 ans.

### Consulter le journal

`C:\BilanPosturo\journal.log` conserve chaque requête et chaque erreur.
Y chercher `TLS refusé` ou `Traceback` en cas de problème inexpliqué.

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