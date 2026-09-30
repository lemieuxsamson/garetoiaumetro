# Stationnement gratuit probable près du métro

Carte web qui indique, pour une date et une plage horaire, les côtés de rue où le stationnement est probablement **gratuit et permis** autour des stations de la ligne verte Est (Honoré-Beaugrand, Radisson, Langelier, Cadillac, L'Assomption).

Site statique : `index.html` + `data.json`. Aucun serveur, aucune clé d'API.

## Fonctionnement

1. Chaque poteau de signalisation est rattaché au tronçon de rue le plus proche (Géobase), du côté gauche ou droit.
2. Les poteaux sont ordonnés le long du tronçon; chaque panneau s'applique du poteau vers le suivant dans le sens de sa flèche (sans flèche : les deux sens).
3. Dans le navigateur, chaque portion est évaluée pour la date et la plage choisies :
   - vert : aucun panneau actif
   - vert pâle pointillé : aucun panneau répertorié de ce côté (rues locales et collectrices seulement)
   - ambre : gratuit, durée limitée
   - bleu : tarifé
   - rouge : interdit, réservé ou vignette de résident (S3R)
   - gris : non évalué (artère ou autoroute sans panneau répertorié)

Limites : les libellés de panneaux sont interprétés automatiquement; les opérations de déneigement ne sont pas incluses; « jours d'école » est approximé à lun.-ven., sept. à juin. **Outil non officiel : la signalisation sur place a toujours préséance.**

## Mise en ligne avec GitHub Pages

1. Créer un dépôt et y mettre le contenu de ce dossier (glisser-déposer via *Add file → Upload files*, ou `git push`).
2. *Settings → Pages* : source *Deploy from a branch*, branche `main`, dossier `/ (root)`.
3. Le site est publié à `https://<utilisateur>.github.io/<dépôt>/`.

Domaine personnalisé : le fichier `CNAME` publie le site à **https://garetoiaumetro.lemieuxsamson.com**. Côté DNS, un enregistrement `CNAME` `garetoiaumetro` → `<utilisateur>.github.io`; ensuite, cocher *Enforce HTTPS* dans *Settings → Pages*.

## Mise à jour des données

Automatique : le workflow `.github/workflows/maj-donnees.yml` télécharge les deux jeux de données chaque lundi, reconstruit `data.json` et le publie s'il a changé. Pour le lancer à la main : onglet *Actions → Mise à jour des données → Run workflow*.

Manuelle :

```bash
pip install pandas
python scripts/fetch_sources.py          # ou déposer les deux fichiers à la racine
python scripts/build_data.py signalisation_stationnement.csv geobase.json data.json
```

Pour ajouter des stations, modifier la liste `STATIONS` au début de `scripts/build_data.py`.

## Licences

- Code (`index.html`, `scripts/`) : licence MIT, voir `LICENSE`.
- `data.json` : données dérivées, sous licence CC BY 4.0 (Ville de Montréal).

## Sources

- Ville de Montréal, [Signalisation (stationnement sur rue)](https://donnees.montreal.ca/dataset/stationnement-sur-rue-signalisation-courant) et [Géobase](https://donnees.montreal.ca/dataset/geobase), licence CC BY 4.0.
- Fond de carte : [OpenFreeMap](https://openfreemap.org), OpenMapTiles, © contributeurs OpenStreetMap.
- Rendu : [MapLibre GL JS](https://maplibre.org).
