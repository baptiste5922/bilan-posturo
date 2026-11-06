#!/usr/bin/env python3
"""Auxiliaire de l'atelier (contrat C9-T2) : lit dans `serveur/serveur.py` ce
que l'atelier ne doit pas retranscrire — les clés et défauts du bloc `cabinet`,
la règle du logo, le critère « praticien renseigné » — et le rend en JSON sur la
sortie standard.

    python3 -I -B outils/atelier/lire_serveur.py defauts
    python3 -I -B outils/atelier/lire_serveur.py identite <identite-cabinet.json> <travail>

Le serveur est IMPORTÉ, jamais exécuté : aucun appel à `main`, à `demarrer` ni
à `charger_config`, donc `config.json` du dépôt n'est jamais lu. Ce script
n'écrit rien : `-B` (à la charge de l'appelant) évite même le `__pycache__` que
l'import créerait sous `serveur/`.

Codes de retour : 0, 1 (entrée illisible), 2 (usage).
"""

import json
import os
import sys

# Calculée depuis l'emplacement de ce fichier, comme serveur.py le fait pour la
# sienne : l'auxiliaire se lance depuis n'importe quel dossier courant.
RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RACINE, "serveur"))

import serveur  # noqa: E402


def message(texte):
    sys.stderr.write(texte + "\n")


def defauts():
    return {
        "cles": list(serveur.CLES_CABINET),
        "defauts": serveur.CONFIG_DEFAUT["cabinet"],
        "logo_par_defaut": serveur.LOGO_PAR_DEFAUT,
    }


def lire_identite(chemin):
    """Le JSON de l'identité, ou None (et un message) s'il est illisible ou
    n'est pas un objet. La valeur n'est jamais citée dans le message."""
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            identite = json.load(f)
    except (OSError, ValueError) as erreur:
        message("identité illisible ({})".format(type(erreur).__name__))
        return None
    if not isinstance(identite, dict):
        message("identité : la racine doit être un objet JSON")
        return None
    return identite


def verdict_identite(identite, travail):
    try:
        renseigne = bool(serveur.identite_renseignee({"cabinet": identite}))
    except (KeyError, AttributeError, TypeError):
        # Praticien absent ou qui n'est pas une chaîne : il n'est pas renseigné.
        renseigne = False

    logo = identite.get("logo")
    # Le logo par défaut vit dans formulaire/ du dépôt ; tout autre se juge
    # sous le dossier de travail, qui joue pour lui la racine web.
    racine_web = None if logo == serveur.LOGO_PAR_DEFAUT else travail
    chemin, motif = serveur.valider_logo(logo, racine_web)
    return {"praticien_renseigne": renseigne, "logo": [chemin, motif]}


def principal(argv):
    if len(argv) == 1 and argv[0] == "defauts":
        sortie = defauts()
    elif len(argv) == 3 and argv[0] == "identite":
        identite = lire_identite(argv[1])
        if identite is None:
            return 1
        sortie = verdict_identite(identite, argv[2])
    else:
        message("usage : lire_serveur.py defauts | identite <identite-cabinet.json> <travail>")
        return 2
    sys.stdout.write(json.dumps(sortie) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
