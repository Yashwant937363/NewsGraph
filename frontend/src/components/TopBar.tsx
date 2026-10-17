import React, { useState, useEffect, useRef } from 'react';
import type { EventItem, EntityItem, GraphStats, ActionMode } from '../types';
import { searchGraph } from '../services/api';

interface TopBarProps {
  activeEventId: string;
  activeMode: ActionMode;
  explain: boolean;
  stats?: GraphStats;
  loading: boolean;
  onSelectEvent: (eventId: string) => void;
  onSelectEntity: (entityName: string) => void;
  onModeChange: (mode: ActionMode) => void;
  onExplainChange: (explain: boolean) => void;
  onRunAction: () => void;
  onOpenConnectModal: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  activeEventId,
  activeMode,
  explain,
  stats,
  loading,
  onSelectEvent,
  onSelectEntity,
  onModeChange,
  onExplainChange,
  onRunAction,
  onOpenConnectModal,
}) => {
  const [query, setQuery] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [entities, setEntities] = useState<EntityItem[]>([]);
  const [searching, setSearching] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<number | null>(null);

  // Fetch suggestions (either recent events if query is empty, or matching items)
  const fetchSuggestions = async (searchQuery: string) => {
    try {
      setSearching(true);
      const res = await searchGraph(searchQuery, 15);
      setEvents(res.events || []);
      setEntities(res.entities || []);
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setSearching(false);
    }
  };

  // Initial load of recent events
  useEffect(() => {
    fetchSuggestions('');
  }, []);

  // Debounced search when query changes
  useEffect(() => {
    if (debounceTimerRef.current) {
      window.clearTimeout(debounceTimerRef.current);
    }

    debounceTimerRef.current = window.setTimeout(() => {
      fetchSuggestions(query);
    }, 250);

    return () => {
      if (debounceTimerRef.current) {
        window.clearTimeout(debounceTimerRef.current);
      }
    };
  }, [query]);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header
      className="glass-panel"
      style={{
        height: '64px',
        padding: '0 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        zIndex: 50,
        position: 'relative',
        borderRadius: 0,
        borderTop: 'none',
        borderLeft: 'none',
        borderRight: 'none',
      }}
    >
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: '170px' }}>
        <div
          style={{
            width: '34px',
            height: '34px',
            borderRadius: '9px',
            background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 14px rgba(59, 130, 246, 0.45)',
          }}
        >
          <i className="fa-solid fa-circle-nodes" style={{ color: '#fff', fontSize: '16px' }}></i>
        </div>
        <div>
          <div style={{ fontSize: '15px', fontWeight: 700, letterSpacing: '-0.02em', color: '#fff' }}>
            WorldGraph
          </div>
          <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Global Intelligence
          </div>
        </div>
      </div>

      {/* Center Controls: Search Bar & Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, maxWidth: '850px' }}>
        {/* Search Bar with live dropdown */}
        <div ref={containerRef} style={{ position: 'relative', flex: 1 }}>
          <div
            className="glass-input"
            style={{
              display: 'flex',
              alignItems: 'center',
              borderRadius: '8px',
              padding: '0 12px',
              height: '38px',
              gap: '10px',
            }}
          >
            <i
              className={`fa-solid ${searching ? 'fa-spinner animate-spin' : 'fa-magnifying-glass'}`}
              style={{ color: 'var(--text-dim)', fontSize: '13px' }}
            ></i>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setDropdownOpen(true)}
              placeholder="Search incidents, countries, entities, or select event..."
              style={{
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'var(--text-main)',
                fontSize: '13px',
                width: '100%',
              }}
            />
            {query && (
              <button
                onClick={() => setQuery('')}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--text-dim)',
                  cursor: 'pointer',
                  padding: '2px',
                }}
              >
                <i className="fa-solid fa-xmark"></i>
              </button>
            )}
          </div>

          {/* Autocomplete Dropdown */}
          {dropdownOpen && (
            <div
              className="glass-panel-elevated"
              style={{
                position: 'absolute',
                top: '46px',
                left: 0,
                right: 0,
                maxHeight: '380px',
                overflowY: 'auto',
                borderRadius: '8px',
                padding: '8px',
                zIndex: 100,
              }}
            >
              {/* Query Header */}
              <div
                style={{
                  padding: '4px 8px',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'var(--text-dim)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  display: 'flex',
                  justifyContent: 'space-between',
                }}
              >
                <span>{query ? `Search Results for "${query}"` : 'Recent Global Incidents'}</span>
                <span>{events.length + entities.length} found</span>
              </div>

              {/* Entities Section (if searching) */}
              {entities.length > 0 && (
                <div style={{ marginBottom: '8px' }}>
                  <div style={{ padding: '4px 8px', fontSize: '10px', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                    <i className="fa-solid fa-building-columns" style={{ marginRight: '6px' }}></i>
                    Entities ({entities.length})
                  </div>
                  {entities.map((ent) => (
                    <div
                      key={ent.id}
                      onClick={() => {
                        onSelectEntity(ent.canonical_name);
                        setDropdownOpen(false);
                      }}
                      style={{
                        padding: '8px 10px',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: '12px',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <i className="fa-solid fa-tag" style={{ color: 'var(--amber)', fontSize: '11px' }}></i>
                        <span style={{ fontWeight: 600, color: '#fff' }}>{ent.title}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span
                          style={{
                            fontSize: '10px',
                            background: 'rgba(59, 130, 246, 0.15)',
                            color: '#93c5fd',
                            padding: '1px 6px',
                            borderRadius: '10px',
                          }}
                        >
                          {ent.category}
                        </span>
                        <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>
                          {ent.event_count} events
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Events Section */}
              {events.length > 0 ? (
                <div>
                  {entities.length > 0 && (
                    <div style={{ padding: '4px 8px', fontSize: '10px', color: 'var(--accent-blue)', fontWeight: 600 }}>
                      <i className="fa-solid fa-newspaper" style={{ marginRight: '6px' }}></i>
                      Incidents ({events.length})
                    </div>
                  )}
                  {events.map((evt) => (
                    <div
                      key={evt.event_id}
                      onClick={() => {
                        onSelectEvent(evt.event_id);
                        setDropdownOpen(false);
                      }}
                      style={{
                        padding: '8px 10px',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        background: evt.event_id === activeEventId ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                        borderLeft: evt.event_id === activeEventId ? '3px solid var(--accent-blue)' : '3px solid transparent',
                        marginBottom: '2px',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (evt.event_id !== activeEventId) {
                          e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (evt.event_id !== activeEventId) {
                          e.currentTarget.style.background = 'transparent';
                        }
                      }}
                    >
                      <div style={{ fontWeight: 500, color: '#fff', lineHeight: 1.35 }}>{evt.title}</div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          marginTop: '3px',
                          fontSize: '10px',
                          color: 'var(--text-dim)',
                        }}
                      >
                        <span>
                          <i className="fa-regular fa-calendar" style={{ marginRight: '4px' }}></i>
                          {evt.occurred_at}
                        </span>
                        <span>•</span>
                        <span style={{ fontFamily: 'monospace' }}>{evt.event_id}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                !searching && (
                  <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '12px' }}>
                    No matching incidents or entities found.
                  </div>
                )
              )}
            </div>
          )}
        </div>

        {/* Action Mode Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <button
            onClick={() => onModeChange('investigate')}
            className={activeMode === 'investigate' ? 'glass-button-primary' : 'glass-button'}
            style={{ height: '38px', padding: '0 12px' }}
            title="UC-01: Multi-Hop Link Analysis & Neighborhood"
          >
            <i className="fa-solid fa-magnifying-glass-chart"></i>
            <span>Investigate</span>
          </button>

          <button
            onClick={() => onModeChange('impact')}
            className={activeMode === 'impact' ? 'glass-button-primary' : 'glass-button'}
            style={{ height: '38px', padding: '0 12px' }}
            title="UC-02: Blast Radius Traversal & Affected Sectors"
          >
            <i className="fa-solid fa-bullseye"></i>
            <span>Impact Radius</span>
          </button>

          <button
            onClick={onOpenConnectModal}
            className={activeMode === 'connect' ? 'glass-button-primary' : 'glass-button'}
            style={{ height: '38px', padding: '0 12px' }}
            title="UC-03: Shortest & Causal Path Between Two Events"
          >
            <i className="fa-solid fa-route"></i>
            <span>Connect Dots</span>
          </button>
        </div>

        {/* AI Explanation Toggle */}
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: explain ? '#93c5fd' : 'var(--text-muted)',
            cursor: 'pointer',
            userSelect: 'none',
            whiteSpace: 'nowrap',
            padding: '6px 8px',
            borderRadius: '6px',
            background: explain ? 'rgba(59, 130, 246, 0.12)' : 'transparent',
            border: explain ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent',
          }}
          title="Run LangGraph Agent for fact-grounded intelligence briefing with verified quotes"
        >
          <input
            type="checkbox"
            checked={explain}
            onChange={(e) => onExplainChange(e.target.checked)}
            style={{ cursor: 'pointer', accentColor: 'var(--accent-blue)' }}
          />
          <i className="fa-solid fa-wand-magic-sparkles" style={{ fontSize: '11px' }}></i>
          <span>AI Briefing</span>
        </label>

        {/* Run Action Button */}
        <button
          onClick={onRunAction}
          disabled={loading || !activeEventId}
          className="glass-button-primary"
          style={{ height: '38px', padding: '0 14px' }}
        >
          {loading ? (
            <>
              <i className="fa-solid fa-spinner animate-spin"></i>
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <i className="fa-solid fa-bolt"></i>
              <span>Run</span>
            </>
          )}
        </button>
      </div>

      {/* Right Stats Chips */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div
          className="glass-panel"
          style={{
            padding: '4px 10px',
            borderRadius: '12px',
            fontSize: '11px',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <i className="fa-solid fa-circle" style={{ color: 'var(--accent-blue)', fontSize: '8px' }}></i>
          <span>Nodes:</span>
          <strong style={{ color: '#fff' }}>{stats?.total_nodes ?? 0}</strong>
        </div>

        <div
          className="glass-panel"
          style={{
            padding: '4px 10px',
            borderRadius: '12px',
            fontSize: '11px',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <i className="fa-solid fa-link" style={{ color: 'var(--emerald)', fontSize: '9px' }}></i>
          <span>Edges:</span>
          <strong style={{ color: '#fff' }}>{stats?.total_edges ?? 0}</strong>
        </div>
      </div>
    </header>
  );
};
