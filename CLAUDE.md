# Instructions pour Claude — dépôt garetoiaumetro

- **`PROMPT.md` doit rester à jour.** À chaque changement fonctionnel (interface, comportement, données, interprétation des panneaux, workflows, clés, déploiement), mettre à jour dans le même commit :
  1. la section concernée du prompt, pour qu'il permette toujours de recréer l'application telle qu'elle est ;
  2. la ligne « Dernière mise à jour » en tête du fichier ;
  3. le tableau « Historique des fonctionnalités ».
- Les commits automatiques « Données du … » (mise à jour hebdomadaire) ne demandent pas de mise à jour de `PROMPT.md`.
- Garder aussi le `README.md` cohérent avec les changements.
- Langue du projet : français (Québec).
- Ne jamais commiter de clé ni de jeton : ils passent par les secrets GitHub et `config.js` (ignoré par git).
- Pousser sur `main` publie le site : demander l'accord du propriétaire avant chaque push.
