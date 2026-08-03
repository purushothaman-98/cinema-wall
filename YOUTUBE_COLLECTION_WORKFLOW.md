# YouTube Collection Workflow

This scanner uses two different jobs so the free YouTube API quota is spent where it matters.

## 30-minute monitor

Runs every 30 minutes.

- Refreshes statistics for the current active video set.
- Fetches comments only when a video is new, the public comment count changed, or the refresh window is due.
- Does not run broad YouTube discovery.
- Does not search major channels again.

This keeps live tracking cheap and stable.

## Daily discovery

Runs when `video_discovery_hours` has elapsed or `selection_version` changes.

Discovery order:

1. Read recent uploads from known major Tamil review/commentary channels using exact channel IDs.
2. Match those uploads to the active TMDB/manual movie catalog.
3. Search weakly covered films directly.
4. Run a small film-by-channel matrix for weak films.
5. Run a small broad open-YouTube search as a fallback.

The major-channel upload feed is the most important layer. It is more reliable than searching YouTube for channel names because it reads the channel's own recent uploads.

## Selection Rules

Videos are tagged separately by:

- `content_format`: full video or Short
- `video_intent`: review, short review, public review, deep analysis, roast/commentary, interview archive, news/update, or promo
- `source_category`: critic, general review, deep analysis, roast/commentary, mixed media, interview archive, or open YouTube

Promotional videos are excluded from review evidence. Interviews and news are kept as context, not mixed into review sentiment.

## Major-Channel Coverage

For major channels, prefer adding stable `channel_id` values in `scanner_config.json`. Channels with IDs can use the low-quota upload-feed path. Channels without IDs remain in the fallback search layer and may be missed more often.

Current exact-ID channels include:

- KaKi's Talkies
- Sudhir Srinivasan
- Galatta Plus
- Second Show
- Delite Cinemas
- Filmi Craft
- Tamil Talkies
- Empty Hand
- Cinema Vikatan
- Valai Pechu

Still worth adding exact channel IDs when confirmed:

- Plip Plip
- Kodangi
- Touring Talkies
- BehindwoodsTV
- Galatta Tamil
- Nona Prince

## Health Checks

After each run, inspect `data/live/scan_metadata.json`.

For 30-minute monitor runs, expected values:

- `discovery_mode`: `monitor_existing_selection`
- `upload_feed_channels_run`: `0`
- `source_channel_queries_run`: `0`
- `channel_matrix_queries_run`: `0`
- `broad_discovery_queries_run`: `0`
- `status`: `healthy`

For daily discovery runs, expected values:

- `discovery_mode`: `daily_tmdb_plus_broad_youtube`
- `upload_feed_channels_run`: greater than `0`
- `upload_feed_matched_hits`: greater than `0` when major channels covered current films
- `status`: `healthy`

