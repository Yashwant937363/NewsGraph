import React, { useState, useEffect, useRef } from 'react';
import type { EventItem, EntityItem } from '../types';
import { searchGraph } from '../services/api';

interface TopBarProps {
  activeEventId?: string;
  loading?: boolean;
  onSelectEvent: (eventId: string) => void;
  onSelectEntity: (entityName: string) => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  activeEventId,
  loading = false,
  onSelectEvent,
  onSelectEntity,
}) => {
  const [query, setQuery] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [entities, setEntities] = useState<EntityItem[]>([]);
  const [searching, setSearching] = useState(false);

  const containerRef = useRef<HTMLFormElement>(null);
  const debounceTimerRef = useRef<number | null>(null);

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

  useEffect(() => {
    fetchSuggestions('');
  }, []);

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

  useEffect(() => {
    const handleClickOutside = (e: Event) => {
      if (!containerRef.current) return;
      const path = (e as any).composedPath ? (e as any).composedPath() : [];
      const isInside =
        containerRef.current.contains(e.target as Node) ||
        path.includes(containerRef.current);

      if (!isInside) {
        setDropdownOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDropdownOpen(false);
      }
    };

    // Use capture phase (true) so clicks on <falkordb-canvas> / Shadow DOM are caught before stopPropagation()
    document.addEventListener('mousedown', handleClickOutside, true);
    document.addEventListener('pointerdown', handleClickOutside, true);
    document.addEventListener('touchstart', handleClickOutside, true);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside, true);
      document.removeEventListener('pointerdown', handleClickOutside, true);
      document.removeEventListener('touchstart', handleClickOutside, true);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const handleSearchSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSearching(true);
    try {
      const res = await searchGraph(query, 15);
      const evts = res.events || [];
      const ents = res.entities || [];
      setEvents(evts);
      setEntities(ents);

      if (evts.length > 0) {
        onSelectEvent(evts[0].event_id);
        setDropdownOpen(false);
      } else if (ents.length > 0) {
        onSelectEntity(ents[0].canonical_name);
        setDropdownOpen(false);
      } else {
        setDropdownOpen(true);
      }
    } catch (err) {
      console.error('Search submit error:', err);
    } finally {
      setSearching(false);
    }
  };

  return (
    <header
      className="glass-panel"
      style={{
        height: '62px',
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
        position: 'relative',
        borderRadius: 0,
        borderTop: 'none',
        borderLeft: 'none',
        borderRight: 'none',
        borderBottom: '1px solid rgba(0, 0, 0, 0.08)',
        background: 'rgba(255, 255, 255, 0.88)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        boxShadow: '0 1px 4px rgba(0, 0, 0, 0.03)',
      }}
    >
      {/* Centered Search Container: Only Search Bar and Search Button */}
      <form
        onSubmit={handleSearchSubmit}
        ref={containerRef}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          width: '100%',
          maxWidth: '620px',
          position: 'relative',
        }}
      >
        {/* Apple Style Frosted Search Input */}
        <div style={{ position: 'relative', flex: 1 }}>
          <div
            className="glass-input"
            style={{
              display: 'flex',
              alignItems: 'center',
              borderRadius: '12px',
              padding: '0 14px',
              height: '40px',
              gap: '10px',
              background: 'rgba(0, 0, 0, 0.04)',
              border: '1px solid rgba(0, 0, 0, 0.08)',
            }}
          >
            <i
              className={`fa-solid ${searching || loading ? 'fa-spinner animate-spin' : 'fa-magnifying-glass'}`}
              style={{ color: 'rgba(0, 0, 0, 0.45)', fontSize: '13.5px' }}
            ></i>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setDropdownOpen(true)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSearchSubmit();
                }
              }}
              placeholder="Search incidents, countries, entities, or topics..."
              style={{
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: '#1d1d1f',
                fontSize: '13.5px',
                width: '100%',
              }}
            />
            {query && (
              <button
                type="button"
                onClick={() => {
                  setQuery('');
                  fetchSuggestions('');
                }}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'rgba(0, 0, 0, 0.45)',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <i className="fa-solid fa-xmark"></i>
              </button>
            )}
          </div>

          {/* Autocomplete Dropdown (Apple Light Frosted Glass) */}
          {dropdownOpen && (
            <div
              className="glass-panel-elevated"
              style={{
                position: 'absolute',
                top: '50px',
                left: 0,
                right: 0,
                maxHeight: '380px',
                overflowY: 'auto',
                borderRadius: '16px',
                padding: '10px',
                zIndex: 100,
                boxShadow: '0 20px 50px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 1)',
              }}
            >
              {/* Header */}
              <div
                style={{
                  padding: '6px 10px',
                  fontSize: '11px',
                  fontWeight: 600,
                  color: 'rgba(0, 0, 0, 0.5)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  display: 'flex',
                  justifyContent: 'space-between',
                  borderBottom: '1px solid rgba(0, 0, 0, 0.08)',
                  marginBottom: '6px',
                }}
              >
                <span>{query ? `Results for "${query}"` : 'Recent Global Incidents'}</span>
                <span>{events.length + entities.length} found</span>
              </div>

              {/* Entities Section */}
              {entities.length > 0 && (
                <div style={{ marginBottom: '10px' }}>
                  <div style={{ padding: '4px 10px', fontSize: '10px', color: '#1d1d1f', fontWeight: 600, textTransform: 'uppercase' }}>
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
                        padding: '8px 12px',
                        borderRadius: '10px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: '12.5px',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <i className="fa-solid fa-tag" style={{ color: 'rgba(0, 0, 0, 0.45)', fontSize: '11px' }}></i>
                        <span style={{ fontWeight: 600, color: '#1d1d1f' }}>{ent.title}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            fontSize: '10px',
                            background: 'rgba(0, 0, 0, 0.06)',
                            color: '#1d1d1f',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            border: '1px solid rgba(0, 0, 0, 0.08)',
                          }}
                        >
                          {ent.category}
                        </span>
                        <span style={{ fontSize: '10px', color: 'rgba(0, 0, 0, 0.45)' }}>
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
                    <div style={{ padding: '4px 10px', fontSize: '10px', color: '#1d1d1f', fontWeight: 600, textTransform: 'uppercase' }}>
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
                        padding: '10px 12px',
                        borderRadius: '10px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        background: evt.event_id === activeEventId ? 'rgba(0, 0, 0, 0.06)' : 'transparent',
                        borderLeft: evt.event_id === activeEventId ? '3px solid #000000' : '3px solid transparent',
                        marginBottom: '3px',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        if (evt.event_id !== activeEventId) {
                          e.currentTarget.style.background = 'rgba(0, 0, 0, 0.04)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (evt.event_id !== activeEventId) {
                          e.currentTarget.style.background = 'transparent';
                        }
                      }}
                    >
                      <div style={{ fontWeight: 500, color: '#1d1d1f', lineHeight: 1.4 }}>{evt.title}</div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          marginTop: '4px',
                          fontSize: '10px',
                          color: 'rgba(0, 0, 0, 0.45)',
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
                  <div style={{ padding: '20px', textAlign: 'center', color: 'rgba(0, 0, 0, 0.45)', fontSize: '12px' }}>
                    No matching incidents or entities found.
                  </div>
                )
              )}
            </div>
          )}
        </div>

        {/* Apple Style Black Pill Search Button */}
        <button
          type="submit"
          disabled={searching || loading}
          className="glass-button-primary"
          style={{
            height: '40px',
            padding: '0 20px',
            borderRadius: '12px',
            flexShrink: 0,
            fontSize: '13px',
            fontWeight: 600,
          }}
        >
          {searching || loading ? (
            <>
              <i className="fa-solid fa-spinner animate-spin"></i>
              <span>Searching...</span>
            </>
          ) : (
            <>
              <i className="fa-solid fa-magnifying-glass"></i>
              <span>Search</span>
            </>
          )}
        </button>
      </form>
    </header>
  );
};
