import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("news_pipeline.temporal_linker")


class TemporalLinker:
    """
    Compares event centroids from the current day against active event centroids
    from the past T-3 to T-1 days.
    If cosine similarity >= threshold (default 0.70):
      - Links the event to the existing Story.
      - Creates PRECEDED / FOLLOWED edges between consecutive events.
    Else:
      - Spawns a new Story for the event.
    """

    def __init__(self, similarity_threshold: float = 0.70):
        self.similarity_threshold = similarity_threshold

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str[:10], "%Y-%m-%d")
        except Exception:
            return None

    def link_events(
        self,
        current_events: List[Dict[str, Any]],
        candidate_events: List[Dict[str, Any]],
        current_date_str: str,
    ) -> List[Dict[str, Any]]:
        """
        Links current day events to previous events/stories or generates new stories.
        Returns enriched event dictionaries with story assignment and sequence links.
        """
        results = []

        # Prepare candidate embeddings
        candidate_matrix = []
        valid_candidates = []

        for cand in candidate_events:
            vec = cand.get("centroid")
            if vec is not None and len(vec) == 384:
                # Ensure float numpy array
                arr = np.array(vec, dtype=np.float32)
                norm = np.linalg.norm(arr)
                if norm > 1e-6:
                    candidate_matrix.append(arr / norm)
                    valid_candidates.append(cand)

        candidate_matrix = np.array(candidate_matrix) if candidate_matrix else None

        for idx, event in enumerate(current_events):
            event_id = event["event_id"]
            centroid = event.get("centroid")

            best_sim = 0.0
            best_candidate: Optional[Dict[str, Any]] = None

            if candidate_matrix is not None and len(candidate_matrix) > 0 and centroid is not None:
                curr_vec = np.array(centroid, dtype=np.float32)
                curr_norm = np.linalg.norm(curr_vec)
                if curr_norm > 1e-6:
                    curr_vec = curr_vec / curr_norm
                    sims = np.dot(candidate_matrix, curr_vec)
                    max_idx = int(np.argmax(sims))
                    best_sim = float(sims[max_idx])

                    if best_sim >= self.similarity_threshold:
                        best_candidate = valid_candidates[max_idx]

            curr_dt = self._parse_date(event.get("occurred_at") or current_date_str)

            if best_candidate and best_candidate.get("story_id"):
                story_id = best_candidate["story_id"]
                prev_event_id = best_candidate["event_id"]
                prev_dt = self._parse_date(best_candidate.get("occurred_at") or "")
                days_gap = (curr_dt - prev_dt).days if (curr_dt and prev_dt) else 1

                logger.info(
                    f"🔗 Linked Event [{event_id}] to Story [{story_id}] "
                    f"(matched Event [{prev_event_id}] with sim={best_sim:.3f}, gap={days_gap}d)"
                )

                results.append({
                    "event": event,
                    "story_id": story_id,
                    "is_new_story": False,
                    "linked_prev_event_id": prev_event_id,
                    "days_gap": days_gap,
                    "similarity": best_sim,
                })
            else:
                # Spawn new Story
                story_id = f"story_{current_date_str}_{idx}"
                logger.info(
                    f"✨ Spawned new Story [{story_id}] for Event [{event_id}] "
                    f"(max similarity to past events: {best_sim:.3f})"
                )

                results.append({
                    "event": event,
                    "story_id": story_id,
                    "is_new_story": True,
                    "linked_prev_event_id": None,
                    "days_gap": None,
                    "similarity": best_sim,
                })

        return results
