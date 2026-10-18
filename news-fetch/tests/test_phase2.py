import pytest
from app.models.schemas.entity import ExtractedEntity, EntityMention
from app.services.entity_normalizer import EntityNormalizer
from app.services.groq_client import GroqClient
from app.services.falkordb_client import FalkorDBClient
from app.core.db import init_db, close_db


def test_entity_schema_validation():
    entity = ExtractedEntity(
        name="United States",
        type="Country",
        role="actor",
        salience=0.95,
        aliases=["US", "USA"],
    )
    assert entity.name == "United States"
    assert entity.type == "Country"
    assert entity.role == "actor"
    assert entity.salience == 0.95
    assert len(entity.aliases) == 2


@pytest.mark.asyncio
async def test_entity_normalizer():
    await init_db()
    try:
        normalizer = EntityNormalizer()
        
        canon, etype, aliases = await normalizer.normalize("US", "Country", ["USA", "America"])
        assert canon == "United States"
        assert etype == "Country"
        assert "US" in aliases or "us" in [a.lower() for a in aliases]

        canon_p, etype_p, _ = await normalizer.normalize("Biden", "Person")
        assert canon_p == "Joe Biden"
        assert etype_p == "Person"

        canon_c, etype_c, _ = await normalizer.normalize("oil", "Commodity")
        assert canon_c == "Crude Oil"
        assert etype_c == "Commodity"
    finally:
        await close_db()


def test_groq_client_rotation():
    client = GroqClient(keys=["test_key_1", "test_key_2", "test_key_3"])
    assert client.total_keys == 3
    assert client.get_current_key() == "test_key_1"
    
    rotated = client.rotate_key(reason="test rotation")
    assert rotated == "test_key_2"
    assert client.get_current_key() == "test_key_2"


def test_groq_client_detailed_rate_limit_formatting():
    import httpx

    client = GroqClient(keys=["gsk_1234567890abcdef1234567890"])
    
    # Mock a 429 response from Groq hitting TPM limit
    tpm_body = {
        "error": {
            "message": "Rate limit reached for model `openai/gpt-oss-120b` in organization `org_xyz` on tokens per minute (TPM): Limit 8000, Used 7500, Requested 600. Please try again in 1.5s.",
            "type": "tokens",
            "code": "rate_limit_exceeded"
        }
    }
    headers = {
        "x-ratelimit-limit-tokens": "8000",
        "x-ratelimit-remaining-tokens": "500",
        "x-ratelimit-reset-tokens": "1.5s",
        "x-ratelimit-limit-requests": "30",
        "x-ratelimit-remaining-requests": "25",
        "x-ratelimit-reset-requests": "2s",
        "retry-after": "1.5",
    }
    resp = httpx.Response(status_code=429, json=tpm_body, headers=headers)
    
    output = client._log_and_print_rate_limit(resp, "gsk_1234567890abcdef1234567890", 429)
    assert "TPM (Tokens Per Minute)" in output
    assert "openai/gpt-oss-120b" in output
    assert "8000" in output
    assert "gsk_1234...7890" in output
    assert "Retry After   : 1.5s" in output


def test_groq_client_lru_key_distribution():
    client = GroqClient(keys=["key_A", "key_B", "key_C"])
    # Initially all keys unused, first optimal key is key_A
    k1 = client.get_optimal_key()
    client.mark_key_used(k1)
    assert k1 == "key_A"

    # Next least recently used is key_B
    k2 = client.get_optimal_key()
    client.mark_key_used(k2)
    assert k2 == "key_B"

    # Next is key_C
    k3 = client.get_optimal_key()
    client.mark_key_used(k3)
    assert k3 == "key_C"

    # Now all have been used once; key_A was used earliest, so next is key_A
    k4 = client.get_optimal_key()
    client.mark_key_used(k4)
    assert k4 == "key_A"


def test_groq_client_fallback_model_switch():
    client = GroqClient(keys=["test_key_1"])
    assert client.active_model == "openai/gpt-oss-120b"
    assert client.fallback_model == "openai/gpt-oss-20b"

    # Switch to fallback model
    new_model = client.switch_to_fallback_model(reason="TPM limit reached")
    assert new_model == "openai/gpt-oss-20b"
    assert client.active_model == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_groq_client_rate_pacing():
    client = GroqClient(keys=["test_key_1"])
    client.requests_per_minute = 600  # 10 req/sec to run fast in tests (0.1s interval)
    import time

    start = time.time()
    await client._pace_request()
    await client._pace_request()
    elapsed = time.time() - start
    assert elapsed >= 0.08  # Ensure pacing delay occurred


def test_falkordb_phase2_writes_and_rules():
    client = FalkorDBClient()
    client.init_schema()

    test_e1 = "test_evt_alpha_999"
    test_e2 = "test_evt_beta_999"
    test_c1 = "TestCountryAlpha"
    test_c2 = "TestCountryBeta"

    try:
        # 1. Create two test events
        client.graph.query(
            "MERGE (e1:Event {event_id: $id1}) MERGE (e2:Event {event_id: $id2})",
            {"id1": test_e1, "id2": test_e2},
        )

        # 2. Write two test Country entities
        client.write_entity(canonical_name=test_c1, entity_type="Country", aliases=["TCA"])
        client.write_entity(canonical_name=test_c2, entity_type="Country", aliases=["TCB"])

        # 3. Link both events to both countries
        client.link_event_involves(test_e1, test_c1, role="actor")
        client.link_event_involves(test_e1, test_c2, role="location")
        client.link_event_involves(test_e2, test_c1, role="actor")
        client.link_event_involves(test_e2, test_c2, role="actor")

        # 4. Run rule-based country RELATED_TO linking
        edges_created = client.create_country_related_edges()
        assert edges_created >= 1

        # 5. Verify the RELATED_TO edge has trust contract properties
        res = client.graph.query(
            """
            MATCH (e1:Event {event_id: $id1})-[r:RELATED_TO]->(e2:Event {event_id: $id2})
            RETURN r.status, r.confidence, r.agent
            """,
            {"id1": test_e1, "id2": test_e2},
        )
        assert len(res.result_set) == 1
        row = res.result_set[0]
        assert row[0] == "related"
        assert float(row[1]) == 0.5
        assert row[2] == "rule_engine_v1"

    finally:
        # Cleanup test graph nodes
        client.graph.query(
            """
            MATCH (e:Event) WHERE e.event_id IN [$id1, $id2] DETACH DELETE e
            """,
            {"id1": test_e1, "id2": test_e2},
        )
        client.graph.query(
            """
            MATCH (c:Country) WHERE c.canonical_name IN [$c1, $c2] DETACH DELETE c
            """,
            {"c1": test_c1, "c2": test_c2},
        )
