# UseCase.md

**Project:** WorldGraph — AI that understands how world events are connected
**Hackathon:** Graph Hacks: Building Next-Gen RAG (WeMakeDevs × FalkorDB)

This document lists the product use cases WorldGraph must support. Each use case states the actor, the FalkorDB dependency, the flow, and the acceptance criteria. The graph schema is defined separately.

---

## Track 1 — Investigation and Risk

**Track focus:** Multi-hop link analysis, identity resolution, fraud ring detection, evidence and case mapping, explainable results.

---

### UC-01 — Investigate Event (Multi-Hop Link Analysis)

**Actor:** Analyst / Journalist
**FalkorDB dependency:** Multi-hop traversal, path ranking

**Trigger:** User sees "BREAKING: Country X imposes semiconductor export restrictions" and clicks **Investigate this event**.

**Main Flow:**

1. User selects an event node.
2. Backend executes multi-hop traversal in FalkorDB.
3. Connection layer ranks paths by confidence, evidence count, and causal strength.
4. LLM generates an explanation using **only** the returned graph facts.
5. Frontend expands the graph visually:
   - 1 hop: direct entities (countries, companies, commodities).
   - 2 hops: related events, organizations, people.
   - 3 hops: industries, downstream impacts.

**Questions supported:**

- What caused this?
- What previous events are connected?
- Which countries and industries are most exposed?
- Show me the chain connecting Event A and Event B.
- What other current stories might be part of the same larger event?

**Acceptance Criteria:**

- Multi-hop traversal executed by FalkorDB, not the LLM.
- Every path edge has `status`, `confidence`, and `evidence_ids`.
- User can expand the graph one hop at a time.
- No path = no causal claim returned.

---

### UC-02 — Impact Radius (Tracing an Impact)

**Actor:** Analyst / Editor
**FalkorDB dependency:** Bounded BFS traversal

**Trigger:** User clicks **Impact Radius** on an event.

**Main Flow:**

1. User selects hop count: 1, 2, or 3+.
2. Backend runs bounded BFS from the event node over `AFFECTS`, `CONTRIBUTED_TO`, and `IMPACTED` edges, filtered by a confidence threshold.
3. Results are grouped by entity type: Countries, Companies, Industries, Commodities.
4. Frontend renders a radial graph with a ranked impact list.

**Example output:**

```
Red Sea disruption
      │
      ├── affects → Shipping Routes
      │                 ↓
      │              Oil Trade
      │                 ↓
      │             Energy Prices
      │
      ├── involves → Countries
      │
      └── related_to → Previous attacks
                          ↓
                     Regional conflict
```

**Acceptance Criteria:**

- Hop count visible to the user.
- Each impacted entity shows the full path and its evidence.
- Inferred impacts labeled 🟡.
- Query returns in < 5 seconds for a 3-hop traversal.

---

### UC-03 — Connect the Dots (Finding a Path)

**Actor:** Analyst / Journalist
**FalkorDB dependency:** `shortestPath` and path ranking

**Trigger:** User selects two seemingly unrelated events and clicks **Connect the Dots**.

**Example:**

- Event A: "Oil prices rise."
- Event B: "European airline shares fall."

**Main Flow:**

1. Backend finds the shortest and strongest paths in FalkorDB between the two event nodes.
2. Paths are ranked by:
   - Edge confidence.
   - Evidence count.
   - Source credibility.
   - Causal strength (`CAUSED` > `CONTRIBUTED_TO` > `AFFECTS` > `RELATED_TO`).
3. LLM summarizes the top paths.
4. Frontend renders the path:

```
Regional conflict
       ↓
Shipping disruption
       ↓
Oil supply concerns
       ↓
Oil price increase
       ↓
Jet fuel costs
       ↓
Airline operating costs
       ↓
Airline market reaction
```

**Acceptance Criteria:**

- Every edge is 🟢 Confirmed, 🟡 Inferred, or ⚪ Related.
- User can click each edge to see the evidence drawer.
- If no meaningful path exists: "No evidence-backed connection found."
- No path is presented as causal unless at least one `CAUSED` edge exists on it.

---

### UC-04 — View Evidence Trail (Evidence and Case Mapping)

**Actor:** All users
**FalkorDB dependency:** Edge → Article → Source traversal

**Trigger:** User clicks any edge, node, or claim.

