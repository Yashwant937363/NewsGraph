# NewsGraph API Reference & Frontend Integration Guide

This guide details all backend endpoints for **NewsGraph (Track 1 — Investigation, Risk & Evidence)**, how the frontend triggers each endpoint, request parameters, JavaScript `fetch` examples, and response schemas.

---

## Base URLs
- Local Development: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

---

## Summary of Endpoints

| Use Case | Method | Path | Description | LLM Latency |
| :--- | :--- | :--- | :--- | :--- |
| **System** | `GET` | `/health` | Check FalkorDB connectivity | None (< 2ms) |
| **Events** | `GET` | `/track1/events` | List recent events for sidebar/dropdown | None (< 5ms) |
| **UC-01** | `GET` | `/track1/investigate/{event_id}` | 2-hop multi-hop investigation graph & AI briefing | Optional (~2-4s when `explain=true`) |
| **UC-02** | `GET` | `/track1/impact/{event_id}` | Blast radius traversal, grouped sectors & AI briefing | Optional (~2-4s when `explain=true`) |
| **UC-03** | `GET` | `/track1/connect` | Shortest path between Event A and Event B & AI bridge | Optional (~2-4s when `explain=true`) |
| **UC-04** | `GET` | `/track1/evidence/edge` | Full provenance, reliability & quotes for clicked edge | None (< 5ms) |
| **UC-04** | `GET` | `/track1/evidence/node/{node_id}` | Reporting articles & quotes for clicked node | None (< 5ms) |

---

## 1. Events List

### Trigger:
Page initialization, search dropdown, or sidebar recent events feed.

### Request:
```http
GET /track1/events?limit=25
```

- **Query Parameters:**
  - `limit` (integer, optional, default: `25`): Number of recent events to retrieve.

### Frontend Example:
```javascript
const response = await fetch('/track1/events?limit=25');
const events = await response.json();
// [ { "event_id": "evt_2026-10-07_0", "title": "...", "occurred_at": "2026-10-07" }, ... ]
```

### Response Schema (`200 OK`):
```json
[
  {
    "event_id": "evt_2026-10-07_0",
    "title": "Israelis mourn on anniversary of Oct. 7 attack as Palestinians grapple with war it sparked",
    "occurred_at": "2026-10-07"
  },
  {
    "event_id": "evt_2026-09-08_0",
    "title": "SMU-Florida State Kicked Off With Only Some Lights, No Replay After Power Outage",
    "occurred_at": "2026-09-08"
  }
]
```

---

## 2. UC-01: Investigate Event (Multi-Hop Graph)

### Trigger:
- User selects an event from the list and clicks **"Investigate Event"**.
- User right-clicks a node on `@falkordb/canvas` and chooses **"Investigate"**.

### Request:
```http
GET /track1/investigate/{event_id}?explain=true
```

- **Path Parameters:**
  - `event_id` (string, required): The target event ID (e.g. `evt_2026-10-07_0`).
- **Query Parameters:**
  - `explain` (boolean, optional, default: `false`):
    - `false`: Fast sub-10ms graph retrieval for instant canvas rendering.
    - `true`: Invokes the LangGraph intelligence agent for fact-grounded briefing.

### Frontend Example:
```javascript
// 1. Instant graph load
const fastResp = await fetch(`/track1/investigate/${eventId}?explain=false`);
const graphData = await fastResp.json();
canvas.loadGraph(graphData.graph); // Directly compatible with @falkordb/canvas

// 2. Load AI explanation in the background
const explainResp = await fetch(`/track1/investigate/${eventId}?explain=true`);
const fullData = await explainResp.json();
renderSidePanel(fullData.explanation);
```

