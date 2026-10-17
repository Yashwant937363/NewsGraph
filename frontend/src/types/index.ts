// Graph canvas types
export interface GraphNode {
  id: string | number;
  labels: string[];
  color: string;
  visible?: boolean;
  data: Record<string, any>;
}

export interface GraphLink {
  id: string | number;
  relationship: string;
  source: string | number | GraphNode;
  target: string | number | GraphNode;
  color?: string;
  visible?: boolean;
  data?: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface GraphStats {
  total_nodes?: number;
  total_edges?: number;
  countries_count?: number;
  companies_count?: number;
  industries_count?: number;
}

// Search types
export interface EventItem {
  id: string;
  event_id: string;
  title: string;
  occurred_at: string;
  category?: string;
  summary?: string;
  type: 'event';
}

export interface EntityItem {
  id: string;
  canonical_name: string;
  title: string;
  labels: string[];
  event_count: number;
  category: string;
  type: 'entity';
}

export interface SearchResponse {
  query: string;
  events: EventItem[];
  entities: EntityItem[];
}

// UC-01: Investigate Event types
export interface KeyActor {
  entity: string;
  type?: string;
  role?: string;
}

export interface VerifiedQuote {
  claim?: string;
  quote: string;
  publisher?: string;
  url?: string;
}

export interface ReadMoreItem {
  title: string;
  url: string;
  publisher?: string;
  published_at?: string;
}

export interface InvestigationExplanation {
  headline?: string;
  incident_overview?: string;
  key_actors?: KeyActor[];
  causal_drivers?: string[];
  verified_quotes_and_metrics?: VerifiedQuote[];
  read_more?: ReadMoreItem[];
  grounding_score?: number;
}

export interface InvestigationResponse {
  event_id: string;
  stats?: GraphStats;
  graph: GraphData;
  explanation?: InvestigationExplanation;
}

// UC-02: Impact Radius types
export interface SectorImpact {
  name: string;
  impact: string;
  confidence?: number;
}

export interface CriticalChokepoint {
  category?: string;
  name: string;
  vulnerability: string;
}

export interface ImpactExplanation {
  headline?: string;
  blast_radius_overview?: string;
  impacted_sectors?: Record<string, SectorImpact[]>;
  critical_chokepoints?: CriticalChokepoint[];
  verified_metrics?: VerifiedQuote[];
  read_more?: ReadMoreItem[];
  grounding_score?: number;
}

export interface ImpactResponse {
  event_id: string;
  grouped_impacts?: Record<string, string[]>;
  events_impacted?: Array<{ event_id: string; title: string; occurred_at: string }>;
  graph: GraphData;
  explanation?: ImpactExplanation;
}

// UC-03: Connect the Dots types
export interface PathStep {
  step_number: number;
  from_node: string;
  to_node: string;
  relationship: string;
  status?: string;
  confidence?: number;
  mechanism?: string;
}

export interface ConnectExplanation {
  headline?: string;
  bridge_narrative?: string;
  path_steps?: PathStep[];
  verified_metrics?: VerifiedQuote[];
  read_more?: ReadMoreItem[];
  grounding_score?: number;
}

export interface ConnectResponse {
  connection: {
    source_event_id: string;
    target_event_id: string;
    found: boolean;
    path_length: number;
  };
  graph: GraphData;
  explanation?: ConnectExplanation;
}

// UC-04: Evidence Trail types
export interface EdgeProps {
  source_id: string;
  target_id: string;
  edge_type: string;
  status: 'confirmed' | 'inferred' | 'related' | string;
  confidence: number;
  rationale?: string;
  agent?: string;
  created_at?: string | null;
  valid_from?: string | null;
}

export interface SupportingChunk {
  chunk_id: string;
  chunk_index?: number;
  text: string;
}

export interface EvidenceSource {
  url: string;
  title: string;
  publisher: string;
  reliability: number;
  published_at?: string;
  supporting_chunks?: SupportingChunk[];
}

export interface EdgeEvidenceResponse {
  edge: EdgeProps;
  sources: EvidenceSource[];
  contradictions: string[];
  anomalies: string[];
}

export interface ArticleMention {
  url: string;
  title: string;
  publisher?: string;
  reliability?: number;
  published_at?: string;
  snippet?: string;
}

export interface NodeEvidenceResponse {
  node_id: string;
  labels: string[];
  title?: string;
  occurred_at?: string;
  articles_count: number;
  articles: ArticleMention[];
}

export type ActionMode = 'investigate' | 'impact' | 'connect';
