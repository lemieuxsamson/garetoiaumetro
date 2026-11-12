# Gare-toi au métro

Carte web qui indique les côtés de rue où le stationnement est probablement **gratuit et permis** à Montréal, selon l'heure, de deux façons :

- **Autour de moi** : la position GPS du téléphone est suivie en temps réel; la carte montre les rues dans un rayon de 300, 500 ou 800 m, pour la durée de stationnement choisie (de maintenant à +30 min … +24 h). Le calcul se refait à chaque déplacement de 40 m et chaque minute.
- **Près d'une station** : stations de la ligne verte Est (Honoré-Beaugrand à L'Assomption), pour une date et une plage horaire.

Site statique : `index.html` + `data/` (règles + tuiles d'environ 1 km chargées à la demande). Aucun serveur.

## Fonctionnement

1. Chaque poteau de signalisation est rattaché au tronçon de rue le plus proche (Géobase), du côté gauche ou droit.
2. Les poteaux sont ordonnés le long du tronçon; chaque panneau s'applique du poteau vers le suivant dans le sens de sa flèche (sans flèche : les deux sens).
3. Dans le navigateur, chaque portion est évaluée pour la plage choisie (sur plusieurs jours au besoin) :
   - vert : aucun panneau actif (ou durée maximale suffisante pour la durée prévue)
   - vert pâle pointillé : aucun panneau répertorié de ce côté (rues locales et collectrices seulement)
   - ambre : gratuit, durée limitée
   - bleu : tarifé
   - rouge : interdit, réservé ou vignette de résident (S3R, permis de secteur)
   - gris : non évalué (artère sans panneau, ou secteur où la signalisation est peu répertoriée)

Couverture : la densité de poteaux par km de rue est calculée par arrondissement. En deçà de 15 poteaux/km (Saint-Laurent, Verdun, LaSalle, Lachine, Montréal-Nord, Saint-Léonard, Pierrefonds-Roxboro, L'Île-Bizard, villes liées), les rues sans panneau ne sont pas présumées libres.

Limites : **les places tarifées (bornes) ne sont pas incluses**, le tarif n'étant pas indiqué par des panneaux; les libellés de panneaux sont interprétés automatiquement; les opérations de déneigement ne sont pas incluses; « jours d'école » est approximé à lun.-ven., sept. à juin. **Outil non officiel : la signalisation sur place a toujours préséance.**

**Suivi du véhicule** : en mode « Autour de moi », la carte suit le véhicule et tourne avec sa direction (véhicule placé dans le bas de l'écran pour voir devant). La direction vient du GPS en mouvement, ou est déduite de deux positions successives. Le bouton « Direction en haut / Nord en haut » change l'orientation; déplacer ou tourner la carte à la main suspend le suivi jusqu'à « Recentrer sur moi ».

**Simulation** : en mode « Autour de moi », le lien « Simuler une position » met le GPS réel en pause. On touche la carte pour placer le véhicule, on le glisse pour le faire rouler (la flèche suit la direction, le calcul se refait tous les 40 m), et on peut choisir une heure simulée qui avance ensuite avec l'horloge. L'URL garde la position et l'heure simulées (`#m=gps&sim=45.5845,-73.5409&t=2026-11-06T10:00`), pratique pour partager un scénario de test.

La localisation exige HTTPS (fourni par GitHub Pages) et l'autorisation du navigateur. En mode GPS, la page garde l'écran allumé quand le navigateur le permet.

## Mise en ligne avec GitHub Pages

1. Créer le dépôt et y mettre le contenu de ce dossier.
2. *Settings → Pages → Build and deployment → Source* : **GitHub Actions**.
3. *Settings → Pages → Custom domain* : `garetoiaumetro.lemieuxsamson.com`, puis *Enforce HTTPS*. Côté DNS : enregistrement `CNAME` `garetoiaumetro` → `<utilisateur>.github.io`.
4. Chaque `push` sur `main` déclenche `.github/workflows/deploy.yml`, qui assemble le site et le publie.

## Fond Mapbox et recherche d'adresse (jeton Mapbox)

Avec un jeton Mapbox, la carte utilise Mapbox GL JS (style *Standard* : bâtiments, arbres, points d'intérêt) et le mode « Station ou adresse » offre une recherche d'adresse (Mapbox Geocoding, limitée à l'île de Montréal). Sans jeton, la page revient à MapLibre + OpenFreeMap, sans recherche.

1. Sur [account.mapbox.com](https://account.mapbox.com/access-tokens/), créer un jeton **public** (`pk.…`), portées par défaut seulement.
2. Dans *URL restrictions*, ajouter `https://garetoiaumetro.lemieuxsamson.com` (et `http://localhost:8000` pour les tests locaux).
3. Dans le dépôt : *Settings → Secrets and variables → Actions → New repository secret*, nom `MAPBOX_TOKEN`.
4. Relancer *Actions → Déploiement → Run workflow*.

Niveaux gratuits Mapbox : 50 000 chargements de carte et 100 000 requêtes de géocodage par mois.

**Compte sans moyen de paiement (accès « démo »)** : un seul jeton, non restreignable par URL, avec des plafonds plus bas; aucune facturation n'est possible. Si Mapbox refuse le jeton (401/403) ou signale une limite (429), la page repasse automatiquement sur OpenFreeMap, masque la recherche d'adresse et n'essaie plus Mapbox pendant 6 h sur cet appareil. Après l'ajout d'un moyen de paiement, créer un nouveau jeton restreint à l'URL du site et remplacer le secret.

## Street View intégré (clé Google)

Sans clé, les boutons Street View ouvrent Google Maps dans un nouvel onglet. Avec une clé, Street View s'affiche sous la carte, orienté vers le côté de rue choisi.

1. Console Google Cloud : activer **Maps Embed API** sur un projet (gratuite; un compte de facturation est tout de même exigé).
2. Créer une clé API et la **restreindre** :
   - *Sites Web (référents HTTP)* : `https://garetoiaumetro.lemieuxsamson.com/*` et `http://localhost:*/*`;
   - *Restrictions d'API* : **Maps Embed API** seulement.
3. Dans le dépôt : *Settings → Secrets and variables → Actions → New repository secret*, nom `GMAPS_EMBED_KEY`, valeur = la clé.
4. Relancer le déploiement (*Actions → Déploiement → Run workflow*).

La clé n'est jamais commitée : `config.js` est généré au déploiement. Elle reste toutefois visible dans le navigateur des visiteurs (c'est inévitable pour un site statique); ce sont les restrictions ci-dessus qui la protègent.

Test local : copier `config.example.js` en `config.js` (ignoré par git), y mettre la clé, puis `python3 -m http.server` et ouvrir `http://localhost:8000`.

## Mise à jour des données

Automatique : le workflow `.github/workflows/maj-donnees.yml` télécharge les deux jeux de données chaque lundi, reconstruit les tuiles de `data/` et les publie si elles ont changé. Pour le lancer à la main : onglet *Actions → Mise à jour des données → Run workflow*.

Manuelle :

```bash
pip install pandas
python scripts/fetch_sources.py          # ou déposer les deux fichiers à la racine
python scripts/build_data.py signalisation_stationnement.csv geobase.json data
```

Pour ajouter des stations, modifier la liste `STATIONS` au début de `scripts/build_data.py`.

## Licences

- Code (`index.html`, `scripts/`) : licence MIT, voir `LICENSE`.
- `data/` : données dérivées, sous licence CC BY 4.0 (Ville de Montréal).

## Sources

- Ville de Montréal, [Signalisation (stationnement sur rue)](https://donnees.montreal.ca/dataset/stationnement-sur-rue-signalisation-courant) et [Géobase](https://donnees.montreal.ca/dataset/geobase), licence CC BY 4.0.
- Fond de carte : [OpenFreeMap](https://openfreemap.org), OpenMapTiles, © contributeurs OpenStreetMap.
- Rendu : [MapLibre GL JS](https://maplibre.org).