### Response Schema (`200 OK`):
```json
{
  "event_id": "evt_2026-10-07_0",
  "stats": {
    "total_nodes": 74,
    "total_edges": 120,
    "countries_count": 6,
    "companies_count": 0,
    "industries_count": 2
  },
  "graph": {
    "nodes": [
      {
        "id": "evt_2026-10-07_0",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": {
          "title": "Israelis mourn on anniversary of Oct. 7 attack",
          "occurred_at": "2026-10-07",
          "category": "conflict"
        }
      }
    ],
    "links": [
      {
        "id": "rel_12345",
        "relationship": "INVOLVES",
        "source": "evt_2026-10-07_0",
        "target": "Israel",
        "color": "#10B981",
        "visible": true,
        "data": {
          "status": "confirmed",
          "confidence": 1.0,
          "evidence_ids": ["https://reuters.com/article-url"]
        }
      }
    ]
  },
  "explanation": {
    "headline": "Regional Spillover Analysis of October 7 Memorial Operations",
    "incident_overview": "Comprehensive two-paragraph overview of the incident, geographical spread, and key milestones.",
    "key_actors": [
      {
        "entity": "Israeli Defense Forces",
        "type": "Government / Regulator",
        "role": "Security enforcement and border monitoring"
      }
    ],
    "causal_drivers": [
      "Prior military exchange in southern border sector",
      "Anniversary regional heightened alert"
    ],
    "verified_quotes_and_metrics": [
      {
        "claim": "Over 1,200 casualties reported during initial offensive.",
        "quote": "Official state casualty records verified over 1,200 individuals lost their lives...",
        "publisher": "Reuters",
        "url": "https://reuters.com/article-url"
      }
    ],
    "read_more": [
      {
        "title": "Anniversary of Oct 7 Observed Amid Escalating Tensions",
        "url": "https://reuters.com/article-url",
        "publisher": "Reuters",
        "published_at": "2026-10-07T08:00:00Z"
      }
    ],
    "grounding_score": 0.95
  }
}
```

---

## 3. UC-02: Impact Radius & Blast Radius Assessment

### Trigger:
- User clicks the **"Impact Radius"** tab or right-clicks an event node and selects **"Calculate Blast Radius"**.

### Request:
```http
GET /track1/impact/{event_id}?explain=true
```

- **Path Parameters:**
  - `event_id` (string, required): Center event ID.
- **Query Parameters:**
  - `explain` (boolean, optional, default: `false`):
    - `false`: Fast traversal (< 15ms) of downstream affected entities and events.
    - `true`: Generates systemic shockwave analysis and critical chokepoints.

### Frontend Example:
```javascript
const resp = await fetch(`/track1/impact/${eventId}?explain=true`);
const impactData = await resp.json();

// Update canvas with radial blast graph
canvas.loadGraph(impactData.graph);

// Render categorized badges (Country, Company, Industry, Commodity)
renderGroupedPills(impactData.grouped_impacts);

// Render downstream cascade timeline
renderCascadeEvents(impactData.events_impacted);
```

### Response Schema (`200 OK`):
```json
{
  "event_id": "evt_2026-09-08_0",
  "grouped_impacts": {
    "Country": ["United States"],
    "Organization": ["NCAA", "Florida State Seminoles", "SMU Mustangs"],
    "Location": ["Tallahassee", "Doak Campbell Stadium"]
  },
  "events_impacted": [
    {
      "event_id": "evt_2026-09-08_4",
      "title": "Hundreds of flights delayed across eastern corridor",
      "occurred_at": "2026-09-08"
    }
  ],
  "graph": {
    "nodes": [ /* nodes styled for @falkordb/canvas */ ],
    "links": [ /* links styled for @falkordb/canvas */ ]
  },
  "explanation": {
    "headline": "Grid Outage Cascades into Regional Venue and Broadcast Disruptions",
    "blast_radius_overview": "Power disruption caused severe scheduling ripples across host city infrastructure and collegiate athletic programming.",
    "impacted_sectors": {
      "Country": [
        {
          "name": "United States",
          "impact": "Regional energy grid scrutiny across university athletic facilities",
          "confidence": 0.95
        }
      ],
      "Industry": [
        {
          "name": "Sports Entertainment",
          "impact": "National television broadcast delays and ad slot reallocations",
          "confidence": 0.92
        }
      ]
    },
    "critical_chokepoints": [
      {
        "category": "Infrastructure",
        "name": "Doak Campbell Substation Feed",
        "vulnerability": "Single-point-of-failure transformer trip lacking automated backup switch"
      }
    ],
    "verified_metrics": [
      {
        "claim": "Game kickoff was postponed by 1 hour and 45 minutes.",
        "quote": "Officials announced kickoff was officially rescheduled for 9:15 p.m. ET following power restoration.",
        "publisher": "Fox Sports",
        "url": "https://www.foxsports.com/..."
      }
    ],
    "read_more": [
      {
        "title": "SMU-Florida State Kicked Off After Stadium Power Delay",
        "url": "https://www.foxsports.com/...",
        "publisher": "Fox Sports",
        "published_at": "2026-09-08T01:24:35Z"
      }
    ],
    "grounding_score": 0.93
  }
}
```

---

## 4. UC-03: Connect the Dots (Shortest & Causal Path)

### Trigger:
- User selects **Event A** ("Set as Start Point"), selects **Event B** ("Set as End Point"), and clicks **"Connect the Dots"**.
- User types in top query bar: `Connect [Event A] to [Event B]`.

