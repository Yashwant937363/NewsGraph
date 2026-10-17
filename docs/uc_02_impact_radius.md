# UC-02: Impact Radius (Tracing an Impact)

**Actor:** Analyst / Editor  
**Track:** Track 1 — Investigation and Risk  
**FalkorDB Core Primitives:** Bounded BFS traversal, entity grouping, native vector index, graph-scoped `:Chunk` vector search  
**Visualization Engine:** `@falkordb/canvas` (`layout="radial"` or `"force-directed"`)  

---

## 1. Objective & User Trigger

- **Trigger:** On any `:Event` node in the graph, the user **right-clicks** and selects **"Impact Radius"** from the context menu.
- **Action:** Backend executes an impact traversal in FalkorDB over causal and impact edges (`AFFECTS`, `CONTRIBUTED_TO`, `IMPACTED`, `INVOLVES`), and queries the top semantic `:Chunk` nodes reporting on the exposure.
- **Result:** 
  - The canvas updates to show the blast radius radiating outward from the selected event.
  - A side panel presents:
    1. **Grouped Impacts Breakdown:** Exposed entities grouped by category (Countries, Companies, Industries, Commodities, Downstream Events).
    2. **AI Impact Explanation:** Summary of the blast radius and exposed sectors grounded strictly in graph facts and cited article chunks.

---

## 2. Frontend Experience

1. **Graph Interaction:**
   - User right-clicks an `:Event` node and clicks **"Impact Radius"**.
   - No manual hop sliders are required; the BFS traversal automatically bounds the blast radius.
   - `@falkordb/canvas` re-renders with the target event at the center, radiating outward to affected entities and downstream events.
2. **Impact Inspector Side Panel (The Shockwave Briefing):**
   - The canvas updates to isolate the blast radius radiating outward from the central event.
   - A side panel renders a structured impact briefing:
     1. **Blast Radius Overview:** Concise summary of the overall systemic shockwave and affected geographic regions.
     2. **Impacted Sectors with Mechanisms:** Categorized breakdowns across **Countries**, **Companies**, **Industries**, and **Commodities** detailing *how* each entity is affected and its exposure confidence.
     3. **Critical Chokepoints:** Immediate supply chain vulnerabilities and bottlenecks.
     4. **Transmission Metrics & Evidence:** Quotes, percentages, and financial impacts extracted from `:Chunk` nodes via `search_subgraph_chunks`.
     5. **Read More About This Impact:** Clickable source cards with the primary **Article Title** as the anchor, publisher trust badge (e.g. *Reuters [1.0]*), and outbound URL.

---

## 3. FalkorDB Traversal Implementation

The backend queries FalkorDB to find all downstream entities and events impacted:

```cypher
MATCH (center:Event {event_id: $event_id})
MATCH (center)-[r:AFFECTS|CONTRIBUTED_TO|IMPACTED|INVOLVES*1..2]-(ent:Entity)
WITH DISTINCT center, ent, labels(ent) AS ent_labels
RETURN 
    ent.canonical_name AS entity_name,
    ent_labels AS labels,
    reduce(s = '', x IN ent_labels | CASE WHEN x <> 'Entity' THEN x ELSE s END) AS primary_type
LIMIT 100
```

And downstream impacted events:

```cypher
MATCH (center:Event {event_id: $event_id})
MATCH (center)-[r:CAUSED|CONTRIBUTED_TO*1..2]->(downstream:Event)
WHERE downstream.event_id <> $event_id
RETURN DISTINCT 
    downstream.event_id AS event_id,
    downstream.title AS title,
    downstream.occurred_at AS occurred_at
LIMIT 30
```

---

## 4. Grounded AI Explanation (FalkorDB Native Vector RAG & Agentic Scoped Tool)

When `explain=true`, the backend enriches the impact synthesis using **Agentic Graph-Scoped Vector Search**:

### 4.1 Strict Blast-Radius Graph Scoping
Rather than scanning articles globally, the system computes the **blast-radius whitelist** up to 2–3 hops:
1. **Scope Traversal:** Includes the investigated event, downstream impacted events, and articles directly reporting on the event or mentioning the affected entities:
   ```cypher
   MATCH (center:Event {event_id: $event_id})-[r:AFFECTS|CONTRIBUTED_TO|IMPACTED|INVOLVES|CAUSED*1..2]-(target)
   OPTIONAL MATCH (target)<-[:REPORTS_ON|MENTIONS]-(a:Article)
   RETURN collect(DISTINCT target.event_id) AS scoped_event_ids,
          collect(DISTINCT a.url) AS scoped_article_urls
   ```
2. **Whitelist Boundary:** All candidate `:Chunk` nodes must belong to this specific impact neighborhood.

### 4.2 Agentic Investigative Tool: `search_subgraph_chunks`
The LLM agent is equipped with `search_subgraph_chunks(query, limit=5)` to interrogate specific vulnerability vectors (e.g., semiconductor foundry halts, commodity price shocks, logistics bottleneck timelines) without retrieving irrelevant macro news.

