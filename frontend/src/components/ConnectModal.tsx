import React, { useState, useEffect } from 'react';
import type { EventItem } from '../types';
import { searchGraph } from '../services/api';

interface ConnectModalProps {
  isOpen: boolean;
  defaultStartId?: string;
  defaultTargetId?: string;
  defaultStartTitle?: string;
  defaultTargetTitle?: string;
  onClose: () => void;
  onConnect: (sourceId: string, targetId: string) => void;
}

export const ConnectModal: React.FC<ConnectModalProps> = ({
  isOpen,
  defaultStartId = '',
  defaultTargetId = '',
  onClose,
  onConnect,
}) => {
  const [startId, setStartId] = useState(defaultStartId);
  const [targetId, setTargetId] = useState(defaultTargetId);
  const [events, setEvents] = useState<EventItem[]>([]);

  useEffect(() => {
    if (isOpen) {
      setStartId(defaultStartId);
      setTargetId(defaultTargetId);
      fetchEvents();
    }
  }, [isOpen, defaultStartId, defaultTargetId]);

  const fetchEvents = async () => {
    try {
      const res = await searchGraph('', 30);
      setEvents(res.events || []);
    } catch (err) {
      console.error('Failed to load events for connect modal:', err);
    }
  };

  const handleSwap = () => {
    const temp = startId;
    setStartId(targetId);
    setTargetId(temp);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (startId && targetId && startId !== targetId) {
      onConnect(startId, targetId);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(3, 6, 15, 0.75)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        className="glass-panel-elevated"
        style={{
          width: '520px',
          maxWidth: '100%',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.6)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'rgba(59, 130, 246, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--accent-blue)',
              }}
            >
              <i className="fa-solid fa-route"></i>
            </div>
            <div>
              <div style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>Connect the Dots</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Find shortest & causal path between two global incidents (UC-03)
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              fontSize: '16px',
            }}
          >
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {/* Start Point A */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--emerald)', marginBottom: '6px', textTransform: 'uppercase' }}>
              <i className="fa-solid fa-flag" style={{ marginRight: '6px' }}></i>
              Source Event A (Origin)
            </label>
            <select
              value={startId}
              onChange={(e) => setStartId(e.target.value)}
              className="glass-input"
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '8px',
                fontSize: '12.5px',
              }}
            >
              <option value="">-- Select Source Event A --</option>
              {events.map((evt) => (
                <option key={evt.event_id} value={evt.event_id}>
                  {evt.occurred_at} | {evt.title.length > 60 ? evt.title.substring(0, 60) + '...' : evt.title}
                </option>
              ))}
            </select>
          </div>

          {/* Swap Button */}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <button
              type="button"
              onClick={handleSwap}
              style={{
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--card-border)',
                borderRadius: '50%',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--text-muted)',
                cursor: 'pointer',
              }}
              title="Swap start and target events"
            >
              <i className="fa-solid fa-arrows-up-down"></i>
            </button>
          </div>

          {/* Target Point B */}
          <div>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--accent-blue)', marginBottom: '6px', textTransform: 'uppercase' }}>
              <i className="fa-solid fa-bullseye" style={{ marginRight: '6px' }}></i>
              Target Event B (Destination)
            </label>
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              className="glass-input"
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '8px',
                fontSize: '12.5px',
              }}
            >
              <option value="">-- Select Target Event B --</option>
              {events.map((evt) => (
                <option key={evt.event_id} value={evt.event_id} disabled={evt.event_id === startId}>
                  {evt.occurred_at} | {evt.title.length > 60 ? evt.title.substring(0, 60) + '...' : evt.title}
                </option>
              ))}
            </select>
          </div>

          {/* Submit */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              className="glass-button"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={!startId || !targetId || startId === targetId}
              className="glass-button-primary"
            >
              <i className="fa-solid fa-route"></i>
              <span>Find Causal Path</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