### Request:
```http
GET /track1/connect?source_event_id={id1}&target_event_id={id2}&explain=true
```

- **Query Parameters:**
  - `source_event_id` (string, required): Starting Event ID.
  - `target_event_id` (string, required): Ending Event ID.
  - `explain` (boolean, optional, default: `true`): Whether to generate the causal bridge explanation.

### Frontend Example:
```javascript
const resp = await fetch(
  `/track1/connect?source_event_id=${srcId}&target_event_id=${tgtId}&explain=true`
);
const data = await resp.json();

if (!data.connection.found) {
  showToast("No evidence-backed connection found between these events.");
} else {
  // Highlight only the connecting path chain on the canvas
  canvas.isolatePath(data.graph);
  // Render step-by-step causal transition cards
  renderPathSteps(data.explanation.path_steps);
}
```

### Response Schema (`200 OK` - Connected):
```json
{
  "connection": {
    "source_event_id": "evt_2026-09-08_1",
    "target_event_id": "evt_2026-09-09_0",
    "found": true,
    "path_length": 2
  },
  "graph": {
    "nodes": [
      {
        "id": "evt_2026-09-08_1",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": { "title": "UK announces trade sanctions" }
      },
      {
        "id": "evt_2026-09-08_4",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": { "title": "UK flights disrupted by air traffic glitch" }
      },
      {
        "id": "evt_2026-09-09_0",
        "labels": ["Event"],
        "color": "#3B82F6",
        "visible": true,
        "data": { "title": "European transport ministry meeting" }
      }
    ],
    "links": [
      {
        "id": "rel_path_101",
        "relationship": "RELATED_TO",
        "source": "evt_2026-09-08_1",
        "target": "evt_2026-09-08_4",
        "color": "#3B82F6",
        "visible": true,
        "data": { "status": "related", "confidence": 0.85 }
      },
      {
        "id": "rel_path_102",
        "relationship": "PRECEDED",
        "source": "evt_2026-09-08_4",
        "target": "evt_2026-09-09_0",
        "color": "#3B82F6",
        "visible": true,
        "data": { "status": "confirmed", "confidence": 0.95 }
      }
    ]
  },
  "explanation": {
    "headline": "UK Policy Shifts and Transportation Disruptions Precede European Summit",
    "bridge_narrative": "Britain's diplomatic announcements coincided with national aviation infrastructure glitches, prompting bilateral coordination at the subsequent European transport summit.",
    "path_steps": [
      {
        "step_number": 1,
        "from_node": "UK announces trade sanctions",
        "to_node": "UK flights disrupted by air traffic glitch",
        "relationship": "RELATED_TO",
        "status": "related",
        "confidence": 0.85,
        "mechanism": "Co-occurring national developments within the United Kingdom administrative jurisdiction."
      },
      {
        "step_number": 2,
        "from_node": "UK flights disrupted by air traffic glitch",
        "to_node": "European transport ministry meeting",
        "relationship": "PRECEDED",
        "status": "confirmed",
        "confidence": 0.95,
        "mechanism": "Air traffic control failures placed aviation contingency protocols on the emergency agenda."
      }
    ],
    "verified_metrics": [
      {
        "claim": "Over 140 flights canceled due to system error.",
        "quote": "Aviation authorities reported over 140 commercial flights were cancelled...",
        "publisher": "Reuters",
        "url": "https://reuters.com/..."
      }
    ],
    "read_more": [
      {
        "title": "Air Traffic Control Glitch Strands Thousands",
        "url": "https://reuters.com/...",
        "publisher": "Reuters",
        "published_at": "2026-09-08T18:00:00Z"
      }
    ],
    "grounding_score": 0.94
  }
}
```

