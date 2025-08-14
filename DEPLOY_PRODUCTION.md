# Production deployment with Docker

Ce guide explique comment builder et lancer LidSeek en production avec Docker et docker-compose.

## Prerequisites
- Docker et docker-compose installés
- Un fichier `.env.production` à la racine du projet contenant vos secrets (voir exemple ci-dessous)
- Les dossiers `music_downloads/`, `formatted_songs/`, et `slskd_config/` présents

## Example `.env.production` file
```
SLSKD_API_KEY=remplacez_par_votre_cle_secrete
```

## Building the image

```sh
docker compose -f docker-compose.production.yml build
```

## Starting the services

```sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d
```

## Important file structure
- `docker-compose.production.yml` : configuration des services pour la production
- `Dockerfile.production` : image optimisée pour la production
- `.env.production` : secrets et variables d'environnement (ne pas versionner)

## Best practices
- Ne versionnez jamais vos secrets ou fichiers `.env.production`
- Utilisez des volumes pour conserver les téléchargements et logs
- Mettez à jour les images régulièrement (`docker pull ...`)

## Stopping the services

```sh
docker compose -f docker-compose.production.yml down
```

## Update

1. Puller les dernières modifications du code
2. Rebuilder l'image :
   ```sh
   docker compose -f docker-compose.production.yml build
   ```
3. Relancer les services :
   ```sh
   docker compose --env-file .env.production -f docker-compose.production.yml up -d
   ```
