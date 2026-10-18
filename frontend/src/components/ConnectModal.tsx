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
        background: 'rgba(0, 0, 0, 0.3)',
        backdropFilter: 'blur(24px) saturate(180%)',
        WebkitBackdropFilter: 'blur(24px) saturate(180%)',
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
          borderRadius: '20px',
          padding: '24px',
          boxShadow: '0 24px 60px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'rgba(0, 0, 0, 0.06)',
                border: '1px solid rgba(0, 0, 0, 0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#1d1d1f',
                boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.9)',
              }}
            >
              <i className="fa-solid fa-route"></i>
            </div>
            <div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: '#1d1d1f', letterSpacing: '-0.01em' }}>
                Connect the Dots
              </div>
              <div style={{ fontSize: '12px', color: '#6e6e73' }}>
                Find shortest & causal path between two incidents (UC-03)
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'rgba(0, 0, 0, 0.05)',
              border: '1px solid rgba(0, 0, 0, 0.08)',
              borderRadius: '50%',
              width: '28px',
              height: '28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#515154',
              cursor: 'pointer',
              fontSize: '13px',
              transition: 'all 0.15s ease',
            }}
          >
            <i className="fa-solid fa-xmark"></i>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Start Point A */}
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11.5px', fontWeight: 600, color: '#1d1d1f', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              <i className="fa-solid fa-flag" style={{ color: '#6e6e73' }}></i>
              Source Incident A (Origin)
            </label>
            <select
              value={startId}
              onChange={(e) => setStartId(e.target.value)}
              className="glass-input"
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '12px',
                fontSize: '13px',
                color: '#1d1d1f',
                backgroundColor: '#ffffff',
              }}
            >
              <option value="">-- Select Source Incident A --</option>
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
                background: 'rgba(0, 0, 0, 0.05)',
                border: '1px solid rgba(0, 0, 0, 0.08)',
                borderRadius: '50%',
                width: '34px',
                height: '34px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#1d1d1f',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              title="Swap start and target events"
            >
              <i className="fa-solid fa-arrows-up-down"></i>
            </button>
          </div>

          {/* Target Point B */}
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11.5px', fontWeight: 600, color: '#1d1d1f', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              <i className="fa-solid fa-bullseye" style={{ color: '#6e6e73' }}></i>
              Target Incident B (Destination)
            </label>
            <select
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              className="glass-input"
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: '12px',
                fontSize: '13px',
                color: '#1d1d1f',
                backgroundColor: '#ffffff',
              }}
            >
              <option value="">-- Select Target Incident B --</option>
              {events.map((evt) => (
                <option key={evt.event_id} value={evt.event_id} disabled={evt.event_id === startId}>
                  {evt.occurred_at} | {evt.title.length > 60 ? evt.title.substring(0, 60) + '...' : evt.title}
                </option>
              ))}
            </select>
          </div>

          {/* Submit */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
            <button
              type="button"
              onClick={onClose}
              className="glass-button"
              style={{ padding: '8px 16px', borderRadius: '10px' }}
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={!startId || !targetId || startId === targetId}
              className="glass-button-primary"
              style={{ padding: '8px 18px', borderRadius: '10px' }}
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
