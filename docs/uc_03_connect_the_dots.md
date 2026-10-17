# UC-03: Connect the Dots (Finding a Path)

**Actor:** Analyst / Journalist  
**Track:** Track 1 — Investigation and Risk  
**FalkorDB Core Primitives:** `shortestPath`, path ranking, native vector index, path-scoped `:Chunk` vector search  
**Visualization Engine:** `@falkordb/canvas`  

---

## 1. Objective & User Trigger

- **Trigger:** 
  - In the graph canvas, user right-clicks **Event A** and selects **"Set as Start Point"**.
  - User right-clicks **Event B** and selects **"Connect the Dots"**.
  - *(Alternatively: Types in the top search bar: `Connect [Event A] to [Event B]`)*.
- **Action:** Backend finds the shortest and strongest evidence-backed path in FalkorDB between the two events, and performs path-scoped vector search over `:Chunk` nodes across the path.
- **Result:**
  - The canvas isolates and highlights the chain of nodes and edges connecting Event A to Event B.
  - A side panel presents:
    1. **Path Chain View:** Ordered list of steps with trust badges (`🟢 Confirmed`, `🟡 Inferred`, `⚪ Related`).
    2. **AI Bridge Narrative:** Explains how Event A led to or influenced Event B using the graph path and cited article chunks.
    3. **Cited Chunks:** High-similarity article chunks supporting the causal transition.
    4. If no connection exists: displays *"No evidence-backed connection found between these events."*

---

## 2. Frontend Experience

1. **Path Highlighting in `@falkordb/canvas`:**
   - The canvas fades out unrelated nodes and highlights the connecting path chain.
   - Each transition edge displays its relationship label (e.g., `CAUSED`, `AFFECTS`, `PRECEDED`).
2. **Connection Inspector Side Panel (The Causal Bridge Briefing):**
   - The canvas isolates and highlights the connecting path chain between the two events.
   - A side panel renders a structured causal bridge briefing:
     1. **Executive Bridge Narrative:** Concise summary of how Event A influenced Event B across intermediate stages.
     2. **Step-by-Step Causal Path Cards (`path_steps`):** Ordered cards for each hop showing the transition relationship, trust badge (`🟢 Confirmed` / `🟡 Inferred`), confidence score, and specific transmission mechanism.
     3. **Verified Metrics & Quotes:** Hard figures and quotes extracted from `:Chunk` nodes along the path via `search_subgraph_chunks`.
     4. **Read More About This Connection:** Clickable source cards with the primary **Article Title** as the anchor, publisher trust badge (e.g. *Reuters [1.0]*), and outbound URL.
     5. **Unconnected State:** If no path exists, displays *"No evidence-backed connection found between these events."*

---

## 3. FalkorDB Shortest Path Implementation

The backend queries FalkorDB to find the shortest path between the two event nodes:

```cypher
MATCH (e1:Event), (e2:Event)
WHERE e1.event_id = $source_event_id AND e2.event_id = $target_event_id
RETURN shortestPath((e1)-[*]-(e2))
```

### Path Ranking & Causal Validation:
- If multiple paths exist, they are ranked by:
  1. **Causal Strength:** Paths with `CAUSED` or `CONTRIBUTED_TO` edges rank higher than purely thematic `RELATED_TO` edges.
  2. **Edge Confidence:** Average confidence of edges along the path.
  3. **Evidence Count:** Number of supporting articles on the path.
- **Acceptance Rule:** No path is presented as causal unless at least one `CAUSED` or `CONTRIBUTED_TO` edge exists along the chain.

---

## 4. Grounded AI Explanation (FalkorDB Native Vector RAG & Agentic Scoped Tool)

When `explain=true`, the backend generates a step-by-step causal narrative using **Agentic Graph-Scoped Vector Search**:

