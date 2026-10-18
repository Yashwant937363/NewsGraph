import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import init_db, close_db
from app.models.documents.phase3_ledger import Phase3LedgerDocument
from app.services.falkordb_client import FalkorDBClient
from app.services.phase3_tools import Phase3Tools


@pytest.fixture
def falkordb_client():
    client = FalkorDBClient()
    client.init_schema()
    return client


@pytest.fixture
def tools_engine(falkordb_client):
    return Phase3Tools(falkordb_client=falkordb_client)


@pytest.mark.asyncio
async def test_phase3_ledger_document():
    await init_db()
    try:
        eid = "test_phase3_evt_999"
        existing = await Phase3LedgerDocument.find_one(Phase3LedgerDocument.event_id == eid)
        if existing:
            await existing.delete()

        doc = Phase3LedgerDocument(event_id=eid, status="PROCESSING")
        await doc.insert()

        fetched = await Phase3LedgerDocument.find_one(Phase3LedgerDocument.event_id == eid)
        assert fetched is not None
        assert fetched.status == "PROCESSING"

        fetched.status = "COMPLETED"
        fetched.caused_edges = 2
        fetched.affects_edges = 1
        fetched.edges_written = 3
        await fetched.save()

        updated = await Phase3LedgerDocument.find_one(Phase3LedgerDocument.event_id == eid)
        assert updated.status == "COMPLETED"
        assert updated.edges_written == 3
        assert updated.caused_edges == 2

        await updated.delete()
    finally:
        await close_db()


@pytest.mark.asyncio
async def test_write_edge_guardrails_edge_types(tools_engine):
    # Invalid edge type
    res = await tools_engine.write_edge(
        source_id="evt_2026-09-08_0",
        target_id="evt_2026-09-08_1",
        edge_type="NON_EXISTENT_EDGE",
        confidence=0.8,
    )
    assert res.get("rejected") is True
    assert "Invalid edge_type" in res.get("reason", "")


@pytest.mark.asyncio
async def test_write_edge_guardrails_self_loop(tools_engine):
    # Self loop
    res = await tools_engine.write_edge(
        source_id="evt_2026-09-08_0",
        target_id="evt_2026-09-08_0",
        edge_type="CAUSED",
        confidence=0.8,
    )
    assert res.get("rejected") is True
    assert "Self-loops are not allowed" in res.get("reason", "")


@pytest.mark.asyncio
async def test_write_edge_guardrails_confidence_floor(tools_engine):
    # Confidence below 0.55 floor
    res = await tools_engine.write_edge(
        source_id="evt_2026-09-08_0",
        target_id="evt_2026-09-08_1",
        edge_type="CAUSED",
        confidence=0.50,
    )
    assert res.get("rejected") is True
    assert "Confidence" in res.get("reason", "")
    assert "outside valid bounds" in res.get("reason", "")


@pytest.mark.asyncio
async def test_write_edge_guardrails_nonexistent_node(tools_engine):
    # Non-existent node
    res = await tools_engine.write_edge(
        source_id="fake_ghost_event_9999",
        target_id="evt_2026-09-08_1",
        edge_type="CAUSED",
        confidence=0.8,
    )
    assert res.get("rejected") is True
    assert "does not exist in FalkorDB" in res.get("reason", "")


@pytest.mark.asyncio
async def test_write_edge_label_compatibility(tools_engine, falkordb_client):
    # Setup test nodes
    test_e1 = "test_guard_evt_1"
    test_ent = "TestGuardCompany"

    falkordb_client.graph.query(
        "MERGE (e:Event {event_id: $id})",
        {"id": test_e1},
    )
    falkordb_client.write_entity(test_ent, "Company", ["TGC"])

    try:
        # 1. CAUSED requires Event -> Event, not Event -> Entity
        res_compat1 = await tools_engine.write_edge(
            source_id=test_e1,
            target_id=test_ent,
            edge_type="CAUSED",
            confidence=0.8,
            evidence_ids=["https://example.com/art1"],
        )
        assert res_compat1.get("rejected") is True
        assert "target to be an Event" in res_compat1.get("reason", "")

        # 2. AFFECTS requires Event -> Entity, not Event -> Event
        res_compat2 = await tools_engine.write_edge(
            source_id=test_e1,
            target_id=test_e1,  # also self-loop, test with another event
            edge_type="AFFECTS",
            confidence=0.8,
        )
        assert res_compat2.get("rejected") is True

        # 3. Valid AFFECTS (Event -> Entity)
        res_valid = await tools_engine.write_edge(
            source_id=test_e1,
            target_id=test_ent,
            edge_type="AFFECTS",
            confidence=0.75,
            evidence_ids=["https://example.com/art1"],
            rationale="Test impact on company",
        )
        assert res_valid.get("success") is True
        assert res_valid.get("edge_type") == "AFFECTS"

    finally:
        falkordb_client.graph.query(
            "MATCH (e:Event {event_id: $id}) DETACH DELETE e",
            {"id": test_e1},
        )
        falkordb_client.graph.query(
            "MATCH (ent:Entity {canonical_name: $name}) DETACH DELETE ent",
            {"name": test_ent},
        )


