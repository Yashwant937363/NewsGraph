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
        width: '430px',
        maxWidth: '92vw',
        height: '100%',
        position: 'absolute',
        top: 0,
        bottom: 0,
        right: 0,
        zIndex: 40,
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 0,
        borderTop: 'none',
        borderBottom: 'none',
        borderRight: 'none',
        borderLeft: '1px solid rgba(0, 0, 0, 0.08)',
        boxShadow: '-10px 0 40px rgba(0, 0, 0, 0.06)',
      }}
    >
      {/* Apple Segmented Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(0, 0, 0, 0.08)',
          padding: '12px 18px',
          background: 'rgba(255, 255, 255, 0.6)',
        }}
      >
        <div className="apple-segmented-control" style={{ flex: 1, marginRight: '12px' }}>
          <button
            onClick={() => setActiveTab('briefing')}
            className={`apple-segment-item ${activeTab === 'briefing' ? 'active' : ''}`}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            <i className="fa-solid fa-brain" style={{ fontSize: '11px' }}></i>
            <span>AI Briefing</span>
          </button>

          <button
            onClick={() => setActiveTab('evidence')}
            className={`apple-segment-item ${activeTab === 'evidence' ? 'active' : ''}`}
            style={{ flex: 1, justifyContent: 'center' }}
          >
            <i className="fa-solid fa-shield-halved" style={{ fontSize: '11px' }}></i>
            <span>Evidence</span>
            {(edgeEvidence || nodeEvidence) && (
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: '#1d1d1f',
                }}
              />
            )}
          </button>
        </div>

        <button
          onClick={onClose}
          style={{
            background: 'rgba(0, 0, 0, 0.05)',
            border: 'none',
            color: '#1d1d1f',
            borderRadius: '50%',
            width: '28px',
            height: '28px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            fontSize: '13px',
            transition: 'background 0.15s ease',
          }}
          title="Close drawer"
        >
          <i className="fa-solid fa-xmark"></i>
        </button>
      </div>

      {/* Drawer Body (Clean Apple Light Mode Typography) */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '18px 22px', fontSize: '13px' }}>
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
                        fontSize: '16px',
                        fontWeight: 700,
                        color: '#1d1d1f',
                        lineHeight: 1.4,
                        marginBottom: '14px',
                        letterSpacing: '-0.01em',
                      }}
                    >
                      {investigationBriefing.headline || 'Incident Intelligence Briefing'}
                    </div>

                    {/* Overview */}
                    {investigationBriefing.incident_overview && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Incident Overview
                        </div>
                        <div
                          style={{
                            background: 'rgba(0, 0, 0, 0.03)',
                            border: '1px solid rgba(0, 0, 0, 0.06)',
                            borderRadius: '12px',
                            padding: '14px',
                            lineHeight: 1.6,
                            color: '#1d1d1f',
                            fontSize: '12.5px',
                          }}
                        >
                          {investigationBriefing.incident_overview}
                        </div>
                      </div>
                    )}

                    {/* Key Actors */}
                    {investigationBriefing.key_actors && investigationBriefing.key_actors.length > 0 && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Key Actors & Targets
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {investigationBriefing.key_actors.map((actor, idx) => (
                            <div
                              key={idx}
                              style={{
                                background: 'rgba(0, 0, 0, 0.03)',
                                border: '1px solid rgba(0, 0, 0, 0.06)',
                                borderRadius: '10px',
                                padding: '10px 12px',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontWeight: 600, color: '#1d1d1f', fontSize: '12.5px' }}>{actor.entity}</span>
                                {actor.type && (
                                  <span style={{ fontSize: '10px', color: '#1d1d1f', background: 'rgba(0, 0, 0, 0.06)', padding: '2px 8px', borderRadius: '10px' }}>
                                    {actor.type}
                                  </span>
                                )}
                              </div>
                              {actor.role && (
                                <div style={{ fontSize: '11px', color: '#6e6e73', marginTop: '4px' }}>
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
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Causal Catalysts
                        </div>
                        <ul style={{ paddingLeft: '18px', color: '#515154', fontSize: '12px', lineHeight: 1.6 }}>
                          {investigationBriefing.causal_drivers.map((driver, idx) => (
                            <li key={idx} style={{ marginBottom: '5px' }}>
                              {driver}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Verified Quotes & Metrics */}
                    {investigationBriefing.verified_quotes_and_metrics && investigationBriefing.verified_quotes_and_metrics.length > 0 && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Verified Evidence & Quotes
                        </div>
                        {investigationBriefing.verified_quotes_and_metrics.map((item, idx) => (
                          <div
                            key={idx}
                            style={{
                              borderLeft: '3px solid #1d1d1f',
                              background: 'rgba(0, 0, 0, 0.03)',
                              padding: '10px 14px',
                              borderRadius: '0 10px 10px 0',
                              marginBottom: '8px',
                            }}
                          >
                            {item.claim && <div style={{ fontWeight: 600, color: '#1d1d1f', fontSize: '12px', marginBottom: '4px' }}>{item.claim}</div>}
                            <div style={{ fontStyle: 'italic', color: '#515154', fontSize: '11.5px', lineHeight: 1.5 }}>
                              "{item.quote}"
                            </div>
                            {item.publisher && (
                              <div style={{ fontSize: '10px', color: '#1d1d1f', marginTop: '6px', fontWeight: 600, opacity: 0.8 }}>
                                Outlet: {item.publisher}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Read More */}
                    {investigationBriefing.read_more && investigationBriefing.read_more.length > 0 && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Reporting Sources
                        </div>
                        {investigationBriefing.read_more.map((rm, idx) => (
                          <a
                            key={idx}
                            href={rm.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              display: 'block',
                              background: 'rgba(0, 0, 0, 0.03)',
                              border: '1px solid rgba(0, 0, 0, 0.06)',
                              borderRadius: '10px',
                              padding: '10px 12px',
                              marginBottom: '6px',
                              textDecoration: 'none',
                              transition: 'all 0.15s ease',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = 'rgba(0, 0, 0, 0.06)';
                              e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.15)';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'rgba(0, 0, 0, 0.03)';
                              e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.06)';
                            }}
                          >
                            <div style={{ fontSize: '10px', fontWeight: 700, color: '#6e6e73', textTransform: 'uppercase' }}>
                              {rm.publisher || 'Verified Outlet'}
                            </div>
                            <div style={{ fontSize: '12px', color: '#1d1d1f', fontWeight: 500, marginTop: '3px' }}>
                              {rm.title}
                            </div>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: 'rgba(0, 0, 0, 0.45)', marginTop: '50px' }}>
                    <i className="fa-solid fa-wand-magic-sparkles" style={{ fontSize: '26px', marginBottom: '12px', opacity: 0.6 }}></i>
                    <div>Enable "AI Explain" in the right-click menu or search to generate a fact-grounded synthesis.</div>
                  </div>
                )}
              </div>
            )}

            {/* UC-02 Impact Radius Briefing */}
            {activeMode === 'impact' && (
              <div>
                {impactBriefing ? (
                  <div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#1d1d1f', lineHeight: 1.4, marginBottom: '14px' }}>
                      {impactBriefing.headline || 'Blast Radius & Shockwave Briefing'}
                    </div>

                    {impactBriefing.blast_radius_overview && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Blast Radius Overview
                        </div>
                        <div
                          style={{
                            background: 'rgba(0, 0, 0, 0.03)',
                            border: '1px solid rgba(0, 0, 0, 0.06)',
                            borderRadius: '12px',
                            padding: '14px',
                            lineHeight: 1.6,
                            color: '#1d1d1f',
                            fontSize: '12.5px',
                          }}
                        >
                          {impactBriefing.blast_radius_overview}
                        </div>
                      </div>
                    )}

                    {/* Impacted Sectors */}
                    {impactBriefing.impacted_sectors && Object.keys(impactBriefing.impacted_sectors).length > 0 && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Exposed Sectors & Geographies
                        </div>
                        {Object.entries(impactBriefing.impacted_sectors).map(([sector, items]) => (
                          <div key={sector} style={{ marginBottom: '12px' }}>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: '#1d1d1f', marginBottom: '6px' }}>
                              {sector}
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                              {items.map((it, idx) => (
                                <div
                                  key={idx}
                                  style={{
                                    background: 'rgba(0, 0, 0, 0.03)',
                                    border: '1px solid rgba(0, 0, 0, 0.06)',
                                    borderRadius: '8px',
                                    padding: '8px 10px',
                                  }}
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span style={{ fontWeight: 600, color: '#1d1d1f', fontSize: '12px' }}>{it.name}</span>
                                    {it.confidence && (
                                      <span style={{ fontSize: '10px', color: '#6e6e73' }}>
                                        {Math.round(it.confidence * 100)}% conf
                                      </span>
                                    )}
                                  </div>
                                  <div style={{ fontSize: '11px', color: '#515154', marginTop: '3px' }}>
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
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Critical Vulnerabilities & Chokepoints
                        </div>
                        {impactBriefing.critical_chokepoints.map((cp, idx) => (
                          <div
                            key={idx}
                            style={{
                              borderLeft: '3px solid #1d1d1f',
                              background: 'rgba(0, 0, 0, 0.03)',
                              padding: '10px 12px',
                              borderRadius: '0 10px 10px 0',
                              marginBottom: '6px',
                              fontSize: '12px',
                            }}
                          >
                            <div style={{ fontWeight: 600, color: '#1d1d1f' }}>{cp.name}</div>
                            <div style={{ color: '#515154', marginTop: '3px' }}>{cp.vulnerability}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: 'rgba(0, 0, 0, 0.45)', marginTop: '50px' }}>
                    <i className="fa-solid fa-bullseye" style={{ fontSize: '26px', marginBottom: '12px', opacity: 0.6 }}></i>
                    <div>Run Impact Radius with "AI Explain" enabled to see shockwave analysis.</div>
                  </div>
                )}
              </div>
            )}

            {/* UC-03 Connect the Dots Briefing */}
            {activeMode === 'connect' && (
              <div>
                {connectBriefing ? (
                  <div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: '#1d1d1f', lineHeight: 1.4, marginBottom: '14px' }}>
                      {connectBriefing.headline || 'Causal Bridge Synthesis'}
                    </div>

                    {connectBriefing.bridge_narrative && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Executive Bridge Narrative
                        </div>
                        <div
                          style={{
                            background: 'rgba(0, 0, 0, 0.03)',
                            border: '1px solid rgba(0, 0, 0, 0.06)',
                            borderRadius: '12px',
                            padding: '14px',
                            lineHeight: 1.6,
                            color: '#1d1d1f',
                            fontSize: '12.5px',
                          }}
                        >
                          {connectBriefing.bridge_narrative}
                        </div>
                      </div>
                    )}

                    {/* Path Steps */}
                    {connectBriefing.path_steps && connectBriefing.path_steps.length > 0 && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                          Step-by-Step Causal Path
                        </div>
                        {connectBriefing.path_steps.map((step) => (
                          <div
                            key={step.step_number}
                            style={{
                              background: 'rgba(0, 0, 0, 0.03)',
                              border: '1px solid rgba(0, 0, 0, 0.06)',
                              borderRadius: '10px',
                              padding: '12px',
                              marginBottom: '8px',
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '11px', fontWeight: 700, color: '#1d1d1f' }}>
                                STEP {step.step_number}
                              </span>
                              <span
                                style={{
                                  fontSize: '10px',
                                  padding: '2px 8px',
                                  borderRadius: '6px',
                                  background: 'rgba(0, 0, 0, 0.06)',
                                  color: '#1d1d1f',
                                }}
                              >
                                {step.status || 'related'} {step.confidence ? `(${Math.round(step.confidence * 100)}%)` : ''}
                              </span>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '8px 0', fontSize: '12px', color: '#1d1d1f' }}>
                              <span style={{ fontWeight: 600 }}>{step.from_node}</span>
                              <i className="fa-solid fa-arrow-right" style={{ color: 'rgba(0, 0, 0, 0.35)', fontSize: '10px' }}></i>
                              <span style={{ fontWeight: 600 }}>{step.to_node}</span>
                            </div>

                            {step.mechanism && (
                              <div style={{ fontSize: '11.5px', color: '#515154', lineHeight: 1.5 }}>
                                {step.mechanism}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', color: 'rgba(0, 0, 0, 0.45)', marginTop: '50px' }}>
                    <i className="fa-solid fa-route" style={{ fontSize: '26px', marginBottom: '12px', opacity: 0.6 }}></i>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '3px 10px',
                      borderRadius: '8px',
                      background: 'rgba(0, 0, 0, 0.06)',
                      color: '#1d1d1f',
                      border: '1px solid rgba(0, 0, 0, 0.08)',
                    }}
                  >
                    <i className="fa-solid fa-circle-check" style={{ marginRight: '5px' }}></i>
                    {edgeEvidence.edge.status.toUpperCase()}
                  </span>

                  <span style={{ fontSize: '11px', color: 'rgba(0, 0, 0, 0.55)' }}>
                    Confidence: <strong style={{ color: '#1d1d1f' }}>{Math.round((edgeEvidence.edge.confidence || 1.0) * 100)}%</strong>
                  </span>
                </div>

                <div style={{ fontSize: '13px', fontWeight: 600, color: '#1d1d1f', marginBottom: '8px' }}>
                  {edgeEvidence.edge.source_id} ──({edgeEvidence.edge.edge_type})──► {edgeEvidence.edge.target_id}
                </div>

                {edgeEvidence.edge.rationale && (
                  <div style={{ background: 'rgba(0, 0, 0, 0.03)', border: '1px solid rgba(0, 0, 0, 0.06)', borderRadius: '10px', padding: '12px', margin: '12px 0', fontSize: '12px', color: '#1d1d1f', lineHeight: 1.55 }}>
                    <strong>Rationale:</strong> {edgeEvidence.edge.rationale}
                  </div>
                )}

                {/* Sources & quotes */}
                <div style={{ marginTop: '18px' }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>
                    Supporting Sources & Citations ({edgeEvidence.sources.length})
                  </div>
                  {edgeEvidence.sources.map((src, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'rgba(0, 0, 0, 0.03)',
                        border: '1px solid rgba(0, 0, 0, 0.06)',
                        borderRadius: '10px',
                        padding: '12px',
                        marginBottom: '10px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, color: '#1d1d1f', textTransform: 'uppercase' }}>
                          {src.publisher}
                        </span>
                        <span style={{ fontSize: '10px', color: 'rgba(0, 0, 0, 0.55)' }}>
                          Reliability: <strong style={{ color: '#1d1d1f' }}>{src.reliability}</strong>
                        </span>
                      </div>
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: '12.5px', color: '#1d1d1f', textDecoration: 'none', display: 'block', margin: '5px 0', fontWeight: 500 }}
                        onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                        onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
                      >
                        {src.title}
                      </a>
                      {src.supporting_chunks && src.supporting_chunks.map((chk, cIdx) => (
                        <div
                          key={cIdx}
                          style={{
                            fontSize: '11.5px',
                            color: '#515154',
                            background: 'rgba(0, 0, 0, 0.04)',
                            padding: '8px 10px',
                            borderRadius: '6px',
                            marginTop: '6px',
                            borderLeft: '2px solid #1d1d1f',
                            lineHeight: 1.5,
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
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      background: 'rgba(0, 0, 0, 0.06)',
                      color: '#1d1d1f',
                      padding: '3px 10px',
                      borderRadius: '8px',
                    }}
                  >
                    {nodeEvidence.labels.join(' : ')}
                  </span>
                </div>

                <div style={{ fontSize: '16px', fontWeight: 700, color: '#1d1d1f', marginBottom: '6px', lineHeight: 1.4 }}>
                  {nodeEvidence.title || nodeEvidence.node_id}
                </div>

                {nodeEvidence.occurred_at && (
                  <div style={{ fontSize: '11.5px', color: 'rgba(0, 0, 0, 0.55)', marginBottom: '16px' }}>
                    Occurred on: {nodeEvidence.occurred_at}
                  </div>
                )}

                {/* Explore this event button */}
                {nodeEvidence.labels.includes('Event') && onExploreEvent && (
                  <button
                    onClick={() => onExploreEvent(nodeEvidence.node_id)}
                    className="glass-button-primary"
                    style={{ width: '100%', justifyContent: 'center', marginBottom: '18px', borderRadius: '12px' }}
                  >
                    <i className="fa-solid fa-magnifying-glass-chart"></i>
                    <span>Investigate This Incident</span>
                  </button>
                )}

                {/* Reporting Articles */}
                <div>
                  <div style={{ fontSize: '10px', fontWeight: 700, color: 'rgba(0, 0, 0, 0.45)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>
                    Reporting Coverage ({nodeEvidence.articles_count} articles)
                  </div>
                  {nodeEvidence.articles.map((art, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'rgba(0, 0, 0, 0.03)',
                        border: '1px solid rgba(0, 0, 0, 0.06)',
                        borderRadius: '10px',
                        padding: '12px',
                        marginBottom: '10px',
                      }}
                    >
                      <div style={{ fontSize: '10px', fontWeight: 700, color: '#6e6e73', textTransform: 'uppercase' }}>
                        {art.publisher || 'Verified Outlet'}
                      </div>
                      <a
                        href={art.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ fontSize: '12.5px', color: '#1d1d1f', textDecoration: 'none', display: 'block', margin: '5px 0', fontWeight: 500 }}
                        onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
                        onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
                      >
                        {art.title}
                      </a>
                      {art.snippet && (
                        <div style={{ fontSize: '11.5px', color: '#515154', lineHeight: 1.5 }}>
                          {art.snippet}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', color: 'rgba(0, 0, 0, 0.45)', marginTop: '50px' }}>
                <i className="fa-solid fa-shield-halved" style={{ fontSize: '26px', marginBottom: '12px', opacity: 0.6 }}></i>
                <div>Click any edge or node in the canvas to inspect its trust provenance and source citations.</div>
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
