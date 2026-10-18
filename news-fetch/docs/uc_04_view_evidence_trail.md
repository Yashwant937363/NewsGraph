# UC-04: View Evidence Trail (Evidence and Case Mapping)

**Actor:** All Users (Analyst 🔍, Editor ✍️, Viewer 👁️)  
**Track:** Track 1 — Investigation and Risk  
**FalkorDB Core Primitives:** `Edge → Article → Source` traversal, sub-millisecond property lookups  
**LLM Usage:** **None (0 tokens / Zero API latency)** — 100% deterministic Cypher traversal  
**Latency SLA:** $< 5\text{ ms}$ (direct in-memory FalkorDB query)  
**Visualization Engine:** `@falkordb/canvas` + Slide-out Evidence Drawer  

---

## 1. Objective & User Trigger

- **Trigger:** In the `@falkordb/canvas` interface, the user **clicks** on any causal edge (e.g., `[:CAUSED]`, `[:AFFECTS]`, `[:CONTRIBUTED_TO]`, `[:INVOLVES]`) or node (e.g., `:Event`, `:Statement`).
- **Action:** Backend executes an instant, deterministic Cypher query to retrieve the edge's persisted trust metadata, resolves the URLs in `evidence_ids` against `:Article` and `:Source` nodes, and pulls supporting text chunks.
- **Result:** The canvas highlights the selected edge/node, and the **Evidence Drawer** slides out from the right showing full provenance, publisher reliability scores, timestamps, and quotes.

---

## 2. Frontend Experience

```text
┌─────────────────────────────────────────────────────────────┐
│ 🔍 EVIDENCE TRAIL: [Event A] ──(CAUSED)──► [Event B]       │
├─────────────────────────────────────────────────────────────┤
│ STATUS:         🟢 Confirmed (Confidence: 94%)             │
│ CREATED BY:     Editor (or AI Agent: graph_agent_v1)        │
│ VALID FROM:     2026-09-12T14:30:00Z                        │
│                                                             │
│ 🧠 RATIONALE                                                │
│ "Red Sea maritime tanker attacks forced immediate rerouting │
│ around the Cape of Good Hope, creating a 14-day supply      │
│ delay that triggered crude oil spot price spikes."          │
│                                                             │
│ 📰 SUPPORTING SOURCES (3 Articles, 2 Verified Outlets)      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🟢 Reuters (Reliability: 1.0) | 2026-09-12              │ │
│ │ "Red Sea Missile Strike Diverts Commercial Tankers"     │ │
│ │ 💬 Supporting Quote / Chunk:                            │ │
│ │ "...Three major shipping consortiums announced all      │ │
│ │ transit through the Bab el-Mandeb strait is halted..."  │ │
│ │ 🔗 [Open Original Article]                             │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🟢 Bloomberg (Reliability: 0.95) | 2026-09-13           │ │
│ │ "Crude Spot Rates Surge 4.8% on Maritime Supply Fears"  │ │
│ │ 💬 Supporting Quote / Chunk:                            │ │
│ │ "...Brent crude reached $88/barrel following shipping   │ │
│ │ disruptions in the Middle East corridor..."             │ │
│ │ 🔗 [Open Original Article]                             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│ ⚠️ CONTRADICTING CLAIMS                                     │
│ None detected. (Or displays alternative explanations)       │
│                                                             │
│ ✍️ EDITOR ACTION (Visible only to Editor role)             │
│ [ ✏️ Edit Trust / Override Connection (UC-08) ]            │
└─────────────────────────────────────────────────────────────┘
```

1. **Edge Glow:** The clicked edge receives an active halo on `<falkordb-canvas>`.
2. **Trust & Provenance Badge:**
   - `🟢 Confirmed`: Solid green badge (verified by credible primary outlet or curated by Editor).
   - `🟡 Inferred`: Amber dashed badge (AI-hypothesized link pending editorial confirmation).
   - `⚪ Related`: Muted gray badge (thematic co-occurrence without confirmed causality).
3. **Agent / Human Attribution:** Explicitly identifies whether the connection was made by an autonomous agent (`agent: "graph_agent_v1"`) or a verified journalist/editor (`agent: "editor"`).
4. **Source Reliability Indicators:** Each supporting article displays its publisher credibility badge (`reliability: 1.0` for wire services like Reuters/AP; scaled scores for regional/opinion outlets).
5. **Direct Source Link:** Every citation provides a clickable outbound link to the primary publisher article.
6. **Editor Action (UC-08 Bridge):** If the active user has selected the `Editor` role from the top switcher, an **"Edit Connection"** button appears, allowing immediate curation without leaving the canvas.

---

## 3. FalkorDB Traversal Implementation

Because all trust properties and rationales are persisted when the edge or event is created, retrieval requires **zero LLM generation**:

### 3.1 Edge Evidence Traversal
```cypher
MATCH (s)-[r]->(t)
WHERE (s.event_id = $src OR s.canonical_name = $src)
  AND (t.event_id = $tgt OR t.canonical_name = $tgt)
  AND type(r) = $edge_type
WITH r, properties(r) AS props

// Match supporting articles from evidence_ids
OPTIONAL MATCH (a:Article)-[:PUBLISHED_BY]->(src:Source)
WHERE a.url IN props.evidence_ids

// Match supporting first chunk for quote snippet
OPTIONAL MATCH (a)-[:HAS_CHUNK]->(c:Chunk {chunk_index: 0})

RETURN props,
       collect(DISTINCT {
         url: a.url,
         title: a.title,
         description: a.description,
         published_at: a.published_at,
         publisher_name: coalesce(src.name, "Unknown"),
         reliability: coalesce(src.reliability, 1.0),
         supporting_quote: coalesce(c.text, a.description, "")
       }) AS articles
```

