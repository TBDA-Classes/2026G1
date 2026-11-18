# Lancer le dashboard Storey 1 sur son ordinateur

Notice pas à pas pour Windows (les différences pour Mac sont indiquées).
Durée : 15 minutes la première fois, 30 secondes ensuite.

---

## 0. Ce qu'il faut avoir

| Besoin | Comment vérifier | Si absent |
|---|---|---|
| **Anaconda** (Python 3.10 ou plus récent) | Menu Démarrer → taper « Anaconda Prompt » | Télécharger sur https://www.anaconda.com/download, installer avec les options par défaut |
| **Le dépôt 2026G1** sur l'ordinateur | Un dossier avec `data`, `reports`, `src` et `params.yaml` | Étape 1 |
| Un navigateur (Chrome, Firefox, Edge) | — | — |

Tout tourne sur ton ordinateur : pas de compte Streamlit, pas besoin d'internet une fois installé.

---

## 1. Récupérer le dépôt

**Option A — ZIP (le plus simple)**
1. Ouvrir https://github.com/TBDA-Classes/2026G1 → bouton vert **Code** → **Download ZIP**.
2. Clic droit sur le ZIP → **Extraire tout…** dans un dossier simple, par exemple `Documents\TBDA`.

**Option B — GitHub Desktop (mises à jour faciles)**
1. Installer https://desktop.github.com
2. **File → Clone repository → URL** : `https://github.com/TBDA-Classes/2026G1`
3. Plus tard, pour récupérer les nouveautés : **Fetch origin** puis **Pull origin**.

**Vérifier l'organisation.** Le dossier `dashboard` doit être **à la racine du dépôt**, à côté de `data` et `reports` :

```
2026G1\                         (ou 2026G1-main\)
├── data\
│   └── processed\cedint_hourly_v1.parquet   ← les données figées
├── reports\                                  ← les résultats du modelling
├── src\
├── params.yaml
└── dashboard\
    ├── app.py                                ← le fichier à lancer
    ├── requirements.txt
    └── views\ ...
```

Si le dossier `dashboard` n'est pas encore dans le dépôt, copie-le à cet endroit.
Attention au double dossier créé par certains ZIP (`2026G1-main\2026G1-main\`) : va dans celui qui contient `data`.

---

## 2. Ouvrir l'Anaconda Prompt

1. **Menu Démarrer** (touche ⊞) → taper **Anaconda Prompt** → l'ouvrir.
2. Une fenêtre noire s'affiche : `(base) C:\Users\Prenom>`. `(base)` = Python d'Anaconda actif.

**Mac :** application **Terminal** (Spotlight → « Terminal »).

---

## 3. Aller à la racine du dépôt

1. Dans l'Explorateur Windows, ouvrir le dossier du dépôt (celui qui contient `data`, `reports`, `dashboard`).
2. Cliquer dans la **barre d'adresse** : le chemin s'affiche en texte. Le copier (Ctrl+C).
3. Dans l'Anaconda Prompt, taper `cd /d "`, coller, fermer les guillemets, Entrée :
   ```
   cd /d "C:\Users\Prenom\Documents\TBDA\2026G1-main"
   ```
   Les **guillemets** sont indispensables si le chemin contient des espaces ou des accents.
4. Vérifier avec `dir` : on doit voir `data`, `reports`, `dashboard`, `params.yaml`.

**Mac :** `cd "/Users/prenom/Documents/TBDA/2026G1-main"` puis `ls`.

---

## 4. Installer les bibliothèques (une seule fois)

```
pip install -r dashboard\requirements.txt
```

Installe Streamlit (le site), Plotly (les graphiques), pandas, pyarrow (fichiers .parquet) et PyYAML
(lecture de `params.yaml`). 1 à 3 minutes ; la dernière ligne dit `Successfully installed …`
ou `Requirement already satisfied`. (Mac : `dashboard/requirements.txt`.)

**Optionnel, plus propre : un environnement dédié**
```
conda create -n tbda python=3.12 -y
conda activate tbda
pip install -r dashboard\requirements.txt
```
Ensuite, taper `conda activate tbda` à chaque fois avant de lancer le dashboard.

---

## 5. Lancer le dashboard

```
streamlit run dashboard\app.py
```

- La première fois, Streamlit peut demander un e-mail : **appuyer sur Entrée** sans rien écrire.
- Le navigateur s'ouvre sur **http://localhost:8501** (sinon, copier l'adresse dans le navigateur).
- **Laisser la fenêtre noire ouverte** : c'est elle qui fait tourner le dashboard.