### Response Schema (`200 OK` - Unconnected):
```json
{
  "connection": {
    "source_event_id": "evt_A",
    "target_event_id": "evt_B",
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

## 5. UC-04: View Evidence Trail (Slide-out Drawer)

### 5.1 Edge Evidence Trail

#### Trigger:
User **clicks on any edge/relationship line** on `@falkordb/canvas`.

#### Request:
```http
GET /track1/evidence/edge?source_id={src}&target_id={tgt}&edge_type={type}
```
*(Alias also supported: `GET /api/v1/evidence/edge?...`)*

- **Query Parameters:**
  - `source_id` (string, required): Source event ID or entity canonical name.
  - `target_id` (string, required): Target event ID or entity canonical name.
  - `edge_type` (string, required): Relationship type (e.g. `CAUSED`, `AFFECTS`, `INVOLVES`).

#### Frontend Example:
```javascript
canvas.on('edgeClick', async (edge) => {
  const resp = await fetch(
    `/track1/evidence/edge?source_id=${edge.source}&target_id=${edge.target}&edge_type=${edge.relationship}`
  );
  if (resp.ok) {
    const evidence = await resp.json();
    openEvidenceDrawer(evidence);
  }
});
```

#### Response Schema (`200 OK`):
```json
{
  "edge": {
    "source_id": "evt_2026-09-08_0",
    "target_id": "SMU",
    "edge_type": "AFFECTS",
    "status": "confirmed",
    "confidence": 0.92,
    "rationale": "The power outage at Doak Campbell Stadium delayed the start of the SMU vs Florida State game, directly affecting participating teams.",
    "agent": "graph_agent_v1",
    "created_at": "2026-10-09T19:18:53.371822Z",
    "valid_from": "2026-10-09T19:18:53.371822Z",
    "valid_to": null
  },
  "sources": [
    {
      "url": "https://www.foxsports.com/stories/college-football/smu-vs-florida-state-delayed-nearly-two-hours-due-power-outage",
      "title": "SMU-Florida State Kicked Off With Only Some Lights, No Replay After Power Outage",
      "publisher": "Fox Sports",
      "reliability": 1.0,
      "published_at": "2026-09-08T01:24:35Z",
      "supporting_chunks": [
        {
          "chunk_id": "https://www.foxsports.com/...#c0",
          "chunk_index": 0,
          "text": "Florida State and No. 19 SMU kicked off at 9:15 p.m. ET at Doak Campbell Stadium after an outage plunged the venue into partial darkness..."
        }
      ]
    }
  ],
  "contradictions": [],
  "anomalies": []
}
```

---

### 5.2 Node Evidence Trail

#### Trigger:
User **clicks on any node** (Event or Entity) on `@falkordb/canvas` to view all reporting/mentioning coverage.

#### Request:
```http
GET /track1/evidence/node/{node_id}
```
*(Alias also supported: `GET /api/v1/evidence/node/{node_id}`)*

- **Path Parameters:**
  - `node_id` (string, required): Event ID (e.g. `evt_2026-09-08_0`) or Entity canonical name (e.g. `SMU`, `China`).

#### Frontend Example:
```javascript
canvas.on('nodeClick', async (node) => {
  const resp = await fetch(`/track1/evidence/node/${node.id}`);
  if (resp.ok) {
    const nodeEvidence = await resp.json();
    renderNodeDrawer(nodeEvidence);
  }
});
```

#### Response Schema (`200 OK`):
```json
{
  "node_id": "evt_2026-09-08_0",
  "labels": ["Event"],
  "title": "SMU-Florida State Kicked Off With Only Some Lights, No Replay After Power Outage",
  "occurred_at": "2026-09-08",
  "articles_count": 40,
  "articles": [
    {
      "url": "https://sports.yahoo.com/articles/start-no-19-smu-florida-000226810.html",
      "title": "Start of No. 19 SMU-Florida State game delayed by power outage",
      "publisher": "Yahoo Entertainment",
      "reliability": 1.0,
      "published_at": "2026-09-08T00:02:26Z",
      "snippet": "TALLAHASSEE, Fla. (AP) — The game between No. 19 SMU and Florida State kicked off after a delay of nearly two hours on Monday night due to a power outage at the stadium..."
    }
  ]
}
```

---

## 6. Color Standards for `@falkordb/canvas`

When rendering nodes or edges, use the backend-provided `color` hex field. The palette conforms to:

| Label / Category | Hex Color | Visual Meaning |
| :--- | :--- | :--- |
| **Event** | `#3B82F6` | Blue (Central incident nodes) |
| **Country** | `#10B981` | Green (Geographic sovereign entities) |
| **Company** | `#F59E0B` | Amber (Corporate entities) |
| **Industry** | `#8B5CF6` | Purple (Economic sectors) |
| **Organization** | `#06B6D4` | Cyan (Agencies, governing bodies) |
| **Location** | `#EC4899` | Pink (Cities, stadiums, straits) |
| **Person** | `#F43F5E` | Rose (Leaders, figures) |
| **Article** | `#64748B` | Slate (Primary media items) |
| **Causal Edge** (`CAUSED`, `AFFECTS`) | `#10B981` | Solid Green (Confirmed causal link) |
| **Inferred Edge** | `#F59E0B` | Amber (Hypothesized link) |
| **Temporal Edge** (`PRECEDED`) | `#3B82F6` | Blue (Chronological sequence) |