@pytest.mark.asyncio
async def test_write_edge_evidence_downgrade(tools_engine, falkordb_client):
    test_e1 = "test_ev_down_1"
    test_e2 = "test_ev_down_2"

    falkordb_client.graph.query(
        "MERGE (e1:Event {event_id: $id1}) MERGE (e2:Event {event_id: $id2})",
        {"id1": test_e1, "id2": test_e2},
    )

    try:
        # CAUSED without evidence_ids should downgrade to RELATED_TO
        res = await tools_engine.write_edge(
            source_id=test_e1,
            target_id=test_e2,
            edge_type="CAUSED",
            confidence=0.8,
            evidence_ids=[],  # No evidence!
        )
        assert res.get("success") is True
        assert res.get("edge_type") == "RELATED_TO"
        assert res.get("downgraded") is True
        assert res.get("status") == "related"

    finally:
        falkordb_client.graph.query(
            "MATCH (e:Event) WHERE e.event_id IN [$id1, $id2] DETACH DELETE e",
            {"id1": test_e1, "id2": test_e2},
        )


def test_editor_curation_protection(falkordb_client):
    test_e1 = "test_ev_cur_1"
    test_e2 = "test_ev_cur_2"

    falkordb_client.graph.query(
        "MERGE (e1:Event {event_id: $id1}) MERGE (e2:Event {event_id: $id2})",
        {"id1": test_e1, "id2": test_e2},
    )

    try:
        # 1. Editor curates edge
        falkordb_client.write_reasoning_edge(
            source_id=test_e1,
            target_id=test_e2,
            edge_type="CAUSED",
            status="confirmed",
            confidence=0.99,
            evidence_ids=["https://editor-evidence.com"],
            rationale="Verified by Senior News Editor",
            agent="editor",
        )

        # 2. Later AI agent tries to overwrite with lower confidence and different status
        falkordb_client.write_reasoning_edge(
            source_id=test_e1,
            target_id=test_e2,
            edge_type="CAUSED",
            status="inferred",
            confidence=0.60,
            evidence_ids=["https://ai-evidence.com"],
            rationale="AI inferred overwrite attempt",
            agent="graph_agent_v1",
        )

        # 3. Verify editor values preserved
        r = falkordb_client.graph.query(
            """
            MATCH (s:Event {event_id: $id1})-[r:CAUSED]->(t:Event {event_id: $id2})
            RETURN r.status, r.confidence, r.rationale, r.agent
            """,
            {"id1": test_e1, "id2": test_e2},
        )
        assert len(r.result_set) == 1
        row = r.result_set[0]
        assert row[0] == "confirmed"
        assert float(row[1]) == 0.99
        assert row[2] == "Verified by Senior News Editor"
        assert row[3] == "editor"

    finally:
        falkordb_client.graph.query(
            "MATCH (e:Event) WHERE e.event_id IN [$id1, $id2] DETACH DELETE e",
            {"id1": test_e1, "id2": test_e2},
        )


def test_phase3_api_endpoints():
    client = TestClient(app)

    # 1. Stats endpoint
    resp = client.get("/api/v1/phase3/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_events_in_graph" in data
    assert "reasoning_stats" in data

    # 2. Investigate endpoint (UC-01)
    resp_inv = client.get("/api/v1/phase3/investigate/evt_2026-09-08_0?hops=1")
    assert resp_inv.status_code == 200
    data_inv = resp_inv.json()
    assert "center_event_id" in data_inv
    assert "nodes" in data_inv

    # 3. Impact radius endpoint (UC-02)
    resp_imp = client.get("/api/v1/phase3/impact/evt_2026-09-08_0?hops=2")
    assert resp_imp.status_code == 200
    data_imp = resp_imp.json()
    assert "event_id" in data_imp
    assert "grouped_impacts" in data_imp

    # 4. Connect the dots endpoint (UC-03)
    resp_conn = client.get(
        "/api/v1/phase3/connect?source_event_id=evt_2026-09-08_0&target_event_id=evt_2026-09-08_1"
    )
    assert resp_conn.status_code == 200
    assert "found" in resp_conn.json()

    # 5. Connect the dots self-connection should reject
    resp_bad = client.get(
        "/api/v1/phase3/connect?source_event_id=evt_2026-09-08_0&target_event_id=evt_2026-09-08_0"
    )
    assert resp_bad.status_code == 400
