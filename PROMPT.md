# Prompt de reconstruction — Gare-toi au métro

> Ce fichier décrit l'application assez précisément pour qu'un assistant IA (ou une personne) puisse la recréer de zéro.
> Il est tenu à jour à chaque changement fonctionnel du dépôt (voir `CLAUDE.md`).
> Dernière mise à jour : 2026-11-18 (état au commit « Carte en plein écran, et installation sur l'écran d'accueil »).

---

## Le prompt

Construis une petite application web statique, en français (Québec), appelée **« Gare-toi au métro »**, publiée sur GitHub Pages au domaine `garetoiaumetro.lemieuxsamson.com`. Elle indique, pour une plage horaire, les **côtés de rue où le stationnement est probablement gratuit et permis** à Montréal, soit autour de la position GPS du conducteur, soit autour d'une station de métro ou d'une adresse. Aucun serveur : un `index.html` autonome, des données JSON précalculées et des workflows GitHub Actions.

### 1. Données sources (Ville de Montréal, licence CC BY 4.0)

- **Signalisation (stationnement sur rue)**, CSV (ressource Données Québec `7f1d4ae9-1a12-46d7-953e-6b9c18c78680`). Colonnes utilisées : `POTEAU_ID_POT`, `Latitude`, `Longitude`, `DESCRIPTION_RPA` (texte du panneau), `FLECHE_PAN` (flèche), `DESCRIPTION_REP` (garder `Réel`), `PAS_SUR_RUE` (garder vide), `NOM_ARROND`.
- **Géobase, réseau routier**, GeoJSON (ressource `9d3d60d8-4e7f-493e-8d6a-dcd040319d8d`). Propriétés : `ODONYME`/`NOM_VOIE`, `CLASSE`, `ARR_GCH`.
- Les données tarifées de l'AMD (bornes, places payantes) **ne sont pas** utilisées ; la page l'indique clairement.

### 2. Script de construction `scripts/build_data.py` (Python + pandas)

Usage : `python3 scripts/build_data.py signalisation_stationnement.csv geobase.json data`. Un second script `scripts/fetch_sources.py` télécharge les deux sources via l'API CKAN de Données Québec (`resource_show`).