### 4.1 Strict Path-Chain Graph Scoping
The search space is strictly bounded to the identified connecting path chain:
1. **Path Sequence Extraction:** The shortest path query extracts the sequence of intermediate events, transition entities, and their reporting articles:
   ```cypher
   MATCH path = shortestPath((e1:Event {event_id: $e1})-[*]-(e2:Event {event_id: $e2}))
   UNWIND nodes(path) AS n
   OPTIONAL MATCH (n)<-[:REPORTS_ON|MENTIONS]-(a:Article)
   RETURN collect(DISTINCT n.event_id) AS path_event_ids,
          collect(DISTINCT a.url) AS path_article_urls
   ```
2. **Whitelist Boundary:** Only chunks linked to nodes directly situated along this connecting chain can be retrieved.

### 4.2 Agentic Investigative Tool: `search_subgraph_chunks`
The LLM agent uses `search_subgraph_chunks(query, limit=5)` to verify specific transition links along the path (e.g., *"How did the crude oil price increase affect European airline fuel surcharges?"*).

### 4.3 Native FalkorDB Scoped Vector Cypher
```cypher
MATCH (e:Event)<-[:REPORTS_ON]-(a:Article)-[:HAS_CHUNK]->(c:Chunk)
WHERE (e.event_id IN $path_event_ids OR a.url IN $path_article_urls)
  AND c.embedding IS NOT NULL
WITH DISTINCT a, c, (1.0 - vec.cosineDistance(c.embedding, vecf32($query_vector))) AS similarity
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
- **Strict Path Adherence:** The model cannot invent bridge links from unrelated stories.
- **Accurate Step Grounding:** Each causal transition along the path is grounded in verified quotes and statistics from the path's reporting chunks.


---

## 5. API Contract

### Request:
`GET /api/v1/connect?source_event_id={id1}&target_event_id={id2}&explain=true`

- **Query Parameters:**
  - `source_event_id` (string, required): Starting event ID.
  - `target_event_id` (string, required): Ending event ID.
  - `explain` (boolean, optional, default: `true`): Whether to generate the grounded LLM narrative and cited chunks.

### Response Schema:
```json
{
  "connection": {
    "source_event_id": "evt_2026-09-08_01",
    "target_event_id": "evt_2026-09-15_04",
    "found": true,
    "path_length": 3
  },
  "graph": {
    "nodes": [
      {
        "id": "evt_2026-09-08_01",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": { "title": "Red Sea Shipping Missile Attacks" }
      },
      {
        "id": "Crude Oil",
        "labels": ["Entity", "Commodity"],
        "color": "#EAB308",
        "visible": true,
        "data": { "canonical_name": "Crude Oil" }
      },
      {
        "id": "evt_2026-09-12_02",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": { "title": "Global Energy Price Spike" }
      },
      {
        "id": "evt_2026-09-15_04",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": { "title": "European Airline Stock Selloff" }
      }
    ],
    "links": [
      {
        "id": "rel_path_01",
        "relationship": "AFFECTS",
        "source": "evt_2026-09-08_01",
        "target": "Crude Oil",
        "color": "#10B981",
        "visible": true,
        "data": {
          "status": "confirmed",
          "confidence": 0.95,
          "evidence_ids": ["https://reuters.com/oil-shipping-crisis"]
        }
      },
      {
        "id": "rel_path_02",
        "relationship": "CAUSED",
        "source": "Crude Oil",
        "target": "evt_2026-09-12_02",
        "color": "#10B981",
        "visible": true,
        "data": {
          "status": "confirmed",
          "confidence": 0.92,
          "evidence_ids": ["https://bloomberg.com/brent-crude-spike"]
        }
      },
      {
        "id": "rel_path_03",
        "relationship": "CONTRIBUTED_TO",
        "source": "evt_2026-09-12_02",
        "target": "evt_2026-09-15_04",
        "color": "#F59E0B",
        "visible": true,
        "data": {
          "status": "inferred",
          "confidence": 0.87,
          "evidence_ids": ["https://ft.com/airline-stocks-drop"]
        }
      }
    ]
  },
  "explanation": {
    "headline": "Maritime Disruptions in Red Sea Trigger European Airline Equity Selloff",
    "bridge_narrative": "Red Sea tanker attacks forced commercial vessels into a 14-day detour around Africa, driving Brent crude past $88/barrel. The resulting jet fuel price spike compressed airline operating margins, triggering widespread sector selloffs.",
    "path_steps": [
      {
        "step_number": 1,
        "from_node": "Red Sea Shipping Missile Attacks",
        "to_node": "Crude Oil",
        "relationship": "AFFECTS",
        "status": "confirmed",
        "confidence": 0.95,
        "mechanism": "Attacks in the Bab el-Mandeb strait forced oil tankers into extended transit around Africa, disrupting direct European crude supplies."
      },
      {
        "step_number": 2,
        "from_node": "Crude Oil",
        "to_node": "Global Energy Price Spike",
        "relationship": "CAUSED",
        "status": "confirmed",
        "confidence": 0.92,
        "mechanism": "Delivery delays and maritime insurance surcharges drove spot Brent crude prices up 8.5% within 48 hours."
      },
      {
        "step_number": 3,
        "from_node": "Global Energy Price Spike",
        "to_node": "European Airline Stock Selloff",
        "relationship": "CONTRIBUTED_TO",
        "status": "inferred",
        "confidence": 0.87,
        "mechanism": "Surging jet fuel costs prompted major European carriers to issue margin warnings, leading to a 4.2% drop in airline equities."
      }
    ],
    "verified_metrics": [
      {
        "claim": "Rerouting around Africa added $1.2M in bunker fuel costs per tanker voyage.",
        "quote": "Maritime brokers confirmed bunker fuel expenditures jumped by over $1.2 million for standard Suezmax voyages...",
        "publisher": "Reuters",
        "url": "https://reuters.com/oil-shipping-crisis"
      }
    ],
    "read_more": [
      {
        "title": "Red Sea Shipping Attacks Drive Tanker Rerouting",
        "url": "https://reuters.com/oil-shipping-crisis",
        "publisher": "Reuters",
        "published_at": "2026-09-08T14:00:00Z"
      },
      {
        "title": "Brent Crude Hits Two-Month High on Transit Bottlenecks",
        "url": "https://bloomberg.com/brent-crude-spike",
        "publisher": "Bloomberg",
        "published_at": "2026-09-12T09:30:00Z"
      },
      {
        "title": "Airlines Tumble as Jet Fuel Surge Clouds Quarterly Outlook",
        "url": "https://ft.com/airline-stocks-drop",
        "publisher": "Financial Times",
        "published_at": "2026-09-15T15:45:00Z"
      }
    ],
    "grounding_score": 0.94
  }
}
```

### Special Case: No Connection Found
```json
{
  "connection": {
    "source_event_id": "evt_2026-09-08_01",
    "target_event_id": "evt_2026-09-15_99",
    "found": false,
    "path_length": 0
  },
  "graph": {
    "nodes": [],
    "links": []
  },
  "explanation": {
    "headline": "No Connection Found",
    "bridge_narrative": "No evidence-backed connection found between these events in the knowledge graph.",
    "path_steps": [],
    "verified_metrics": [],
    "read_more": [],
    "grounding_score": 0.0
  }
}
```

---

## 6. Acceptance Criteria & Implementation Status

- [x] Triggered by setting start node and end node via right-click or top search bar.
- [x] Computes shortest and strongest path using FalkorDB `shortestPath`.
- [x] If no path exists, returns `"found": false` with *"No evidence-backed connection found."*
- [x] Native FalkorDB vector RAG: 13,297 `:Chunk` nodes pre-embedded with 384-d vectors (`all-MiniLM-L6-v2`).
- [x] Path-scoped vector search via `query_path_chunks()` extracts top cited chunks supporting the causal bridge.
- [x] Supports `explain=true` and `explain=false`.
- [x] Graph payload formatted directly for `<falkordb-canvas>`.
