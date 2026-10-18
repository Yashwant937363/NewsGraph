import logging
from typing import Any, Dict, List, Optional
from app.config import Settings, get_settings
from app.services.falkordb_client import FalkorDBClient

logger = logging.getLogger("news_pipeline.phase1_service")


class Phase1Service:
    """
    Business logic and graph traversal service for Phase 1 visualization:
    Queries FalkorDB for Stories, Events, Articles, Sources, and their structural edges.
    Formats data for interactive force-directed graphs and timelines.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.falkordb = FalkorDBClient(self.settings)

    def get_overview_stats(self) -> Dict[str, Any]:
        """Returns overall graph counts and summary for Phase 1 & Phase 2."""
        stats = self.falkordb.get_graph_stats()
        phase2_stats = self.falkordb.get_phase2_stats()
        
        # Get date span
        date_res = self.falkordb.graph.query(
            """
            MATCH (e:Event)
            RETURN min(e.occurred_at) AS min_date,
                   max(e.occurred_at) AS max_date,
                   count(DISTINCT e.occurred_at) AS active_days
            """
        )
        min_date, max_date, active_days = "", "", 0
        if date_res.result_set and len(date_res.result_set[0]) >= 3:
            min_date = date_res.result_set[0][0] or ""
            max_date = date_res.result_set[0][1] or ""
            active_days = date_res.result_set[0][2] or 0

        phase3_stats = self.falkordb.get_reasoning_stats()

        return {
            "graph_stats": stats,
            "phase2_stats": phase2_stats,
            "phase3_stats": phase3_stats,
            "min_date": min_date,
            "max_date": max_date,
            "active_days": active_days,
        }

    def get_dates_summary(self) -> List[Dict[str, Any]]:
        """Returns per-date event, story, and article counts for timeline scrubber."""
        res = self.falkordb.graph.query(
            """
            MATCH (e:Event)
            OPTIONAL MATCH (a:Article)-[:REPORTS_ON]->(e)
            RETURN e.occurred_at AS date,
                   count(DISTINCT e) AS event_count,
                   count(DISTINCT a) AS article_count
            ORDER BY date ASC
            """
        )
        dates = []
        for row in res.result_set:
            if row[0]:
                dates.append({
                    "date": row[0],
                    "event_count": row[1],
                    "article_count": row[2],
                })
        return dates

    def get_stories(
        self,
        skip: int = 0,
        limit: int = 30,
        search: Optional[str] = None,
        min_events: int = 1,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves paginated stories with event counts and date ranges,
        supporting search and minimum event filtering.
        """
        search_filter = ""
        params: Dict[str, Any] = {"min_events": min_events, "skip": skip, "limit": limit}

        if search and search.strip():
            params["search_term"] = f"(?i).*{search.strip()}.*"
            search_filter = "AND s.title =~ $search_term"

        date_filter = ""
        if date and date.strip():
            params["date"] = date.strip()
            date_filter = "AND e.occurred_at = $date"

        query = f"""
            MATCH (e:Event)-[:PART_OF]->(s:Story)
            WHERE 1=1 {search_filter} {date_filter}
            WITH s, count(DISTINCT e) AS event_count,
                 min(e.occurred_at) AS start_date,
                 max(e.occurred_at) AS end_date
            WHERE event_count >= $min_events
            RETURN s.story_id AS story_id,
                   s.title AS title,
                   s.article_count AS article_count,
                   event_count,
                   start_date,
                   end_date
            ORDER BY event_count DESC, s.article_count DESC
            SKIP $skip LIMIT $limit
        """
        res = self.falkordb.graph.query(query, params)
        stories = []
        for row in res.result_set:
            stories.append({
                "story_id": row[0],
                "title": row[1] or "Untitled Story",
                "article_count": row[2] or 0,
                "event_count": row[3],
                "start_date": row[4] or "",
                "end_date": row[5] or "",
            })

        # Total count
        count_query = f"""
            MATCH (e:Event)-[:PART_OF]->(s:Story)
            WHERE 1=1 {search_filter} {date_filter}
            WITH s, count(DISTINCT e) AS event_count
            WHERE event_count >= $min_events
            RETURN count(DISTINCT s) AS total
        """
        c_res = self.falkordb.graph.query(count_query, params)
        total = c_res.result_set[0][0] if c_res.result_set else len(stories)

        return {
            "stories": stories,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    def get_story_graph(
        self,
        story_id: str,
        include_articles: bool = True,
        include_entities: bool = True,
        include_related: bool = True,
        include_statements: bool = True,
        max_articles_per_event: int = 4,
        max_entities_per_event: int = 6,
    ) -> Dict[str, Any]:
        """
        Builds a force-directed graph structure (nodes & edges) for a single story.
        Includes:
        - The Story node (hub)
        - All Event nodes linked via PART_OF
        - PRECEDED edges between sequential events
        - Top reporting Articles and Source publishers
        """
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_ids = set()

        def add_node(nid: str, label: str, group: str, title: str, size: int = 20, **kwargs):
            if nid not in node_ids:
                node_ids.add(nid)
                node_dict = {
                    "id": nid,
                    "label": label,
                    "group": group,
                    "title": title,
                    "size": size,
                    **kwargs,
                }
                nodes.append(node_dict)

        def add_edge(from_id: str, to_id: str, label: str, title: str = "", dashes: bool = False, **kwargs):
            edges.append({
                "from": from_id,
                "to": to_id,
                "label": label,
                "title": title,
                "dashes": dashes,
                "arrows": "to",
                **kwargs,
            })

        # 1. Fetch Story
        story_res = self.falkordb.graph.query(
            "MATCH (s:Story {story_id: $id}) RETURN s.story_id, s.title, s.article_count, s.first_seen, s.last_seen",
            {"id": story_id},
        )
        story_info = None
        if story_res.result_set and len(story_res.result_set[0]) >= 2:
            row = story_res.result_set[0]
            story_info = {
                "story_id": row[0],
                "title": row[1] or story_id,
                "article_count": row[2] or 0,
                "first_seen": row[3] or "",
                "last_seen": row[4] or "",
            }
            add_node(
                nid=row[0],
                label=(row[1][:40] + "...") if len(row[1] or "") > 40 else row[1],
                group="story",
                title=f"Story: {row[1]}<br>Articles: {row[2]}",
                size=35,
                full_title=row[1],
            )

        # 2. Fetch Events belonging to Story
        events_res = self.falkordb.graph.query(
            """
            MATCH (e:Event)-[:PART_OF]->(s:Story {story_id: $id})
            RETURN e.event_id AS event_id,
                   e.title AS title,
                   e.summary AS summary,
                   e.occurred_at AS occurred_at,
                   e.category AS category
            ORDER BY e.occurred_at ASC, e.event_id ASC
            """,
            {"id": story_id},
        )
        story_events = []
        event_ids_list = []

        for row in events_res.result_set:
            eid = row[0]
            etitle = row[1] or eid
            summary = row[2] or ""
            occurred_at = row[3] or ""
            category = row[4] or "General"

            event_ids_list.append(eid)
            story_events.append({
                "event_id": eid,
                "title": etitle,
                "summary": summary,
                "occurred_at": occurred_at,
                "category": category,
            })

            add_node(
                nid=eid,
                label=f"[{occurred_at[-5:]}] " + ((etitle[:32] + "...") if len(etitle) > 32 else etitle),
                group="event",
                title=f"Event ({occurred_at}): {etitle}<br>{summary[:120]}...",
                size=26,
                full_title=etitle,
                occurred_at=occurred_at,
                category=category,
                summary=summary,
            )

            # Edge: Event -> Story (PART_OF)
            add_edge(from_id=eid, to_id=story_id, label="PART_OF", title="Belongs to Story", dashes=True)

        # 3. Fetch PRECEDED edges among these events
        if event_ids_list:
            preceded_res = self.falkordb.graph.query(
                """
                MATCH (e1:Event)-[p:PRECEDED]->(e2:Event)
                WHERE e1.event_id IN $eids AND e2.event_id IN $eids
                RETURN e1.event_id, e2.event_id, p.days_gap
                """,
                {"eids": event_ids_list},
            )
            for row in preceded_res.result_set:
                gap = row[2] or 1
                add_edge(
                    from_id=row[0],
                    to_id=row[1],
                    label=f"PRECEDED (+{gap}d)",
                    title=f"Preceded by {gap} day(s)",
                    color={"color": "#38bdf8", "highlight": "#0284c7"},
                    width=2,
                )

        # 4. Fetch top articles per event if requested
        if include_articles and event_ids_list:
            for eid in event_ids_list:
                art_res = self.falkordb.graph.query(
                    """
                    MATCH (a:Article)-[r:REPORTS_ON]->(e:Event {event_id: $eid})
                    OPTIONAL MATCH (a)-[:PUBLISHED_BY]->(s:Source)
                    RETURN a.url, a.title, r.similarity, s.source_id, s.name, a.published_at
                    ORDER BY r.similarity DESC
                    LIMIT $limit
                    """,
                    {"eid": eid, "limit": max_articles_per_event},
                )
                for row in art_res.result_set:
                    a_url = row[0]
                    a_title = row[1] or "Article"
                    sim = float(row[2]) if row[2] is not None else 1.0
                    s_id = row[3]
                    s_name = row[4] or "Publisher"
                    pub_at = row[5] or ""

                    # Add Article node
                    add_node(
                        nid=a_url,
                        label=(a_title[:28] + "...") if len(a_title) > 28 else a_title,
                        group="article",
                        title=f"Article: {a_title}<br>Source: {s_name}<br>Similarity: {sim:.2f}",
                        size=15,
                        url=a_url,
                        full_title=a_title,
                        source_name=s_name,
                        published_at=pub_at,
                    )
                    # Edge Article -> Event (REPORTS_ON)
                    add_edge(
                        from_id=a_url,
                        to_id=eid,
                        label=f"{sim:.2f}",
                        title=f"REPORTS_ON (similarity {sim:.2f})",
                        color={"color": "#2dd4bf"},
                        width=max(1, int(sim * 2.5)),
                    )

                    # Add Source node and PUBLISHED_BY edge
                    if s_id:
                        add_node(
                            nid=s_id,
                            label=s_name,
                            group="source",
                            title=f"Source: {s_name}",
                            size=18,
                            source_name=s_name,
                        )
                        add_edge(
                            from_id=a_url,
                            to_id=s_id,
                            label="PUBLISHED_BY",
                            title="Published By",
                            dashes=True,
                            color={"color": "#fbbf24"},
                        )

        # 5. Phase 2: Fetch Entities involved in these events
        if include_entities and event_ids_list:
            ent_res = self.falkordb.graph.query(
                """
                MATCH (e:Event)-[r:INVOLVES]->(ent:Entity)
                WHERE e.event_id IN $eids
                RETURN e.event_id, ent.canonical_name, labels(ent), r.role, ent.aliases
                LIMIT 150
                """,
                {"eids": event_ids_list},
            )
            ent_counts_per_event = {}
            for row in ent_res.result_set:
                eid = row[0]
                cname = row[1]
                lbls = row[2] or []
                role = row[3] or "actor"
                aliases = row[4] or []

                count = ent_counts_per_event.get(eid, 0)
                if count >= max_entities_per_event:
                    continue
                ent_counts_per_event[eid] = count + 1

                types = [l for l in lbls if l != "Entity"]
                etype = types[0] if types else "Entity"
                grp = etype.lower()

                # Add Entity node
                add_node(
                    nid=cname,
                    label=cname,
                    group=grp,
                    title=f"Entity ({etype}): {cname}<br>Role: {role}",
                    size=20,
                    entity_type=etype,
                    canonical_name=cname,
                    aliases=aliases,
                )

                # Edge Event -> Entity (INVOLVES)
                add_edge(
                    from_id=eid,
                    to_id=cname,
                    label=f"INVOLVES ({role})",
                    title=f"Involves as {role}",
                    color={"color": "#38bdf8", "opacity": 0.8},
                    dashes=True,
                )

        # 6. Phase 2: Fetch RELATED_TO edges between story events
        if include_related and event_ids_list:
            rel_res = self.falkordb.graph.query(
                """
                MATCH (e1:Event)-[r:RELATED_TO]->(e2:Event)
                WHERE e1.event_id IN $eids AND e2.event_id IN $eids
                RETURN e1.event_id, e2.event_id, r.confidence, r.rationale, r.status
                """,
                {"eids": event_ids_list},
            )
            for row in rel_res.result_set:
                e1, e2, conf, rat, st = row
                add_edge(
                    from_id=e1,
                    to_id=e2,
                    label="RELATED_TO",
                    title=f"Related (confidence: {conf})<br>{rat}",
                    color={"color": "#f97316", "highlight": "#ea580c"},
                    dashes=True,
                    width=2,
                )

        # 7. Phase 2: Fetch official Statement nodes
        if include_statements and event_ids_list:
            stmt_res = self.falkordb.graph.query(
                """
                MATCH (e:Event)-[:INCLUDES_STATEMENT]->(st:Statement)
                WHERE e.event_id IN $eids
                RETURN e.event_id, st.statement_id, st.text, st.issued_at
                """,
                {"eids": event_ids_list},
            )
            for row in stmt_res.result_set:
                eid, sid, text, issued_at = row
                add_node(
                    nid=sid,
                    label="Official Statement",
                    group="statement",
                    title=f"Official Statement ({issued_at})<br>{text[:120]}...",
                    size=20,
                    full_text=text,
                    issued_at=issued_at,
                )
                add_edge(from_id=eid, to_id=sid, label="STATEMENT", color={"color": "#14b8a6"})

        # 8. Phase 3: Fetch reasoning edges (CAUSED, CONTRIBUTED_TO, AFFECTS)
        if event_ids_list:
            causal_res = self.falkordb.graph.query(
                """
                MATCH (e1:Event)-[r:CAUSED|CONTRIBUTED_TO]->(e2:Event)
                WHERE e1.event_id IN $eids AND e2.event_id IN $eids
                RETURN e1.event_id, e2.event_id, type(r), r.confidence, r.rationale, r.status, r.agent, r.evidence_ids
                """,
                {"eids": event_ids_list},
            )
            for row in causal_res.result_set:
                e1, e2, rtype, conf, rat, st, ag, ev_ids = row
                conf_val = float(conf) if conf is not None else 0.7
                is_caused = rtype == "CAUSED"
                add_edge(
                    from_id=e1,
                    to_id=e2,
                    label=rtype,
                    title=f"<b>{rtype}</b> ({st})<br>Confidence: {int(conf_val*100)}%<br>Agent: {ag or 'graph_agent_v1'}<br>{rat or ''}",
                    color={"color": "#ef4444" if is_caused else "#f59e0b", "highlight": "#dc2626" if is_caused else "#d97706"},
                    dashes=not is_caused,
                    width=3.5 if is_caused else 2.5,
                    edge_type=rtype,
                    status=st or "inferred",
                    confidence=conf_val,
                    rationale=rat or "",
                    agent=ag or "",
                    evidence_ids=ev_ids or [],
                )

            if include_entities:
                impact_res = self.falkordb.graph.query(
                    """
                    MATCH (e:Event)-[r:AFFECTS]->(ent:Entity)
                    WHERE e.event_id IN $eids
                    RETURN e.event_id, ent.canonical_name, r.confidence, r.rationale, r.status, r.agent, r.evidence_ids
                    LIMIT 50
                    """,
                    {"eids": event_ids_list},
                )
                for row in impact_res.result_set:
                    eid, cname, conf, rat, st, ag, ev_ids = row
                    conf_val = float(conf) if conf is not None else 0.7
                    add_edge(
                        from_id=eid,
                        to_id=cname,
                        label="AFFECTS",
                        title=f"<b>AFFECTS</b> ({st})<br>Confidence: {int(conf_val*100)}%<br>{rat or ''}",
                        color={"color": "#a855f7", "highlight": "#9333ea"},
                        width=2.5,
                        edge_type="AFFECTS",
                        status=st or "inferred",
                        confidence=conf_val,
                        rationale=rat or "",
                        agent=ag or "",
                        evidence_ids=ev_ids or [],
                    )

        return {
            "story": story_info,
            "events": story_events,
            "nodes": nodes,
            "edges": edges,
        }

    def get_event_detail(self, event_id: str) -> Dict[str, Any]:
        """Retrieves detailed event payload with all articles, Phase 2 entities, and connections."""
        e_res = self.falkordb.graph.query(
            """
            MATCH (e:Event {event_id: $id})
            OPTIONAL MATCH (e)-[:PART_OF]->(st:Story)
            RETURN e.event_id, e.title, e.summary, e.category, e.occurred_at,
                   e.first_seen, e.last_seen, st.story_id, st.title
            """,
            {"id": event_id},
        )
        if not e_res.result_set:
            return {"error": "Event not found"}

        row = e_res.result_set[0]
        event_dict = {
            "event_id": row[0],
            "title": row[1] or "",
            "summary": row[2] or "",
            "category": row[3] or "General",
            "occurred_at": row[4] or "",
            "first_seen": row[5] or "",
            "last_seen": row[6] or "",
            "story_id": row[7],
            "story_title": row[8],
        }

        # Articles reporting on event
        art_res = self.falkordb.graph.query(
            """
            MATCH (a:Article)-[r:REPORTS_ON]->(e:Event {event_id: $id})
            OPTIONAL MATCH (a)-[:PUBLISHED_BY]->(s:Source)
            RETURN a.url, a.title, a.description, a.published_at, a.author,
                   r.similarity, s.name, a.url_to_image
            ORDER BY r.similarity DESC
            """,
            {"id": event_id},
        )
        articles = []
        for a_row in art_res.result_set:
            articles.append({
                "url": a_row[0],
                "title": a_row[1] or "",
                "description": a_row[2] or "",
                "published_at": a_row[3] or "",
                "author": a_row[4] or "",
                "similarity": float(a_row[5]) if a_row[5] is not None else 1.0,
                "source_name": a_row[6] or "Unknown",
                "url_to_image": a_row[7] or "",
            })
        event_dict["articles"] = articles

        # Phase 2: Involved Entities
        ent_res = self.falkordb.graph.query(
            """
            MATCH (e:Event {event_id: $id})-[r:INVOLVES]->(ent:Entity)
            RETURN ent.canonical_name, labels(ent), r.role, ent.aliases
            """,
            {"id": event_id},
        )
        entities = []
        for erow in ent_res.result_set:
            types = [l for l in erow[1] if l != "Entity"]
            entities.append({
                "canonical_name": erow[0],
                "type": types[0] if types else "Entity",
                "role": erow[2] or "actor",
                "aliases": erow[3] or [],
            })
        event_dict["entities"] = entities

        # Phase 2: Related Events (rule-based)
        rel_res = self.falkordb.graph.query(
            """
            MATCH (e:Event {event_id: $id})-[r:RELATED_TO]-(peer:Event)
            RETURN peer.event_id, peer.title, peer.occurred_at, r.confidence, r.rationale
            LIMIT 10
            """,
            {"id": event_id},
        )
        related_events = []
        for rrow in rel_res.result_set:
            related_events.append({
                "event_id": rrow[0],
                "title": rrow[1] or "",
                "occurred_at": rrow[2] or "",
                "confidence": float(rrow[3]) if rrow[3] is not None else 0.5,
                "rationale": rrow[4] or "",
            })
        event_dict["related_events"] = related_events

        # Phase 2: Official Statements
        stmt_res = self.falkordb.graph.query(
            """
            MATCH (e:Event {event_id: $id})-[:INCLUDES_STATEMENT]->(st:Statement)
            OPTIONAL MATCH (st)-[:SOURCE_ARTICLE]->(a:Article)
            RETURN st.statement_id, st.text, st.issued_at, a.url, a.title
            """,
            {"id": event_id},
        )
        statements = []
        for srow in stmt_res.result_set:
            statements.append({
                "statement_id": srow[0],
                "text": srow[1] or "",
                "issued_at": srow[2] or "",
                "source_url": srow[3] or "",
                "article_title": srow[4] or "",
            })
        event_dict["statements"] = statements

        # Preceded and Followed links
        prev_res = self.falkordb.graph.query(
            """
            MATCH (prev:Event)-[p:PRECEDED]->(e:Event)
            WHERE e.event_id = $id
            RETURN prev.event_id, prev.title, prev.occurred_at, p.days_gap
            """,
            {"id": event_id},
        )
        next_res = self.falkordb.graph.query(
            """
            MATCH (e:Event)-[p:PRECEDED]->(nxt:Event)
            WHERE e.event_id = $id
            RETURN nxt.event_id, nxt.title, nxt.occurred_at, p.days_gap
            """,
            {"id": event_id},
        )
        event_dict["preceded_by"] = [
            {"event_id": r[0], "title": r[1], "occurred_at": r[2], "days_gap": r[3]}
            for r in prev_res.result_set
        ]
        event_dict["followed_by"] = [
            {"event_id": r[0], "title": r[1], "occurred_at": r[2], "days_gap": r[3]}
            for r in next_res.result_set
        ]

        # Phase 3: Causal and Reasoning links
        causal_links = {
            "causes": [],      # downstream: this event caused or contributed to other events
            "caused_by": [],   # upstream: other events caused or contributed to this event
            "affects": [],     # entities this event affects
            "impacted_by": [], # entities that impacted this event
        }
        try:
            down_res = self.falkordb.graph.query(
                """
                MATCH (e:Event)-[r:CAUSED|CONTRIBUTED_TO]->(tgt:Event)
                WHERE e.event_id = $id
                RETURN tgt.event_id, tgt.title, tgt.occurred_at, type(r), r.confidence, r.rationale, r.status, r.agent, r.evidence_ids
                """,
                {"id": event_id},
            )
            for row in down_res.result_set:
                causal_links["causes"].append({
                    "target_id": row[0],
                    "title": row[1] or "",
                    "occurred_at": row[2] or "",
                    "edge_type": row[3],
                    "confidence": float(row[4]) if row[4] is not None else 0.7,
                    "rationale": row[5] or "",
                    "status": row[6] or "inferred",
                    "agent": row[7] or "graph_agent_v1",
                    "evidence_ids": row[8] or [],
                })

            up_res = self.falkordb.graph.query(
                """
                MATCH (src:Event)-[r:CAUSED|CONTRIBUTED_TO]->(e:Event)
                WHERE e.event_id = $id
                RETURN src.event_id, src.title, src.occurred_at, type(r), r.confidence, r.rationale, r.status, r.agent, r.evidence_ids
                """,
                {"id": event_id},
            )
            for row in up_res.result_set:
                causal_links["caused_by"].append({
                    "source_id": row[0],
                    "title": row[1] or "",
                    "occurred_at": row[2] or "",
                    "edge_type": row[3],
                    "confidence": float(row[4]) if row[4] is not None else 0.7,
                    "rationale": row[5] or "",
                    "status": row[6] or "inferred",
                    "agent": row[7] or "graph_agent_v1",
                    "evidence_ids": row[8] or [],
                })

            aff_res = self.falkordb.graph.query(
                """
                MATCH (e:Event)-[r:AFFECTS]->(ent:Entity)
                WHERE e.event_id = $id
                RETURN ent.canonical_name, labels(ent), r.confidence, r.rationale, r.status, r.agent, r.evidence_ids
                """,
                {"id": event_id},
            )
            for row in aff_res.result_set:
                lbls = [l for l in (row[1] or []) if l != "Entity"]
                causal_links["affects"].append({
                    "canonical_name": row[0],
                    "type": lbls[0] if lbls else "Entity",
                    "confidence": float(row[2]) if row[2] is not None else 0.7,
                    "rationale": row[3] or "",
                    "status": row[4] or "inferred",
                    "agent": row[5] or "graph_agent_v1",
                    "evidence_ids": row[6] or [],
                })

            imp_res = self.falkordb.graph.query(
                """
                MATCH (ent:Entity)-[r:IMPACTED]->(e:Event)
                WHERE e.event_id = $id
                RETURN ent.canonical_name, labels(ent), r.confidence, r.rationale, r.status, r.agent, r.evidence_ids
                """,
                {"id": event_id},
            )
            for row in imp_res.result_set:
                lbls = [l for l in (row[1] or []) if l != "Entity"]
                causal_links["impacted_by"].append({
                    "canonical_name": row[0],
                    "type": lbls[0] if lbls else "Entity",
                    "confidence": float(row[2]) if row[2] is not None else 0.7,
                    "rationale": row[3] or "",
                    "status": row[4] or "inferred",
                    "agent": row[5] or "graph_agent_v1",
                    "evidence_ids": row[6] or [],
                })
        except Exception as e:
            logger.error(f"Error fetching causal links for {event_id}: {e}")

        event_dict["causal_links"] = causal_links

        return event_dict

    def get_entities(
        self,
        entity_type: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Returns paginated list of Phase 2 entities with event mention counts."""
        target_label = entity_type if entity_type and entity_type.capitalize() in {
            "Country", "Company", "Person", "Organization", "Industry", "Commodity", "Location"
        } else "Entity"

        search_filter = ""
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if search and search.strip():
            params["search_term"] = f"(?i).*{search.strip()}.*"
            search_filter = "AND ent.canonical_name =~ $search_term"

        query = f"""
            MATCH (e:Event)-[:INVOLVES]->(ent:{target_label})
            WHERE 1=1 {search_filter}
            WITH ent, count(DISTINCT e) AS event_count
            RETURN ent.canonical_name AS name,
                   labels(ent) AS labels,
                   event_count,
                   ent.aliases AS aliases
            ORDER BY event_count DESC, name ASC
            SKIP $skip LIMIT $limit
        """
        res = self.falkordb.graph.query(query, params)
        entities = []
        for row in res.result_set:
            lbls = row[1] or []
            types = [l for l in lbls if l != "Entity"]
            entities.append({
                "canonical_name": row[0],
                "type": types[0] if types else "Entity",
                "event_count": row[2],
                "aliases": row[3] or [],
            })

        # Count total
        count_res = self.falkordb.graph.query(f"MATCH (ent:{target_label}) RETURN count(ent)")
        total = count_res.result_set[0][0] if count_res.result_set else len(entities)

        return {
            "entities": entities,
            "total": total,
            "skip": skip,
            "limit": limit,
            "entity_type": entity_type or "All",
        }

    def get_entity_graph(self, canonical_name: str, max_events: int = 12) -> Dict[str, Any]:
        """Builds an ego-network force-directed graph around a single Entity."""
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        node_ids = set()

        def add_node(nid: str, label: str, group: str, title: str, size: int = 20, **kwargs):
            if nid not in node_ids:
                node_ids.add(nid)
                nodes.append({
                    "id": nid,
                    "label": label,
                    "group": group,
                    "title": title,
                    "size": size,
                    **kwargs,
                })

        def add_edge(from_id: str, to_id: str, label: str, title: str = "", dashes: bool = False, **kwargs):
            edges.append({
                "from": from_id,
                "to": to_id,
                "label": label,
                "title": title,
                "dashes": dashes,
                "arrows": "to",
                **kwargs,
            })

        # 1. Fetch Entity details
        ent_res = self.falkordb.graph.query(
            "MATCH (ent:Entity {canonical_name: $name}) RETURN labels(ent), ent.aliases",
            {"name": canonical_name},
        )
        if not ent_res.result_set:
            return {"error": f"Entity '{canonical_name}' not found"}

        lbls = ent_res.result_set[0][0] or []
        aliases = ent_res.result_set[0][1] or []
        types = [l for l in lbls if l != "Entity"]
        etype = types[0] if types else "Entity"

        add_node(
            nid=canonical_name,
            label=canonical_name,
            group=etype.lower(),
            title=f"Entity ({etype}): {canonical_name}",
            size=36,
            canonical_name=canonical_name,
            entity_type=etype,
            aliases=aliases,
        )

        # 2. Fetch Events connected to this entity
        events_res = self.falkordb.graph.query(
            """
            MATCH (e:Event)-[r:INVOLVES]->(ent:Entity {canonical_name: $name})
            RETURN e.event_id, e.title, e.summary, e.occurred_at, e.category, r.role
            ORDER BY e.occurred_at DESC
            LIMIT $limit
            """,
            {"name": canonical_name, "limit": max_events},
        )
        for row in events_res.result_set:
            eid, etitle, summary, occurred_at, cat, role = row
            add_node(
                nid=eid,
                label=f"[{occurred_at[-5:]}] " + ((etitle[:30] + "...") if len(etitle or "") > 30 else etitle),
                group="event",
                title=f"Event ({occurred_at}): {etitle}<br>{summary[:120]}...",
                size=24,
                full_title=etitle,
                summary=summary,
                occurred_at=occurred_at,
                category=cat,
            )
            add_edge(
                from_id=eid,
                to_id=canonical_name,
                label=f"INVOLVES ({role})",
                title=f"Role: {role}",
                color={"color": "#38bdf8"},
                dashes=True,
            )

        return {
            "entity": {"canonical_name": canonical_name, "type": etype, "aliases": aliases},
            "nodes": nodes,
            "edges": edges,
        }