**Main Flow:**

1. Backend reads the edge's trust properties (`status`, `confidence`, `rationale`, `evidence_ids`).
2. For each URL in `evidence_ids`, backend resolves the `:Article` node and its `:Source`.
3. Returns:
   - Supporting articles.
   - Source reliability score.
   - Publication time.
   - Contradicting evidence, if any.
   - Agent rationale (who created the edge and why).
4. Frontend displays the evidence drawer.

**Acceptance Criteria:**

- Every 🟢 Confirmed edge has at least one credible source.
- 🟡 Inferred edges show rationale and supporting evidence.
- ⚪ Related edges show connection but no causal claim.
- Contradictions are visible.

---

## Track 2 — Best Agentic AI Use Case

**Track focus:** Autonomous AI agents, multi-agent state sharing, persistent cognitive memory (episodic, semantic, procedural), high-concurrency memory lookups, sub-millisecond traversals.

---

### UC-05 — Story Evolution (Episodic Memory)

**Actor:** Journalist / Editor
**FalkorDB dependency:** Temporal graph snapshots, `EVOLVED_FROM` edges

**Trigger:** User opens a developing story.

**Main Flow:**

1. System clusters related events into a `Story` node.
2. Memory layer creates `MemorySnapshot` nodes at intervals.
3. Each snapshot links to event nodes and edge states at that time.
4. User sees a timeline:

```
Day 1: Protest → Government response
Day 2: International condemnation
Day 3: Sanctions → Currency reaction
```

5. User clicks any day to load that graph state.

**Acceptance Criteria:**

- Timeline is based on actual graph evolution, not article timestamps alone.
- Each event links to evidence.
- A story can span multiple countries and entity types.
- Snapshot diffing enables UC-06.

---

### UC-06 — What Changed Since Yesterday? (Temporal Diff)

**Actor:** Journalist / Editor
**FalkorDB dependency:** Graph diff between snapshots

**Trigger:** User clicks **What changed?** on a story.

**Main Flow:**

1. Backend retrieves the current graph and a previous snapshot (or filters edges by `valid_from` / `valid_to` against a reference timestamp).
2. Memory layer diffs nodes, edges, and properties.
3. Changes classified:

| Classification | Meaning                        | Example               |
| -------------- | ------------------------------ | --------------------- |
| 🆕 NEW         | Node or edge added             | Sanctions announced   |
| 🔄 CHANGED     | Property or relation changed   | Protest → nationwide  |
| ✅ RESOLVED    | Edge removed or status changed | Airport closure ended |
| ⏳ ONGOING     | No change, still active        | Negotiations          |

4. LLM generates a change summary with citations.
5. Frontend shows the diff view.

**Acceptance Criteria:**

- Diff is based on actual graph changes, not LLM guesswork.
- Each change links to a source article.
- User can toggle between Day 1 / Day 2 / Day 3 views.
- No hallucinated changes.

---

### UC-07 — Agent Handoff with Shared FalkorDB Memory

**Actor:** System (multi-agent swarm)
**FalkorDB dependency:** Shared state, persistent memory

**Trigger:** New article ingested.

**Agent Flow:**

```
News Collector Agent
      ↓
Fact / Source Agent
      ↓
Connection Agent
      ↓
Impact Agent
      ↓
Shared FalkorDB Memory
```

| Agent       | Reads from FalkorDB | Writes to FalkorDB                                    |
| ----------- | ------------------- | ----------------------------------------------------- |
| Collector   | Source config       | `Article` node                                        |
| Fact/Source | Article node        | `Source` reliability, `Statement` nodes               |
| Connection  | Entities + Article  | `CAUSED`, `AFFECTS`, `RELATED_TO` edges with evidence |
| Impact      | Event + edges       | `IMPACTED` edges, ranked impacts                      |
| Memory      | All nodes/edges     | `MemorySnapshot` node, diff results                   |

**Agent Rules:**

- Never create a 🟢 Confirmed edge without evidence.
- 🟡 Inferred edges must include `rationale`.
- Agents share state through FalkorDB, not in-memory buffers.
- Editor overrides take precedence over AI.

**Acceptance Criteria:**

- Agent handoffs survive across sessions.
- FalkorDB serves as the persistent cognitive memory layer.
- Sub-millisecond traversals for agent loop lookups.
- Multi-agent state sharing visible in audit log.

