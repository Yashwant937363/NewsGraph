# WorldGraph — Revised Pipeline & FalkorDB Data Model

**Purpose of this doc:** Mental model only. Enough for an agent to implement without ambiguity. No code — just what flows where and what the graph looks like.

---

## Part 1 — The Pipeline (Mental Model)

### Phase 1 — Foundation (articles → events → stories)

```
MongoDB (ArticleDocument)
    │
    │ group by published_at date
    ▼
[Daily batch of articles]
    │
    │ dedup (URL + SimHash)
    ▼
[Unique articles]
    │
    │ embed (all-MiniLM-L6-v2, 384-d)
    ▼
[Vectors]
    │
    │ DBSCAN (eps=0.35, min_samples=2, cosine)
    ▼
[Daily micro-clusters]
    │
    │ temporal linker (compare centroids across T-3 → T-1, threshold 0.70)
    ▼
[EventThreads spanning multiple days]
    │
    │ write to FalkorDB
    ▼
:Article, :Source, :Event, :Story + structural edges
```

**Key rule:** Each day is an atomic unit. Ledger tracks which dates are done so re-runs are free. Every write is `MERGE` (idempotent).

**What Phase 1 gives you:** the "skeleton" — who reported what, grouped into events, grouped into multi-day stories. Nothing causal yet. No entity typing yet.

---

### Phase 2 — Enrichment (entities, typing, evidence)

```
[Each :Event from Phase 1]
    │
    │ take top-5 articles by centroid similarity
    │ concat title + description
    ▼
[LLM: extract entities with types + salience]
    │
    │ normalize: "US" → "United States", "Biden" → "Joe Biden"
    │ (cache alias resolutions so we never ask twice)
    ▼
[Typed entities: Country / Company / Person / Organization /
                 Industry / Commodity / Location]
    │
    │ write to FalkorDB
    ▼
:Entity nodes (multi-labeled) + :INVOLVES (Event→Entity)
                              + :MENTIONS (Article→Entity)
```

**Also in Phase 2 (rule-based, no LLM):**

- Consecutive events in the same Story → `PRECEDED` edge.
- Events sharing ≥ 2 `:Country` entities → weak `RELATED_TO` edge (confidence ~0.5).
- Official-source articles (`.gov`, `who.int`) → `:Statement` node linked to the Event.

**What Phase 2 gives you:** UC-01 (Investigate) and UC-02 (Impact Radius) already work — multi-hop traversal over typed entities is possible.

---

### Phase 3 — Reasoning (LLM builds causal edges via tools)

```
[Each :Event]
    │
    │ LLM is given: event title, summary, entities, top articles
    │ LLM is given: tools (NOT raw Cypher)
    ▼
┌──────────────────────────────────────────────────────┐
│  Agent Loop (max 25 tool calls per event)            │
│                                                      │
│  LLM can call:                                       │
│    • get_event_context(event_id)                     │
│    • find_candidate_links(event_id)                  │
│    • list_entities(event_id, type)                   │
│    • search_articles(query)                          │
│    • get_article_text(url)                           │
│    • write_edge(...)   ← the only write tool         │
│                                                      │
│  LLM CANNOT write raw Cypher.                        │
│  Every write_edge call is validated by Python:       │
│    - edge type in allowlist                          │
│    - confidence ≥ 0.55                               │
│    - evidence_ids required for confirmed/inferred    │
│    - no self-loops                                   │
│    - MERGE (idempotent)                              │
└──────────────────────────────────────────────────────┘
    │
    ▼
Causal/impact edges written with full audit trail
```

**Why tools, not raw Cypher:** raw Cypher lets the LLM drop the graph, drift the schema, skip evidence, and blow up cost. Tools make the agent autonomous _and_ auditable. This is also the story you tell judges for Track 2.

**What Phase 3 gives you:** UC-03 (Connect the Dots) — real causal paths. UC-04 (Evidence Trail) — every edge has `evidence_ids`. UC-07 (Agent Handoff) — the audit log IS the deliverable.

---

### Phase 4 — Newsroom & Memory (lightweight, last)

```
[Journalist CSV]  →  :Journalist + :Topic + :EXPERT_IN
[Articles with matching author]  →  :WRITTEN_BY

[Nightly]  →  compute subgraph hash per :Story  →  :MemorySnapshot
```

**What Phase 4 gives you:** UC-05, UC-06, UC-09, UC-10.

---

### Pipeline Summary

| Phase                 | Input             | Output                       | Unlocks                    |
| --------------------- | ----------------- | ---------------------------- | -------------------------- |
| 1 — Foundation        | MongoDB articles  | Article/Event/Story skeleton | Base graph                 |
| 2 — Enrichment        | Events            | Typed entities + mentions    | UC-01, UC-02               |
| 3 — Reasoning         | Events + entities | Causal/impact edges          | UC-03, UC-04, UC-07, UC-08 |
| 4 — Newsroom & Memory | Journalist data   | Expert + snapshot layer      | UC-05, UC-06, UC-09, UC-10 |

