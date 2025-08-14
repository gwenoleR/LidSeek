<p align="center">
  <img src="./public/assets/images/logo.svg" width="250" alt="Logo" >
</p>

<h1 align="center">LidSeek</h1>
<h3 align="center">A Lidarr alternative based on Soulseek</h3>

<p align="center">
  <a href="https://www.buymeacoffee.com/gwenoler" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;" ></a>
</p>

---

## Prerequisites

* This app is using Soulseek to download music. So you have to create a Soulseek account to use it. 
Personnaly I use [Nicotine+](https://nicotine-plus.org) to manage my Soulseek Account 

* The app communicate with the Soulseek Deamon using an [API KEY](https://github.com/slskd/slskd/blob/master/docs/config.md#authentication).  You can generate one with a random string between 16 and 255 characters


## Installation

```sh
# Create a new directory
mkdir lidseek
cd lidseek

# Create docker-compose.yml and copy the example contents into it
touch docker-compose.yml
nano docker-compose.yml

# Create .env and copy the example contents into it. Configure as you see fit
touch .env
nano .env

# Create soulseek.yml and copy the example contents into it. Configure as you see fit
touch config/soulseek.yml
nano config/soulseek.yml
```

### docker-compose.yml

```yaml
services:
  app:
    image: 
    ports:
      - "8081:8081"
    environment:
      - REDIS_HOST=redis
      - SLSKD_HOST=http://slskd:5030
      - SLSKD_API_KEY=${SLSKD_API_KEY}
    volumes:
      - ./music_downloads:/downloads
      - ./formatted_songs:/formatted_songs
    depends_on:
      - redis
      - slskd
    restart: unless-stopped

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    restart: unless-stopped

  slskd:
    image: slskd/slskd:latest
    ports:
      - "5030:5030"
    volumes:
      - ./music_downloads:/app/downloads
      - ./config/slskd.yml:/app/slskd.yml:ro
    environment:
      - SLSKD_REMOTE_CONFIGURATION=true
      - SLSKD_SHARED_DIR=/downloads
      - SLSKD_API_KEY=${SLSKD_API_KEY}
      - SLSKD_REMOTE_ACCESS=true
    restart: unless-stopped
```

### .env

```sh
# Example .env file for LidSeek
# Copy this file to .env and fill in the required values

# User agent
USER_AGENT_NAME=LidSeek
USER_AGENT_VERSION=1.0.0
USER_AGENT_EMAIL=contact@email.com

# Download check interval (in seconds)
DOWNLOAD_CHECK_INTERVAL=5

# Slskd
SLSKD_HOST=http://slskd:5030
SLSKD_API_KEY=<SOULSEEK_API_KEY>
SLSKD_URL_BASE=/
SLSKD_DOWNLOAD_DIR=/downloads
SLSKD_ALLOWED_FILETYPES=mp3,flac
SLSKD_IGNORED_USERS=
SLSKD_MIN_MATCH_RATIO=0.5

# Destination folder for formatted files
FORMATTED_SONGS_DIR=/formatted_songs
```

### soulseek.yml

```yaml
soulseek:
  address: vps.slsknet.org
  port: 2271
  username: <SOULSEEK_USER>
  password: <SOULSEEK_USER_PASSWORD>
  description: |
    A slskd user. https://github.com/slskd/slskd
  listen_ip_address: 0.0.0.0
  listen_port: 50300
  diagnostic_level: Info
  distributed_network:
    disabled: false
    disable_children: false
    child_limit: 25
    logging: false
  connection:
    timeout:
      connect: 10000
      inactivity: 15000
    buffer:
      read: 16384
      write: 16384
      transfer: 262144
      write_queue: 250
    proxy:
      enabled: false
      address: ~
      port: ~
      username: ~
      password: ~
shares:
  directories:
    - /app/downloads
  filters:
    - \.ini$
    - Thumbs.db$
    - \.DS_Store$
  cache:
    storage_mode: memory
    workers: 16
    retention: ~ # retain indefinitely (do not automatically re-scan)
web:
  authentication:
    api_keys:
      lidseek:
        key: <SOULSEEK_API_KEY>

```

## Running the app

To run the application run the following command:

```sh
docker compose up
```

The docker container is now running; navigate to http://localhost:8081/ to access the app.

