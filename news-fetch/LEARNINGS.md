# LEARNINGS.md
> Institutional memory for the **WorldGraph / NewsFetch** project.  
> Any AI agent or developer resuming this project should read this file first.

---

## Table of Contents

1. [Project Overview & Vision](#1-project-overview--vision)
2. [Full Project Structure](#2-full-project-structure)
3. [Environment & Infrastructure](#3-environment--infrastructure)
4. [Configuration (`app/config.py`)](#4-configuration-appconfigpy)
5. [Phase 0 — MongoDB Ingestion Worker](#5-phase-0--mongodb-ingestion-worker)
6. [Article Explorer UI](#6-article-explorer-ui)
7. [Phase 1 — Events, Stories & FalkorDB](#7-phase-1--events-stories--falkordb)
8. [How to Run Everything](#8-how-to-run-everything)
9. [Testing](#9-testing)
10. [Key Gotchas & Hard-Won Lessons](#10-key-gotchas--hard-won-lessons)
11. [Current State of the Pipeline](#11-current-state-of-the-pipeline)
12. [Next Steps](#12-next-steps)
13. [Architectural Decisions](#13-architectural-decisions)

---

## 1. Project Overview & Vision

**WorldGraph** is a news intelligence pipeline that:

1. Ingests high-signal global news articles from NewsAPI into MongoDB.
2. Deduplicates articles (exact URL + SimHash near-duplicate detection).
3. Embeds articles using Sentence-BERT (`all-MiniLM-L6-v2`, 384-d vectors).
4. Clusters articles using DBSCAN into real-world **Event micro-clusters**.
5. Links Events across days using cosine-similarity temporal linking → **Stories** (evolving narratives).
6. Writes everything into **FalkorDB** (Redis-backed property graph database) as a structured knowledge graph.
7. *(Phase 2, future)* Uses Groq LLMs (`openai/gpt-oss-120b`) to extract entities (people, orgs, places) and enrich the graph.
8. *(Phase 3, future)* Uses LLM agent tools to detect causal relationships between events.

See [`RevisedProject.md`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/RevisedProject.md) for the full architectural spec and [`Project.md`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/Project.md) for the original design.

---

## 2. Full Project Structure

```text
NewsFetch/
├── AGENTS.md                          # Coding rules & architectural guidelines (READ FIRST)
├── LEARNINGS.md                       # This file — institutional memory
├── Project.md                         # Original pipeline design spec
├── RevisedProject.md                  # Full revised WorldGraph pipeline spec (Phase 1–3)
├── UseCase.md                         # Use-case documentation
├── Queries.md                         # 400 candidate boolean search queries
├── requirements.txt                   # Pinned Python dependencies
├── pytest.ini                         # Pytest config (pythonpath = .)
├── .env                               # Secrets — NEWS_API_KEYS, GROQ_API_KEYS, MONGODB_URL
├── run_worker.py                      # CLI: MongoDB ingestion worker (Phase 0)
├── run_phase1.py                      # CLI: Phase 1 pipeline runner
├── test_pipeline.py                   # Standalone pipeline smoke-test script
│
└── app/
    ├── main.py                        # FastAPI app entry point; lifespan: MongoDB init/close
    ├── config.py                      # Pydantic Settings — all env vars in one place
    ├── dependencies.py                # FastAPI dependency injection helpers
    │
    ├── core/
    │   ├── db.py                      # Motor + Beanie lifecycle: init_db(), close_db()
    │   └── logging.py                 # Structured logging (namespace: news_pipeline.*)
    │
    ├── models/
    │   ├── documents/
    │   │   ├── article.py             # ArticleDocument — Beanie doc, unique URL index
    │   │   ├── fetch_state.py         # FetchStateDocument — worker resume checkpoint
    │   │   ├── phase1_ledger.py       # Phase1LedgerDocument — per-date Phase 1 tracking
    │   │   └── __init__.py            # Exports all documents
    │   └── schemas/
    │       ├── article.py             # ArticleDetail, ArticleListResponse (API schemas)
    │       └── cluster.py             # EventCluster, PipelineMetrics, PipelineResponse
    │
    ├── services/
    │   ├── key_rotator.py             # Multi-key rotator (429/401 → next key; live .env reload)
    │   ├── selected_queries.py        # 150 curated high-signal queries (chosen from Queries.md)
    │   ├── news_fetcher.py            # NewsAPI /everything client wrapper
    │   ├── dedup.py                   # DeduplicationService: URL SHA-1 + SimHash near-dedup
    │   ├── embeddings.py              # EmbeddingService: SentenceTransformer 384-d encoder
    │   ├── clustering.py              # ClusteringService: DBSCAN + Silhouette score
    │   ├── temporal_linker.py         # TemporalLinker: links T-day events to T-3..T-1 stories
    │   ├── falkordb_client.py         # FalkorDBClient: schema init + idempotent Cypher writes
    │   ├── phase1_pipeline.py         # Phase1Pipeline: orchestrates the full Phase 1 flow
    │   └── pipeline.py                # (Legacy) In-memory pipeline orchestrator
    │
    ├── workers/
    │   └── fetch_worker.py            # Resumable 150-query NewsAPI ingestion worker
    │
    ├── api/
    │   ├── router.py                  # API v1 router aggregator
    │   └── routes/
    │       ├── articles.py            # GET /articles (HTML), GET /api/v1/articles, /stats
    │       └── pipeline.py            # POST /api/v1/pipeline/run, GET /pipeline/health
    │
    └── templates/
        └── articles.html              # Tailwind CSS UI: infinite scroll, search, filters
```

---

## 3. Environment & Infrastructure

### `.env` File

```bash
NEWS_API_KEY=<primary_key>
NEWS_API_KEYS=<key1>,<key2>,<key3>,<key4>    # comma-separated; rotated on 429
GROQ_API_KEYS=<key1>,<key2>,...               # comma-separated; for Phase 2/3 LLM calls
# MONGODB_URL defaults to mongodb://localhost:27017
```

> **Never commit `.env`.** It contains API secrets.

### Docker Services

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| MongoDB | `mongo:latest` | `27017` | Database `news_pipeline` |
| FalkorDB | `falkordb/falkordb:latest` | `6379` (Redis protocol), `3000` (Browser UI) | Graph: `worldgraph` |

Start them:
```bash
# MongoDB
docker run -d --name mongodb -p 27017:27017 mongo:latest

# FalkorDB
docker run -d --name falkordb -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

### Python Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Configuration (`app/config.py`)

[`app/config.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/config.py) is the **single source of truth** for all settings. Uses `pydantic-settings` with `.env` file support.

| Setting | Default | Purpose |
|---------|---------|---------|
| `mongodb_url` | `mongodb://localhost:27017` | MongoDB connection |
| `mongodb_db_name` | `news_pipeline` | Database name |
| `falkordb_host` | `localhost` | FalkorDB host |
| `falkordb_port` | `6379` | FalkorDB port |
| `falkordb_graph` | `worldgraph` | Graph name in FalkorDB |
| `groq_api_keys` | `""` | Comma-separated Groq API keys |
| `groq_model` | `openai/gpt-oss-120b` | LLM model for Phase 2/3 |
| `temporal_window_days` | `3` | How many past days to compare events against |
| `temporal_similarity_threshold` | `0.70` | Cosine similarity cutoff for story linking |
| `date_from` | `2026-09-08` | Ingestion window start |
| `date_to` | `2026-10-07` | Ingestion window end |
| `embedding_model_name` | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `embedding_batch_size` | `64` | Batch size for encoding |
| `dbscan_eps` | `0.35` | DBSCAN radius (cosine distance) |
| `dbscan_min_samples` | `2` | DBSCAN minimum cluster size |
| `simhash_distance_threshold` | `1` | Max SimHash bit-distance for near-duplicates |

**Key methods:**
- `settings.get_api_keys() → list[str]` — returns all NEWS API keys deduplicated
- `settings.get_groq_api_keys() → list[str]` — returns all Groq API keys deduplicated
- `get_settings()` — `@lru_cache` singleton; use this everywhere, not `Settings()` directly

---

## 5. Phase 0 — MongoDB Ingestion Worker

### Goal
Fetch articles from NewsAPI `/v2/everything` for 150 curated queries over a 30-day window (`2026-09-08` → `2026-10-07`) and store them deduplicated in MongoDB.

### Why 150 Curated Queries?
Early runs with generic queries (`*` or broad keywords) returned low-value commercial noise (vacuum cleaner deals, affiliate promotions, retail sales). The 150 queries in [`app/services/selected_queries.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/services/selected_queries.py) were hand-picked from [`Queries.md`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/Queries.md) to cover:

- Military conflicts, airstrikes, ceasefires
- Terrorism, hostage crises, mass casualty events
- Diplomacy, UN resolutions, ICC warrants
- Elections, impeachments, coups
- Civil unrest, protests, internet blackouts
- Economic crises: sovereign debt defaults, bank collapses, IMF bailouts
- Corporate: bankruptcies, mass layoffs, antitrust probes
- Tech: AI breakthroughs, ransomware, zero-day vulns, semiconductor shortages
- Natural disasters: earthquakes, tsunamis, wildfires, hurricanes
- Health emergencies, refugee crises, plane crashes, infrastructure failures

### Key Files

| File | Role |
|------|------|
| [`app/workers/fetch_worker.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/workers/fetch_worker.py) | Main worker: pagination, key rotation, dedup, state persistence |
| [`app/services/selected_queries.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/services/selected_queries.py) | The 150 unique query strings |
| [`app/services/key_rotator.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/services/key_rotator.py) | Multi-key rotator with live `.env` reload |
| [`app/models/documents/fetch_state.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/models/documents/fetch_state.py) | Resume checkpoint (per-query progress) |
| [`app/models/documents/article.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/models/documents/article.py) | ArticleDocument with unique URL index |
| [`run_worker.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/run_worker.py) | CLI entry point |

### Pagination Logic

NewsAPI returns max 100 articles per page. Developer plan has a hard limit of 100 total per query (HTTP 426 on page ≥ 2). The worker:

1. Fetches page 1 → reads `totalResults`
2. Calculates `total_pages = ceil(totalResults / 100)`
3. Iterates pages 2..N — handles HTTP 426 gracefully (skips, does not crash)
4. After each page, writes to MongoDB with dedup check

### Key Rotation

[`KeyRotator`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/services/key_rotator.py):
- Loads all keys from `NEWS_API_KEYS` + `NEWS_API_KEY` at startup
- On HTTP 429: rotates to next key, reloads `.env` first (in case new keys were added at runtime)
- On HTTP 401: removes bad key, continues
- If all keys exhausted: raises `RuntimeError`

### Deduplication on Ingest

Before inserting, the worker checks if `url` already exists in MongoDB. If found, it merges the `matched_queries` list (adds the new query tag if not already present) and skips the insert.

### State Persistence & Resumability

`FetchStateDocument` in MongoDB (`fetch_state` collection) stores:
- Which queries have been completed
- The current page number for in-progress queries
- Error messages for failed queries

On restart, the worker reads this state and skips already-completed queries. Use `--reset` to clear state and restart from scratch.

### CLI Commands

```bash
# Check current progress
python run_worker.py --status

# Run with default settings (all 150 queries, full date range)
python run_worker.py

# Run with a limit (first N articles per query for testing)
python run_worker.py --limit 200

# Reset state and start from scratch
python run_worker.py --reset

# Custom date range
python run_worker.py --from-date 2026-09-08 --to-date 2026-10-07
```

### Results

- **11,030 articles** successfully ingested into MongoDB (`news_pipeline.articles`)
- All **150/150 queries** completed
- Date range: `2026-09-08` → `2026-10-07`

---

## 6. Article Explorer UI

A web UI to browse, search, and filter ingested articles.

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/articles` | GET | HTML page with infinite-scroll article explorer |
| `/api/v1/articles` | GET | Paginated JSON API (params: `page`, `limit`, `search`, `source`, `query`) |
| `/api/v1/articles/stats` | GET | Article counts, source counts, query tag counts |

### Key Files

| File | Role |
|------|------|
| [`app/templates/articles.html`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/templates/articles.html) | Full UI: Tailwind CSS, IntersectionObserver lazy loading, debounced search |
| [`app/api/routes/articles.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/api/routes/articles.py) | Route handlers (thin; business logic stays in service layer) |

### Features

- **Infinite scroll**: `IntersectionObserver` fires on sentinel element to load next page
- **Debounced search**: 300ms debounce on the search input → fewer DB queries
- **Source filter**: dropdown of all unique sources
- **Query tag filter**: browse articles by which of the 150 queries matched them

### Run the UI

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
# Open: http://localhost:8000/articles
```

---

## 6.1 Phase 1 Graph Explorer UI (`/phase1` or `/graph`)

A dedicated, interactive force-directed graph and story evolution timeline page built specifically to visualize Phase 1 FalkorDB output.

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/phase1` or `/graph` | GET | Full visualizer UI (Vis-Network interactive graph + Story timeline) |
| `/api/v1/phase1/stats` | GET | Graph statistics & active date span |
| `/api/v1/phase1/dates` | GET | Per-date event and article counts |
| `/api/v1/phase1/stories` | GET | Paginated stories with event counts & date ranges |
| `/api/v1/phase1/story/{id}/graph` | GET | Force-directed nodes & edges for a narrative thread |
| `/api/v1/phase1/event/{id}` | GET | Detailed event view with reporting articles & temporal predecessor links |

### Key Files

| File | Role |
|------|------|
| [`app/templates/phase1_explorer.html`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/templates/phase1_explorer.html) | Interactive Vis-Network graph canvas, timeline evolution view, node inspector drawer |
| [`app/services/phase1_service.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/services/phase1_service.py) | Graph traversal queries, subgraph extraction, timeline structuring |
| [`app/api/routes/phase1.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/api/routes/phase1.py) | Thin API endpoints & HTML template route |

### Features

- **Force-Directed Network Graph (Vis-Network)**:
  - `:Story` hub nodes (purple hexagons)
  - `:Event` micro-cluster nodes (sky blue circles)
  - `:Article` nodes (teal dots)
  - `:Source` nodes (amber squares)
  - `PRECEDED (+days)` sequential arrows connecting events across days
  - `REPORTS_ON` similarity edges with thickness proportional to centroid similarity
- **Story Evolution Timeline**:
  - Chronological multi-day timeline showing each event's progression, date, category, and summary
- **Node Inspector Drawer**:
  - Clicking any node opens a details drawer with full summaries, reporting articles with similarity percentages, source links, and preceding/following events.
- **Story Search & Filters**:
  - Filter by minimum events (All / Multi-day $\ge 2$ / Deep $\ge 5$), date picker, debounced keyword search.

### Run the Phase 1 Explorer

```bash
uvicorn app.main:app --reload --port 8000
# Open in browser: http://localhost:8000/phase1
```

## 7. Phase 1 — Events, Stories & FalkorDB

### Overview

Phase 1 processes MongoDB articles day-by-day and builds a knowledge graph in FalkorDB:

```
MongoDB Articles (by date)
    │
    ▼ DeduplicationService (URL SHA-1 + SimHash)
    │
    ▼ EmbeddingService (SentenceTransformer 384-d)
    │
    ▼ ClusteringService (DBSCAN cosine-distance)
    │      → each cluster = an Event
    │
    ▼ TemporalLinker (compare today's events vs T-3..T-1)
    │      → if similarity ≥ 0.70 → link Event to existing Story
    │      → else create new Story
    │
    ▼ FalkorDBClient (idempotent MERGE writes)
         → :Article, :Source, :Event, :Story nodes
         → :REPORTS_ON, :PUBLISHED_BY, :PART_OF, :PRECEDED_BY edges
```

### FalkorDB Graph Schema

#### Node Labels

| Label | Key Properties | Description |
|-------|---------------|-------------|
| `:Article` | `url`, `title`, `published_at`, `source_name` | Individual news article |
| `:Source` | `source_id`, `name`, `reliability` | News publisher |
| `:Event` | `event_id`, `occurred_at`, `category`, `centroid` (384-d vecf32) | DBSCAN cluster of related articles |
| `:Story` | `story_id`, `title`, `started_at`, `last_updated_at` | Evolving narrative linking Events |

#### Edge Types

| Edge | From → To | Meaning |
|------|-----------|---------|
| `:REPORTS_ON` | Article → Event | Article is part of this event cluster |
| `:PUBLISHED_BY` | Article → Source | Article was published by this source |
| `:PART_OF` | Event → Story | Event belongs to this story |
| `:PRECEDED_BY` | Event → Event | Temporal predecessor relationship |

#### Indexes

```
Article.url           — lookup by URL
Source.source_id      — lookup by source identifier
Event.event_id        — lookup by event identifier
Event.occurred_at     — range queries on date
Event.category        — filter by category
Story.story_id        — lookup by story identifier
Article.published_at  — range queries on publication date
Event.centroid        — 384-d cosine vector index (for temporal similarity)
```

### ID Naming Conventions

- **Event ID**: `evt_{date}_{cluster_idx}` (e.g., `evt_2026-09-08_0`)
- **Story ID** (new story on first day): `story_{date}_{idx}` (e.g., `story_2026-09-08_0`)
- **Source ID**: lowercased source name with spaces replaced by `-`

### The Ledger System (`Phase1LedgerDocument`)

[`app/models/documents/phase1_ledger.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/models/documents/phase1_ledger.py) tracks per-date processing state:

| Field | Type | Values |
|-------|------|--------|
| `date` | str | `YYYY-MM-DD` |
| `status` | str | `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED` |
| `raw_articles_count` | int | Articles pulled from MongoDB for this date |
| `deduped_articles_count` | int | After URL + SimHash dedup |
| `clusters_count` | int | DBSCAN clusters (= Events created) |
| `stories_created` | int | New stories started |
| `stories_extended` | int | Existing stories extended by temporal linking |
| `error_message` | str \| None | Set if status == FAILED |
| `started_at` | datetime | When processing began |
| `completed_at` | datetime | When processing finished |

A date already `COMPLETED` is skipped unless `--force` is passed.

### Key Service Classes & Their Correct APIs

> **Critical**: The method names matter — using the wrong name causes `AttributeError`.

| Class | Module | Key Method | Return Type |
|-------|--------|-----------|-------------|
| `DeduplicationService` | `app.services.dedup` | `deduplicate(articles)` | `tuple(articles, url_dupes, content_dupes)` |
| `EmbeddingService` | `app.services.embeddings` | `generate_embeddings(texts)` | `np.ndarray` (shape: N×384) |
| `ClusteringService` | `app.services.clustering` | `cluster_articles(articles, embeddings)` | `tuple(clusters, noise_articles, metrics_dict)` |
| `TemporalLinker` | `app.services.temporal_linker` | `link(today_events, past_events)` | `dict: event_id → story_id` |
| `FalkorDBClient` | `app.services.falkordb_client` | `write_article_and_source()`, `write_event()`, `write_story()`, `link_event_to_story()`, `link_events_preceded()` | None |

**`ClusteringService` note**: clusters are `EventCluster` objects. Access articles via `.articles` attribute (not dict keys).

**`DeduplicationService` note**: the class is named `DeduplicationService`, not `DedupService`.

### `vecf32` Syntax for FalkorDB

When writing vector properties to FalkorDB:

```python
# CORRECT — must wrap the list with vecf32()
self.graph.query(
    "MERGE (e:Event {event_id: $id}) SET e.centroid = vecf32($vec)",
    {"id": event_id, "vec": centroid_list}
)

# WRONG — plain list will not create a proper vector property
"SET e.centroid = $vec"
```

Vector search uses:
```cypher
CALL db.idx.vector.queryNodes("Event", "centroid", 10, vecf32($vec))
YIELD node, score
RETURN node.event_id, score
```

### CLI Commands for Phase 1

```bash
# Check ledger status and FalkorDB graph stats
python run_phase1.py --status

# Process a specific date
python run_phase1.py --date 2026-09-08

# Re-process even if already COMPLETED
python run_phase1.py --date 2026-09-08 --force

# Process all dates in MongoDB, chronologically
python run_phase1.py --run-all

# Process first 3 dates only (for fast verification)
python run_phase1.py --run-all --limit-days 3

# Clear all FalkorDB graph data before running
python run_phase1.py --clear-graph --run-all

# Debug logging
python run_phase1.py --run-all --log-level DEBUG
```

### Graph Stats After 2026-09-08

The first date was successfully processed:

| Entity | Count |
|--------|-------|
| :Article nodes | 543 |
| :Source nodes | 187 |
| :Event nodes | 48 |
| :Story nodes | 48 |
| :REPORTS_ON edges | 209 |
| :PUBLISHED_BY edges | 543 |
| :PART_OF edges | 48 |
| :PRECEDED_BY edges | 0 (first day, no past events) |

---

## 8. How to Run Everything

### Step 1: Start Docker Services

```bash
docker start mongodb falkordb
# or docker run ... if not created yet (see §3)
```

### Step 2: Activate Python Environment

```bash
cd /home/yashwant/MyProject/GraphHacksHackathons/NewsFetch
source .venv/bin/activate
```

### Step 3: Run MongoDB Ingestion Worker (Phase 0)

```bash
# Check if already done (should show 150/150 queries completed)
python run_worker.py --status

# If not done, run it:
python run_worker.py
```

### Step 4: Run Phase 1 Pipeline

```bash
# Check current Phase 1 progress
python run_phase1.py --status

# Process all remaining dates (skips COMPLETED dates)
python run_phase1.py --run-all
```

> **Note**: `--run-all` loads the embedding model once (~42 seconds) and reuses it for all dates. This is much faster than processing dates one at a time.

### Step 5: Browse Articles UI

```bash
uvicorn app.main:app --reload --port 8000
# Open: http://localhost:8000/articles
```

### Step 6: Access FalkorDB Browser UI

Open `http://localhost:3000` — this is the FalkorDB graph browser.

---

## 9. Testing

### Test Files

| File | Tests | Coverage |
|------|-------|----------|
| [`tests/test_api.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/tests/test_api.py) | 5 | FastAPI routes, `/articles` HTML, `/api/v1/articles`, `/stats` |
| [`tests/test_pipeline.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/tests/test_pipeline.py) | 5 | Dedup, clustering, embeddings, e2e pipeline |
| [`tests/test_worker.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/tests/test_worker.py) | 3 | 150 queries list, KeyRotator, Beanie document models |

### Run Tests

```bash
pytest tests/ -v
# All 13 tests should pass
```

### pytest.ini

```ini
[pytest]
pythonpath = .
asyncio_mode = auto
```

---

## 10. Key Gotchas & Hard-Won Lessons

### 1. Motor/Beanie Version Conflict

**Problem**: `motor>=3.7.0` breaks `beanie 2.x`.

**Solution**: Pin to:
```
beanie>=1.30.0,<2.0.0
motor>=3.6.0,<3.7.0
pymongo>=4.9.0,<4.10.0
```

These are already in [`requirements.txt`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/requirements.txt).

### 2. NewsAPI Developer Plan: Max 100 Results

The developer plan returns HTTP **426** when requesting page 2+. The worker handles this gracefully: it logs the warning, breaks the pagination loop, and moves on to the next query. This means we get at most 100 articles per query on the developer tier.

### 3. FalkorDB `vecf32()` is Mandatory

You **must** use `vecf32($vec)` when setting vector properties. A plain Python list assigned as a property will NOT be stored as a vector and vector search will fail silently or error.

### 4. FalkorDB COUNT Subqueries

Complex `COUNT { MATCH (:Article) }` subquery syntax may not work in all FalkorDB versions. Use individual queries instead:
```cypher
MATCH (n:Article) RETURN count(n) AS count
```

### 5. Embedding Model Load Time

`all-MiniLM-L6-v2` takes **~42 seconds** to load on first use. When running `--run-all`, the model is cached in-process across all dates — much faster than loading per-date.

### 6. Process Kill OOM (exit 132)

`2026-09-09` was being processed when the process was killed with exit code 132 (SIGILL or OOM). The ledger entry for that date will show `PROCESSING` or `FAILED`. Use `--force` to retry:
```bash
python run_phase1.py --date 2026-09-09 --force
```

### 7. `DeduplicationService` vs `DedupService`

The class in [`app/services/dedup.py`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/app/services/dedup.py) is named `DeduplicationService`. Do not use `DedupService` — it does not exist.

### 8. `ClusteringService.cluster_articles()` Return Signature

Returns a **3-tuple**: `(clusters, noise_articles, metrics_dict)`
- `clusters`: list of `EventCluster` objects (access articles via `.articles`)
- `noise_articles`: articles DBSCAN could not assign to any cluster
- `metrics_dict`: silhouette score, cluster count, etc.

### 9. `EmbeddingService.generate_embeddings()` Method Name

The correct method is `generate_embeddings(texts: list[str]) -> np.ndarray`. Do not use `encode_articles()` — that method does not exist.

### 10. `init_db()` Must Be Called Before Any Beanie Query

`Phase1Pipeline.process_date()` calls `await init_db(self.settings)` at the top. If you call Beanie queries without `init_db()`, you'll get `CollectionWasNotInitialized` errors.

---

## 11. Current State of the Pipeline

| Component | Status |
|-----------|--------|
| MongoDB articles | ✅ **11,030 articles** ingested, all 150 queries completed |
| Article Explorer UI | ✅ Working at `http://localhost:8000/articles` |
| FalkorDB schema | ✅ All indexes (Article, Source, Event, Story, Entity, Country, Company, Person, Organization, Industry, Commodity, Location, Statement) + 384-d vector index |
| Phase 1 (Foundation) | ✅ **100% COMPLETED** (30/30 dates) — 10,945 articles, 806 sources, 899 events, 689 stories, 210 preceded edges |
| Phase 2 (Enrichment) | ✅ **100% COMPLETED** — 899 events enriched, 2,333 entities, 5,427 involves, 4,241 related edges |
| Phase 3 (Reasoning & Causal Edges) | ✅ **IMPLEMENTED & TESTED** — Autonomous Tool Calling Loop, Trust Property Contract, Phase3Ledger, CLI runner `run_phase3.py`, Product Use Cases API routes |
| UI Graph Visualizer | ✅ **UPDATED** — `/phase1`, `/phase2`, `/graph` supports Phase 1 + Phase 2 entities, ego-networks, statement nodes, and filters |

### MongoDB Collections

| Collection | Documents | Notes |
|------------|-----------|-------|
| `articles` | ~11,030 | Unique URL index; `matched_queries` array for filter tags |
| `fetch_state` | 150 | One per query; tracks completion/progress |
| `phase1_ledger` | 30 | All 30 dates marked `COMPLETED` |
| `phase2_ledger` | 899 | All 899 events marked `COMPLETED` |
| `phase3_ledger` | 899 | Event-by-event reasoning tracking (resumable) |
| `entity_alias_cache` | dynamic | Persistent cache for normalized aliases |

---

## 12. Phase 2 Usage & Commands

### CLI Runner: `run_phase2.py`

```bash
# Check current Phase 2 status and graph entity counts
python run_phase2.py --status

# Test run first 5 events
python run_phase2.py --limit 5

# Enrich a specific event by ID
python run_phase2.py --event-id evt_2026-09-08_0

# Run enrichment across all 899 events
python run_phase2.py --run-all

# Run only rule-based links (country RELATED_TO edges)
python run_phase2.py --rules-only
```

---

## 13. Phase 3 Usage & Causal Reasoning

Phase 3 introduces an **Autonomous Agent Tool Calling Loop** (`graph_agent_v1`) to determine causal and impact edges between events and entities.

### Guardrails & Trust Property Contract
1. **Tool-Guarded Persistence**: The agent has NO direct Cypher execution privileges. It must use the `write_edge` tool.
2. **Confidence Floor**: Every edge must have `confidence >= 0.55` (values below 0.55 are rejected).
3. **Evidence Requirement**: High-impact causal edges (`CAUSED`, `CONTRIBUTED_TO`) require at least one cited article URL in `evidence_ids`. If missing, the engine automatically downgrades the edge to `RELATED_TO` (or rejects).
4. **Self-Loop Prevention**: Self-referencing edges (`source_id == target_id`) are rejected.
5. **Node Existence Verification**: Source and target nodes must exist in FalkorDB before writing.
6. **Human Editor Protection**: Edges written with `agent="editor"` cannot be overwritten or downgraded by AI agents.

### CLI Runner: `run_phase3.py`

```bash
# Check current Phase 3 status and reasoning edge breakdown
python run_phase3.py --status

# Test run on a single event
python run_phase3.py --event-id evt_2026-09-08_0

# Test run first 5 events
python run_phase3.py --limit 5

# Run with fallback model (openai/gpt-oss-20b)
python run_phase3.py --event-id evt_2026-09-08_15 --model openai/gpt-oss-20b

# Run with custom request-per-minute pacing (default: 8 req/min across pool)
python run_phase3.py --run-all --rpm 8
```

### Groq Rate Limit Strategy & TPM Protection
To eliminate 429 TPM limits when running Phase 3 across 8 Groq API keys:
1. **Token Usage Reduction**:
   - `SYSTEM_PROMPT` streamlined from ~450 tokens to ~130 tokens.
   - `PHASE3_TOOLS_SPEC` tool and argument descriptions compacted.
   - Tool execution results in message history compacted to prevent prompt bloat.
   - `max_tokens` set to 1024 (avoiding 2048 token reservations by Groq while giving full room for JSON completion).
2. **LRU Key Distribution & Rate Pacing**:
   - Requests are distributed across all keys in the pool using Least-Recently-Used (LRU) selection.
   - Built-in rate pacer enforces `requests_per_minute` (default: 8 req/min, i.e., 7.5s interval between requests). With 8 keys, each key is only hit once every 60s, allowing its 8k TPM window to completely reset.
3. **Automatic Secondary Fallback Model (`openai/gpt-oss-20b`)**:
   - Primary model: `openai/gpt-oss-120b`
   - Secondary fallback model: `openai/gpt-oss-20b`
   - If a TPM limit (HTTP 429/413) is detected, `GroqClient` automatically activates fallback to `openai/gpt-oss-20b` and retries seamlessly with full native tool-calling support.
4. **Header Telemetry & Detailed Error Logging**:
   - On any 429/413 status, prints a clear diagnostic banner with limit type (TPM/RPM/RPD), used vs requested tokens, remaining tokens, reset countdown, and retry-after backoff.

### Web Explorer Phase 3 Visualizer (`/phase1`, `/phase2`, `/graph`)
Even when rate-limited on Groq API tokens, the existing Phase 3 graph is fully interactive and visualizable via the unified explorer:
1. **Tri-Tab Sidebar**:
   - **Tab 1 (Stories)**: Narrative thread explorer with multi-day evolution filters.
   - **Tab 2 (Entities)**: Phase 2 typed entity directory with category filters.
   - **Tab 3 (Causal AI)**:
     - **Mode 1 (Edges Feed)**: Filterable list of all generated reasoning edges (`CAUSED`, `CONTRIBUTED_TO`, `AFFECTS`, `IMPACTED`) showing confidence bars, rationale snippets, and 1-click graph plotting.
     - **Mode 2 (UC-01 Multi-Hop)**: Interactive depth traversal (1-3 hops) plotting connected actors, downstream effects, and causal paths.
     - **Mode 3 (UC-02 Impact Radius)**: Bounded BFS calculating and rendering impacted countries, companies, industries, and commodities.
     - **Mode 4 (UC-03 Connect the Dots)**: Finds and plots the shortest/strongest causal chain between any two events.
2. **Interactive Graph Styling**:
   - 🔴 **CAUSED**: `#f43f5e`, width 3.0, bold arrows
   - 🟡 **CONTRIBUTED_TO**: `#f59e0b`, width 2.5, dashed arrows
   - 🟣 **AFFECTS**: `#a855f7`, width 2.0, smooth curves
   - 🔷 **IMPACTED**: `#06b6d4`, width 2.0
   - Toolbar toggle: `Causal Links` checkbox enables/disables reasoning edges on the fly.
3. **Trust Properties & Evidence Inspector Drawer**:
   - Clicking any reasoning edge in the graph or feed inspects its Trust Properties: confidence progress bar, status (`inferred`/`confirmed`), source agent (`causal_agent` or `editor`), agent rationale, and supporting evidence URLs with reliability scores.
   - **UC-08 Human Curation**: Editors can confirm or adjust edge confidence directly in the UI. Curation permanently sets `agent='editor'`, protecting edges from AI overwrite.
4. **Event Inspector Integration**:
   - Clicking any Event node renders its Phase 3 causal links (Downstream Effects, Upstream Causes, Affected Entities) alongside Phase 2 entities and reporting articles, with one-click buttons to run UC-01 Multi-Hop or UC-02 Impact Radius.

---

## 14. Architectural Decisions

### Why FalkorDB?

FalkorDB is Redis-backed (fast writes, low latency) and supports both property graph Cypher queries and vector search in the same index. This allows Phase 1 (structural graph) and future Phase 2 (semantic similarity search) to coexist in one store.

### Why DBSCAN for Clustering?

DBSCAN is density-based — it doesn't require specifying the number of clusters upfront and naturally handles noise (articles that don't belong to any event cluster). Articles in the noise set are still written to FalkorDB as standalone articles but not linked to Events.

### Why SimHash for Near-Dedup?

URL-based dedup (SHA-1 of URL) catches exact duplicates but not the same story published under a slightly different URL. SimHash provides locality-sensitive hashing that flags near-duplicate content (e.g., wire service articles republished verbatim across 5 outlets).

### Why Ledger-Based Progress Tracking?

The embedding step for a single day (300-600 articles) takes 30-120 seconds. If the process is killed mid-day (OOM, power cut, etc.), without a ledger we'd have to re-run all already-processed days. The `Phase1LedgerDocument`, `Phase2LedgerDocument`, and `Phase3LedgerDocument` make every unit of work atomic and fully resumable.

### Multi-Key Rotation Strategy

Both `KeyRotator` (NewsAPI) and `GroqClient` share the same pattern:
1. Keep an ordered list of keys
2. On rate-limit response: try next key
3. On invalid-key response: permanently remove that key
4. Reload `.env` before rotation (allows adding keys at runtime without restart)

---

*Last updated: 2026-10-10 by AI agent based on full session history.*

