# UC-01: Investigate Event (Multi-Hop Link Analysis)

**Actor:** Analyst / Journalist  
**Track:** Track 1 — Investigation and Risk  
**FalkorDB Core Primitives:** Multi-hop neighborhood traversal, native vector index, graph-scoped `:Chunk` vector search  
**Visualization Engine:** `@falkordb/canvas`  

---

## 1. Objective & User Trigger

- **Trigger:** On any `:Event` node in the graph, the user **right-clicks** and selects **"Investigate Event"** from the context menu.
- **Action:** Backend executes multi-hop neighborhood traversal in FalkorDB around the selected event, paired with graph-scoped native vector search across `:Chunk` nodes reporting on the event.
- **Result:** The user gets an updated graph showing the event's connected neighborhood (actors, causes, preceding incidents, downstream impacts) along with an AI-generated explanation grounded in high-similarity article chunks.

---

## 2. Frontend Experience

1. **Graph Interaction:**
   - User views the graph rendered in `@falkordb/canvas`.
   - Right-clicking an `:Event` node opens a context menu with options (including **"Investigate Event"**).
   - No manual hop sliders are required; the system automatically bounds multi-hop expansion.
2. **Investigation Side Panel (The 4-Pillar Intelligence Briefing):**
   - The canvas updates to isolate the investigated event's connected subgraph.
   - A side panel renders a structured intelligence briefing:
     1. **Incident Overview:** Concise summary of what happened, location, and date.
     2. **Key Actors & Targets:** Participating governments, corporations, and figures.
     3. **Root Causes & Preceding Events:** Direct predecessor incidents and causal catalysts from the multi-hop neighborhood.
     4. **Hard Evidence & Verified Metrics:** Exact numbers, financial impacts, and quotes extracted from `:Chunk` nodes via `search_subgraph_chunks`.
     5. **Read More About This Event:** Clickable source cards displaying the primary **Article Title** as the anchor, publisher trust badge (e.g. *Reuters [1.0]*), and outbound URL.

---

## 3. FalkorDB Traversal Implementation

The backend queries FalkorDB to extract the event's connected structural neighborhood:

```cypher
MATCH (center:Event {event_id: $event_id})
MATCH (center)-[rel_path*1..2]-(neighbor)
UNWIND rel_path AS rel
WITH DISTINCT center, startNode(rel) AS sn, endNode(rel) AS en, rel
RETURN 
    coalesce(sn.event_id, sn.canonical_name, sn.url) AS src_id,
    labels(sn) AS src_labels,
    coalesce(sn.title, sn.canonical_name, sn.name, sn.url) AS src_title,
    coalesce(en.event_id, en.canonical_name, en.url) AS tgt_id,
    labels(en) AS tgt_labels,
    coalesce(en.title, en.canonical_name, en.name, en.url) AS tgt_title,
    type(rel) AS rel_type,
    properties(rel) AS rel_props
LIMIT 120
```

---

## 4. Grounded AI Explanation (FalkorDB Native Vector RAG & Agentic Scoped Tool)

When `explain=true`, the backend generates a fact-backed explanation using an **Agentic Graph-Scoped Vector Search**:

### 4.1 Strict 3-Hop Graph Scoping Architecture
Rather than executing an open-ended similarity search across the entire database, the system enforces **Strict Subgraph Scoping**:
1. **Multi-Hop Boundary:** The investigation begins by resolving all `:Event`, `:Entity`, and `:Article` nodes within a **3-hop traversal radius** of the investigated event:
   ```cypher
   MATCH (center:Event {event_id: $event_id})-[*1..3]-(n)
   WHERE n:Event OR n:Article
   RETURN collect(DISTINCT coalesce(n.event_id, n.url)) AS scoped_ids
   ```
2. **Graph-Scoped Boundary Constraint:** The set of discovered event IDs and article URLs forms the *investigation whitelist*. Vector similarity search is strictly locked to chunks connected to nodes inside this 3-hop boundary.

### 4.2 Agentic Investigative Tool: `search_subgraph_chunks`
During explanation generation, the LLM agent (Groq / `openai/gpt-oss-120b` or `llama-3.3-70b-versatile`) is equipped with a dedicated tool to dynamically probe the investigated subgraph for specific evidence:

```json
{
  "name": "search_subgraph_chunks",
  "description": "Performs vector similarity search for specific claims, numbers, or quotes, STRICTLY scoped to articles and events within the investigated 3-hop subgraph.",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Specific investigative query (e.g., 'TSMC production halt announcements', 'reported power grid transformer damage')"
      },
      "limit": {
        "type": "integer",
        "description": "Max chunks to retrieve (default: 5)",
        "default": 5
      }
    },
    "required": ["query"]
  }
}
```

### 4.3 Native FalkorDB Scoped Vector Query
When the model invokes `search_subgraph_chunks(query="...")`, the backend encodes `query` with `all-MiniLM-L6-v2` and runs native Cypher vector distance restricted by the whitelist:

