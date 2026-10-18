import logging
from typing import Any, Dict, List, Optional, Tuple
from falkordb import FalkorDB
from app.config import Settings, get_settings

logger = logging.getLogger("news_pipeline.falkordb")


class FalkorDBClient:
    """
    Manages FalkorDB connection, schema constraints/indexes,
    and idempotent Cypher writes for Phase 1 of WorldGraph.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._db: Optional[FalkorDB] = None
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            self._db = FalkorDB(
                host=self.settings.falkordb_host,
                port=self.settings.falkordb_port,
            )
            self._graph = self._db.select_graph(self.settings.falkordb_graph)
        return self._graph

    def init_schema(self) -> None:
        """Creates schema indexes and vector index in FalkorDB (idempotent)."""
        logger.info(f"Initializing FalkorDB schema for graph '{self.settings.falkordb_graph}'...")
        indexes = [
            "CREATE INDEX FOR (a:Article) ON (a.url)",
            "CREATE INDEX FOR (s:Source) ON (s.source_id)",
            "CREATE INDEX FOR (e:Event) ON (e.event_id)",
            "CREATE INDEX FOR (e:Event) ON (e.occurred_at)",
            "CREATE INDEX FOR (e:Event) ON (e.category)",
            "CREATE INDEX FOR (st:Story) ON (st.story_id)",
            "CREATE INDEX FOR (a:Article) ON (a.published_at)",
            "CREATE INDEX FOR (c:Country) ON (c.canonical_name)",
            "CREATE INDEX FOR (c:Company) ON (c.canonical_name)",
            "CREATE INDEX FOR (p:Person) ON (p.canonical_name)",
            "CREATE INDEX FOR (o:Organization) ON (o.canonical_name)",
            "CREATE INDEX FOR (i:Industry) ON (i.canonical_name)",
            "CREATE INDEX FOR (cmd:Commodity) ON (cmd.canonical_name)",
            "CREATE INDEX FOR (l:Location) ON (l.canonical_name)",
            "CREATE INDEX FOR (ent:Entity) ON (ent.canonical_name)",
            "CREATE INDEX FOR (st:Statement) ON (st.statement_id)",
            "CREATE INDEX FOR (c:Chunk) ON (c.chunk_id)",
        ]
        for idx_query in indexes:
            try:
                self.graph.query(idx_query)
            except Exception as e:
                # FalkorDB may raise if index already exists
                if "already indexed" not in str(e).lower() and "already exists" not in str(e).lower():
                    logger.debug(f"Index notice ({idx_query}): {e}")

        # Vector Index on Event.centroid (384-d, cosine)
        try:
            self.graph.query(
                "CREATE VECTOR INDEX FOR (e:Event) ON (e.centroid) "
                "OPTIONS {dimension: 384, similarityFunction: 'cosine'}"
            )
            logger.info("Created 384-d cosine vector index on :Event(centroid).")
        except Exception as e:
            if "already" not in str(e).lower():
                logger.debug(f"Vector index notice: {e}")

        # Vector Index on Chunk.embedding (384-d, cosine)
        try:
            self.graph.query(
                "CREATE VECTOR INDEX FOR (c:Chunk) ON (c.embedding) "
                "OPTIONS {dimension: 384, similarityFunction: 'cosine'}"
            )
            logger.info("Created 384-d cosine vector index on :Chunk(embedding).")
        except Exception as e:
            if "already" not in str(e).lower():
                logger.debug(f"Chunk vector index notice: {e}")

        logger.info("FalkorDB schema initialized successfully.")

    def write_article_and_source(self, article_data: Dict[str, Any]) -> None:
        """Writes an :Article node and its :Source node + PUBLISHED_BY edge."""
        url = article_data.get("url")
        if not url:
            return

        source_name = article_data.get("source_name") or "Unknown"
        source_id = article_data.get("source_id") or source_name.lower().replace(" ", "-")

        # Merge Source
        self.graph.query(
            """
            MERGE (s:Source {source_id: $source_id})
            ON CREATE SET s.name = $source_name, s.reliability = 1.0
            """,
            {"source_id": source_id, "source_name": source_name},
        )

        # Merge Article
        self.graph.query(
            """
            MERGE (a:Article {url: $url})
            ON CREATE SET a.title = $title,
                          a.description = $description,
                          a.author = $author,
                          a.published_at = $published_at,
                          a.url_to_image = $url_to_image
            """,
            {
                "url": url,
                "title": article_data.get("title") or "",
                "description": article_data.get("description") or "",
                "author": article_data.get("author") or "",
                "published_at": article_data.get("published_at") or "",
                "url_to_image": article_data.get("url_to_image") or "",
            },
        )

        # Merge PUBLISHED_BY edge
        self.graph.query(
            """
            MATCH (a:Article {url: $url})
            MATCH (s:Source {source_id: $source_id})
            MERGE (a)-[:PUBLISHED_BY]->(s)
            """,
            {"url": url, "source_id": source_id},
        )

    def write_event(
        self,
        event_dict: Dict[str, Any],
        articles_with_sim: List[Dict[str, Any]],
    ) -> None:
        """
        Writes an :Event node with 384-d vector centroid and connects
        each article with REPORTS_ON {similarity}.
        """
        centroid = event_dict.get("centroid", [])
        if len(centroid) != 384:
            centroid = [0.0] * 384

        self.graph.query(
            """
            MERGE (e:Event {event_id: $event_id})
            ON CREATE SET e.title = $title,
                          e.summary = $summary,
                          e.category = $category,
                          e.sentiment = $sentiment,
                          e.occurred_at = $occurred_at,
                          e.first_seen = $first_seen,
                          e.last_seen = $last_seen,
                          e.centroid = vecf32($centroid)
            ON MATCH SET e.last_seen = $last_seen
            """,
            {
                "event_id": event_dict["event_id"],
                "title": event_dict.get("title", ""),
                "summary": event_dict.get("summary", ""),
                "category": event_dict.get("category", "General"),
                "sentiment": event_dict.get("sentiment", "neutral"),
                "occurred_at": event_dict.get("occurred_at", ""),
                "first_seen": event_dict.get("first_seen", ""),
                "last_seen": event_dict.get("last_seen", ""),
                "centroid": centroid,
            },
        )

        # Connect articles via REPORTS_ON
        for item in articles_with_sim:
            url = item.get("url")
            sim = float(item.get("similarity", 1.0))
            if url:
                self.graph.query(
                    """
                    MATCH (a:Article {url: $url})
                    MATCH (e:Event {event_id: $event_id})
                    MERGE (a)-[r:REPORTS_ON]->(e)
                    ON CREATE SET r.similarity = $sim
                    """,
                    {"url": url, "event_id": event_dict["event_id"], "sim": sim},
                )

    def write_story(self, story_dict: Dict[str, Any], new_articles_count: int = 0) -> None:
        """Writes or updates a :Story node."""
        self.graph.query(
            """
            MERGE (st:Story {story_id: $story_id})
            ON CREATE SET st.title = $title,
                          st.first_seen = $first_seen,
                          st.last_seen = $last_seen,
                          st.article_count = $article_count
            ON MATCH SET st.last_seen = $last_seen,
                         st.article_count = st.article_count + $new_count
            """,
            {
                "story_id": story_dict["story_id"],
                "title": story_dict.get("title", ""),
                "first_seen": story_dict.get("first_seen", ""),
                "last_seen": story_dict.get("last_seen", ""),
                "article_count": story_dict.get("article_count", 0),
                "new_count": new_articles_count,
            },
        )

    def link_event_to_story(self, event_id: str, story_id: str) -> None:
        """Creates :PART_OF edge from Event to Story."""
        self.graph.query(
            """
            MATCH (e:Event {event_id: $event_id})
            MATCH (st:Story {story_id: $story_id})
            MERGE (e)-[:PART_OF]->(st)
            """,
            {"event_id": event_id, "story_id": story_id},
        )

    def link_events_preceded(self, prev_event_id: str, next_event_id: str, days_gap: int) -> None:
        """Creates PRECEDED and FOLLOWED edges between consecutive events."""
        self.graph.query(
            """
            MATCH (e1:Event {event_id: $prev_id})
            MATCH (e2:Event {event_id: $next_id})
            MERGE (e1)-[r1:PRECEDED]->(e2)
            ON CREATE SET r1.days_gap = $days_gap
            MERGE (e2)-[r2:FOLLOWED]->(e1)
            ON CREATE SET r2.days_gap = $days_gap
            """,
            {
                "prev_id": prev_event_id,
                "next_id": next_event_id,
                "days_gap": max(0, days_gap),
            },
        )

    def get_recent_events(self, from_date: str, to_date: str) -> List[Dict[str, Any]]:
        """
        Retrieves events within a date range [from_date, to_date]
        along with their centroids and linked story ID.
        """
        res = self.graph.query(
            """
            MATCH (e:Event)
            WHERE e.occurred_at >= $from_date AND e.occurred_at <= $to_date
            OPTIONAL MATCH (e)-[:PART_OF]->(st:Story)
            RETURN e.event_id AS event_id,
                   e.title AS title,
                   e.occurred_at AS occurred_at,
                   e.centroid AS centroid,
                   st.story_id AS story_id
            """,
            {"from_date": from_date, "to_date": to_date},
        )
        events = []
        for row in res.result_set:
            events.append({
                "event_id": row[0],
                "title": row[1],
                "occurred_at": row[2],
                "centroid": row[3],
                "story_id": row[4],
            })
        return events

    def get_graph_stats(self) -> Dict[str, Any]:
        """Returns total counts of nodes and edges in the WorldGraph."""
        stats = {
            "articles": 0,
            "sources": 0,
            "events": 0,
            "stories": 0,
            "reports_on_edges": 0,
            "published_by_edges": 0,
            "part_of_edges": 0,
            "preceded_edges": 0,
        }
        try:
            # Count nodes
            res = self.graph.query("""
                RETURN 
                    COUNT { MATCH (:Article) } AS articles,
                    COUNT { MATCH (:Source) } AS sources,
                    COUNT { MATCH (:Event) } AS events,
                    COUNT { MATCH (:Story) } AS stories
            """)
            if res.result_set and len(res.result_set[0]) >= 4:
                stats["articles"] = res.result_set[0][0]
                stats["sources"] = res.result_set[0][1]
                stats["events"] = res.result_set[0][2]
                stats["stories"] = res.result_set[0][3]
        except Exception:
            # Fallback simple queries if subquery syntax differs
            for label in ["Article", "Source", "Event", "Story"]:
                try:
                    r = self.graph.query(f"MATCH (n:{label}) RETURN count(n)")
                    stats[label.lower() + "s" if not label.endswith("y") else "stories"] = r.result_set[0][0]
                except Exception:
                    pass

        try:
            r = self.graph.query("MATCH ()-[r:REPORTS_ON]->() RETURN count(r)")
            stats["reports_on_edges"] = r.result_set[0][0]
            r = self.graph.query("MATCH ()-[r:PUBLISHED_BY]->() RETURN count(r)")
            stats["published_by_edges"] = r.result_set[0][0]
            r = self.graph.query("MATCH ()-[r:PART_OF]->() RETURN count(r)")
            stats["part_of_edges"] = r.result_set[0][0]
            r = self.graph.query("MATCH ()-[r:PRECEDED]->() RETURN count(r)")
            stats["preceded_edges"] = r.result_set[0][0]
        except Exception as e:
            logger.debug(f"Edge count notice: {e}")

        return stats

    def get_all_events(self) -> List[Dict[str, Any]]:
        """Returns all events with ID, title, summary, occurred_at, category."""
        res = self.graph.query(
            """
            MATCH (e:Event)
            RETURN e.event_id AS event_id,
                   e.title AS title,
                   e.summary AS summary,
                   e.occurred_at AS occurred_at,
                   e.category AS category
            ORDER BY e.occurred_at ASC, e.event_id ASC
            """
        )
        events = []
        for row in res.result_set:
            events.append({
                "event_id": row[0],
                "title": row[1] or "",
                "summary": row[2] or "",
                "occurred_at": row[3] or "",
                "category": row[4] or "General",
            })
        return events

    def get_event_top_articles(self, event_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves top articles linked to an event by similarity to centroid.
        """
        res = self.graph.query(
            """
            MATCH (a:Article)-[r:REPORTS_ON]->(e:Event {event_id: $event_id})
            RETURN a.url AS url,
                   a.title AS title,
                   a.description AS description,
                   a.published_at AS published_at,
                   a.author AS author,
                   r.similarity AS similarity
            ORDER BY r.similarity DESC
            LIMIT $limit
            """,
            {"event_id": event_id, "limit": limit},
        )
        articles = []
        for row in res.result_set:
            articles.append({
                "url": row[0],
                "title": row[1] or "",
                "description": row[2] or "",
                "published_at": row[3] or "",
                "author": row[4] or "",
                "similarity": float(row[5]) if row[5] is not None else 1.0,
            })
        return articles

    def write_entity(self, canonical_name: str, entity_type: str, aliases: List[str]) -> None:
        """
        Writes a multi-labeled :Entity node (:Entity:<Type>) with canonical_name and aliases.
        """
        valid_types = {
            "Country",
            "Company",
            "Person",
            "Organization",
            "Industry",
            "Commodity",
            "Location",
        }
        target_type = entity_type if entity_type in valid_types else "Organization"

        query = f"""
            MERGE (e:Entity:{target_type} {{canonical_name: $name}})
            ON CREATE SET e.aliases = $aliases
            ON MATCH SET e.aliases = $aliases
        """
        self.graph.query(query, {"name": canonical_name, "aliases": aliases})

    def link_event_involves(self, event_id: str, canonical_name: str, role: str = "actor") -> None:
        """Creates :INVOLVES edge from Event to Entity."""
        self.graph.query(
            """
            MATCH (e:Event {event_id: $event_id})
            MATCH (ent:Entity {canonical_name: $name})
            MERGE (e)-[r:INVOLVES]->(ent)
            ON CREATE SET r.role = $role
            ON MATCH SET r.role = $role
            """,
            {"event_id": event_id, "name": canonical_name, "role": role},
        )

    def link_article_mentions(
        self,
        article_url: str,
        canonical_name: str,
        count: int = 1,
        salience: float = 0.5,
    ) -> None:
        """Creates :MENTIONS edge from Article to Entity."""
        self.graph.query(
            """
            MATCH (a:Article {url: $url})
            MATCH (ent:Entity {canonical_name: $name})
            MERGE (a)-[r:MENTIONS]->(ent)
            ON CREATE SET r.count = $count, r.salience = $salience
            ON MATCH SET r.count = $count, r.salience = $salience
            """,
            {
                "url": article_url,
                "name": canonical_name,
                "count": max(1, count),
                "salience": round(float(salience), 3),
            },
        )

    def write_statement(
        self,
        statement_id: str,
        event_id: str,
        article_url: str,
        text: str,
        issued_at: str,
    ) -> None:
        """
        Writes an official :Statement node linked to Event and Article.
        """
        self.graph.query(
            """
            MERGE (st:Statement {statement_id: $stmt_id})
            ON CREATE SET st.text = $text, st.issued_at = $issued_at
            WITH st
            MATCH (e:Event {event_id: $event_id})
            MERGE (e)-[:INCLUDES_STATEMENT]->(st)
            WITH st
            MATCH (a:Article {url: $url})
            MERGE (st)-[:SOURCE_ARTICLE]->(a)
            """,
            {
                "stmt_id": statement_id,
                "text": text,
                "issued_at": issued_at,
                "event_id": event_id,
                "url": article_url,
            },
        )

    def create_country_related_edges(self) -> int:
        """
        Phase 2 Rule-based linking:
        Events sharing >= 2 :Country entities are connected with a weak RELATED_TO edge
        conforming to the Trust Property Contract.
        """
        from datetime import datetime
        now_iso = datetime.utcnow().isoformat() + "Z"

        res = self.graph.query(
            """
            MATCH (e1:Event)-[:INVOLVES]->(c:Country)<-[:INVOLVES]-(e2:Event)
            WHERE e1.event_id < e2.event_id
            WITH e1, e2, collect(c.canonical_name) AS shared_countries
            WHERE size(shared_countries) >= 2
            WITH e1, e2, shared_countries,
                 reduce(s = '', x IN shared_countries | s + (CASE WHEN s = '' THEN '' ELSE ', ' END) + x) AS countries_str
            MERGE (e1)-[r:RELATED_TO {agent: 'rule_engine_v1'}]->(e2)
            ON CREATE SET r.status = 'related',
                          r.confidence = 0.5,
                          r.evidence_ids = [],
                          r.rationale = 'Events share countries: ' + countries_str,
                          r.created_at = $now,
                          r.valid_from = $now
            RETURN count(r)
            """,
            {"now": now_iso},
        )
        count = 0
        if res.result_set and len(res.result_set[0]) > 0:
            count = res.result_set[0][0]
        return count

    def get_phase2_stats(self) -> Dict[str, Any]:
        """Returns statistics of Phase 2 entities and edges."""
        stats = {
            "entities_total": 0,
            "countries": 0,
            "companies": 0,
            "persons": 0,
            "organizations": 0,
            "industries": 0,
            "commodities": 0,
            "locations": 0,
            "statements": 0,
            "involves_edges": 0,
            "mentions_edges": 0,
            "related_to_edges": 0,
        }
        for label, key in [
            ("Entity", "entities_total"),
            ("Country", "countries"),
            ("Company", "companies"),
            ("Person", "persons"),
            ("Organization", "organizations"),
            ("Industry", "industries"),
            ("Commodity", "commodities"),
            ("Location", "locations"),
            ("Statement", "statements"),
        ]:
            try:
                r = self.graph.query(f"MATCH (n:{label}) RETURN count(n)")
                stats[key] = r.result_set[0][0]
            except Exception:
                pass

        for edge, key in [
            ("INVOLVES", "involves_edges"),
            ("MENTIONS", "mentions_edges"),
            ("RELATED_TO", "related_to_edges"),
        ]:
            try:
                r = self.graph.query(f"MATCH ()-[r:{edge}]->() RETURN count(r)")
                stats[key] = r.result_set[0][0]
            except Exception:
                pass

        return stats

    def node_exists(self, node_id: str) -> Tuple[bool, Optional[str]]:
        """
        Checks whether node_id exists in the graph as an :Event or :Entity.
        Returns (exists: bool, label_or_type: Optional[str]).
        """
        # 1. Check Event
        try:
            r = self.graph.query(
                "MATCH (e:Event) WHERE e.event_id = $id RETURN 'Event' LIMIT 1",
                {"id": node_id},
            )
            if r.result_set and len(r.result_set) > 0:
                return True, "Event"
        except Exception as e:
            logger.debug(f"Event check notice: {e}")

        # 2. Check Entity
        try:
            r = self.graph.query(
                "MATCH (ent:Entity) WHERE ent.canonical_name = $id RETURN labels(ent) LIMIT 1",
                {"id": node_id},
            )
            if r.result_set and len(r.result_set) > 0:
                lbls = r.result_set[0][0]
                # Return specific entity type if present (e.g. Country, Company)
                specific = [l for l in lbls if l != "Entity"]
                return True, specific[0] if specific else "Entity"
        except Exception as e:
            logger.debug(f"Entity check notice: {e}")

        return False, None

    def get_event_entities(self, event_id: str, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns entities involved in this event, optionally filtered by type."""
        try:
            query = """
                MATCH (e:Event)-[r:INVOLVES]->(ent:Entity)
                WHERE e.event_id = $event_id
                RETURN ent.canonical_name AS name, labels(ent) AS labels, r.role AS role, ent.aliases AS aliases
            """
            res = self.graph.query(query, {"event_id": event_id})
            entities = []
            for row in res.result_set:
                lbls = row[1] or []
                types = [l for l in lbls if l != "Entity"]
                etype = types[0] if types else "Entity"
                if entity_type and etype.lower() != entity_type.lower():
                    continue
                entities.append({
                    "canonical_name": row[0],
                    "type": etype,
                    "role": row[2] or "actor",
                    "aliases": row[3] or [],
                })
            return entities
        except Exception as e:
            logger.error(f"Error fetching event entities for {event_id}: {e}")
            return []

    def get_candidate_links(self, event_id: str, limit: int = 12) -> List[Dict[str, Any]]:
        """
        Retrieves candidate events and entities for causal/narrative reasoning:
        1. Preceded or shared-story events (narrative threads)
        2. Events sharing 1 or more entities (thematic overlap)
        3. Directly involved entities (for AFFECTS/IMPACTED reasoning)
        """
        candidates: List[Dict[str, Any]] = []
        seen_ids = set()

        # 1. Story peer events
        try:
            r1 = self.graph.query(
                """
                MATCH (e:Event)-[:PART_OF]->(s:Story)<-[:PART_OF]-(peer:Event)
                WHERE e.event_id = $eid AND peer.event_id <> $eid
                RETURN peer.event_id AS id, peer.title AS title, peer.summary AS summary,
                       peer.occurred_at AS occurred_at, peer.category AS category,
                       'Story peer in narrative: ' + s.story_id AS reason
                LIMIT 5
                """,
                {"eid": event_id},
            )
            for row in r1.result_set:
                cid = row[0]
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    candidates.append({
                        "id": cid,
                        "label": "Event",
                        "title": row[1] or "",
                        "summary": row[2] or "",
                        "occurred_at": row[3] or "",
                        "category": row[4] or "",
                        "reason": row[5] or "Story peer",
                    })
        except Exception as e:
            logger.debug(f"Candidate story query notice: {e}")

        # 2. Shared entity peer events
        try:
            r2 = self.graph.query(
                """
                MATCH (e:Event)-[:INVOLVES]->(ent:Entity)<-[:INVOLVES]-(peer:Event)
                WHERE e.event_id = $eid AND peer.event_id <> $eid
                WITH peer, collect(ent.canonical_name) AS shared
                RETURN peer.event_id AS id, peer.title AS title, peer.summary AS summary,
                       peer.occurred_at AS occurred_at, peer.category AS category,
                       'Shared entities: ' + reduce(s = '', x IN shared | s + (CASE WHEN s = '' THEN '' ELSE ', ' END) + x) AS reason
                LIMIT 6
                """,
                {"eid": event_id},
            )
            for row in r2.result_set:
                cid = row[0]
                if cid not in seen_ids and len(candidates) < limit:
                    seen_ids.add(cid)
                    candidates.append({
                        "id": cid,
                        "label": "Event",
                        "title": row[1] or "",
                        "summary": row[2] or "",
                        "occurred_at": row[3] or "",
                        "category": row[4] or "",
                        "reason": row[5] or "Shared entity",
                    })
        except Exception as e:
            logger.debug(f"Candidate shared entities query notice: {e}")

        # 3. Directly involved entities (targets for AFFECTS or sources for IMPACTED)
        try:
            r3 = self.graph.query(
                """
                MATCH (e:Event)-[r:INVOLVES]->(ent:Entity)
                WHERE e.event_id = $eid
                RETURN ent.canonical_name AS id, labels(ent) AS labels, r.role AS role
                LIMIT 8
                """,
                {"eid": event_id},
            )
            for row in r3.result_set:
                cid = row[0]
                lbls = row[1] or []
                types = [l for l in lbls if l != "Entity"]
                etype = types[0] if types else "Entity"
                if cid not in seen_ids and len(candidates) < limit:
                    seen_ids.add(cid)
                    candidates.append({
                        "id": cid,
                        "label": etype,
                        "title": cid,
                        "summary": f"{etype} entity (role: {row[2]}) directly involved in this event",
                        "occurred_at": "",
                        "category": etype,
                        "reason": f"Directly involved {etype} entity",
                    })
        except Exception as e:
            logger.debug(f"Candidate direct entities query notice: {e}")

        return candidates

    def write_reasoning_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        status: str,
        confidence: float,
        evidence_ids: List[str],
        rationale: Optional[str] = None,
        agent: str = "graph_agent_v1",
    ) -> bool:
        """
        Writes a reasoning edge (CAUSED, CONTRIBUTED_TO, AFFECTS, IMPACTED, RELATED_TO)
        to FalkorDB following the Trust Property Contract.
        Protects human curator edits (agent='editor') from being overwritten.
        """
        from datetime import datetime
        now_iso = datetime.utcnow().isoformat() + "Z"
        rat = rationale or ""

        # Determine node match patterns based on edge type
        if edge_type in ("CAUSED", "CONTRIBUTED_TO", "RELATED_TO"):
            src_match = "MATCH (s:Event) WHERE s.event_id = $src"
            tgt_match = "MATCH (t:Event) WHERE t.event_id = $tgt"
        elif edge_type == "AFFECTS":
            src_match = "MATCH (s:Event) WHERE s.event_id = $src"
            tgt_match = "MATCH (t:Entity) WHERE t.canonical_name = $tgt"
        elif edge_type == "IMPACTED":
            src_match = "MATCH (s:Entity) WHERE s.canonical_name = $src"
            tgt_match = "MATCH (t:Event) WHERE t.event_id = $tgt"
        else:
            logger.error(f"Unsupported edge type: {edge_type}")
            return False

        cypher = f"""
            {src_match}
            {tgt_match}
            MERGE (s)-[r:{edge_type}]->(t)
            ON CREATE SET r.status = $status,
                          r.confidence = $confidence,
                          r.evidence_ids = $evidence_ids,
                          r.rationale = $rationale,
                          r.agent = $agent,
                          r.created_at = $now,
                          r.valid_from = $now,
                          r.valid_to = null
            ON MATCH SET r.status = CASE WHEN r.agent = 'editor' THEN r.status ELSE $status END,
                         r.confidence = CASE WHEN r.agent = 'editor' THEN r.confidence ELSE $confidence END,
                         r.evidence_ids = CASE WHEN r.agent = 'editor' THEN r.evidence_ids ELSE $evidence_ids END,
                         r.rationale = CASE WHEN r.agent = 'editor' THEN r.rationale ELSE $rationale END,
                         r.valid_from = CASE WHEN r.agent = 'editor' THEN r.valid_from ELSE $now END
        """

        try:
            self.graph.query(
                cypher,
                {
                    "src": source_id,
                    "tgt": target_id,
                    "status": status,
                    "confidence": round(float(confidence), 3),
                    "evidence_ids": evidence_ids or [],
                    "rationale": rat,
                    "agent": agent,
                    "now": now_iso,
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to write reasoning edge ({source_id})-[:{edge_type}]->({target_id}): {e}")
            return False

    def get_reasoning_stats(self) -> Dict[str, Any]:
        """Returns statistics for Phase 3 reasoning edges."""
        stats = {
            "caused_edges": 0,
            "contributed_edges": 0,
            "affects_edges": 0,
            "impacted_edges": 0,
            "related_to_edges": 0,
            "confirmed_edges": 0,
            "inferred_edges": 0,
            "related_edges": 0,
        }
        for edge_type, key in [
            ("CAUSED", "caused_edges"),
            ("CONTRIBUTED_TO", "contributed_edges"),
            ("AFFECTS", "affects_edges"),
            ("IMPACTED", "impacted_edges"),
            ("RELATED_TO", "related_to_edges"),
        ]:
            try:
                r = self.graph.query(f"MATCH ()-[r:{edge_type}]->() RETURN count(r)")
                stats[key] = r.result_set[0][0]
            except Exception:
                pass

        for st_val, key in [
            ("confirmed", "confirmed_edges"),
            ("inferred", "inferred_edges"),
            ("related", "related_edges"),
        ]:
            try:
                r = self.graph.query(
                    f"MATCH ()-[r]->() WHERE r.status = '{st_val}' RETURN count(r)"
                )
                stats[key] = r.result_set[0][0]
            except Exception:
                pass

        return stats

    def get_reasoning_edges(
        self,
        edge_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Returns reasoning edges with full trust properties for the UI directory and visualizer.
        """
        type_str = f":{edge_type}" if edge_type else ":CAUSED|CONTRIBUTED_TO|AFFECTS|IMPACTED"
        status_filter = f"WHERE r.status = '{status}'" if status else ""

        cypher = f"""
            MATCH (s)-[r{type_str}]->(t)
            {status_filter}
            RETURN coalesce(s.event_id, s.canonical_name, 'Unknown') AS src_id,
                   coalesce(s.title, s.canonical_name, 'Unknown') AS src_title,
                   labels(s) AS src_labels,
                   type(r) AS rel_type,
                   r.status AS status,
                   r.confidence AS confidence,
                   r.rationale AS rationale,
                   r.agent AS agent,
                   r.evidence_ids AS evidence_ids,
                   coalesce(t.event_id, t.canonical_name, 'Unknown') AS tgt_id,
                   coalesce(t.title, t.canonical_name, 'Unknown') AS tgt_title,
                   labels(t) AS tgt_labels
            ORDER BY r.confidence DESC
            SKIP $skip LIMIT $limit
        """
        try:
            res = self.graph.query(cypher, {"skip": skip, "limit": limit})
            edges = []
            for row in res.result_set:
                edges.append({
                    "source_id": row[0],
                    "source_title": row[1],
                    "source_labels": row[2] or [],
                    "edge_type": row[3],
                    "status": row[4] or "inferred",
                    "confidence": float(row[5]) if row[5] is not None else 0.5,
                    "rationale": row[6] or "",
                    "agent": row[7] or "graph_agent_v1",
                    "evidence_ids": row[8] or [],
                    "target_id": row[9],
                    "target_title": row[10],
                    "target_labels": row[11] or [],
                })
            return edges
        except Exception as e:
            logger.error(f"Error fetching reasoning edges: {e}")
            return []

    def get_shortest_path(self, event1_id: str, event2_id: str) -> Optional[Dict[str, Any]]:
        """
        UC-03 Connect the Dots:
        Finds the shortest path between two Event nodes in FalkorDB.
        """
        try:
            cypher = """
                MATCH (e1:Event), (e2:Event)
                WHERE e1.event_id = $src AND e2.event_id = $tgt
                RETURN shortestPath((e1)-[*]-(e2))
            """
            res = self.graph.query(cypher, {"src": event1_id, "tgt": event2_id})
            if not res.result_set or not res.result_set[0] or res.result_set[0][0] is None:
                return None

            path = res.result_set[0][0]
            nodes_data = []
            for n in path.nodes():
                props = getattr(n, "properties", {})
                lbls = getattr(n, "labels", [])
                nodes_data.append({
                    "id": props.get("event_id") or props.get("canonical_name") or props.get("url") or str(props),
                    "labels": lbls,
                    "title": props.get("title") or props.get("canonical_name") or "",
                    "summary": props.get("summary") or props.get("description") or "",
                })

            edges_data = []
            for e in path.edges():
                props = getattr(e, "properties", {})
                rel = getattr(e, "relation", "CONNECTED")
                edges_data.append({
                    "type": rel,
                    "status": props.get("status", "related"),
                    "confidence": props.get("confidence", 0.5),
                    "rationale": props.get("rationale", ""),
                    "agent": props.get("agent", ""),
                    "evidence_ids": props.get("evidence_ids", []),
                })

            return {
                "source_event_id": event1_id,
                "target_event_id": event2_id,
                "path_length": len(edges_data),
                "nodes": nodes_data,
                "edges": edges_data,
            }
        except Exception as e:
            logger.error(f"Error computing shortest path between {event1_id} and {event2_id}: {e}")
            return None

    def get_impact_radius(self, event_id: str, hops: int = 2) -> Dict[str, Any]:
        """
        UC-02 Impact Radius:
        Bounded BFS from an Event node over AFFECTS, CONTRIBUTED_TO, IMPACTED, and INVOLVES edges.
        Groups impacted entities by label (Country, Company, Industry, Commodity, Organization, etc.).
        """
        max_hops = min(max(hops, 1), 3)
        res = {
            "event_id": event_id,
            "hops": max_hops,
            "grouped_impacts": {
                "Country": [],
                "Company": [],
                "Industry": [],
                "Commodity": [],
                "Organization": [],
                "Person": [],
                "Location": [],
                "Other": [],
            },
            "events_impacted": [],
        }

        try:
            # 1. Direct and downstream entity impacts
            cypher = f"""
                MATCH (e:Event)
                WHERE e.event_id = $eid
                MATCH (e)-[r:AFFECTS|CONTRIBUTED_TO|IMPACTED|INVOLVES*1..{max_hops}]-(ent:Entity)
                RETURN DISTINCT ent.canonical_name AS name, labels(ent) AS labels
            """
            r = self.graph.query(cypher, {"eid": event_id})
            for row in r.result_set:
                name = row[0]
                lbls = row[1] or []
                types = [l for l in lbls if l != "Entity"]
                target_group = types[0] if types and types[0] in res["grouped_impacts"] else "Other"
                if name not in res["grouped_impacts"][target_group]:
                    res["grouped_impacts"][target_group].append(name)

            # 2. Downstream impacted events
            cypher_ev = f"""
                MATCH (e:Event)
                WHERE e.event_id = $eid
                MATCH (e)-[r:CAUSED|CONTRIBUTED_TO*1..{max_hops}]->(downstream:Event)
                WHERE downstream.event_id <> $eid
                RETURN DISTINCT downstream.event_id AS id, downstream.title AS title, downstream.occurred_at AS occurred_at
            """
            r_ev = self.graph.query(cypher_ev, {"eid": event_id})
            for row in r_ev.result_set:
                res["events_impacted"].append({
                    "event_id": row[0],
                    "title": row[1] or "",
                    "occurred_at": row[2] or "",
                })

        except Exception as e:
            logger.error(f"Error computing impact radius for {event_id}: {e}")

        return res

    def investigate_event_multihop(self, event_id: str, hops: int = 2) -> Dict[str, Any]:
        """
        UC-01 Investigate Event:
        Multi-hop neighborhood extraction from an event (1-2 hops).
        Returns all reachable nodes and relationships with full trust properties.
        """
        result = {
            "center_event_id": event_id,
            "nodes": [],
            "edges": [],
        }
        node_map = {}
        edge_set = set()

        try:
            # Center event details
            r_center = self.graph.query(
                "MATCH (e:Event) WHERE e.event_id = $eid RETURN e.event_id, e.title, e.summary, e.occurred_at, e.category",
                {"eid": event_id},
            )
            if r_center.result_set:
                row = r_center.result_set[0]
                node_map[event_id] = {
                    "id": row[0],
                    "labels": ["Event"],
                    "title": row[1] or "",
                    "summary": row[2] or "",
                    "category": row[4] or "",
                    "occurred_at": row[3] or "",
                }

            # 1-2 hop neighbors over all relationships
            cypher = f"""
                MATCH (e:Event)
                WHERE e.event_id = $eid
                MATCH (e)-[r*1..{min(hops, 2)}]-(neighbor)
                UNWIND r AS rel
                WITH startNode(rel) AS sn, endNode(rel) AS en, rel
                RETURN coalesce(sn.event_id, sn.canonical_name, sn.url) AS src,
                       labels(sn) AS src_labels,
                       coalesce(sn.title, sn.canonical_name) AS src_title,
                       coalesce(en.event_id, en.canonical_name, en.url) AS tgt,
                       labels(en) AS tgt_labels,
                       coalesce(en.title, en.canonical_name) AS tgt_title,
                       type(rel) AS rel_type,
                       properties(rel) AS rel_props
                LIMIT 100
            """
            r = self.graph.query(cypher, {"eid": event_id})
            for row in r.result_set:
                src_id, src_lbls, src_title, tgt_id, tgt_lbls, tgt_title, rel_type, rel_props = row
                if src_id and src_id not in node_map:
                    node_map[src_id] = {
                        "id": src_id,
                        "labels": src_lbls or [],
                        "title": src_title or src_id,
                    }
                if tgt_id and tgt_id not in node_map:
                    node_map[tgt_id] = {
                        "id": tgt_id,
                        "labels": tgt_lbls or [],
                        "title": tgt_title or tgt_id,
                    }

                edge_key = (src_id, tgt_id, rel_type)
                if edge_key not in edge_set:
                    edge_set.add(edge_key)
                    props = rel_props or {}
                    result["edges"].append({
                        "source": src_id,
                        "target": tgt_id,
                        "type": rel_type,
                        "status": props.get("status", "related"),
                        "confidence": props.get("confidence", 0.5),
                        "rationale": props.get("rationale", ""),
                        "agent": props.get("agent", ""),
                        "evidence_ids": props.get("evidence_ids", []),
                    })

            result["nodes"] = list(node_map.values())
        except Exception as e:
            logger.error(f"Error investigating event {event_id}: {e}")

        return result

    def get_edge_evidence(self, source_id: str, target_id: str, edge_type: str) -> Optional[Dict[str, Any]]:
        """
        UC-04 Evidence Trail:
        Finds the edge between source_id and target_id, extracts its trust properties,
        and joins each URL in evidence_ids with its :Article and :Source node.
        """
        try:
            cypher = f"""
                MATCH (s)-[r:{edge_type}]->(t)
                WHERE (s.event_id = $src OR s.canonical_name = $src)
                  AND (t.event_id = $tgt OR t.canonical_name = $tgt)
                RETURN properties(r) AS props
                LIMIT 1
            """
            res = self.graph.query(cypher, {"src": source_id, "tgt": target_id})
            if not res.result_set or not res.result_set[0]:
                return None

            props = res.result_set[0][0] or {}
            evidence_urls = props.get("evidence_ids") or []

            # Join supporting articles with source publisher
            articles_info = []
            if evidence_urls:
                art_res = self.graph.query(
                    """
                    MATCH (a:Article)-[:PUBLISHED_BY]->(src:Source)
                    WHERE a.url IN $urls
                    RETURN a.url AS url, a.title AS title, a.description AS description,
                           a.published_at AS published_at, src.name AS source_name,
                           src.reliability AS reliability
                    """,
                    {"urls": evidence_urls},
                )
                for row in art_res.result_set:
                    articles_info.append({
                        "url": row[0],
                        "title": row[1] or "",
                        "description": row[2] or "",
                        "published_at": row[3] or "",
                        "source_name": row[4] or "Unknown",
                        "reliability": row[5] if row[5] is not None else 1.0,
                    })

            return {
                "source_id": source_id,
                "target_id": target_id,
                "edge_type": edge_type,
                "status": props.get("status", "related"),
                "confidence": props.get("confidence", 0.5),
                "rationale": props.get("rationale", ""),
                "agent": props.get("agent", "unknown"),
                "evidence_ids": evidence_urls,
                "articles": articles_info,
                "created_at": props.get("created_at"),
                "valid_from": props.get("valid_from"),
            }
        except Exception as e:
            logger.error(f"Error fetching edge evidence ({source_id})-[:{edge_type}]->({target_id}): {e}")
    def write_article_chunks(self, article_url: str, chunks_data: List[Dict[str, Any]]) -> int:
        """
        Persists :Chunk nodes with 384-d vector embeddings and links them to their :Article.
        Uses vecf32 for native FalkorDB vector indexing.
        """
        written = 0
        for chk in chunks_data:
            chunk_id = chk["chunk_id"]
            idx = int(chk.get("chunk_index", 0))
            text = chk.get("text", "")
            wc = int(chk.get("word_count", 0))
            emb = chk.get("embedding", [])
            if len(emb) != 384:
                emb = [0.0] * 384

            cypher = f"""
                MATCH (a:Article {{url: $url}})
                MERGE (c:Chunk {{chunk_id: $cid}})
                ON CREATE SET c.chunk_index = $idx,
                              c.text = $text,
                              c.word_count = $wc,
                              c.embedding = vecf32({emb})
                ON MATCH SET c.text = $text,
                             c.word_count = $wc,
                             c.embedding = vecf32({emb})
                MERGE (a)-[r:HAS_CHUNK]->(c)
                ON CREATE SET r.index = $idx
            """
            try:
                self.graph.query(
                    cypher,
                    {
                        "url": article_url,
                        "cid": chunk_id,
                        "idx": idx,
                        "text": text,
                        "wc": wc,
                    },
                )
                written += 1
            except Exception as e:
                logger.error(f"Failed to write chunk {chunk_id}: {e}")

        return written

    def query_event_chunks(
        self,
        event_id: str,
        query_vector: List[float],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        UC-01 & UC-02 Graph-Scoped Vector Search:
        Traverses from the target Event to its reporting Articles to their Chunks,
        and computes native vector cosine similarity against the query vector.
        """
        if len(query_vector) != 384:
            query_vector = [0.0] * 384

        cypher = f"""
            MATCH (e:Event {{event_id: $eid}})<-[:REPORTS_ON]-(a:Article)-[:HAS_CHUNK]->(c:Chunk)
            WHERE c.embedding IS NOT NULL
            WITH a, c, (1.0 - vec.cosineDistance(c.embedding, vecf32({query_vector}))) AS similarity
            RETURN a.title AS article_title,
                   a.url AS article_url,
                   c.chunk_id AS chunk_id,
                   c.chunk_index AS chunk_index,
                   c.text AS chunk_text,
                   similarity
            ORDER BY similarity DESC
            LIMIT $limit
        """
        results = []
        try:
            res = self.graph.query(cypher, {"eid": event_id, "limit": limit})
            for row in res.result_set:
                results.append({
                    "article_title": row[0] or "",
                    "article_url": row[1] or "",
                    "chunk_id": row[2] or "",
                    "chunk_index": row[3] or 0,
                    "chunk_text": row[4] or "",
                    "similarity": round(float(row[5]), 4) if row[5] is not None else 0.0,
                })
        except Exception as e:
            logger.error(f"Error querying event chunks for {event_id}: {e}")

        return results

    def query_path_chunks(
        self,
        event_ids: List[str],
        query_vector: List[float],
        limit: int = 6,
    ) -> List[Dict[str, Any]]:
        """
        UC-03 Connect the Dots Scoped Vector Search:
        Finds chunks across all events along a connecting path, ranked by vector similarity.
        """
        if len(query_vector) != 384:
            query_vector = [0.0] * 384

        cypher = f"""
            MATCH (e:Event)<-[:REPORTS_ON]-(a:Article)-[:HAS_CHUNK]->(c:Chunk)
            WHERE e.event_id IN $eids AND c.embedding IS NOT NULL
            WITH DISTINCT a, c, (1.0 - vec.cosineDistance(c.embedding, vecf32({query_vector}))) AS similarity
            RETURN a.title AS article_title,
                   a.url AS article_url,
                   c.chunk_id AS chunk_id,
                   c.chunk_index AS chunk_index,
                   c.text AS chunk_text,
                   similarity
            ORDER BY similarity DESC
            LIMIT $limit
        """
        results = []
        try:
            res = self.graph.query(cypher, {"eids": event_ids, "limit": limit})
            for row in res.result_set:
                results.append({
                    "article_title": row[0] or "",
                    "article_url": row[1] or "",
                    "chunk_id": row[2] or "",
                    "chunk_index": row[3] or 0,
                    "chunk_text": row[4] or "",
                    "similarity": round(float(row[5]), 4) if row[5] is not None else 0.0,
                })
        except Exception as e:
            logger.error(f"Error querying path chunks: {e}")

        return results

    def get_chunk_stats(self) -> Dict[str, Any]:
        """Returns total counts of :Chunk nodes and :HAS_CHUNK edges in FalkorDB."""
        stats = {"chunk_nodes": 0, "has_chunk_edges": 0}
        try:
            r1 = self.graph.query("MATCH (c:Chunk) RETURN count(c)")
            if r1.result_set:
                stats["chunk_nodes"] = r1.result_set[0][0]
            r2 = self.graph.query("MATCH ()-[r:HAS_CHUNK]->() RETURN count(r)")
            if r2.result_set:
                stats["has_chunk_edges"] = r2.result_set[0][0]
        except Exception as e:
            logger.debug(f"Chunk stats notice: {e}")
        return stats

    def clear_graph(self) -> None:
        """Deletes all nodes and relationships in the graph."""
        logger.warning(f"Clearing entire FalkorDB graph '{self.settings.falkordb_graph}'...")
        try:
            self.graph.delete()
            self._graph = None
            logger.info("Graph deleted. Initializing fresh schema...")
            self.init_schema()
        except Exception as e:
            logger.error(f"Error clearing graph: {e}")


