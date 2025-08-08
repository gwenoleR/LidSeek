# Déploiement en production avec Docker

Ce guide explique comment builder et lancer MusicSearcher en production avec Docker et docker-compose.

## Prérequis
- Docker et docker-compose installés
- Un fichier `.env.production` à la racine du projet contenant vos secrets (voir exemple ci-dessous)
- Les dossiers `music_downloads/`, `formatted_songs/`, et `slskd_config/` présents

## Exemple de fichier `.env.production`
```
SLSKD_API_KEY=remplacez_par_votre_cle_secrete
```

## Construction de l'image

```sh
docker compose -f docker-compose.production.yml build
```

## Lancement des services

```sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

## Structure des fichiers importants
- `docker-compose.production.yml` : configuration des services pour la production
- `Dockerfile.production` : image optimisée pour la production
- `.env.production` : secrets et variables d'environnement (ne pas versionner)

## Bonnes pratiques
- Ne versionnez jamais vos secrets ou fichiers `.env.production`
- Utilisez des volumes pour conserver les téléchargements et logs
- Mettez à jour les images régulièrement (`docker pull ...`)

## Arrêter les services

```sh
docker compose -f docker-compose.production.yml down
```

## Mise à jour

1. Puller les dernières modifications du code
2. Rebuilder l'image :
   ```sh
   docker compose -f docker-compose.production.yml build
   ```
3. Relancer les services :
   ```sh
   docker compose --env-file .env.production -f docker-compose.production.yml up -d
   ```