UC-11 (GraphRAG SDK) is a _different ingestion path_ — if you pursue it, it replaces Phase 2's entity extraction with the SDK's ontology discovery. Decide track before building.

---

## Part 2 — FalkorDB Data Model

### 2.1 Node Labels

Multi-label entities. Every actor carries `:Entity` **and** a specific type, so both generic and typed queries work.

| Label                  | Key properties                                                                                                                 | Notes                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| `:Article`             | `url` (unique), `title`, `description`, `author`, `published_at`, `url_to_image`                                               | Phase 1                       |
| `:Source`              | `source_id` (unique), `name`, `reliability`                                                                                    | Phase 1                       |
| `:Event`               | `event_id` (unique), `title`, `summary`, `category`, `sentiment`, `occurred_at`, `first_seen`, `last_seen`, `centroid` (384-d) | Phase 1                       |
| `:Story`               | `story_id` (unique), `title`, `first_seen`, `last_seen`, `article_count`                                                       | Phase 1 (EventThread renamed) |
| `:Entity:Country`      | `canonical_name` (unique), `aliases`                                                                                           | Phase 2                       |
| `:Entity:Company`      | same                                                                                                                           | Phase 2                       |
| `:Entity:Person`       | same                                                                                                                           | Phase 2                       |
| `:Entity:Organization` | same                                                                                                                           | Phase 2                       |
| `:Entity:Industry`     | same                                                                                                                           | Phase 2                       |
| `:Entity:Commodity`    | same                                                                                                                           | Phase 2                       |
| `:Entity:Location`     | same                                                                                                                           | Phase 2                       |
| `:Topic`               | `name` (unique)                                                                                                                | Phase 4                       |
| `:Journalist`          | `journalist_id` (unique), `name`, `email`                                                                                      | Phase 4                       |
| `:MemorySnapshot`      | `snapshot_id` (unique), `story_id`, `timestamp`, `graph_hash`                                                                  | Phase 4                       |
| `:Statement`           | `statement_id`, `text`, `issued_at`                                                                                            | Phase 2 (optional)            |

---

### 2.2 Edge Types

Grouped by which pipeline phase produces them.

**Phase 1 — Structural**

| Edge                    | From → To        | Properties   |
| ----------------------- | ---------------- | ------------ |
| `REPORTS_ON`            | Article → Event  | `similarity` |
| `PUBLISHED_BY`          | Article → Source | —            |
| `PART_OF`               | Event → Story    | —            |
| `PRECEDED` / `FOLLOWED` | Event ↔ Event    | `days_gap`   |

**Phase 2 — Mentions**

| Edge         | From → To         | Properties                               |
| ------------ | ----------------- | ---------------------------------------- |
| `MENTIONS`   | Article → Entity  | `count`, `salience`                      |
| `INVOLVES`   | Event → Entity    | `role` (`actor` / `location` / `object`) |
| `LOCATED_IN` | Entity → Location | —                                        |

**Phase 2/3 — Reasoning** (all share the trust property set below)

| Edge             | From → To      | Meaning                |
| ---------------- | -------------- | ---------------------- |
| `CAUSED`         | Event → Event  | Strong causal link     |
| `CONTRIBUTED_TO` | Event → Event  | Partial cause          |
| `AFFECTS`        | Event → Entity | Impact on actor/sector |
| `IMPACTED`       | Entity → Event | Passive impact         |
| `RELATED_TO`     | Event → Event  | Non-causal association |

**Phase 4 — Newsroom**

| Edge          | From → To              | Properties               |
| ------------- | ---------------------- | ------------------------ |
| `WRITTEN_BY`  | Article → Journalist   | —                        |
| `EXPERT_IN`   | Journalist → Topic     | `score`, `article_count` |
| `ABOUT`       | Story → Topic          | —                        |
| `COVERED_BY`  | Story → Article        | —                        |
| `SNAPSHOT_OF` | MemorySnapshot → Story | —                        |

---

### 2.3 The Trust Property Contract (non-negotiable)

**Every reasoning edge must carry these.** This is what makes UC-04 (Evidence), UC-06 (Diff), UC-08 (Curation), and UC-07 (Audit) all work with one convention.