1. **Projection locale** équirectangulaire centrée sur 45.55, −73.65 (K = 111 320 m/°).
2. **Tronçons** : toutes les LineString de la Géobase sauf `CLASSE` 1, 3, 9. Pour chacun : nom, longueur, rues transversales aux deux extrémités (`e` : « entre X et Y »), nom géographique de chaque côté (`ln`/`rn` : est, nord, ouest, sud, d'après la normale gauche/droite).
3. **Poteaux** : chaque poteau est projeté sur le tronçon le plus proche (index en grille de 60 m, max 35 m), ce qui donne la distance le long du tronçon et le côté (gauche +1 / droite −1).
4. **Portions de bordure** : pour chaque côté, les poteaux sont triés le long du tronçon ; chaque panneau s'applique du poteau vers le suivant dans le sens de sa flèche (`FLECHE_PAN` 0 ou 8 = deux sens, 2 = gauche, 3 = droite, vu face au panneau ; la direction dépend du côté). Un côté sans poteau donne une portion « sans panneau » (`uns=1`).
5. **Couverture** : densité de poteaux par km de rue locale/collectrice (classes 0 et 5) par arrondissement ; sous **15 poteaux/km**, le tronçon reçoit `cv=0` (signalisation jugée incomplète : Saint-Laurent, Verdun, LaSalle, Lachine, Montréal-Nord, Saint-Léonard, Pierrefonds-Roxboro, L'Île-Bizard, villes liées).
6. **Interprétation des libellés** (`parse_rule`) : normaliser (majuscules, sans accents), puis
   - catégorie : `interdit` (\P, \A, « ARRÊT/STATIONNEMENT INTERDIT », « A 08h… », panonceau d'horaire seul), `vignette` (EXCEPTÉ S3R, VIGNETTE, PERMIS, SECTEUR), `reserve` (EXCEPTÉ, RÉSERVÉ, GARDERIE, LIVRAISON, COMMUNAUTO, DÉBARCADÈRE, AUTOBUS…), `tarife` (TARIF, PARCOMÈTRE, PAYANT), `limite` (P 60 MIN, 120 MIN… avec durée `d` en minutes), `info` (camions, autobus, angle, rappel, remorquage, panonceau d'exception seul…) ;
   - périodes de l'année (`m` = [mois, jour, mois, jour], ex. « 1 AVRIL AU 1 DÉC », « 15 AVR - 15 NOV », « SEPT. À JUIN ») ; « jours d'école / de classe » ≈ lun.-ven., 1er sept. au 23 juin ;
   - fenêtres `w` = [[début_min, fin_min, [jours 0=lun…6=dim]], …] : plages « 9h-21h », « 8H À 17H », « 7h00-21h00 », jours avant ou après les heures, plages de jours (« LUN À VEN », « SAM-DIM »), plusieurs groupes par panneau ; sans heure = toute la journée ; « EN TOUT TEMPS » et « CLIGNOTANT » = toujours.
7. **Sortie** :
   - `data/meta.json` : `{generated, tile:[0.009, 0.0128], stations, rules:[{c,m,w,d,t}], tiles:[clés]}` (`t` = libellé lisible, \P → « Stationnement interdit », \A → « Arrêt interdit ») ;
   - `data/tiles/<ky>_<kx>.json` (ky = ⌊lat/0.009⌋, kx = ⌊lon/0.0128⌋, ≈ 1 km) : `{tr:[{n,e,k,ln,rn,L,cv}], f:[[tronçon, côté, t0, t1, [règles], uns, coordonnées]]}`. Un tronçon va dans la tuile de son milieu. Coordonnées arrondies à 5 décimales. Environ 570 tuiles, 25 Mo au total.
8. **Stations** (mode station) : Honoré-Beaugrand (45.59677, −73.53569), Radisson (45.58915, −73.53943), Langelier (45.58283, −73.54295), Cadillac (45.57708, −73.54684), L'Assomption (45.56960, −73.54690).

### 3. Évaluation dans le navigateur

- Plage horaire découpée par jour (elle peut franchir minuit) ; une règle est **active** si une de ses fenêtres chevauche la plage un jour couvert, pendant sa période de l'année.
- Statut d'une portion (couleur) : `0` libre (vert `#1C9A55`), `4` sans panneau, libre probable (vert pâle pointillé `#7CC79C`, seulement rues de classe 0/5 avec `cv=1`), `1` gratuit durée limitée (ambre `#D6931A`), `2` tarifé (bleu `#2F6BD6`), `3` interdit, réservé ou vignette (rouge `#CC3A2F`), `5` non évalué (gris `#B4BCB6` : artère sans panneau, ou secteur `cv=0`). Une limite de durée **≥ durée prévue** compte comme libre.
- Distance au centre = point le plus proche du tronçon. Compteurs en km de bordure (libres, sans panneau, durée limitée, interdits).
- **Rues les plus prometteuses** : au plus 8, une par rue, triées par distance ; un côté vérifié compte si sa plus longue portion libre continue fait ≥ 25 m ; un côté sans panneau compte s'il fait ≥ 60 m (pénalité de 60 m au tri). Chaque carte : « Rue X, côté ouest », « entre A et B », mètres libres, liens Google Maps / Plans / Waze, bouton Street View orienté vers ce côté.
- **Détail d'une rue** (clic sur la carte ou la liste) : pour chaque côté, mètres libres et liste des panneaux avec longueur couverte et « ne s'applique pas » / « suffisant pour votre durée ».

### 4. Interface (`index.html`, un seul fichier, HTML/CSS/JS sans framework)

- Polices Barlow / Barlow Condensed ; jetons de couleur en variables CSS, mode sombre ; mise en page : panneau latéral 400 px + carte pleine hauteur sur ordinateur, carte 62vh puis listes sur mobile ; légende et notes (tarification non incluse, couverture, déneigement non inclus, « consultez à l'arrêt »), attribution des données.
- **Deux modes** (onglets) :
  1. **Autour de moi** (défaut) : bouton « Activer ma position » (démarrage automatique si la permission est déjà accordée), `watchPosition` haute précision, durée « Je me gare pour » 30 min à 24 h (défaut 2 h), rayon 300/500/800 m (défaut 500), état « Position ±X m · mise à jour il y a… », plage évaluée affichée. Recalcul tous les 40 m de déplacement et chaque minute. Écran gardé allumé (Wake Lock). **Seuls les côtés libres (0 et 4) sont dessinés**, en traits plus épais.
  2. **Station ou adresse** : puces des 5 stations, date, heures de début et de fin, rayon 400/600/900 m (défaut 900) ; toutes les couleurs. Avec un jeton Mapbox : **recherche d'adresse** (Mapbox Geocoding v6, autocomplétion, limitée à l'île : bbox −73.99, 45.40, −73.47, 45.71, langue fr), épingle rouge sur l'adresse choisie.
- **Carte** : chaque portion est une ligne décalée de son côté (`line-offset` selon le zoom), cercle du rayon en pointillé, marqueurs des stations, sélection surlignée, couche de clic invisible large.
- **Suivi du véhicule** (mode GPS) : point bleu + précision ; la carte suit le véhicule et, par défaut, **tourne avec sa direction** (cap GPS si vitesse > 1,5 m/s, sinon déduit de deux positions à plus de 12 m d'écart ; changement ignoré sous 6°), véhicule placé dans le bas de l'écran (marge haute 30 %). Bouton « Direction en haut / Nord en haut » (mémorisé). Déplacer ou tourner la carte à la main suspend le suivi ; « Recentrer sur moi » le reprend. Zoom initial ajusté au rayon.
- **Simulation** (mode GPS) : lien « Simuler une position » ; toucher la carte place le véhicule (orange), le glisser le fait rouler ; heure simulée (`datetime-local`) qui avance avec l'horloge ; URL partageable `#m=gps&sim=lat,lon&t=AAAA-MM-JJTHH:MM` ; « Quitter la simulation » reprend le GPS réel.
- **Street View** : avec une clé Google Maps Embed, panneau intégré sous la carte (moitié basse), orienté vers le côté choisi, bascule entre les côtés, cône orange sur la carte ; sans clé, ouverture dans Google Maps.
- **Plein écran** : bouton en haut à gauche de la carte (API Fullscreen quand elle existe, sinon mode CSS), pastille d'état en haut, détail de rue par-dessus la carte. **PWA** : `manifest.webmanifest` (affichage `standalone`, `start_url ./#m=gps`, icônes « P » 180/192/512 + maskable) et balises Apple pour l'ajout à l'écran d'accueil.
- **État dans l'URL** : `#m=gps&dur=…&gr=…`, `#s=2&d=…&de=…&a=…&r=…`, `#pt=lat,lon&pl=Nom…`. Préférences locales (mode, durée, rayon, orientation) dans `localStorage`, toujours dans un try/catch.

### 5. Fond de carte et clés

- `config.js` (jamais commité, dans `.gitignore`) définit `window.APP_CONFIG = {GMAPS_EMBED_KEY, MAPBOX_TOKEN}` ; `config.example.js` sert de modèle.
- **Avec `MAPBOX_TOKEN`** : Mapbox GL JS v3 (CDN api.mapbox.com), style `mapbox://styles/mapbox/standard` (préréglage `day`, étiquettes de lieux et de transport), couches de l'appli dans le slot `middle` (couche de clic dans `top`).
- **Sinon, ou si Mapbox refuse** (HTTP 401/403/429 sur style, tuiles ou géocodage, ou style non chargé après 10 s) : repli automatique sur **MapLibre GL JS 4.7.1** (unpkg) + **OpenFreeMap positron**, recherche d'adresse masquée, Mapbox ignoré 6 h sur l'appareil (`localStorage`). Le compte Mapbox est en accès « démo » (jeton non restreignable par URL, aucune facturation possible).

### 6. Dépôt et déploiement

- Arborescence : `index.html`, `manifest.webmanifest`, `icons/`, `data/`, `scripts/build_data.py`, `scripts/fetch_sources.py`, `config.example.js`, `CNAME`, `README.md`, `LICENSE` (MIT pour le code ; `data/` sous CC BY 4.0, Ville de Montréal), `.gitignore` (sources CSV/GeoJSON, `config.js`, `.env*`, caches), `PROMPT.md`, `CLAUDE.md`.
- `.github/workflows/deploy.yml` : à chaque push sur `main` (et après la mise à jour des données), assemble `_site/` (index, manifeste, `data/`, `icons/`, `CNAME`) et génère `config.js` à partir des secrets `GMAPS_EMBED_KEY` et `MAPBOX_TOKEN`, puis publie sur GitHub Pages (source « GitHub Actions »).
- `.github/workflows/maj-donnees.yml` : chaque lundi 9 h UTC (et manuellement), télécharge les sources, reconstruit `data/` et le commite s'il a changé.

### 7. Limites à afficher et à respecter

Outil personnel non officiel : la signalisation sur place a préséance. Tarification par bornes non incluse. Déneigement non inclus. « Jours d'école » approximé. Signalisation incomplète dans certains arrondissements (rues grises). En voiture, consulter la carte à l'arrêt ou la confier à un passager.

---

## Historique des fonctionnalités

| Date | Changement |
|---|---|
| 2026-09-30 | MVP : ligne verte Est, poteaux colorés, puis tronçons Géobase, évaluation par côté avec les flèches |
| 2026-09-30 | Carte MapLibre/OpenFreeMap, lien partageable, Street View, mise à jour hebdomadaire, domaine personnalisé |
| 2026-11-05 | v2 : mode GPS « Autour de moi », tuiles pour toute l'île, interprétation élargie, couverture par arrondissement |
| 2026-11-05 | Simulation de position et d'heure ; mode GPS limité aux côtés libres, traits épais |
| 2026-11-05 | Mapbox GL JS + recherche d'adresse, repli automatique sur OpenFreeMap |
| 2026-11-11 | La carte suit le véhicule et sa direction |
| 2026-11-12 | Fond Mapbox Standard |
| 2026-11-16 | Plein écran et installation sur l'écran d'accueil (PWA) |
| 2026-11-18 | Ajout de ce fichier `PROMPT.md` et de `CLAUDE.md` |
