import React, { useState } from 'react';
import type {
  InvestigationExplanation,
  ImpactExplanation,
  ConnectExplanation,
  EdgeEvidenceResponse,
  NodeEvidenceResponse,
  ActionMode,
} from '../types';

interface SideDrawerProps {
  isOpen: boolean;
  activeMode: ActionMode;
  investigationBriefing?: InvestigationExplanation;
  impactBriefing?: ImpactExplanation;
  connectBriefing?: ConnectExplanation;
  edgeEvidence?: EdgeEvidenceResponse | null;
  nodeEvidence?: NodeEvidenceResponse | null;
  onClose: () => void;
  onExploreEvent?: (eventId: string) => void;
}

export const SideDrawer: React.FC<SideDrawerProps> = ({
  isOpen,
  activeMode,
  investigationBriefing,
  impactBriefing,
  connectBriefing,
  edgeEvidence,
  nodeEvidence,
  onClose,
  onExploreEvent,
}) => {
  const [activeTab, setActiveTab] = useState<'briefing' | 'evidence'>('briefing');

  // Auto-switch to evidence tab when an edge or node is selected
  React.useEffect(() => {
    if (edgeEvidence || nodeEvidence) {
      setActiveTab('evidence');
    }
  }, [edgeEvidence, nodeEvidence]);

  if (!isOpen) return null;

  return (
    <aside
      className="glass-panel"
      style={{
        width: '420px',
        maxWidth: '90vw',
        height: 'calc(100vh - 64px)',
        position: 'absolute',
        top: '64px',
        right: 0,
        zIndex: 40,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 0,
        borderTop: 'none',
        borderBottom: 'none',
        borderRight: 'none',
        boxShadow: '-8px 0 32px rgba(0, 0, 0, 0.45)',
      }}
    >
      {/* Drawer Header with Tabs & Close button */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--card-border)',
          padding: '0 12px 0 16px',
          height: '48px',
          background: 'rgba(0, 0, 0, 0.2)',
        }}
      >
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setActiveTab('briefing')}
            style={{
              background: 'transparent',
              border: 'none',
              padding: '12px 10px',
              color: activeTab === 'briefing' ? '#fff' : 'var(--text-muted)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              borderBottom: activeTab === 'briefing' ? '2px solid var(--accent-blue)' : '2px solid transparent',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <i className="fa-solid fa-brain" style={{ color: 'var(--accent-blue)', fontSize: '11px' }}></i>
            <span>AI Briefing</span>
          </button>

          <button
            onClick={() => setActiveTab('evidence')}
            style={{
              background: 'transparent',
              border: 'none',
              padding: '12px 10px',
              color: activeTab === 'evidence' ? '#fff' : 'var(--text-muted)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              borderBottom: activeTab === 'evidence' ? '2px solid var(--emerald)' : '2px solid transparent',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <i className="fa-solid fa-shield-halved" style={{ color: 'var(--emerald)', fontSize: '11px' }}></i>
            <span>Evidence Trail</span>
            {(edgeEvidence || nodeEvidence) && (
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: 'var(--emerald)',
                }}
              />
            )}
          </button>
        </div>

        <button
          onClick={onClose}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-dim)',
            cursor: 'pointer',
            padding: '6px',
            fontSize: '14px',
          }}
          title="Close drawer"
        >
          <i className="fa-solid fa-xmark"></i>
        </button>
      </div>

      {/* Drawer Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', fontSize: '13px' }}>
        {activeTab === 'briefing' ? (
          <div>
            {/* UC-01 Investigation Briefing */}
            {activeMode === 'investigate' && (
              <div>
                {investigationBriefing ? (
                  <div>
                    {/* Headline */}
                    <div
                      style={{
                        fontSize: '15px',
                        fontWeight: 700,
                        color: '#fff',
                        lineHeight: 1.4,
                        marginBottom: '12px',
                      }}
                    >
                      {investigationBriefing.headline || 'Event Investigation Briefing'}
                    </div>

                    {/* Overview */}
                    {investigationBriefing.incident_overview && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Incident Overview
                        </div>
                        <div
                          style={{
                            background: 'rgba(255, 255, 255, 0.03)',
                            border: '1px solid var(--card-border)',
                            borderRadius: '8px',
                            padding: '12px',
                            lineHeight: 1.6,
                            color: '#e2e8f0',
                            fontSize: '12.5px',
                          }}
                        >
                          {investigationBriefing.incident_overview}
                        </div>
                      </div>
                    )}

                    {/* Key Actors */}
                    {investigationBriefing.key_actors && investigationBriefing.key_actors.length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Key Actors & Targets
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {investigationBriefing.key_actors.map((actor, idx) => (
                            <div
                              key={idx}
                              style={{
                                background: 'rgba(255, 255, 255, 0.02)',
                                border: '1px solid var(--card-border)',
                                borderRadius: '6px',
                                padding: '8px 10px',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontWeight: 600, color: '#fff', fontSize: '12px' }}>{actor.entity}</span>
                                {actor.type && (
                                  <span style={{ fontSize: '10px', color: '#93c5fd', background: 'rgba(59, 130, 246, 0.15)', padding: '1px 6px', borderRadius: '4px' }}>
                                    {actor.type}
                                  </span>
                                )}
                              </div>
                              {actor.role && (
                                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '3px' }}>
                                  {actor.role}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Causal Drivers */}
                    {investigationBriefing.causal_drivers && investigationBriefing.causal_drivers.length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Causal Catalysts & Drivers
                        </div>
                        <ul style={{ paddingLeft: '18px', color: '#cbd5e1', fontSize: '12px', lineHeight: 1.6 }}>
                          {investigationBriefing.causal_drivers.map((driver, idx) => (
                            <li key={idx} style={{ marginBottom: '4px' }}>
                              {driver}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Verified Quotes & Metrics */}
                    {investigationBriefing.verified_quotes_and_metrics && investigationBriefing.verified_quotes_and_metrics.length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Verified Quotes & Metrics
                        </div>
                        {investigationBriefing.verified_quotes_and_metrics.map((item, idx) => (
                          <div
                            key={idx}
                            style={{
                              borderLeft: '3px solid var(--accent-blue)',
                              background: 'rgba(59, 130, 246, 0.06)',
                              padding: '8px 12px',
                              borderRadius: '0 6px 6px 0',
                              marginBottom: '8px',
                            }}
                          >
                            {item.claim && <div style={{ fontWeight: 600, color: '#fff', fontSize: '12px', marginBottom: '3px' }}>{item.claim}</div>}
                            <div style={{ fontStyle: 'italic', color: '#cbd5e1', fontSize: '11.5px', lineHeight: 1.5 }}>
                              "{item.quote}"
                            </div>
                            {item.publisher && (
                              <div style={{ fontSize: '10px', color: 'var(--emerald)', marginTop: '4px', fontWeight: 600 }}>
                                Source: {item.publisher}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Read More Articles */}
                    {investigationBriefing.read_more && investigationBriefing.read_more.length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Primary Reporting Sources
                        </div>
                        {investigationBriefing.read_more.map((rm, idx) => (
                          <a
                            key={idx}
                            href={rm.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              display: 'block',
                              background: 'rgba(255, 255, 255, 0.02)',
                              border: '1px solid var(--card-border)',
                              borderRadius: '6px',
                              padding: '8px 10px',
                              marginBottom: '6px',
                              textDecoration: 'none',
                              transition: 'all 0.15s ease',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-blue)')}
                            onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--card-border)')}
                          >
                            <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--emerald)', textTransform: 'uppercase' }}>
                              {rm.publisher || 'Verified Outlet'}
                            </div>
                            <div style={{ fontSize: '12px', color: '#93c5fd', fontWeight: 500, marginTop: '2px' }}>
                              {rm.title}
                            </div>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: 'var(--text-dim)', marginTop: '40px' }}>
                    <i className="fa-solid fa-wand-magic-sparkles" style={{ fontSize: '24px', marginBottom: '10px', opacity: 0.5 }}></i>
                    <div>Check "AI Briefing" and click Run to generate a fact-grounded intelligence briefing.</div>
                  </div>
                )}
              </div>
            )}

            {/* UC-02 Impact Radius Briefing */}
            {activeMode === 'impact' && (
              <div>
                {impactBriefing ? (
                  <div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: '#fff', lineHeight: 1.4, marginBottom: '12px' }}>
                      {impactBriefing.headline || 'Systemic Impact Shockwave Briefing'}
                    </div>

                    {impactBriefing.blast_radius_overview && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Blast Radius Overview
                        </div>
                        <div
                          style={{
                            background: 'rgba(255, 255, 255, 0.03)',
                            border: '1px solid var(--card-border)',
                            borderRadius: '8px',
                            padding: '12px',
                            lineHeight: 1.6,
                            color: '#e2e8f0',
                            fontSize: '12.5px',
                          }}
                        >
                          {impactBriefing.blast_radius_overview}
                        </div>
                      </div>
                    )}

                    {/* Impacted Sectors breakdown */}
                    {impactBriefing.impacted_sectors && Object.keys(impactBriefing.impacted_sectors).length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Exposed Sectors & Geographies
                        </div>
                        {Object.entries(impactBriefing.impacted_sectors).map(([sector, items]) => (
                          <div key={sector} style={{ marginBottom: '10px' }}>
                            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--amber)', marginBottom: '4px' }}>
                              {sector}
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {items.map((it, idx) => (
                                <div
                                  key={idx}
                                  style={{
                                    background: 'rgba(255, 255, 255, 0.02)',
                                    border: '1px solid var(--card-border)',
                                    borderRadius: '6px',
                                    padding: '6px 10px',
                                  }}
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontWeight: 600, color: '#fff', fontSize: '11.5px' }}>{it.name}</span>
                                    {it.confidence && (
                                      <span style={{ fontSize: '10px', color: 'var(--emerald)' }}>
                                        {Math.round(it.confidence * 100)}% conf
                                      </span>
                                    )}
                                  </div>
                                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                                    {it.impact}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Critical Chokepoints */}
                    {impactBriefing.critical_chokepoints && impactBriefing.critical_chokepoints.length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--rose)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Critical Vulnerabilities & Chokepoints
                        </div>
                        {impactBriefing.critical_chokepoints.map((cp, idx) => (
                          <div
                            key={idx}
                            style={{
                              borderLeft: '3px solid var(--rose)',
                              background: 'rgba(244, 63, 94, 0.08)',
                              padding: '8px 10px',
                              borderRadius: '0 6px 6px 0',
                              marginBottom: '6px',
                              fontSize: '11.5px',
                            }}
                          >
                            <div style={{ fontWeight: 600, color: '#fff' }}>{cp.name}</div>
                            <div style={{ color: '#fca5a5', marginTop: '2px' }}>{cp.vulnerability}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: 'var(--text-dim)', marginTop: '40px' }}>
                    <i className="fa-solid fa-bullseye" style={{ fontSize: '24px', marginBottom: '10px', opacity: 0.5 }}></i>
                    <div>Run Impact Radius with "AI Briefing" enabled to see blast radius synthesis.</div>
                  </div>
                )}
              </div>
            )}

            {/* UC-03 Connect the Dots Briefing */}
            {activeMode === 'connect' && (
              <div>
                {connectBriefing ? (
                  <div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: '#fff', lineHeight: 1.4, marginBottom: '12px' }}>
                      {connectBriefing.headline || 'Causal Bridge Narrative'}
                    </div>

                    {connectBriefing.bridge_narrative && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Executive Connection Synthesis
                        </div>
                        <div
                          style={{
                            background: 'rgba(255, 255, 255, 0.03)',
                            border: '1px solid var(--card-border)',
                            borderRadius: '8px',
                            padding: '12px',
                            lineHeight: 1.6,
                            color: '#e2e8f0',
                            fontSize: '12.5px',
                          }}
                        >
                          {connectBriefing.bridge_narrative}
                        </div>
                      </div>
                    )}

                    {/* Step-by-Step Path Cards */}
                    {connectBriefing.path_steps && connectBriefing.path_steps.length > 0 && (
                      <div style={{ marginBottom: '16px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Step-by-Step Causal Path
                        </div>
                        {connectBriefing.path_steps.map((step) => (
                          <div
                            key={step.step_number}
                            style={{
                              background: 'rgba(255, 255, 255, 0.02)',
                              border: '1px solid var(--card-border)',
                              borderRadius: '8px',
                              padding: '10px',
                              marginBottom: '8px',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-blue)' }}>
                                STEP {step.step_number}
                              </span>
                              <span
                                style={{
                                  fontSize: '10px',
                                  padding: '1px 6px',
                                  borderRadius: '4px',
                                  background: step.status === 'confirmed' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                                  color: step.status === 'confirmed' ? 'var(--emerald)' : 'var(--amber)',
                                }}
                              >
                                {step.status || 'related'} {step.confidence ? `(${Math.round(step.confidence * 100)}%)` : ''}
                              </span>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', margin: '6px 0', fontSize: '11.5px', color: '#fff' }}>
                              <span style={{ fontWeight: 600 }}>{step.from_node}</span>
                              <i className="fa-solid fa-arrow-right" style={{ color: 'var(--text-dim)', fontSize: '10px' }}></i>
                              <span style={{ fontWeight: 600 }}>{step.to_node}</span>
                            </div>

                            {step.mechanism && (
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                                {step.mechanism}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: 'var(--text-dim)', marginTop: '40px' }}>
                    <i className="fa-solid fa-route" style={{ fontSize: '24px', marginBottom: '10px', opacity: 0.5 }}></i>
                    <div>Select Event A and Event B using "Connect Dots" to generate a causal bridge narrative.</div>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          /* Evidence Trail Tab (UC-04) */
          <div>
            {edgeEvidence ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: edgeEvidence.edge.status === 'confirmed' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                      color: edgeEvidence.edge.status === 'confirmed' ? '#6ee7b7' : '#fcd34d',
                      border: edgeEvidence.edge.status === 'confirmed' ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(245, 158, 11, 0.4)',
                    }}
                  >
                    <i className="fa-solid fa-circle-check" style={{ marginRight: '4px' }}></i>
                    {edgeEvidence.edge.status.toUpperCase()}
                  </span>
                  <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                    Confidence: <strong>{Math.round((edgeEvidence.edge.confidence || 1.0) * 100)}%</strong>
                  </span>
                </div>

                <div style={{ fontSize: '13px', fontWeight: 600, color: '#fff', marginBottom: '6px' }}>
                  {edgeEvidence.edge.source_id} ──({edgeEvidence.edge.edge_type})──► {edgeEvidence.edge.target_id}
                </div>

                {edgeEvidence.edge.rationale && (
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', border: '1px solid var(--card-border)', borderRadius: '6px', padding: '10px', margin: '10px 0', fontSize: '12px', color: '#cbd5e1', lineHeight: 1.5 }}>
                    <strong>Rationale:</strong> {edgeEvidence.edge.rationale}
                  </div>
                )}

                {/* Sources & quotes */}
                <div style={{ marginTop: '16px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Supporting Outlets & Quotes ({edgeEvidence.sources.length})
                  </div>
                  {edgeEvidence.sources.map((src, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid var(--card-border)',
                        borderRadius: '6px',
                        padding: '10px',
                        marginBottom: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--emerald)', textTransform: 'uppercase' }}>
                          {src.publisher}
                        </span>
                        <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>
                          Reliability: <strong>{src.reliability}</strong>
                        </span>
                      </div>
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: '12px', color: '#93c5fd', textDecoration: 'none', display: 'block', margin: '4px 0', fontWeight: 500 }}
                      >
                        {src.title}
                      </a>
                      {src.supporting_chunks && src.supporting_chunks.map((chk, cIdx) => (
                        <div
                          key={cIdx}
                          style={{
                            fontSize: '11px',
                            color: 'var(--text-muted)',
                            background: 'rgba(0, 0, 0, 0.25)',
                            padding: '6px 8px',
                            borderRadius: '4px',
                            marginTop: '4px',
                            borderLeft: '2px solid var(--emerald)',
                            lineHeight: 1.45,
                          }}
                        >
                          "{chk.text}"
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            ) : nodeEvidence ? (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      background: 'rgba(59, 130, 246, 0.2)',
                      color: '#93c5fd',
                      padding: '2px 8px',
                      borderRadius: '4px',
                    }}
                  >
                    {nodeEvidence.labels.join(' : ')}
                  </span>
                </div>

                <div style={{ fontSize: '15px', fontWeight: 700, color: '#fff', marginBottom: '6px', lineHeight: 1.4 }}>
                  {nodeEvidence.title || nodeEvidence.node_id}
                </div>

                {nodeEvidence.occurred_at && (
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '14px' }}>
                    Occurred on: {nodeEvidence.occurred_at}
                  </div>
                )}

                {/* Explore this event button */}
                {nodeEvidence.labels.includes('Event') && onExploreEvent && (
                  <button
                    onClick={() => onExploreEvent(nodeEvidence.node_id)}
                    className="glass-button-primary"
                    style={{ width: '100%', justifyContent: 'center', marginBottom: '16px' }}
                  >
                    <i className="fa-solid fa-magnifying-glass-chart"></i>
                    <span>Investigate This Incident</span>
                  </button>
                )}

                {/* Reporting Articles */}
                <div>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '8px' }}>
                    Reporting Coverage ({nodeEvidence.articles_count} articles)
                  </div>
                  {nodeEvidence.articles.map((art, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid var(--card-border)',
                        borderRadius: '6px',
                        padding: '10px',
                        marginBottom: '8px',
                      }}
                    >
                      <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--emerald)', textTransform: 'uppercase' }}>
                        {art.publisher || 'Verified Outlet'}
                      </div>
                      <a
                        href={art.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: '12px', color: '#93c5fd', textDecoration: 'none', display: 'block', margin: '4px 0', fontWeight: 500 }}
                      >
                        {art.title}
                      </a>
                      {art.snippet && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                          {art.snippet}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: 'var(--text-dim)', marginTop: '40px' }}>
                <i className="fa-solid fa-shield-halved" style={{ fontSize: '24px', marginBottom: '10px', opacity: 0.5 }}></i>
                <div>Click any edge or node in the canvas to inspect its trust provenance and source citations.</div>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