| Property       | Type                                                       | Required when       |
| -------------- | ---------------------------------------------------------- | ------------------- |
| `status`       | `"confirmed"` \| `"inferred"` \| `"related"`               | Always              |
| `confidence`   | float 0–1                                                  | Always              |
| `evidence_ids` | list of article URLs                                       | status ≠ `related`  |
| `rationale`    | string                                                     | status = `inferred` |
| `agent`        | string (e.g. `rule_engine_v1`, `graph_agent_v1`, `editor`) | Always              |
| `created_at`   | ISO timestamp                                              | Always              |
| `valid_from`   | ISO timestamp                                              | Always              |
| `valid_to`     | ISO timestamp or null                                      | When superseded     |

**Why `valid_from`/`valid_to`:** enables UC-06 (What Changed) without needing full snapshot duplication. A diff = "edges where `valid_from > T1` OR `valid_to < T2`."

**Why `evidence_ids` as a list on the edge (not a node):** FalkorDB edges can't point to other edges. Storing evidence URLs as a property array is the pragmatic choice and keeps `shortestPath` (UC-03) working. This is the fix to the bug in the original FinalProject UC-04 Cypher.

---

### 2.4 Constraints & Indexes (run once, idempotent)

| Constraint on                                                                                    | Field            |
| ------------------------------------------------------------------------------------------------ | ---------------- |
| `:Article`                                                                                       | `url`            |
| `:Source`                                                                                        | `source_id`      |
| `:Event`                                                                                         | `event_id`       |
| `:Story`                                                                                         | `story_id`       |
| `:Topic`                                                                                         | `name`           |
| `:Journalist`                                                                                    | `journalist_id`  |
| `:MemorySnapshot`                                                                                | `snapshot_id`    |
| `:Country` / `:Company` / `:Person` / `:Organization` / `:Industry` / `:Commodity` / `:Location` | `canonical_name` |

Indexes on: `Event.occurred_at`, `Event.category`, `Article.published_at`, `CAUSED.status`.

Vector index on `Event.centroid` (dim 384, cosine) — enables incremental linking and similarity-based queries directly in the graph.

---

### 2.5 How Each Use Case Maps to the Model

| UC                      | What it queries                                                                                                 |
| ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| UC-01 Investigate       | Variable-length path from an `:Event` (1–3 hops) over any edge                                                  |
| UC-02 Impact Radius     | Bounded BFS from `:Event` over `AFFECTS`/`CONTRIBUTED_TO`/`IMPACTED`, grouped by entity label                   |
| UC-03 Connect the Dots  | `shortestPath` between two `:Event` nodes                                                                       |
| UC-04 Evidence Trail    | Edge properties (`status`, `confidence`, `rationale`, `evidence_ids`) → join to `:Article` → `:Source`          |
| UC-05 Story Evolution   | `:Story` → `PART_OF` → `:Event` ordered by `occurred_at`                                                        |
| UC-06 What Changed      | Filter edges by `valid_from`/`valid_to` vs. a reference timestamp                                               |
| UC-07 Agent Handoff     | Read `agent` + `created_at` on all edges; the audit trail                                                       |
| UC-08 Curate            | Update edge `status` / `confidence` / `rationale` with `agent="editor"`                                         |
| UC-09 Previous Coverage | Event → RELATED_TO → Event → COVERED_BY → Article → WRITTEN_BY → Journalist                                     |
| UC-10 Expert Journalist | Topic → EXPERT_IN → Journalist, ranked by `article_count` + recency                                             |
| UC-11 GraphRAG SDK      | Same schema; SDK's `apply_changes()` writes `:Article` and `:Entity` nodes; the reasoning edges are still yours |

---

## Part 3 — Rules the Agent Must Not Violate

Encode these into the pipeline; they are what make the demo credible.

1. **Idempotency:** every write is `MERGE` keyed on a stable ID. Re-running any stage must not duplicate nodes or edges.
2. **No orphan edges:** every reasoning edge must reference two nodes that already exist (agent can't invent IDs).
3. **No evidence, no causal claim:** `CAUSED` / `CONTRIBUTED_TO` edges require `evidence_ids`. If the LLM can't cite an article, the edge becomes `RELATED_TO` or is dropped.
4. **No raw Cypher from LLM:** only typed tool calls. Read-only Cypher is optional but must reject mutations by regex.
5. **Confidence floor:** reject edges below `0.55` (configurable). Prevents speculative graph pollution.
6. **Editor > Agent:** when an editor curates an edge, set `agent="editor"` and never overwrite it in later runs.
7. **Ledger checkpoints:** Phase 1 is day-by-day. Phase 2/3 are event-by-event. Both resumable after crash.

---

## Part 4 — One-Line Mental Model

> **MongoDB holds the raw evidence. Phase 1 turns it into a graph of Articles→Events→Stories. Phase 2 types the actors. Phase 3 lets an LLM propose causal edges through guarded tools. Every edge carries its own evidence and audit trail. Every query the demo makes is a graph traversal.**

That's the whole thing. Freeze the schema in 2.1–2.3, build Phase 1 first, and the rest is additive.
