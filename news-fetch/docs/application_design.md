# WorldGraph Application Design & Architecture

**Project:** WorldGraph — AI Knowledge Graph for Global Event Intelligence  
**Hackathon:** Graph Hacks: Building Next-Gen RAG (WeMakeDevs × FalkorDB)  
**Status:** Phase 0 — Core Architecture & Requirements Discussion  

---

## 1. System Overview & Technology Stack

The goal of WorldGraph is to transform fragmented global news streams into an interactive, multi-hop knowledge graph with explainable causal links, temporal timelines, and agentic memory.

```
┌────────────────────────────────────────────────────────┐
│           Frontend (React + TypeScript + Vite)         │
│  • Official `@falkordb/canvas` (<falkordb-canvas>)     │
│  • Force-directed, Radial (UC-02), and Tree (UC-05)    │
│  • Role Switcher Bar (Analyst 🔍 vs Editor ✍️)        │
│  • Event Timeline & Temporal Diff View                 │
│  • Multi-Hop Query & Evidence Drawer                   │
│  • Editor Curation Panel (UC-08)                       │
└───────────────────────────▲────────────────────────────┘
                            │ REST / JSON (with X-User-Role)
┌───────────────────────────▼────────────────────────────┐
│              Backend (FastAPI + Python)                │
│  • Thin API Routes (`/api/v1/...`)                     │
│  • Role Dependency (`get_current_role`)                │
│  • Graph Traversal & Cypher Query Services             │
│  • Hybrid GraphRAG & LLM Explainer Services (Groq)     │
│  • Curation & Audit Logging Services                   │
└─────────────┬────────────────────────────┬─────────────┘
              │                            │
              ▼                            ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│   FalkorDB (Graph DB)    │  │   MongoDB (Doc Store)    │
│  • :Article, :Source     │  │  • Raw Ingestion Pool    │
│  • :Event, :Story        │  │  • Pipeline Ledgers      │
│  • :Entity (Country/Org) │  │  • Curation Audit Trail  │
│  • Causal & Impact Edges │  │  • Saved Investigations  │
│  • Memory Snapshots      │  │                          │
└──────────────────────────┘  └──────────────────────────┘
```

### Core Stack Components:
- **Frontend:** React 18+, TypeScript, Vite, Tailwind CSS, **`@falkordb/canvas`** (official FalkorDB graph component), Lucide icons.
- **Backend:** FastAPI (Python 3.11+, async I/O, Pydantic v2 schemas).
- **Graph Database:** FalkorDB (Cypher traversal, shortest paths, BFS impact radius, `vecf32` vector search, episodic snapshots).
- **Document & Metadata Store:** MongoDB (via Motor & Beanie for raw news articles, processing ledgers, and curation audit logs).
- **Inference & LLM:** Groq (Llama-3.3-70b-versatile) for causal verification, connection reasoning, and natural language explanations.

---

## 2. Analysis: Do We Need Authentication?

