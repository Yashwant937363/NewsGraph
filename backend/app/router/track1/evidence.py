from urllib.parse import urlparse
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException

from app.config.falkordb_client import get_falkordb_graph
from app.router.track1.common import _clean_props

router = APIRouter(prefix="/evidence", tags=["evidence"])


def _publisher_from_url(u: str) -> str:
    """Fallback publisher resolution from domain."""
    if not u:
        return "Unknown Outlet"
    netloc = urlparse(u).netloc.lower().replace("www.", "")
    domain_map = {
        "reuters.com": "Reuters",
        "bloomberg.com": "Bloomberg",
        "aljazeera.com": "Al Jazeera",
        "foxsports.com": "Fox Sports",
        "sports.yahoo.com": "Yahoo Sports",
        "yahoo.com": "Yahoo",
        "nature.com": "Nature",
        "profootballnetwork.com": "Pro Football Network",
        "ft.com": "Financial Times",
        "rferl.org": "Radio Free Europe",
    }
    if netloc in domain_map:
        return domain_map[netloc]
    parts = netloc.split(".")
    return parts[0].capitalize() if parts else "News Outlet"


@router.get("/edge")
async def get_edge_evidence(
    source_id: str,
    target_id: str,
    edge_type: str,
):
    """
    UC-04: View Edge Evidence Trail.
    Retrieves persisted edge trust metadata, resolves evidence_ids to Article and Source
    nodes with reliability scores, and pulls supporting chunk quotes.
    Zero LLM latency (< 5ms).
    """
    graph = get_falkordb_graph()
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB graph is not initialized.",
        )

    # 1. Query the edge and connected nodes
    edge_query = """
    MATCH (s)-[r]->(t)
    WHERE ((s.event_id = $src OR s.canonical_name = $src OR s.url = $src)
           AND (t.event_id = $tgt OR t.canonical_name = $tgt OR t.url = $tgt)
           AND type(r) = $edge_type)
       OR ((s.event_id = $tgt OR s.canonical_name = $tgt OR s.url = $tgt)
           AND (t.event_id = $src OR t.canonical_name = $src OR t.url = $src)
           AND type(r) = $edge_type)
    RETURN
        properties(r) AS rel_props,
        labels(s) AS s_labels,
        properties(s) AS s_props,
        labels(t) AS t_labels,
        properties(t) AS t_props,
        type(r) AS rel_type,
        coalesce(s.event_id, s.canonical_name, s.url) AS actual_src,
        coalesce(t.event_id, t.canonical_name, t.url) AS actual_tgt
    LIMIT 1
    """
    res = graph.query(edge_query, {"src": source_id, "tgt": target_id, "edge_type": edge_type})
    if not res.result_set:
        raise HTTPException(
            status_code=404,
            detail=f"No edge of type '{edge_type}' found between '{source_id}' and '{target_id}'.",
        )

    (
        rel_props,
        s_labels,
        s_props,
        t_labels,
        t_props,
        actual_type,
        actual_src,
        actual_tgt,
    ) = res.result_set[0]

    clean_edge_props = _clean_props(rel_props)
    evidence_ids: List[str] = clean_edge_props.get("evidence_ids") or []

    # If edge had no explicit evidence_ids, fall back to articles reporting on source/target events
    if not evidence_ids:
        backup_q = """
        MATCH (a:Article)-[:REPORTS_ON]->(e:Event)
        WHERE e.event_id IN [$src, $tgt]
        RETURN DISTINCT a.url
        LIMIT 5
        """
        b_res = graph.query(backup_q, {"src": source_id, "tgt": target_id})
        evidence_ids = [row[0] for row in b_res.result_set if row[0]]

    # 2. Retrieve articles, sources, and supporting chunks
    sources_data = []
    reliabilities = []

    if evidence_ids:
        # Fetch articles
        art_q = """
        MATCH (a:Article)
        WHERE a.url IN $urls
        RETURN a.url, a.title, a.published_at, a.description
        """
        art_res = graph.query(art_q, {"urls": evidence_ids})
        art_map: Dict[str, Dict[str, Any]] = {
            row[0]: {
                "url": row[0],
                "title": row[1] or "Reporting Article",
                "published_at": row[2],
                "description": row[3] or "",
            }
            for row in art_res.result_set
        }

        # Fetch publisher / source info
        src_q = """
        MATCH (a:Article)-[:PUBLISHED_BY]->(src:Source)
        WHERE a.url IN $urls
        RETURN a.url, src.name, src.reliability
        """
        src_res = graph.query(src_q, {"urls": evidence_ids})
        src_map: Dict[str, Dict[str, Any]] = {
            row[0]: {
                "publisher": row[1] or _publisher_from_url(row[0]),
                "reliability": float(row[2]) if row[2] is not None else 1.0,
            }
            for row in src_res.result_set
        }

        # Fetch supporting chunks
        chunk_q = """
        MATCH (a:Article)-[:HAS_CHUNK]->(c:Chunk)
        WHERE a.url IN $urls
        RETURN a.url, c.chunk_id, c.chunk_index, c.text
        ORDER BY c.chunk_index ASC
        """
        chunk_res = graph.query(chunk_q, {"urls": evidence_ids})
        chunks_map: Dict[str, List[Dict[str, Any]]] = {}
        for row in chunk_res.result_set:
            u, cid, cidx, ctxt = row
            if u not in chunks_map:
                chunks_map[u] = []
            if len(chunks_map[u]) < 3:  # Keep top chunks
                chunks_map[u].append({
                    "chunk_id": cid,
                    "chunk_index": cidx,
                    "text": ctxt or "",
                })

        for u in evidence_ids:
            if u in art_map:
                art_info = art_map[u]
                publisher_info = src_map.get(u, {
                    "publisher": _publisher_from_url(u),
                    "reliability": 1.0,
                })
                sup_chunks = chunks_map.get(u, [])
                if not sup_chunks and art_info.get("description"):
                    sup_chunks = [{
                        "chunk_id": f"{u}#desc",
                        "chunk_index": 0,
                        "text": art_info["description"],
                    }]

                rel_val = publisher_info["reliability"]
                reliabilities.append(rel_val)

                sources_data.append({
                    "url": u,
                    "title": art_info["title"],
                    "publisher": publisher_info["publisher"],
                    "reliability": rel_val,
                    "published_at": art_info["published_at"],
                    "supporting_chunks": sup_chunks,
                })

    # 3. Deterministic Contradictions & Anomalies Detection
    contradictions = []
    anomalies = []

    # Check for rejected status
    if clean_edge_props.get("status") == "rejected":
        contradictions.append({
            "type": "rejected_connection",
            "description": f"Connection of type '{edge_type}' was marked rejected during curation.",
        })

    # Check for opposing edge conflicts
    opposing_q = """
    MATCH (t)-[r]->(s)
    WHERE (s.event_id = $src OR s.canonical_name = $src)
      AND (t.event_id = $tgt OR t.canonical_name = $tgt)
      AND type(r) <> $edge_type
    RETURN type(r), properties(r).status
    LIMIT 3
    """
    opp_res = graph.query(opposing_q, {"src": source_id, "tgt": target_id, "edge_type": edge_type})
    for o_row in opp_res.result_set:
        if o_row[1] == "rejected":
            contradictions.append({
                "type": "conflicting_edge",
                "description": f"Opposing edge '{o_row[0]}' is marked rejected between these nodes.",
            })

    # Temporal Precedence Anomaly
    s_clean = _clean_props(s_props)
    t_clean = _clean_props(t_props)
    s_time = s_clean.get("occurred_at")
    t_time = t_clean.get("occurred_at")
    if s_time and t_time and edge_type in ("CAUSED", "CONTRIBUTED_TO", "PRECEDED"):
        if str(t_time) < str(s_time):
            anomalies.append({
                "type": "temporal_precedence_anomaly",
                "description": f"Target occurred at '{t_time}' which is chronologically earlier than source at '{s_time}'.",
            })

    # Low-Trust Outlier Warning
    if reliabilities and (sum(reliabilities) / len(reliabilities)) < 0.70:
        anomalies.append({
            "type": "low_trust_warning",
            "description": "Average publisher reliability of supporting sources is below 0.70.",
        })

    return {
        "edge": {
            "source_id": str(actual_src),
            "target_id": str(actual_tgt),
            "edge_type": actual_type,
            "status": clean_edge_props.get("status", "confirmed"),
            "confidence": float(clean_edge_props.get("confidence", 0.9)),
            "rationale": clean_edge_props.get("rationale", ""),
            "agent": clean_edge_props.get("agent", "graph_agent_v1"),
            "created_at": clean_edge_props.get("created_at"),
            "valid_from": clean_edge_props.get("valid_from"),
            "valid_to": clean_edge_props.get("valid_to"),
        },
        "sources": sources_data,
        "contradictions": contradictions,
        "anomalies": anomalies,
    }


