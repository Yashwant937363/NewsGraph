import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from app.config import Settings, get_settings
from app.core.db import init_db
from app.models.documents.phase2_ledger import Phase2LedgerDocument
from app.models.schemas.entity import ExtractedEntity, VALID_ENTITY_TYPES, VALID_ROLES
from app.services.entity_normalizer import EntityNormalizer
from app.services.falkordb_client import FalkorDBClient
from app.services.groq_client import GroqClient

logger = logging.getLogger("news_pipeline.phase2")

# Official domains for rule-based Statement extraction
OFFICIAL_DOMAINS = (
    ".gov",
    "who.int",
    "un.org",
    "state.gov",
    "whitehouse.gov",
    "defense.gov",
    "kremlin.ru",
    "gov.uk",
    "europa.eu",
    "iaea.org",
    "imf.org",
)


class Phase2Pipeline:
    """
    Executes Phase 2 of WorldGraph: Enrichment (Entities, Typing, Evidence).
    - Top-5 articles per event -> Groq LLM extraction (Country, Company, Person, etc.)
    - Entity normalization & alias resolution (with MongoDB cache)
    - Multi-labeled :Entity nodes + :INVOLVES + :MENTIONS edges
    - Rule-based official :Statement nodes
    - Rule-based :RELATED_TO edges for events sharing >= 2 :Country entities
    - Event-by-event ledger tracking in Phase2LedgerDocument
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.falkordb = FalkorDBClient(self.settings)
        self.groq_client = GroqClient(self.settings)
        self.normalizer = EntityNormalizer()

    @staticmethod
    def is_official_source(url: str) -> bool:
        """Checks if URL domain matches recognized governmental/international bodies."""
        if not url:
            return False
        try:
            domain = urlparse(url).netloc.lower()
            return any(domain.endswith(od) or od in domain for od in OFFICIAL_DOMAINS)
        except Exception:
            return False

    async def enrich_event(
        self,
        event: Dict[str, Any],
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Enriches a single Event:
        Extracts entities via Groq, normalizes, writes nodes and mentions,
        checks for official statements, and updates ledger.
        """
        event_id = event["event_id"]
        await init_db(self.settings)

        # 1. Check Ledger
        ledger = await Phase2LedgerDocument.find_one(Phase2LedgerDocument.event_id == event_id)
        if ledger and ledger.status == "COMPLETED" and not force:
            logger.info(f"⏭️  Event {event_id} already COMPLETED in Phase 2 ledger. Skipping.")
            return {
                "event_id": event_id,
                "status": "SKIPPED",
                "entities_count": ledger.entities_count,
                "mentions_count": ledger.mentions_count,
            }

        if ledger is None:
            ledger = Phase2LedgerDocument(event_id=event_id, status="PROCESSING")
            await ledger.insert()
        else:
            ledger.status = "PROCESSING"
            ledger.updated_at = datetime.utcnow()
            await ledger.save()

        try:
            # 2. Get top-5 articles for event from FalkorDB
            top_articles = self.falkordb.get_event_top_articles(event_id, limit=5)
            if not top_articles:
                logger.warning(f"No articles found for event {event_id}.")
                ledger.status = "COMPLETED"
                ledger.completed_at = datetime.utcnow()
                await ledger.save()
                return {"event_id": event_id, "status": "COMPLETED", "entities_count": 0}

            # 3. Rule-based Official Statements extraction (.gov, who.int, etc.)
            statements_count = 0
            for art in top_articles:
                url = art.get("url") or ""
                if self.is_official_source(url):
                    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
                    stmt_id = f"stmt_{event_id}_{url_hash}"
                    text = f"{art.get('title', '')}: {art.get('description', '')}".strip()
                    issued_at = art.get("published_at") or datetime.utcnow().isoformat()
                    self.falkordb.write_statement(
                        statement_id=stmt_id,
                        event_id=event_id,
                        article_url=url,
                        text=text,
                        issued_at=issued_at,
                    )
                    statements_count += 1
                    logger.info(f"Created official :Statement node {stmt_id} from {url}")

            # 4. Prepare Context for LLM
            articles_text_blocks = []
            for i, art in enumerate(top_articles, 1):
                t = art.get("title") or ""
                d = art.get("description") or ""
                articles_text_blocks.append(f"[{i}] Title: {t}\nDescription: {d}")

            articles_combined = "\n\n".join(articles_text_blocks)
            event_title = event.get("title") or ""
            event_summary = event.get("summary") or ""

            prompt_user = (
                f"Event Title: {event_title}\n"
                f"Event Summary: {event_summary}\n\n"
                f"Articles Reporting on this Event:\n{articles_combined}\n\n"
                "Extract all salient entities involved in or mentioned by this event. "
                "Classify each entity strictly into one of the allowed types."
            )

            prompt_system = (
                "You are an expert news intelligence entity extractor.\n"
                "Extract real-world entities mentioned in the provided news event.\n\n"
                "Allowed Types:\n"
                "- Country: sovereign nations, states (e.g., 'United States', 'Ukraine', 'China')\n"
                "- Company: commercial corporations (e.g., 'TSMC', 'Nvidia', 'Boeing')\n"
                "- Person: political leaders, executives, public figures (e.g., 'Joe Biden', 'Vladimir Putin')\n"
                "- Organization: non-governmental, international, or official organizations (e.g., 'United Nations', 'NATO', 'EU', 'Hamas')\n"
                "- Industry: economic or technology sectors (e.g., 'Semiconductors', 'Aviation', 'Energy')\n"
                "- Commodity: traded physical goods/assets (e.g., 'Crude Oil', 'Natural Gas', 'Gold')\n"
                "- Location: cities, regions, geographic choke points (e.g., 'Red Sea', 'Kyiv', 'Gaza Strip')\n\n"
                "Allowed Roles:\n"
                "- 'actor': primary participant/decision-maker\n"
                "- 'location': geographic place where event occurs\n"
                "- 'object': target, commodity, or impacted item\n\n"
                "Output STRICT JSON format with no additional commentary:\n"
                "{\n"
                '  "entities": [\n'
                '    {\n'
                '      "name": "United States",\n'
                '      "type": "Country",\n'
                '      "role": "actor",\n'
                '      "salience": 0.95,\n'
                '      "aliases": ["US", "USA", "America"]\n'
                "    }\n"
                "  ]\n"
                "}"
            )

            # 5. Call Groq
            messages = [
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user},
            ]
            llm_response = await self.groq_client.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
                response_json=True,
            )

            raw_entities = llm_response.get("entities", [])
            if not isinstance(raw_entities, list):
                raw_entities = []

            # 6. Normalize and Write Entities & Edges
            written_entities = 0
            mentions_count = 0

            for raw_item in raw_entities:
                if not isinstance(raw_item, dict):
                    continue
                name = raw_item.get("name", "").strip()
                if not name or len(name) < 2:
                    continue

                etype = raw_item.get("type", "Organization").capitalize()
                if etype not in VALID_ENTITY_TYPES:
                    etype = "Organization"

                role = raw_item.get("role", "actor").lower()
                if role not in VALID_ROLES:
                    role = "actor"

                salience = float(raw_item.get("salience", 0.5))
                salience = max(0.1, min(1.0, salience))
                aliases = raw_item.get("aliases", [])
                if not isinstance(aliases, list):
                    aliases = []

                # Normalize entity name and aliases
                canon_name, canon_type, all_aliases = await self.normalizer.normalize(
                    raw_name=name,
                    entity_type=etype,
                    model_aliases=aliases,
                )

                if not canon_name:
                    continue

                # Write :Entity node to FalkorDB
                self.falkordb.write_entity(
                    canonical_name=canon_name,
                    entity_type=canon_type,
                    aliases=all_aliases,
                )
                written_entities += 1

                # Link Event -> Entity (:INVOLVES)
                self.falkordb.link_event_involves(
                    event_id=event_id,
                    canonical_name=canon_name,
                    role=role,
                )

                # Link Articles -> Entity (:MENTIONS)
                # Check which of the top articles mention this entity
                search_terms = {canon_name.lower()} | {a.lower() for a in all_aliases if len(a) > 2}
                for art in top_articles:
                    art_url = art.get("url")
                    if not art_url:
                        continue
                    art_text = f"{art.get('title', '')} {art.get('description', '')}".lower()
                    
                    # Count occurrences
                    match_count = 0
                    for term in search_terms:
                        # Use word boundary search
                        pattern = r"\b" + re.escape(term) + r"\b"
                        match_count += len(re.findall(pattern, art_text))

                    if match_count > 0:
                        art_salience = salience if canon_name.lower() in art.get("title", "").lower() else round(salience * 0.75, 2)
                        self.falkordb.link_article_mentions(
                            article_url=art_url,
                            canonical_name=canon_name,
                            count=match_count,
                            salience=art_salience,
                        )
                        mentions_count += 1

            # 7. Update Ledger
            ledger.status = "COMPLETED"
            ledger.entities_count = written_entities
            ledger.mentions_count = mentions_count
            ledger.statements_count = statements_count
            ledger.completed_at = datetime.utcnow()
            ledger.updated_at = datetime.utcnow()
            await ledger.save()

            logger.info(
                f"✓ Event {event_id} enriched: {written_entities} entities, "
                f"{mentions_count} mentions, {statements_count} statements."
            )

            return {
                "event_id": event_id,
                "status": "COMPLETED",
                "entities_count": written_entities,
                "mentions_count": mentions_count,
                "statements_count": statements_count,
            }

        except Exception as e:
            logger.error(f"Error enriching event {event_id}: {e}", exc_info=True)
            ledger.status = "FAILED"
            ledger.error_message = str(e)
            ledger.updated_at = datetime.utcnow()
            await ledger.save()
            raise

    async def run_rule_based_links(self) -> int:
        """
        Creates weak :RELATED_TO edges between events sharing >= 2 :Country entities.
        """
        logger.info("Running rule-based country RELATED_TO linking...")
        created_edges = self.falkordb.create_country_related_edges()
        logger.info(f"Rule engine created/verified {created_edges} RELATED_TO edge(s).")
        return created_edges

    async def process_all_events(
        self,
        limit: Optional[int] = None,
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Processes pending events across FalkorDB.
        """
        await init_db(self.settings)
        self.falkordb.init_schema()

        events = self.falkordb.get_all_events()
        logger.info(f"Total events in FalkorDB: {len(events)}")

        if limit is not None:
            events = events[:limit]
            logger.info(f"Processing limit applied: {len(events)} events.")

        results = []
        for idx, evt in enumerate(events, 1):
            logger.info(f"[{idx}/{len(events)}] Processing event {evt['event_id']}...")
            res = await self.enrich_event(evt, force=force)
            results.append(res)
            # Brief pause to respect rate limits
            await asyncio.sleep(0.2)

        # After entities are loaded, run rule-based links
        await self.run_rule_based_links()

        return results

    async def get_summary(self) -> Dict[str, Any]:
        """Returns Phase 2 ledger progress and FalkorDB graph counts."""
        await init_db(self.settings)
        all_events = self.falkordb.get_all_events()
        ledgers = await Phase2LedgerDocument.find_all().to_list()
        completed = [l for l in ledgers if l.status == "COMPLETED"]
        failed = [l for l in ledgers if l.status == "FAILED"]

        p2_stats = self.falkordb.get_phase2_stats()
        base_stats = self.falkordb.get_graph_stats()

        return {
            "total_events_in_graph": len(all_events),
            "events_completed": len(completed),
            "events_failed": len(failed),
            "events_pending": max(0, len(all_events) - len(completed)),
            "base_stats": base_stats,
            "phase2_stats": p2_stats,
        }
