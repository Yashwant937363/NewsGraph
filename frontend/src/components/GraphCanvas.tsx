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
  onInvestigateNode: (nodeId: string, explain?: boolean) => void;
  onImpactNode: (nodeId: string, explain?: boolean) => void;
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
  const [aiExplain, setAiExplain] = useState<boolean>(true);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    node: null,
  });

  const highlightNode = (nodeId: string) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      const gd = canvas.getGraphData?.();
      if (gd && gd.nodes) {
        gd.nodes.forEach((n: any) => {
          if (!n._originalColor) {
            n._originalColor = n.color || '#3B82F6';
          }
          if (String(n.id) === String(nodeId)) {
            // High-contrast dark highlight for Apple Light Mode
            n.color = '#000000';
          } else {
            n.color = n._originalColor;
          }
        });
        canvas.refresh?.();
      }
    } catch (e) {
      console.error('Highlight node error:', e);
    }
  };

  const clearHighlight = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    try {
      const gd = canvas.getGraphData?.();
      if (gd && gd.nodes) {
        gd.nodes.forEach((n: any) => {
          if (n._originalColor) {
            n.color = n._originalColor;
          }
        });
        canvas.refresh?.();
      }
    } catch {}
  };

  // Initialize canvas configurations
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.setConfig({
      backgroundColor: '#f8fafc',
      foregroundColor: '#1d1d1f',
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
          highlightNode(String(node.id));
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

          highlightNode(String(node.id));

          setContextMenu({
            visible: true,
            x: offsetX,
            y: offsetY,
            node,
          });
        },
        onBackgroundClick: () => {
          setContextMenu((prev) => ({ ...prev, visible: false }));
          clearHighlight();
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

    const timer = window.setTimeout(() => {
      try {
        canvas.zoomToFit(1.15);
      } catch {
        // ignore
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
        background: '#f8fafc',
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

      {/* Floating Canvas Controls (Apple Segmented Style) */}
      <div
        className="glass-panel"
        style={{
          position: 'absolute',
          top: '18px',
          right: '18px',
          borderRadius: '12px',
          padding: '3px 4px',
          display: 'flex',
          alignItems: 'center',
          gap: '3px',
          zIndex: 10,
          background: 'rgba(255, 255, 255, 0.92)',
          border: '1px solid rgba(0, 0, 0, 0.08)',
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.05)',
        }}
      >
        <span style={{ fontSize: '10px', fontWeight: 600, color: '#86868b', padding: '0 8px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          Layout
        </span>

        <button
          onClick={() => handleSwitchLayout('force')}
          style={{
            background: currentLayout === 'force' ? '#1d1d1f' : 'transparent',
            border: 'none',
            color: currentLayout === 'force' ? '#ffffff' : '#515154',
            padding: '5px 11px',
            borderRadius: '8px',
            fontSize: '11.5px',
            fontWeight: currentLayout === 'force' ? 600 : 500,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            boxShadow: currentLayout === 'force' ? '0 2px 6px rgba(0, 0, 0, 0.15)' : 'none',
          }}
          title="Force-directed organic simulation (UC-01)"
        >
          <i className="fa-solid fa-atom" style={{ marginRight: '5px' }}></i>
          Force
        </button>

        <button
          onClick={() => handleSwitchLayout('radial')}
          style={{
            background: currentLayout === 'radial' ? '#1d1d1f' : 'transparent',
            border: 'none',
            color: currentLayout === 'radial' ? '#ffffff' : '#515154',
            padding: '5px 11px',
            borderRadius: '8px',
            fontSize: '11.5px',
            fontWeight: currentLayout === 'radial' ? 600 : 500,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            boxShadow: currentLayout === 'radial' ? '0 2px 6px rgba(0, 0, 0, 0.15)' : 'none',
          }}
          title="Concentric blast radius rings (UC-02)"
        >
          <i className="fa-solid fa-bullseye" style={{ marginRight: '5px' }}></i>
          Radial
        </button>

        <button
          onClick={() => handleSwitchLayout('tree')}
          style={{
            background: currentLayout === 'tree' ? '#1d1d1f' : 'transparent',
            border: 'none',
            color: currentLayout === 'tree' ? '#ffffff' : '#515154',
            padding: '5px 11px',
            borderRadius: '8px',
            fontSize: '11.5px',
            fontWeight: currentLayout === 'tree' ? 600 : 500,
            cursor: 'pointer',
            transition: 'all 0.15s ease',
            boxShadow: currentLayout === 'tree' ? '0 2px 6px rgba(0, 0, 0, 0.15)' : 'none',
          }}
          title="Hierarchical causal flow tree (UC-03)"
        >
          <i className="fa-solid fa-diagram-project" style={{ marginRight: '5px' }}></i>
          Tree
        </button>

        <div style={{ width: '1px', height: '18px', background: 'rgba(0, 0, 0, 0.08)', margin: '0 4px' }} />

        <button
          onClick={handleZoomFit}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#515154',
            padding: '5px 9px',
            borderRadius: '8px',
            fontSize: '11.5px',
            cursor: 'pointer',
            transition: 'all 0.15s ease',
          }}
          title="Auto-fit viewport"
        >
          <i className="fa-solid fa-expand"></i>
        </button>
      </div>

      {/* Floating Legend (Apple Frosted Capsule) */}
      <div
        className="glass-panel"
        style={{
          position: 'absolute',
          bottom: '18px',
          left: '18px',
          borderRadius: '14px',
          padding: '12px 16px',
          fontSize: '11px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          zIndex: 10,
          background: 'rgba(255, 255, 255, 0.92)',
          border: '1px solid rgba(0, 0, 0, 0.08)',
        }}
      >
        <div style={{ fontSize: '10px', fontWeight: 700, color: '#86868b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Node Palette
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#3B82F6' }}></div>
            <span style={{ color: '#1d1d1f' }}>Event</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10B981' }}></div>
            <span style={{ color: '#1d1d1f' }}>Country</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#F59E0B' }}></div>
            <span style={{ color: '#1d1d1f' }}>Company</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#8B5CF6' }}></div>
            <span style={{ color: '#1d1d1f' }}>Industry</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#06B6D4' }}></div>
            <span style={{ color: '#1d1d1f' }}>Organization</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#64748B' }}></div>
            <span style={{ color: '#1d1d1f' }}>Article</span>
          </div>
        </div>
      </div>

      {/* iOS Style Frosted Context Menu */}
      {contextMenu.visible && contextMenu.node && (
        <div
          className="glass-panel-elevated"
          style={{
            position: 'absolute',
            top: `${contextMenu.y}px`,
            left: `${contextMenu.x}px`,
            borderRadius: '16px',
            padding: '8px',
            minWidth: '220px',
            zIndex: 100,
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255, 255, 255, 1)',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Apple iOS AI Explain Toggle Switch */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 10px',
              borderRadius: '10px',
              background: 'rgba(0, 0, 0, 0.04)',
              marginBottom: '6px',
              border: '1px solid rgba(0, 0, 0, 0.06)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#1d1d1f', fontWeight: 500 }}>
              <i className="fa-solid fa-wand-magic-sparkles" style={{ color: aiExplain ? '#1d1d1f' : 'rgba(0, 0, 0, 0.4)', fontSize: '11px' }}></i>
              <span>AI Explain</span>
            </div>
            <div
              onClick={(e) => {
                e.stopPropagation();
                setAiExplain((prev) => !prev);
              }}
              style={{
                width: '34px',
                height: '18px',
                borderRadius: '10px',
                background: aiExplain ? '#1d1d1f' : 'rgba(0, 0, 0, 0.16)',
                cursor: 'pointer',
                position: 'relative',
                transition: 'background 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
              title="Toggle AI intelligence agent explanation"
            >
              <div
                style={{
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  background: '#ffffff',
                  position: 'absolute',
                  top: '2px',
                  left: aiExplain ? '18px' : '2px',
                  transition: 'left 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
                }}
              />
            </div>
          </div>

          {/* Action options (iOS Style items) */}
          <div
            onClick={() => {
              const id = String(contextMenu.node?.id);
              setContextMenu((prev) => ({ ...prev, visible: false }));
              onInvestigateNode(id, aiExplain);
            }}
            style={{
              padding: '7px 10px',
              borderRadius: '9px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '12.5px',
              color: '#1d1d1f',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-solid fa-magnifying-glass-chart" style={{ color: '#1d1d1f', width: '16px' }}></i>
            <span>Investigate Event</span>
          </div>

          <div
            onClick={() => {
              const id = String(contextMenu.node?.id);
              setContextMenu((prev) => ({ ...prev, visible: false }));
              onImpactNode(id, aiExplain);
            }}
            style={{
              padding: '7px 10px',
              borderRadius: '9px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '12.5px',
              color: '#1d1d1f',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-solid fa-bullseye" style={{ color: '#1d1d1f', width: '16px' }}></i>
            <span>Calculate Impact Radius</span>
          </div>

          <div style={{ height: '1px', background: 'rgba(0, 0, 0, 0.06)', margin: '5px 0' }} />

          <div
            onClick={() => {
              const id = String(contextMenu.node?.id);
              const title = contextMenu.node?.data?.title || id;
              setContextMenu((prev) => ({ ...prev, visible: false }));
              onSetStartNode(id, title);
            }}
            style={{
              padding: '7px 10px',
              borderRadius: '9px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '12.5px',
              color: '#1d1d1f',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-solid fa-flag" style={{ color: '#1d1d1f', width: '16px' }}></i>
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
              padding: '7px 10px',
              borderRadius: '9px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '12.5px',
              color: '#1d1d1f',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-solid fa-route" style={{ color: '#1d1d1f', width: '16px' }}></i>
            <span>Connect to Here (B)</span>
          </div>

          <div style={{ height: '1px', background: 'rgba(0, 0, 0, 0.06)', margin: '5px 0' }} />

          <div
            onClick={() => {
              if (contextMenu.node) {
                onNodeClick(contextMenu.node);
                setContextMenu((prev) => ({ ...prev, visible: false }));
              }
            }}
            style={{
              padding: '7px 10px',
              borderRadius: '9px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              fontSize: '12.5px',
              color: '#515154',
              transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(0, 0, 0, 0.05)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
          >
            <i className="fa-regular fa-file-lines" style={{ width: '16px' }}></i>
            <span>View Evidence & Articles</span>
          </div>
        </div>
      )}

      {/* Apple Loading Spinner */}
      {loading && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'rgba(245, 245, 247, 0.75)',
            backdropFilter: 'blur(16px)',
            WebkitBackdropFilter: 'blur(16px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '14px',
            zIndex: 30,
          }}
        >
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              border: '3px solid rgba(0, 0, 0, 0.12)',
              borderTopColor: '#1d1d1f',
            }}
            className="animate-spin"
          />
          <div style={{ fontSize: '13px', color: '#1d1d1f', fontWeight: 500, letterSpacing: '-0.01em' }}>
            {loadingMessage}
          </div>
        </div>
      )}
    </div>
  );
};