@router.get("/node")
@router.get("/node/{node_id:path}")
async def get_node_evidence(node_id: Optional[str] = None):
    """
    UC-04: View Node Evidence Trail.
    Retrieves node metadata, reporting/mentioning articles, publisher reliability badges,
    and excerpt text snippets. Supports Events, Entities, and Articles.
    Zero LLM latency (< 5ms).
    """
    if not node_id or node_id.strip() == "" or node_id == "None":
        raise HTTPException(
            status_code=400,
            detail="A valid node_id parameter is required.",
        )

    graph = get_falkordb_graph()
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="FalkorDB graph is not initialized.",
        )

    # 1. Match the node
    node_query = """
    MATCH (n)
    WHERE n.event_id = $id OR n.story_id = $id OR n.canonical_name = $id OR n.url = $id OR n.name = $id OR n.title = $id
    RETURN
        coalesce(n.event_id, n.story_id, n.canonical_name, n.url, n.name, toString(id(n))) AS id,
        labels(n) AS labels,
        coalesce(n.title, n.canonical_name, n.name, n.story_id, n.event_id) AS title,
        coalesce(n.occurred_at, n.published_at, n.first_seen) AS occurred_at,
        properties(n) AS props
    LIMIT 1
    """
    res = graph.query(node_query, {"id": node_id})
    if not res.result_set:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{node_id}' not found.",
        )

    matched_id, labels, title, occurred_at, props = res.result_set[0]
    clean_node_props = _clean_props(props)
    labels_list = list(labels or [])
    is_article = "Article" in labels_list
    is_story = "Story" in labels_list
    is_event = "Event" in labels_list

    # Handle Story nodes
    if is_story:
        evt_q = """
        MATCH (e:Event)-[:PART_OF]->(s:Story)
        WHERE s.story_id = $id OR s.title = $id
        RETURN e.event_id, e.title, e.occurred_at
        LIMIT 10
        """
        evt_res = graph.query(evt_q, {"id": matched_id})
        story_events = [row[0] for row in evt_res.result_set if row[0]]

        articles_data = []
        if story_events:
            art_q = """
            MATCH (a:Article)-[:REPORTS_ON]->(e:Event)
            WHERE e.event_id IN $evt_ids
            OPTIONAL MATCH (a)-[:PUBLISHED_BY]->(src:Source)
            RETURN DISTINCT a.url, a.title, a.published_at, src.name, src.reliability, a.description
            LIMIT 25
            """
            art_res = graph.query(art_q, {"evt_ids": story_events})
            for row in art_res.result_set:
                url, art_title, pub_at, s_name, s_rel, desc = row
                snippet = (desc or "")[:280] + "..." if desc and len(desc) > 280 else (desc or "")
                articles_data.append({
                    "url": url,
                    "title": art_title or "Story Article",
                    "publisher": s_name or _publisher_from_url(url),
                    "reliability": float(s_rel) if s_rel is not None else 1.0,
                    "published_at": pub_at,
                    "snippet": snippet,
                })

        return {
            "node_id": str(matched_id),
            "labels": labels_list,
            "title": title or clean_node_props.get("title") or str(matched_id),
            "occurred_at": clean_node_props.get("first_seen") or clean_node_props.get("last_seen") or occurred_at,
            "articles_count": len(articles_data),
            "articles": articles_data,
        }

    if is_article:
        # Match article's own publisher and reliability
        src_q = """
        MATCH (a:Article {url: $url})-[:PUBLISHED_BY]->(src:Source)
        RETURN src.name, src.reliability
        LIMIT 1
        """
        src_res = graph.query(src_q, {"url": matched_id})
        pub_name = (
            src_res.result_set[0][0]
            if src_res.result_set and src_res.result_set[0][0]
            else _publisher_from_url(str(matched_id))
        )
        pub_rel = (
            float(src_res.result_set[0][1])
            if src_res.result_set and src_res.result_set[0][1] is not None
            else 1.0
        )

        # Match text chunks for snippets
        chk_q = """
        MATCH (a:Article {url: $url})-[:HAS_CHUNK]->(c:Chunk)
        RETURN c.chunk_id, c.chunk_index, c.text
        ORDER BY c.chunk_index ASC
        LIMIT 5
        """
        chk_res = graph.query(chk_q, {"url": matched_id})
        chunks_text = [row[2] for row in chk_res.result_set if row[2]]
        primary_snippet = (
            chunks_text[0]
            if chunks_text
            else (clean_node_props.get("description") or "")
        )
        if len(primary_snippet) > 280:
            primary_snippet = primary_snippet[:280] + "..."

        # Fetch the event(s) this article reports on
        evt_q = """
        MATCH (a:Article {url: $url})-[:REPORTS_ON]->(e:Event)
        RETURN e.event_id, e.title, e.occurred_at
        LIMIT 5
        """
        evt_res = graph.query(evt_q, {"url": matched_id})
        related_events = [row[0] for row in evt_res.result_set if row[0]]

        articles_data = [{
            "url": str(matched_id),
            "title": title or clean_node_props.get("title") or "Reporting Article",
            "publisher": pub_name,
            "reliability": pub_rel,
            "published_at": clean_node_props.get("published_at"),
            "snippet": primary_snippet,
        }]

        # Fetch corroborating articles reporting on the same event
        if related_events:
            corrob_q = """
            MATCH (e:Event)<-[:REPORTS_ON]-(other:Article)
            WHERE e.event_id IN $evt_ids AND other.url <> $url
            OPTIONAL MATCH (other)-[:PUBLISHED_BY]->(osrc:Source)
            RETURN DISTINCT other.url, other.title, other.published_at, osrc.name, osrc.reliability, other.description
            LIMIT 20
            """
            c_res = graph.query(corrob_q, {"evt_ids": related_events, "url": matched_id})
            for c_row in c_res.result_set:
                c_url, c_title, c_pub_at, c_src_name, c_src_rel, c_desc = c_row
                c_snippet = (
                    (c_desc or "")[:280] + "..."
                    if c_desc and len(c_desc) > 280
                    else (c_desc or "")
                )
                articles_data.append({
                    "url": c_url,
                    "title": c_title or "Corroborating Article",
                    "publisher": c_src_name or _publisher_from_url(c_url),
                    "reliability": float(c_src_rel) if c_src_rel is not None else 1.0,
                    "published_at": c_pub_at,
                    "snippet": c_snippet,
                })

        return {
            "node_id": str(matched_id),
            "labels": labels_list,
            "title": title or str(matched_id),
            "occurred_at": clean_node_props.get("published_at") or occurred_at,
            "articles_count": len(articles_data),
            "articles": articles_data,
        }

    # 2. Match reporting/mentioning articles for Event or Entity
    if is_event:
        art_query = """
        MATCH (a:Article)-[:REPORTS_ON]->(e:Event)
        WHERE e.event_id = $id
        MATCH (a)-[:PUBLISHED_BY]->(src:Source)
        RETURN a.url, a.title, a.published_at, src.name, src.reliability, a.description
        LIMIT 25
        """
        count_query = """
        MATCH (a:Article)-[:REPORTS_ON]->(e:Event)
        WHERE e.event_id = $id
        RETURN count(a)
        """
    else:
        art_query = """
        MATCH (a:Article)-[:MENTIONS]->(ent:Entity)
        WHERE ent.canonical_name = $id OR ent.name = $id
        MATCH (a)-[:PUBLISHED_BY]->(src:Source)
        RETURN a.url, a.title, a.published_at, src.name, src.reliability, a.description
        LIMIT 25
        """
        count_query = """
        MATCH (a:Article)-[:MENTIONS]->(ent:Entity)
        WHERE ent.canonical_name = $id OR ent.name = $id
        RETURN count(a)
        """

    art_res = graph.query(art_query, {"id": node_id})
    cnt_res = graph.query(count_query, {"id": node_id})
    total_articles = cnt_res.result_set[0][0] if cnt_res.result_set else len(art_res.result_set)

    # 3. Collect sample chunks for snippets
    matched_urls = [row[0] for row in art_res.result_set if row[0]]
    chunks_map: Dict[str, str] = {}
    if matched_urls:
        chunk_q = """
        MATCH (a:Article)-[:HAS_CHUNK]->(c:Chunk)
        WHERE a.url IN $urls AND c.chunk_index = 0
        RETURN a.url, c.text
        """
        c_res = graph.query(chunk_q, {"urls": matched_urls})
        for row in c_res.result_set:
            chunks_map[row[0]] = row[1] or ""

    articles_data = []
    for row in art_res.result_set:
        url, art_title, published_at, src_name, src_rel, desc = row
        snippet = chunks_map.get(url) or desc or ""
        if len(snippet) > 280:
            snippet = snippet[:280] + "..."
        articles_data.append({
            "url": url,
            "title": art_title or "Reporting Article",
            "publisher": src_name or _publisher_from_url(url),
            "reliability": float(src_rel) if src_rel is not None else 1.0,
            "published_at": published_at,
            "snippet": snippet,
        })

    return {
        "node_id": str(matched_id),
        "labels": labels_list,
        "title": title or str(matched_id),
        "occurred_at": occurred_at or clean_node_props.get("occurred_at"),
        "articles_count": total_articles,
        "articles": articles_data,
    }
