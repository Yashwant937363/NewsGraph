import React, { useEffect, useRef, useState } from 'react';
import type { FalkorDBCanvas } from '@falkordb/canvas';
import '@falkordb/canvas';
import type { GraphData, GraphNode, GraphLink } from '../types';

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  node: GraphNode | null;
}

interface GraphCanvasProps {
  data: GraphData;
  loading: boolean;
  loadingMessage?: string;
  onNodeClick: (node: GraphNode) => void;
  onLinkClick: (link: GraphLink) => void;
  onInvestigateNode: (nodeId: string) => void;
  onImpactNode: (nodeId: string) => void;
  onSetStartNode: (nodeId: string, nodeTitle: string) => void;
  onSetTargetNode: (nodeId: string, nodeTitle: string) => void;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  data,
  loading,
  loadingMessage = 'Querying FalkorDB graph...',
  onNodeClick,
  onLinkClick,
  onInvestigateNode,
  onImpactNode,
  onSetStartNode,
  onSetTargetNode,
}) => {
  const canvasRef = useRef<FalkorDBCanvas>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [currentLayout, setCurrentLayout] = useState<'force' | 'radial' | 'tree'>('force');
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    node: null,
  });

  // Initialize canvas configurations
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.setConfig({
      backgroundColor: '#060913',
      foregroundColor: '#F8FAFC',
      captionsKeys: ['title', 'canonical_name', 'name', 'event_id'],
      showPropertyKeyPrefix: false,
      layoutMode: 'force',
      simulation: {
        centerStrength: 0.04,
        chargeStrength: -380,
      },
      eventHandlers: {
        onNodeClick: (node: GraphNode) => {
          setContextMenu((prev) => ({ ...prev, visible: false }));
          onNodeClick(node);
        },
        onLinkClick: (link: GraphLink) => {
          setContextMenu((prev) => ({ ...prev, visible: false }));
          onLinkClick(link);
        },
        onNodeRightClick: (node: GraphNode, event: MouseEvent) => {
          event.preventDefault();
          const rect = containerRef.current?.getBoundingClientRect();
          const offsetX = rect ? event.clientX - rect.left : event.clientX;
          const offsetY = rect ? event.clientY - rect.top : event.clientY;

          setContextMenu({
            visible: true,
            x: offsetX,
            y: offsetY,
            node,
          });
        },
        onBackgroundClick: () => {
          setContextMenu((prev) => ({ ...prev, visible: false }));
        },
      },
    });
  }, [onNodeClick, onLinkClick]);

  // Update canvas data when props change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.setData({
      nodes: (data.nodes || []).map((n) => ({
        ...n,
        visible: n.visible ?? true,
        color: n.color || '#3B82F6',
      })),
      links: (data.links || []).map((l) => ({
        ...l,
        visible: l.visible ?? true,
        color: l.color || '#94A3B8',
      })),
    } as any);

    // Auto-fit after short delay for simulation initialization
    const timer = window.setTimeout(() => {
      try {
        canvas.zoomToFit(1.15);
      } catch {
        // ignore layout fit timing
      }
    }, 450);

    return () => window.clearTimeout(timer);
  }, [data]);

  // Layout mode switcher
  const handleSwitchLayout = (mode: 'force' | 'radial' | 'tree') => {
    setCurrentLayout(mode);
    const canvas = canvasRef.current;
    if (!canvas) return;

    if (mode === 'radial') {
      canvas.setConfig({
        layoutMode: 'radial',
        layoutOptions: {
          radial: {
            direction: 'out',
            levelDistance: 130,
          },
        },
      });
    } else if (mode === 'tree') {
      canvas.setConfig({
        layoutMode: 'tree',
        layoutOptions: {
          tree: {
            direction: 'lr',
            levelDistance: 170,
            nodeSpacing: 100,
          },
        },
      });
    } else {
      canvas.setConfig({
        layoutMode: 'force',
      });
    }

    setTimeout(() => {
      try {
        canvas.zoomToFit(1.15);
      } catch {
        // ignore
      }
    }, 400);
  };

  const handleZoomFit = () => {
    try {
      canvasRef.current?.zoomToFit(1.15);
    } catch {
      // ignore
    }
  };

  // Close context menu on outside click
  useEffect(() => {
    const handleGlobalClick = () => {
      if (contextMenu.visible) {
        setContextMenu((prev) => ({ ...prev, visible: false }));
      }
    };
    window.addEventListener('click', handleGlobalClick);
    return () => window.removeEventListener('click', handleGlobalClick);
  }, [contextMenu.visible]);

  return (
    <div
      ref={containerRef}
      style={{
        flex: 1,
        position: 'relative',
        width: '100%',
        height: '100%',
        background: 'radial-gradient(ellipse at 40% 30%, #0d152a 0%, #060913 80%)',
        overflow: 'hidden',
      }}
    >
      {/* FalkorDB Canvas Element */}
      <falkordb-canvas
        ref={canvasRef}
        style={{
          width: '100%',
          height: '100%',
          display: 'block',
        }}
      />

      {/* Floating Canvas View Controls (Top-Right) */}
      <div
        className="glass-panel"
        style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          borderRadius: '10px',
          padding: '4px 6px',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          zIndex: 10,
        }}
      >
        <span style={{ fontSize: '10px', fontWeight: 600, color: 'var(--text-dim)', padding: '0 6px', textTransform: 'uppercase' }}>
          Layout
        </span>

        <button
          onClick={() => handleSwitchLayout('force')}
          style={{
            background: currentLayout === 'force' ? 'rgba(59, 130, 246, 0.25)' : 'transparent',
            border: currentLayout === 'force' ? '1px solid rgba(59, 130, 246, 0.5)' : '1px solid transparent',
            color: currentLayout === 'force' ? '#93c5fd' : 'var(--text-muted)',
            padding: '4px 8px',
            borderRadius: '6px',
            fontSize: '11px',
            cursor: 'pointer',
          }}
          title="Force-directed organic simulation (UC-01)"
        >
          <i className="fa-solid fa-atom" style={{ marginRight: '4px' }}></i>
          Force
        </button>

        <button
          onClick={() => handleSwitchLayout('radial')}
          style={{
            background: currentLayout === 'radial' ? 'rgba(59, 130, 246, 0.25)' : 'transparent',
            border: currentLayout === 'radial' ? '1px solid rgba(59, 130, 246, 0.5)' : '1px solid transparent',
            color: currentLayout === 'radial' ? '#93c5fd' : 'var(--text-muted)',
            padding: '4px 8px',
            borderRadius: '6px',
            fontSize: '11px',
            cursor: 'pointer',
          }}
          title="Concentric blast radius rings (UC-02)"
        >
          <i className="fa-solid fa-bullseye" style={{ marginRight: '4px' }}></i>
          Radial
        </button>

        <button
          onClick={() => handleSwitchLayout('tree')}
          style={{
            background: currentLayout === 'tree' ? 'rgba(59, 130, 246, 0.25)' : 'transparent',
            border: currentLayout === 'tree' ? '1px solid rgba(59, 130, 246, 0.5)' : '1px solid transparent',
            color: currentLayout === 'tree' ? '#93c5fd' : 'var(--text-muted)',
            padding: '4px 8px',
            borderRadius: '6px',
            fontSize: '11px',
            cursor: 'pointer',
          }}
          title="Hierarchical causal flow tree (UC-03)"
        >
          <i className="fa-solid fa-diagram-project" style={{ marginRight: '4px' }}></i>
          Tree
        </button>

        <div style={{ width: '1px', height: '18px', background: 'var(--card-border)', margin: '0 4px' }} />

        <button
          onClick={handleZoomFit}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            padding: '4px 8px',
            borderRadius: '6px',
            fontSize: '11px',
            cursor: 'pointer',
          }}
          title="Auto-fit viewport"
        >
          <i className="fa-solid fa-expand"></i>
        </button>
      </div>

      {/* Floating Legend Overlay (Bottom-Left) */}
      <div
        className="glass-panel"
        style={{
          position: 'absolute',
          bottom: '16px',
          left: '16px',
          borderRadius: '10px',
          padding: '10px 14px',
          fontSize: '11px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          zIndex: 10,
        }}
      >
        <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Node Palette
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#3B82F6' }}></div>
            <span>Event</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10B981' }}></div>
            <span>Country</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#F59E0B' }}></div>
            <span>Company</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#8B5CF6' }}></div>
            <span>Industry</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#06B6D4' }}></div>
            <span>Organization</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#64748B' }}></div>
            <span>Article</span>
          </div>
        </div>
      </div>

      {/* Node Right-Click Frosted Context Menu */}
      {contextMenu.visible && contextMenu.node && (
        <div
          className="glass-panel-elevated"
          style={{
            position: 'absolute',
            top: `${contextMenu.y}px`,
            left: `${contextMenu.x}px`,
            borderRadius: '8px',
            padding: '6px',
            minWidth: '200px',
            zIndex: 100,
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Node Title header */}
          <div
            style={{
              padding: '6px 8px',
              borderBottom: '1px solid var(--card-border)',
              marginBottom: '4px',
            }}
          >
            <div style={{ fontSize: '11px', fontWeight: 600, color: '#fff', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
              {contextMenu.node.data?.title || contextMenu.node.data?.canonical_name || String(contextMenu.node.id)}
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-dim)' }}>
              {contextMenu.node.labels?.join(' : ')}
            </div>
          </div>

          {/* Action options */}
          <div
            onClick={() => {
              const id = String(contextMenu.node?.id);
              setContextMenu((prev) => ({ ...prev, visible: false }));
              onInvestigateNode(id);
            }}
            style={{
              padding: '6px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: '#fff',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-solid fa-magnifying-glass-chart" style={{ color: 'var(--accent-blue)', width: '16px' }}></i>
            <span>Investigate Event</span>
          </div>

          <div
            onClick={() => {
              const id = String(contextMenu.node?.id);
              setContextMenu((prev) => ({ ...prev, visible: false }));
              onImpactNode(id);
            }}
            style={{
              padding: '6px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: '#fff',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-solid fa-bullseye" style={{ color: 'var(--amber)', width: '16px' }}></i>
            <span>Calculate Impact Radius</span>
          </div>

          <div style={{ height: '1px', background: 'var(--card-border)', margin: '4px 0' }} />

          <div
            onClick={() => {
              const id = String(contextMenu.node?.id);
              const title = contextMenu.node?.data?.title || id;
              setContextMenu((prev) => ({ ...prev, visible: false }));
              onSetStartNode(id, title);
            }}
            style={{
              padding: '6px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: '#fff',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(16, 185, 129, 0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-solid fa-flag" style={{ color: 'var(--emerald)', width: '16px' }}></i>
            <span>Set as Start Point (A)</span>
          </div>

          <div
            onClick={() => {
              const id = String(contextMenu.node?.id);
              const title = contextMenu.node?.data?.title || id;
              setContextMenu((prev) => ({ ...prev, visible: false }));
              onSetTargetNode(id, title);
            }}
            style={{
              padding: '6px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: '#fff',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(59, 130, 246, 0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-solid fa-route" style={{ color: 'var(--accent-blue)', width: '16px' }}></i>
            <span>Connect to Here (B)</span>
          </div>

          <div style={{ height: '1px', background: 'var(--card-border)', margin: '4px 0' }} />

          <div
            onClick={() => {
              if (contextMenu.node) {
                onNodeClick(contextMenu.node);
                setContextMenu((prev) => ({ ...prev, visible: false }));
              }
            }}
            style={{
              padding: '6px 8px',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: 'var(--text-muted)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-regular fa-file-lines" style={{ width: '16px' }}></i>
            <span>View Evidence & Articles</span>
          </div>
        </div>
      )}

      {/* Loading Overlay */}
      {loading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(6, 9, 19, 0.7)',
            backdropFilter: 'blur(6px)',
            WebkitBackdropFilter: 'blur(6px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            zIndex: 30,
          }}
        >
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              border: '3px solid rgba(255, 255, 255, 0.1)',
              borderTopColor: 'var(--accent-blue)',
            }}
            className="animate-spin"
          />
          <div style={{ fontSize: '13px', color: '#93c5fd', fontWeight: 500 }}>
            {loadingMessage}
          </div>
        </div>
      )}
    </div>
  );
};