### Vérifier que tout est branché

- En bas de la barre latérale : `Data: data/processed/cedint_hourly_v1.parquet`.
- Page **Method**, tableau « Data sources » : chaque fichier trouvé est listé, les absents sont marqués « not found ».
- Contrôle rapide : **Overview**, mois **January 2022**, toutes zones → **3,001 kWh**, **52.1 %** en heures creuses, **44** alertes.

---

## 6. Arrêter

Cliquer dans la fenêtre noire puis **Ctrl+C**. Pour relancer plus tard : étapes 2, 3 et 5.

---

## 7. Modifier le code et voir le résultat

1. Lancer le dashboard (étape 5).
2. Ouvrir un fichier dans Spyder, par exemple `dashboard\views\overview.py`, le modifier, **enregistrer** (Ctrl+S).
3. Dans le navigateur, bandeau en haut à droite → **Always rerun** : la page se met à jour à chaque enregistrement.

Ne pas lancer avec le bouton ▶ (F5) de Spyder. Les règles métier (prix, CO₂, heures creuses, seuils)
sont dans **`params.yaml`** à la racine du dépôt, partagé avec l'équipe modelling : les changer change
aussi les notebooks.

---

## 8. Alternative : tout depuis Spyder

Dans la console IPython de Spyder (en bas à droite) :
```
cd "C:\Users\Prenom\Documents\TBDA\2026G1-main"
%pip install -r dashboard\requirements.txt
!streamlit run dashboard\app.py
```
Pour arrêter : carré rouge de la console, ou **Consoles → Redémarrer le noyau**.

---

## 9. Courbe « Expected » pour toutes les heures (une fois, optionnel)

Sans cette étape, la page **Expected vs actual** montre le vrai modèle seulement pour janvier–février 2023
(et la référence B2 de l'équipe pour les autres semaines). Pour avoir le modèle partout :

```
pip install -r requirements.txt
python dashboard\tools\export_expected.py
```

La première ligne installe les bibliothèques du modelling (LightGBM, scikit-learn). Le script réutilise
le code de l'équipe (`src/`) et écrit `dashboard\data\expected_hourly.parquet` en quelques minutes.
Ensuite, dans le dashboard : menu ⋮ en haut à droite → **Clear cache** → **Rerun**.

---

## 10. Mettre à jour quand l'équipe modelling publie de nouveaux résultats

1. Récupérer la dernière version du dépôt (GitHub Desktop : **Pull origin** ; ou nouveau ZIP).
2. Dans le dashboard : menu ⋮ → **Clear cache** → **Rerun** (ou Ctrl+C puis relancer).
3. Si les modèles ont changé, relancer aussi l'étape 9.

---

## 11. Problèmes fréquents

| Message ou symptôme | Cause | Solution |
|---|---|---|
| `'streamlit' n'est pas reconnu…` | Streamlit installé dans un autre Python | `python -m streamlit run dashboard\app.py` |
| `Could not open requirements file` | Pas à la racine du dépôt | Refaire l'étape 3, vérifier avec `dir` |
| `ModuleNotFoundError: plotly` / `pyarrow` / `yaml` | Étape 4 pas faite dans cet environnement | `pip install -r dashboard\requirements.txt` |
| Message rouge « Hourly data not found » | `dashboard` n'est pas à la racine du dépôt | Le déplacer à côté de `data` et `reports` (étape 1) |
| Une page dit « needs reports/… » | Ce fichier du modelling n'est pas dans ta copie du dépôt | Mettre le dépôt à jour (étape 10) |
| `ModuleNotFoundError: lightgbm` (étape 9) | Bibliothèques du modelling absentes | `pip install -r requirements.txt` à la racine |
| `Port 8501 is already in use` | Un dashboard tourne déjà | Fermer l'autre fenêtre, ou ajouter `--server.port 8502` |
| Erreur rouge dans la page | Bug | Copier le message complet et l'envoyer à l'équipe dashboard |
| Premier affichage lent (≈ 10 s) | Calculs initiaux | Normal : ensuite tout est instantané (cache) |

---

## 12. Version en ligne (si l'équipe la met en place)

Sur Streamlit Community Cloud : dépôt `TBDA-Classes/2026G1`, branche `main`, fichier `dashboard/app.py`.
Il suffit alors d'ouvrir le lien `https://….streamlit.app`.