### 3.2 Node Evidence Traversal (When Clicking an Event)
```cypher
MATCH (e:Event {event_id: $event_id})
MATCH (a:Article)-[:REPORTS_ON]->(e)
MATCH (a)-[:PUBLISHED_BY]->(src:Source)
OPTIONAL MATCH (a)-[:HAS_CHUNK]->(c:Chunk {chunk_index: 0})
RETURN e.event_id AS event_id,
       e.title AS event_title,
       e.summary AS event_summary,
       e.occurred_at AS occurred_at,
       collect(DISTINCT {
         url: a.url,
         title: a.title,
         published_at: a.published_at,
         publisher_name: src.name,
         reliability: src.reliability,
         sample_text: coalesce(c.text, a.description, "")
       }) AS reporting_articles
```

---

## 4. Deterministic Contradiction Detection (Without LLM)

Contradictions and evidence divergences are identified deterministically via graph queries:

1. **Conflicting Edge Types:** If an edge between $(E_1)$ and $(E_2)$ is labeled `CAUSED`, but an opposing or parallel edge between them has `status: "rejected"` or conflicting rationale, the drawer flags a contradiction.
2. **Reliability Discrepancies:** If an inferred edge is backed only by outlets with `reliability < 0.70` while a counter-article exists with `reliability = 1.0`, a **"Low-Trust Outlier Warning"** is rendered.
3. **Temporal Inconsistencies:** If $E_1$ claims to have caused $E_2$, but $E_2$'s `occurred_at` timestamp is earlier than $E_1$'s, a **"Temporal Precedence Anomaly"** flag is displayed.

---

## 5. API Contract

### 5.1 Get Edge Evidence
`GET /api/v1/evidence/edge?source_id={src}&target_id={tgt}&edge_type={type}`

#### Query Parameters:
- `source_id` (string, required): Source event ID or entity canonical name.
- `target_id` (string, required): Target event ID or entity canonical name.
- `edge_type` (string, required): Relationship type (e.g., `CAUSED`, `AFFECTS`, `CONTRIBUTED_TO`, `INVOLVES`).

#### Response Schema:
```json
{
  "edge": {
    "source_id": "evt_2026-09-08_01",
    "target_id": "evt_2026-09-12_02",
    "edge_type": "CAUSED",
    "status": "confirmed",
    "confidence": 0.94,
    "rationale": "Red Sea maritime tanker attacks forced immediate rerouting around the Cape of Good Hope, creating supply delays that triggered crude oil spot price spikes.",
    "agent": "graph_agent_v1",
    "created_at": "2026-09-13T04:12:00Z",
    "valid_from": "2026-09-12T14:30:00Z",
    "valid_to": null
  },
  "sources": [
    {
      "url": "https://reuters.com/world/shipping-crisis-2026",
      "title": "Red Sea Missile Strike Diverts Commercial Tankers",
      "publisher": "Reuters",
      "reliability": 1.0,
      "published_at": "2026-09-12T12:00:00Z",
      "supporting_chunks": [
        {
          "chunk_id": "https://reuters.com/world/shipping-crisis-2026#c0",
          "chunk_index": 0,
          "text": "Three major shipping consortiums announced all transit through the Bab el-Mandeb strait is halted following drone strikes..."
        }
      ]
    }
  ],
  "contradictions": [],
  "anomalies": []
}
```

### 5.2 Get Node Evidence
`GET /api/v1/evidence/node/{node_id}`

#### Path Parameter:
- `node_id` (string, required): Event ID (e.g. `evt_2026-09-08_01`) or Entity canonical name.

#### Response Schema:
```json
{
  "node_id": "evt_2026-09-08_01",
  "labels": ["Event"],
  "title": "Red Sea Commercial Shipping Attacks Trigger Maritime Diversions",
  "occurred_at": "2026-09-08",
  "articles_count": 5,
  "articles": [
    {
      "url": "https://reuters.com/world/shipping-crisis-2026",
      "title": "Red Sea Missile Strike Diverts Commercial Tankers",
      "publisher": "Reuters",
      "reliability": 1.0,
      "published_at": "2026-09-08T10:15:00Z",
      "snippet": "Commercial shipping traffic via the Suez Canal dropped 40% after armed drones targeted two tankers..."
    }
  ]
}
```

---

## 6. Acceptance Criteria & Implementation Status

- [x] Triggered by clicking any edge, node, or claim in `@falkordb/canvas`.
- [x] Zero LLM calls at query time; response delivered in $< 5\text{ ms}$ directly from FalkorDB.
- [x] Returns edge trust properties: `status`, `confidence`, `rationale`, `agent`, `valid_from`.
- [x] Resolves `evidence_ids` to `:Article` nodes and `:Source` nodes with `reliability` scores.
- [x] Pulls supporting quote snippets from `:Chunk` nodes.
- [x] Flags deterministic contradictions (opposing edges, reliability gaps, temporal sequence anomalies).
- [x] Provides human curation action for users with `Editor` role (UC-08).