To answer this, we examine the actors and requirements across all 11 use cases from [`UseCase.md`](file:///home/yashwant/MyProject/GraphHacksHackathons/NewsFetch/UseCase.md):

| Use Case | Actors | Permissions Required |
| :--- | :--- | :--- |
| **UC-01 Investigate Event** | Analyst / Journalist | **Read-Only**: Traversal & path expansion |
| **UC-02 Impact Radius** | Analyst / Editor | **Read-Only**: Bounded BFS & entity grouping |
| **UC-03 Connect the Dots** | Analyst / Journalist | **Read-Only**: Shortest path & causal ranking |
| **UC-04 View Evidence Trail** | All Users | **Read-Only**: View article citations & source scores |
| **UC-05 Story Evolution** | Journalist / Editor | **Read-Only**: Timeline playback |
| **UC-06 What Changed?** | Journalist / Editor | **Read-Only**: Temporal diffing of graph snapshots |
| **UC-07 Agent Handoff** | System Swarm | **Internal**: Agent memory read/write |
| **UC-08 Curate Connections** | **Editor** | **Write/Edit**: Approve/Reject/Override inferred edges |
| **UC-09 Previous Coverage** | Journalist | **Read-Only**: Hybrid GraphRAG retrieval |
| **UC-10 Expert Journalist** | Editor / Journalist | **Read-Only**: Graph traversal on expertise |
| **UC-11 Ontology Ingestion** | System | **Internal**: Ingestion pipeline |

### Key Finding on Auth:
The only use case requiring privilege control is **UC-08: Curate AI Connections (Human-in-the-Loop)**:
- Regular users (Analysts, Journalists, Viewers) should explore the graph and read evidence.
- Only an **Editor** should be permitted to change an edge from `🟡 Inferred` to `🟢 Confirmed`, reject false AI connections, or adjust confidence scores.
- Every curation action must record **who** made the change (`curated_by="editor"`), the timestamp, and rationale.

### Confirmed Auth Design: Persona / Role Switcher (`Analyst` 🔍 vs `Editor` ✍️)
- **Concept:** Frontend has a persistent Role Switcher in the top navigation bar.
- **Header Contract:** The frontend passes `X-User-Role: analyst` or `X-User-Role: editor`.
- **Backend Enforcement:**
  - Standard investigation & traversal endpoints (`GET /api/v1/investigate/...`, `GET /api/v1/timeline/...`) are open to all roles.
  - Curation mutation endpoints (`POST /api/v1/curate/...`, `PATCH /api/v1/curate/...`) enforce `current_role == "editor"` via a FastAPI dependency.
  - Every curation event writes an audit record with `curated_by="editor"`, timestamp, and rationale to both FalkorDB edge properties and the MongoDB `curation_audit` collection.
- **Why this is optimal for the Hackathon:** Zero sign-up friction for evaluators while showcasing strict human-in-the-loop governance for UC-08.

---

## 3. Analysis: What Data Must Be Stored & Where?

We have two complementary databases: **FalkorDB** (Graph/Relationships) and **MongoDB** (Documents/Pipeline State). Here is the division of responsibility:

### A. What Goes into FalkorDB? (The Graph Brain)
FalkorDB stores interconnected knowledge and relationship semantics:
1. **Nodes:**
   - `:Article` (id, title, url, published_at, author, description)
   - `:Chunk` (chunk_id, chunk_index, text, word_count, embedding `vecf32[384]`)
   - `:Source` (id, domain, reliability_score, country)
   - `:Event` (id, date, title, summary, centroid `vecf32[384]`)
   - `:Story` (id, title, start_date, last_updated)
   - `:Entity` (`:Country`, `:Company`, `:Industry`, `:Commodity`, `:Topic`, `:Journalist`)
   - `:MemorySnapshot` (id, timestamp, story_id, node_count, edge_count)
2. **Edges:**
   - `HAS_CHUNK` (:Article → :Chunk) — Semantic chunking with native vector search
   - `PUBLISHED_BY` (:Article → :Source)
   - `REPORTS_ON` (:Article → :Event)
   - `PART_OF_STORY` (:Event → :Story)
   - `PRECEDED_BY` (:Event → :Event) — Temporal narrative thread
   - `CAUSED`, `AFFECTS`, `CONTRIBUTED_TO`, `IMPACTED` (Causal/Impact edges)
   - `EXPERT_IN` (:Journalist → :Topic)
3. **Edge Properties (Crucial for Trust & Curation):**
   - `status`: `🟢 confirmed`, `🟡 inferred`, `⚪ related`
   - `confidence`: Float ($0.0 \dots 1.0$)
   - `evidence_ids`: Array of article URLs
   - `rationale`: LLM reasoning or editor note
   - `curated_by`: `system` or `editor_name`
   - `valid_from` / `valid_to`: Temporal validity timestamps

### B. What Goes into MongoDB? (The Ingestion Lake & App Records)
MongoDB handles high-volume document persistence, ledger tracking, and user artifacts:
1. **Raw News Articles (`articles` collection):**
   - Full body text, raw API responses, descriptions, metadata (already implemented).
2. **Pipeline State & Processing Ledgers:**
   - `fetch_state`: NewsAPI pagination and keyword tracking.
   - `phase1_ledger`, `phase2_ledger`, `phase3_ledger`: Daily batch processing states (Pending, Processing, Completed, Failed).
3. **Curation Audit Log (`curation_audit` collection):**
   - Full audit history of human-in-the-loop actions: `edge_id`, `previous_status`, `new_status`, `editor_id`, `rationale`, `timestamp`.
4. **Saved Investigations / Bookmarks (`saved_investigations` collection - optional):**
   - Analyst dossier exports: Event ID, investigated paths, notes, created timestamp.

---

## 4. Frontend UI Layout & Graph Visualization

The frontend presents a clean, focused single-page interface:

1. **Top Bar (Search & Agent Input):**
   - A search/input bar at the top used to search entities, events, or topics in the graph.
   - Operates either as direct search or as an AI agent with graph tools to query, filter, and act on behalf of the user.
   - Persona Switcher (`Analyst` 🔍 vs `Editor` ✍️) in the header.

2. **Main Graph View (Under Top Bar):**
   - Powered by official `@falkordb/canvas` (`<falkordb-canvas>`).
   - Displays nodes and relationships interactively.
   - Users interact directly with nodes to trigger actions (e.g., right-clicking an event node for **UC-01 Investigate Event**, **UC-02 Impact Radius**, **UC-03 Connect the Dots**).
   - Side panel opens with AI explanation and evidence details.


### Visual Styling Contract
FastAPI endpoints return graph payloads standardized for `@falkordb/canvas`:
- **Nodes Color Palette by Label:**
  - `:Event` → `#3B82F6` (Blue)
  - `:Story` → `#8B5CF6` (Purple)
  - `:Country` → `#10B981` (Emerald)
  - `:Company` / `:Org` → `#F59E0B` (Amber)
  - `:Topic` → `#6366F1` (Indigo)
  - `:Article` → `#6B7280` (Gray)
- **Links Color by Status:**
  - `🟢 Confirmed` → `#10B981` (Green, solid)
  - `🟡 Inferred` → `#F59E0B` (Amber, dashed)
  - `⚪ Related` → `#9CA3AF` (Muted gray)

---

### 4.4 Agentic Graph-Scoped Vector Search Tool (`search_subgraph_chunks`)

When the user requests an AI explanation (`explain=true`) for **UC-01 (Investigate Event)**, **UC-02 (Impact Radius)**, or **UC-03 (Connect the Dots)**, the reasoning agent is equipped with a specialized function tool: `search_subgraph_chunks`.

#### The Strict Scoping Guarantee:
A core design rule of WorldGraph is **strict graph bounding**:
1. **No Open-Ended Global Search:** The model is strictly prohibited from searching the full 13,000+ chunk database during an investigation.
2. **Multi-Hop Subgraph Whitelist:** Before invoking the LLM, the backend identifies the relevant subgraph:
   - **UC-01 (Investigate Event):** All events, entities, and articles within a **3-hop traversal radius** of the investigated event.
   - **UC-02 (Impact Radius):** All events, entities, and articles within the **blast radius** (up to 2–3 hops).
   - **UC-03 (Connect the Dots):** All events, entities, and articles situated directly along the **connecting path chain**.
3. **Cypher Vector Enforcement:** When the agent calls `search_subgraph_chunks(query, limit=5)`, the Cypher query dynamically applies the whitelist:
   ```cypher
   MATCH (e:Event)<-[:REPORTS_ON]-(a:Article)-[:HAS_CHUNK]->(c:Chunk)
   WHERE (e.event_id IN $scoped_event_ids OR a.url IN $scoped_article_urls)
     AND c.embedding IS NOT NULL
   WITH a, c, (1.0 - vec.cosineDistance(c.embedding, vecf32($query_vector))) AS similarity
   RETURN a.title AS article_title, a.url AS article_url, c.chunk_id AS chunk_id, c.text AS chunk_text, similarity
   ORDER BY similarity DESC LIMIT $limit
   ```
4. **Benefit:** The LLM can dynamically ask investigative follow-ups (*"What was the stated reason for the pipeline halt?"*, *"Did the ministry verify casualty figures?"*) while remaining 100% grounded within the investigated subgraph.

---

## 5. Phase-by-Phase Delivery Plan

To complete the application document and build the system in phases:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Phase A: Architecture, Data Contracts & API Design (CURRENT PHASE)     │
│  • Confirmed: Persona Switcher (Analyst vs Editor)                     │
│  • Confirmed: Official @falkordb/canvas web component                  │
│  • REST API routes specification and Pydantic schemas                  │
├────────────────────────────────────────────────────────────────────────┤
│ Phase B: Backend API Endpoints & Traversal Services                    │
│  • `/api/v1/investigate` (UC-01 Multi-Hop, UC-03 Shortest Path)        │
│  • `/api/v1/impact` (UC-02 Radial BFS)                                 │
│  • `/api/v1/timeline` (UC-05 Story Evolution, UC-06 Temporal Diff)     │
│  • `/api/v1/curate` (UC-08 Editor overrides + MongoDB audit logging)   │
│  • `/api/v1/evidence` (UC-04 Evidence trail & source citations)        │
├────────────────────────────────────────────────────────────────────────┤
│ Phase C: Frontend Foundation (React + TypeScript + Vite)               │
│  • Initialize Vite + TS + Tailwind CSS + Lucide icons                  │
│  • Install and configure `@falkordb/canvas` custom element wrapper     │
│  • Persona Switcher bar (`Analyst` 🔍 vs `Editor` ✍️)                  │
├────────────────────────────────────────────────────────────────────────┤
│ Phase D: Frontend Views & Interactive Graph Integration                │
│  • Interactive Canvas view with layout toggles (Force, Radial, Tree)   │
│  • Slide-out Evidence Drawer & LLM Causal explanation panel            │
│  • Timeline slider for Story Evolution & What Changed diff             │
│  • Editor Curation Modal (Approve/Reject/Note with role check)         │
├────────────────────────────────────────────────────────────────────────┤
│ Phase E: End-to-End Verification & Polish                              │
│  • Test all 11 hackathon use cases with FalkorDB live instance         │
│  • Verification of audit logs in MongoDB and curated edges in FalkorDB │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Next Discussion Step: Phase B (API Specifications)
Now that Auth (Persona Switcher) and the Graph Visualizer (`@falkordb/canvas`) are locked in, the next phase is to define:
1. The **exact REST API endpoints** and Pydantic request/response schemas.
2. The Cypher query templates powering each endpoint in FalkorDB.
3. How backend graph results map directly to `@falkordb/canvas` JSON format (`{ nodes: [...], links: [...] }`).