---

### UC-08 — Curate AI Connections (Human-in-the-Loop)

**Actor:** Editor
**FalkorDB dependency:** Edge property update

**Trigger:** Editor views an 🟡 Inferred edge.

**Main Flow:**

1. Editor can:
   - Approve as 🟢 Confirmed.
   - Reject.
   - Add a note.
   - Change confidence.
   - Merge with another edge.
2. Curation stored in FalkorDB edge properties (with `agent="editor"`).
3. Curation Agent learns from overrides.

**Acceptance Criteria:**

- All curation changes audited.
- AI agents respect editor overrides in subsequent runs.
- Override reason stored in `rationale` property.

---

## Track 3 — Best Use Case of the GraphRAG SDK

**Track focus:** Ontology generated from raw docs, incremental sync with `apply_changes()`, hybrid vector/keyword/Cypher retrieval, multi-hop graph expansion, verified source attribution.

---

### UC-09 — Newsroom Brain: Find Previous Coverage

**Actor:** Journalist
**FalkorDB dependency:** Graph traversal + hybrid retrieval

**Trigger:** User asks: "Have we covered something similar before?"

**Main Flow:**

1. Backend maps the current story to topics and entities.
2. FalkorDB traverses related events → articles → journalists.
3. Hybrid retrieval combines:
   - Vector similarity on article embeddings.
   - Keyword match on entities.
   - Cypher traversal on graph relationships.
4. Results ranked by similarity and recency.

**Acceptance Criteria:**

- Results come from the internal newsroom graph.
- Similarity based on graph relationships, not just text.
- Source attribution verified.

---

### UC-10 — Newsroom Brain: Find Expert Journalist

**Actor:** Editor / Journalist
**FalkorDB dependency:** Graph traversal + ranking

**Trigger:** User asks: "Who on our team knows the most about this subject?"

**Main Flow:**

1. Backend queries `:Topic` → `:Journalist` via `EXPERT_IN`, joined to their articles in the last 12 months.
2. Ranking uses article count, recency, depth, and source quality.
3. Frontend shows ranked journalists with past work.

**Acceptance Criteria:**

- Expert ranking explainable.
- User can open journalist profile and past coverage.
- GraphRAG SDK ontology constrains what can be extracted.

---

### UC-11 — Ontology-Driven Ingestion with GraphRAG SDK

**Actor:** System
**Track:** GraphRAG SDK
**FalkorDB dependency:** Ontology discovery, `apply_changes()`

**Trigger:** New batch of articles ingested.

**Main Flow:**

1. Ontology Discovery auto-drafts a schema from the article corpus using `method="llm"` or `method="grounded"`.
2. Incremental updates use `apply_changes()`:

```python
apply_changes(
    added=[new_articles],
    modified=[updated_articles],
    deleted=[]
)
```

3. `apply_changes()` routes each list to the right primitive (entity extraction, relation extraction, deduplication).
4. Ontology Evolution safely changes schema on a populated graph.
5. Verified source attribution ensures every extracted fact links to a source.

**Acceptance Criteria:**

- Ontology generated from raw docs, not hardcoded.
- Incremental sync works without full re-ingestion.
- Hybrid retrieval: vector + keyword + Cypher.
- Multi-hop graph expansion supported.

---

## Track Alignment Summary

| Use Case                 | Track 1: Investigation | Track 2: Agentic AI | Track 3: GraphRAG SDK |
| ------------------------ | ---------------------- | ------------------- | --------------------- |
| UC-01 Investigate Event  | ✅ Primary             |                     |                       |
| UC-02 Impact Radius      | ✅ Primary             |                     |                       |
| UC-03 Connect the Dots   | ✅ Primary             |                     |                       |
| UC-04 Evidence Trail     | ✅ Primary             |                     |                       |
| UC-05 Story Evolution    |                        | ✅ Primary          |                       |
| UC-06 What Changed       |                        | ✅ Primary          |                       |
| UC-07 Agent Handoff      |                        | ✅ Primary          |                       |
| UC-08 Curate Connections |                        | ✅ Secondary        |                       |
| UC-09 Previous Coverage  |                        |                     | ✅ Primary            |
| UC-10 Expert Journalist  |                        |                     | ✅ Primary            |
| UC-11 Ontology Ingestion |                        |                     | ✅ Primary            |
