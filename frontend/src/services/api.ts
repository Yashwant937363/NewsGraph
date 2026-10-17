import type {
  SearchResponse,
  InvestigationResponse,
  ImpactResponse,
  ConnectResponse,
  EdgeEvidenceResponse,
  NodeEvidenceResponse,
} from '../types';

const BASE_URL = '';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errMsg = `Request failed with status ${res.status}`;
    try {
      const errData = await res.json();
      if (errData && errData.detail) {
        errMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errMsg);
  }
  return res.json() as Promise<T>;
}

export async function searchGraph(query?: string, limit = 20): Promise<SearchResponse> {
  const params = new URLSearchParams();
  if (query && query.trim()) {
    params.set('q', query.trim());
  }
  params.set('limit', String(limit));
  const res = await fetch(`${BASE_URL}/track1/search?${params.toString()}`);
  return handleResponse<SearchResponse>(res);
}

export async function getEntityEvents(
  entityName: string,
  limit = 15
): Promise<Array<{ event_id: string; title: string; occurred_at: string; relationship?: string }>> {
  const res = await fetch(
    `${BASE_URL}/track1/search/entity/${encodeURIComponent(entityName)}/events?limit=${limit}`
  );
  return handleResponse(res);
}

export async function investigateEvent(
  eventId: string,
  explain = false
): Promise<InvestigationResponse> {
  const res = await fetch(
    `${BASE_URL}/track1/investigate/${encodeURIComponent(eventId)}?explain=${explain}`
  );
  return handleResponse<InvestigationResponse>(res);
}

export async function getImpactRadius(
  eventId: string,
  explain = false
): Promise<ImpactResponse> {
  const res = await fetch(
    `${BASE_URL}/track1/impact/${encodeURIComponent(eventId)}?explain=${explain}`
  );
  return handleResponse<ImpactResponse>(res);
}

export async function connectTheDots(
  sourceEventId: string,
  targetEventId: string,
  explain = true
): Promise<ConnectResponse> {
  const params = new URLSearchParams({
    source_event_id: sourceEventId,
    target_event_id: targetEventId,
    explain: String(explain),
  });
  const res = await fetch(`${BASE_URL}/track1/connect?${params.toString()}`);
  return handleResponse<ConnectResponse>(res);
}

export async function getEdgeEvidence(
  sourceId: string,
  targetId: string,
  edgeType: string
): Promise<EdgeEvidenceResponse> {
  const params = new URLSearchParams({
    source_id: sourceId,
    target_id: targetId,
    edge_type: edgeType,
  });
  const res = await fetch(`${BASE_URL}/track1/evidence/edge?${params.toString()}`);
  return handleResponse<EdgeEvidenceResponse>(res);
}

export async function getNodeEvidence(nodeId: string): Promise<NodeEvidenceResponse> {
  const res = await fetch(`${BASE_URL}/track1/evidence/node/${encodeURIComponent(nodeId)}`);
  return handleResponse<NodeEvidenceResponse>(res);
}
