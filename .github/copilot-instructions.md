# LidSeek AI Coding Agent Instructions

## Project Overview
LidSeek is a self-hosted music automation tool, serving as a Lidarr alternative that uses **Soulseek (via slskd)** for downloads instead of traditional indexers. It integrates **MusicBrainz** for metadata, uses **PostgreSQL** for state tracking, and **Redis** for API caching.

**Core workflow**: User searches artist → selects albums → app searches Soulseek → matches tracks using fuzzy logic → downloads → tags files → organizes into library structure (`Artist/Album (Year)/files`).

## Architecture & Service Boundaries

### Main Application (`app/main.py`)
- **Flask** web server with dependency injection pattern
- Services initialized in `create_app()` and passed to route blueprints via `init_routes()` factory functions
- Background thread manager (`BackgroundTaskManager`) monitors downloads every 5s (configurable via `DOWNLOAD_CHECK_INTERVAL`)
- Database initialization includes retry logic (15 attempts) for Docker startup race conditions

### Service Layer Structure
Services are **stateful singletons** initialized once and shared:

- **`DownloadManager`**: Orchestrates entire download lifecycle (search → match → download → tag → organize)
- **`SlskdDownloader`**: Wraps slskd-api client, handles Soulseek searches and file transfers
- **`TrackMatcher`**: Fuzzy matching between MusicBrainz tracks and Soulseek files (configurable `SLSKD_MIN_MATCH_RATIO`, default 0.5)
- **`MusicBrainzService`**: Artist/album metadata lookup with Redis caching (24h TTL)
- **`FileSystemService`**: File moves and directory structure (`formatted_songs/{artist}/{album (year)}/`)
- **`TaggerService`**: Uses `music-tag` library for MP3/FLAC metadata writing
- **`DownloadStatusTracker`**: Database abstraction for album/track status (`pending → downloading → completed/error`)

### Data Models (`app/models.py`)
SQLAlchemy models with **MBID strings as primary keys**:
- `Artist` → `Album` → `Track` (1-to-many relationships)
- `AlbumBlacklistSource`: tracks failed download sources to avoid retries
- Track model stores both **MusicBrainz metadata** (for matching) and **local_path** (post-download)

### Download State Machine
Status enum in `app/database.py`:
```
PENDING → DOWNLOADING → COMPLETED/ERROR
```
Background threads poll `get_downloading_albums()` and call `_check_download_status()` to update state based on slskd API responses.

## Critical Developer Workflows

### Local Development
```bash
docker-compose up  # Starts app, postgres, redis, slskd, adminer (port 8080)
```
- App runs on port **8081** with Flask debug mode enabled
- Volume mounts: `./app:/app/app` (hot reload), `./music_downloads:/downloads`, `./formatted_songs:/formatted_songs`
- Database persists in `./app/pgdata` (gitignored)

### Environment Configuration
Key variables in `.env` (loaded via `app/config/settings.py`):
- `SLSKD_API_KEY`: Must match slskd container config in `slskd_config/slskd.yml`
- `SLSKD_MIN_MATCH_RATIO`: Track matching threshold (0.0-1.0, lower = more permissive)
- `SLSKD_ALLOWED_FILETYPES`: Comma-separated (default: `mp3,flac`)
- `SLSKD_IGNORED_USERS`: Blacklist users globally
- `DATABASE_URL`: PostgreSQL connection string

### Database Migrations
**No migration framework used** - schema changes require manual SQL or wiping `pgdata/`:
```bash
docker-compose down -v  # Wipes database
docker-compose up       # Recreates from models.py
```

### Debugging Download Issues
1. Check `app/logs/downloads.log` for track matching ratios and slskd API errors
2. Use Adminer (port 8080) to inspect `albums` and `tracks` tables, check `status` columns
3. Verify slskd API key matches between services: `docker-compose logs slskd`
4. Check `AlbumBlacklistSource` table if downloads repeatedly fail from same user

## Project-Specific Conventions

### Track Matching Algorithm (`TrackMatcher`)
- Cleans filenames by removing: track numbers (`^\d+[\s.-]+`), extensions, special chars
- Uses `difflib.SequenceMatcher` for ratio comparison
- **Never match same file to multiple tracks** - uses `matched_tracks` set to prevent duplicates
- Falls back to next-best match if best match already taken

### File Organization Pattern
```
formatted_songs/
  {artist_name}/
    {album_title} ({year})/
      01 - Track Name.mp3
```
- Year extracted from `release_date` field (format: `YYYY-MM-DD`, take first 4 chars)
- Files moved from `music_downloads/` to `formatted_songs/` after tagging

### Blueprint Route Pattern
All route modules use factory pattern:
```python
def init_routes(service1, service2):
    @blueprint.route('/path')
    def handler():
        # use service1, service2
    return blueprint
```
Register in `main.py` via `app.register_blueprint(init_album_routes(musicbrainz, download_mgr))`

### Logging Convention
Every service creates its own logger via `setup_logger(name, filename)`:
- Logs to `app/logs/{filename}`
- Use `self.logger.info/warning/error` in all service methods
- **Always log track matching ratios** for debugging failed downloads

## External Dependencies & Integration Points

### Slskd API Integration
- Official Python client: `slskd-api` package
- **Must handle state transitions**: `Requested → Queued → InProgress → Completed, Succeeded`
- Error states: `Completed, Errored|Cancelled|TimedOut` (see `SlskdFileState` enum)
- Uses `SlskDirectory` and `SlskFile` models (`app/services/slsk_models.py`) to represent search results

### MusicBrainz API
- Uses `musicbrainzngs` library with custom User-Agent (set via `USER_AGENT_*` env vars)
- **Rate limiting handled by Redis caching** - cache keys: `artist:{name}`, `albums:{mbid}`
- Primary/secondary release types filter albums (e.g., `primary_type=Album`, `secondary_type=Compilation`)

### PostgreSQL Usage
- `psycopg2-binary` adapter with SQLAlchemy ORM
- **Connection pooling not configured** - uses default `SessionLocal()` per request
- Foreign keys enforced: deleting Artist cascades to Albums → Tracks

## Common Pitfalls

1. **Track matching too strict**: Lower `SLSKD_MIN_MATCH_RATIO` if legitimate matches fail (check logs for ratios)
2. **Download stuck in "downloading"**: Background thread may have crashed - check thread locks in `BackgroundTaskManager`
3. **Files not moving to library**: Verify `FORMATTED_SONGS_DIR` writable and `FileSystemService.move_track_file()` logs
4. **MusicBrainz 503 errors**: Redis cache miss during high load - increase `CACHE_EXPIRATION` or handle `ConnectionError` exceptions
5. **Slskd API key mismatch**: Must be identical in `docker-compose.yml` (both app and slskd env) and `.env` file

## Testing Approach
**No automated tests exist** - manual testing via:
1. Search for artist with known discography (e.g., "Papa Roach" in current dataset)
2. Monitor logs during download: `docker-compose logs -f app`
3. Verify files appear in `formatted_songs/` with correct tags using `music-tag` CLI

## Key Files to Reference
- `app/services/download_manager.py`: Core download orchestration logic (278 lines)
- `app/services/track_matcher.py`: Fuzzy matching algorithm
- `app/services/downloaders.py`: Slskd API wrapper and state machine
- `app/models.py`: Database schema
- `docker-compose.yml`: Service dependencies and volume mounts


## Global rules
- Always use English on comments