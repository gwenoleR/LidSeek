# Logging Guide

This app provides per-service rotating logs and optional JSON formatting to keep output readable while preserving context for debugging.

## Env toggles

Set these in `.env`:

- `LOG_LEVEL=INFO` — default level for all service loggers.
- `JSON_LOGS=true` — emit structured JSON logs (recommended for filtering).
- `CONSOLE_LOGS=false` — reduce terminal noise, keep logs in files.
- `LOG_DIR=/app/app/logs` — target directory for log files.

## Log files

- `downloads.log` — DownloadManager, SlskdDownloader, DownloadStatusTracker.
- `track_matcher.log` — TrackMatcher decisions, ratios (mostly DEBUG).

## Recommended usage

- Tail focused files:
  - `tail -f app/logs/downloads.log`
  - `tail -f app/logs/track_matcher.log`
- Switch to `DEBUG` when investigating matching details by setting `LOG_LEVEL=DEBUG`.

## Message conventions

Key fields (when JSON logs are enabled):
- `correlation_id` — unique per album processing run.
- `album_mbid`, `album_title`, `artist_name` — identify scope.
- `track_mbid`, `track_title` — when relevant in matching.
- `slsk_user`, `slsk_file`, `state` — Soulseek-specific context.

## Typical events

- `Starting download` — includes source username and file count.
- `Match found` — includes track id, file, and ratio.
- `No result found` — search misses at INFO; enable DEBUG for deeper traces.
- `Error processing files` / `Error starting download` — ERROR with stack trace.

## Tips

- Use JSON logs and `jq` for filtering:

```sh
jq -r 'select(.correlation_id=="<id>") | .msg' app/logs/downloads.log
```

- Keep `CONSOLE_LOGS=false` in Docker to avoid mixed stdout noise.
