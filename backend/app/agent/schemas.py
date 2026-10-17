from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class CitedChunk(BaseModel):
    chunk_id: str = Field(description="Unique deterministic chunk ID (e.g. {url}#c{index})")
    article_title: str = Field(description="Headline of the reporting article")
    article_url: str = Field(description="Canonical URL of the article")
    chunk_index: int = Field(description="Sequential index of the chunk within the article")
    chunk_text: str = Field(description="Excerpt or paragraph text containing the evidence")
    similarity: Optional[float] = Field(default=None, description="Vector cosine similarity score if retrieved via search")


class KeyActor(BaseModel):
    entity: str = Field(description="Name of the government, corporation, or figure")
    type: str = Field(description="Entity category (e.g. 'Government / Regulator', 'Company', 'Person')")
    role: str = Field(description="Specific role or action in the incident")


class VerifiedQuoteMetric(BaseModel):
    claim: str = Field(description="High-level factual assertion or metric")
    quote: str = Field(description="Exact or near-verbatim quote from the reporting article chunk")
    publisher: str = Field(description="Publisher/outlet name (e.g. 'Reuters', 'Bloomberg')")
    url: str = Field(description="Article URL containing the evidence")


class ReadMoreItem(BaseModel):
    title: str = Field(description="Primary article title")
    url: str = Field(description="Canonical outbound URL")
    publisher: str = Field(description="Publisher outlet name")
    published_at: Optional[str] = Field(default=None, description="Publication timestamp if available")


class ImpactedSectorItem(BaseModel):
    name: str = Field(description="Name of the country, company, industry, or commodity")
    impact: str = Field(description="Mechanism detailing how the entity or sector is exposed")
    confidence: float = Field(default=0.9, description="Confidence score between 0.0 and 1.0")


class CriticalChokepointItem(BaseModel):
    category: str = Field(description="Category of chokepoint (e.g. 'Company', 'Industry', 'Infrastructure')")
    name: str = Field(description="Name of the chokepoint entity or facility")
    vulnerability: str = Field(description="Explanation of supply chain or operational bottleneck")


class InvestigateExplanation(BaseModel):
    headline: str = Field(description="Investigative headline summarizing the incident")
    incident_overview: str = Field(description="Concise 1-2 paragraph overview of what happened, location, and date")
    key_actors: List[KeyActor] = Field(default_factory=list, description="Participating governments, corporations, and figures")
    causal_drivers: List[str] = Field(default_factory=list, description="Direct predecessor incidents and causal catalysts")
    verified_quotes_and_metrics: List[VerifiedQuoteMetric] = Field(default_factory=list, description="Verified quotes, casualty figures, and metrics extracted from chunks")
    read_more: List[ReadMoreItem] = Field(default_factory=list, description="Source article cards with publisher badges")
    grounding_score: float = Field(default=0.95, description="Factual grounding confidence score between 0.0 and 1.0")


class ImpactExplanation(BaseModel):
    headline: str = Field(description="Headline summarizing systemic shockwave or blast radius")
    blast_radius_overview: str = Field(description="Concise summary of systemic shockwave and affected regions")
    impacted_sectors: Dict[str, List[ImpactedSectorItem]] = Field(
        default_factory=dict,
        description="Categorized breakdown across Country, Company, Industry, Commodity with impacts and confidence",
    )
    critical_chokepoints: List[CriticalChokepointItem] = Field(
        default_factory=list,
        description="Immediate supply chain vulnerabilities and bottlenecks",
    )
    verified_metrics: List[VerifiedQuoteMetric] = Field(
        default_factory=list,
        description="Verified quotes, percentages, and transmission metrics extracted from chunks",
    )
    read_more: List[ReadMoreItem] = Field(default_factory=list, description="Source article cards with publisher badges")
    grounding_score: float = Field(default=0.93, description="Impact grounding confidence score between 0.0 and 1.0")


class PathStep(BaseModel):
    step_number: int = Field(description="1-based index of the hop along the path")
    from_node: str = Field(description="Name or title of the starting node of this hop")
    to_node: str = Field(description="Name or title of the destination node of this hop")
    relationship: str = Field(description="Relationship label (e.g. CAUSED, AFFECTS, CONTRIBUTED_TO)")
    status: str = Field(default="confirmed", description="Trust badge: confirmed | inferred | related")
    confidence: float = Field(default=0.9, description="Confidence score between 0.0 and 1.0")
    mechanism: str = Field(description="Specific transmission mechanism or factual bridge for this hop")


class ConnectExplanation(BaseModel):
    headline: str = Field(description="Headline summarizing the causal bridge between the two events")
    bridge_narrative: str = Field(description="Concise executive narrative explaining how Event A influenced Event B")
    path_steps: List[PathStep] = Field(default_factory=list, description="Ordered step-by-step causal transition cards")
    verified_metrics: List[VerifiedQuoteMetric] = Field(default_factory=list, description="Verified quotes, figures, and metrics extracted from reporting chunks")
    read_more: List[ReadMoreItem] = Field(default_factory=list, description="Source article cards with publisher badges")
    grounding_score: float = Field(default=0.94, description="Factual grounding confidence score between 0.0 and 1.0")
