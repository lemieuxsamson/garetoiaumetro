// Copier ce fichier en config.js pour tester en local (config.js est ignoré par git).
// En production, config.js est généré par .github/workflows/deploy.yml
// à partir des secrets GitHub GMAPS_EMBED_KEY et MAPBOX_TOKEN.
window.APP_CONFIG = {
  GMAPS_EMBED_KEY: '',   // Google Maps Embed API (Street View intégré)
  MAPBOX_TOKEN: ''       // jeton public Mapbox pk.… (fond de carte + recherche d'adresse)
};