```cypher
MATCH (e:Event)<-[:REPORTS_ON]-(a:Article)-[:HAS_CHUNK]->(c:Chunk)
WHERE (e.event_id IN $scoped_event_ids OR a.url IN $scoped_article_urls)
  AND c.embedding IS NOT NULL
WITH a, c, (1.0 - vec.cosineDistance(c.embedding, vecf32($query_vector))) AS similarity
RETURN a.title AS article_title,
       a.url AS article_url,
       c.chunk_id AS chunk_id,
       c.chunk_index AS chunk_index,
       c.text AS chunk_text,
       similarity
ORDER BY similarity DESC
LIMIT $limit
```

### 4.4 Synthesis Guarantees
- **Zero Hallucination Beyond Scope:** The model cannot cite articles or incidents from outside the 3-hop investigated neighborhood.
- **Accurate Grounding:** The model uses the retrieved chunk text to generate exact quotes, casualty numbers, monetary impacts, and publisher attributions.
- **Rule:** If no causal connection exists, the model states *"No evidence-backed causal path found."*


---

## 5. API Contract

### Request:
`GET /api/v1/investigate/{event_id}?explain=true`

- **Path Parameter:**
  - `event_id` (string, required): ID of the event to investigate (e.g. `evt_2026-09-08_0`).
- **Query Parameter:**
  - `explain` (boolean, optional, default: `true`): Whether to generate the grounded LLM explanation and return cited chunks.

### Response Schema:
```json
{
  "event_id": "evt_2026-09-08_0",
  "stats": {
    "total_nodes": 14,
    "total_edges": 18,
    "countries_count": 2,
    "companies_count": 3,
    "industries_count": 1
  },
  "graph": {
    "nodes": [
      {
        "id": "evt_2026-09-08_0",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": {
          "title": "US Imposes Advanced AI Semiconductor Restrictions",
          "category": "Technology",
          "occurred_at": "2026-09-08"
        }
      },
      {
        "id": "United States",
        "labels": ["Entity", "Country"],
        "color": "#10B981",
        "visible": true,
        "data": { "canonical_name": "United States" }
      }
    ],
    "links": [
      {
        "id": "rel_01",
        "relationship": "INVOLVES",
        "source": "evt_2026-09-08_0",
        "target": "United States",
        "color": "#10B981",
        "visible": true,
        "data": {
          "role": "actor",
          "status": "confirmed",
          "confidence": 1.0,
          "evidence_ids": ["https://reuters.com/article-123"]
        }
      }
    ]
  },
  "explanation": {
    "headline": "US Imposes Advanced AI Semiconductor Restrictions",
    "incident_overview": "On September 8, 2026, the US Department of Commerce officially enacted expanded export curbs targeting advanced chipmaking lithography gear and AI accelerators destined for Asian manufacturing hubs.",
    "key_actors": [
      {
        "entity": "United States Department of Commerce",
        "type": "Government / Regulator",
        "role": "Enacted export curbs"
      },
      {
        "entity": "TSMC",
        "type": "Company",
        "role": "Targeted foundry receiving shipment restrictions"
      }
    ],
    "causal_drivers": [
      "Followed bilateral security reports published 12 days prior.",
      "Preceded by export licensing reviews on advanced high-bandwidth memory (HBM)."
    ],
    "verified_quotes_and_metrics": [
      {
        "claim": "Export restrictions cut advanced foundry equipment deliveries by an estimated 20-25%.",
        "quote": "Industry analysts project immediate 20-25% shipment curbs across Taiwan and regional packaging hubs...",
        "publisher": "Reuters",
        "url": "https://reuters.com/article-123"
      }
    ],
    "read_more": [
      {
        "title": "US Imposes Advanced AI Semiconductor Restrictions",
        "url": "https://reuters.com/article-123",
        "publisher": "Reuters",
        "published_at": "2026-09-08T14:30:00Z"
      },
      {
        "title": "Global Foundries React to Sudden US Chip Curbs",
        "url": "https://bloomberg.com/news/chip-curbs-2026",
        "publisher": "Bloomberg",
        "published_at": "2026-09-08T16:00:00Z"
      }
    ],
    "grounding_score": 0.94
  }
}
```

---

## 6. Acceptance Criteria & Implementation Status

- [x] Triggered by right-clicking an event node and selecting "Investigate Event".
- [x] Neighborhood traversal executed natively by FalkorDB Cypher query.
- [x] Every returned edge carries `status`, `confidence`, and `evidence_ids`.
- [x] Native FalkorDB vector RAG: 13,297 `:Chunk` nodes pre-embedded with 384-d vectors (`all-MiniLM-L6-v2`).
- [x] Graph-scoped vector search via `query_event_chunks()` returns top-matching chunks with cosine similarity.
- [x] Supports `explain=true` (generates AI explanation + cited chunks) and `explain=false` (returns graph only).
- [x] Output formatted directly for `@falkordb/canvas`.