### 4.3 Native FalkorDB Scoped Vector Cypher
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
- **Strict Blast-Radius Isolation:** Only chunks from the affected countries, companies, and industries are accessible to the LLM.
- **Accurate Explanations:** Explains *why* and *how* the specific sectors are exposed based on real publisher claims.


---

## 5. API Contract

### Request:
`GET /api/v1/impact/{event_id}?explain=true`

- **Path Parameter:**
  - `event_id` (string, required): ID of the event to trace (e.g. `evt_2026-09-08_0`).
- **Query Parameter:**
  - `explain` (boolean, optional, default: `true`): Whether to generate the grounded LLM impact summary and cited chunks.

### Response Schema:
```json
{
  "event_id": "evt_2026-09-08_0",
  "graph": {
    "nodes": [
      {
        "id": "evt_2026-09-08_0",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": { "title": "US Imposes Advanced AI Semiconductor Restrictions" }
      },
      {
        "id": "Semiconductors",
        "labels": ["Entity", "Industry"],
        "color": "#EC4899",
        "visible": true,
        "data": { "canonical_name": "Semiconductors" }
      }
    ],
    "links": [
      {
        "id": "rel_impact_01",
        "relationship": "AFFECTS",
        "source": "evt_2026-09-08_0",
        "target": "Semiconductors",
        "color": "#F59E0B",
        "visible": true,
        "data": {
          "status": "inferred",
          "confidence": 0.88,
          "rationale": "Restrictions limit advanced lithography access"
        }
      }
    ]
  },
  "explanation": {
    "headline": "Advanced Chip Curbs Trigger Supply Shock Across Foundries and Automakers",
    "blast_radius_overview": "Export restrictions on cutting-edge lithography gear have created immediate downstream exposure across Taiwanese foundries, with secondary supply chokepoints propagating to automotive microcontrollers.",
    "impacted_sectors": {
      "Country": [
        {
          "name": "Taiwan",
          "impact": "Advanced semiconductor manufacturing hubs face direct export halts on high-end lithography tools.",
          "confidence": 0.95
        },
        {
          "name": "Netherlands",
          "impact": "Domestic lithography equipment suppliers subject to expanded bilateral export restrictions.",
          "confidence": 0.93
        }
      ],
      "Company": [
        {
          "name": "TSMC",
          "impact": "Received regulatory halt orders on high-performance customer wafer shipments to Asian markets.",
          "confidence": 0.96
        },
        {
          "name": "ASML",
          "impact": "Suspended planned maintenance and spare-part delivery contracts for EUV lithography systems.",
          "confidence": 0.92
        }
      ],
      "Industry": [
        {
          "name": "Automotive",
          "impact": "Vehicle assembly plants face secondary microchip supply shortages within 60 to 90 days.",
          "confidence": 0.88
        },
        {
          "name": "Consumer Electronics",
          "impact": "Next-generation hardware product launch schedules delayed.",
          "confidence": 0.85
        }
      ],
      "Commodity": [
        {
          "name": "Silicon Wafers",
          "impact": "Spot contract demand dropped 12% as high-end equipment installations were frozen.",
          "confidence": 0.90
        },
        {
          "name": "Rare Earth Elements",
          "impact": "Export quota retaliation risks threatening permanent magnet supplies.",
          "confidence": 0.82
        }
      ]
    },
    "critical_chokepoints": [
      {
        "category": "Company",
        "name": "TSMC & ASML",
        "vulnerability": "Lithography equipment maintenance suspensions risk halting advanced wafer fabrication lines."
      },
      {
        "category": "Industry",
        "name": "Automotive Assembly",
        "vulnerability": "Automakers face component shortages within 60-90 days due to buffer stock depletion."
      }
    ],
    "verified_metrics": [
      {
        "claim": "Automotive supply chains face production halts within 60 days if equipment export bans persist.",
        "quote": "Industry analysts warned that automotive chip supply chains could face production halts within 60 days...",
        "publisher": "Reuters",
        "url": "https://reuters.com/chips-impact"
      }
    ],
    "read_more": [
      {
        "title": "Global Chip Equipment Makers Halt Advanced Exports",
        "url": "https://reuters.com/chips-impact",
        "publisher": "Reuters",
        "published_at": "2026-09-08T16:00:00Z"
      },
      {
        "title": "Automakers Sound Alarm Over Semiconductor Chokepoints",
        "url": "https://bloomberg.com/automotive-chips-2026",
        "publisher": "Bloomberg",
        "published_at": "2026-09-09T10:30:00Z"
      }
    ],
    "grounding_score": 0.93
  }
}
```

---

## 6. Acceptance Criteria & Implementation Status

- [x] Triggered by right-clicking an event node and selecting "Impact Radius".
- [x] No manual hop count required; blast radius computed automatically via FalkorDB traversal.
- [x] Impacted entities grouped by category (Countries, Companies, Industries, Commodities).
- [x] Native FalkorDB vector RAG: 13,297 `:Chunk` nodes pre-embedded with 384-d vectors (`all-MiniLM-L6-v2`).
- [x] Graph-scoped vector search via `query_event_chunks()` provides cited evidence chunks.
- [x] Supports `explain=true` and `explain=false`.
- [x] Graph payload formatted directly for `<falkordb-canvas>`.
