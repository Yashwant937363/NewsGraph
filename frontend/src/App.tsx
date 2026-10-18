import React, { useState, useEffect, useCallback } from 'react';
import type {
  GraphData,
  GraphNode,
  GraphLink,
  InvestigationExplanation,
  ImpactExplanation,
  ConnectExplanation,
  EdgeEvidenceResponse,
  NodeEvidenceResponse,
  ActionMode,
} from './types';
import {
  searchGraph,
  getEntityEvents,
  investigateEvent,
  getImpactRadius,
  connectTheDots,
  getEdgeEvidence,
  getNodeEvidence,
} from './services/api';
import { TopBar } from './components/TopBar';
import { GraphCanvas } from './components/GraphCanvas';
import { SideDrawer } from './components/SideDrawer';
import { ConnectModal } from './components/ConnectModal';
import './App.css';

export const App: React.FC = () => {
  const [activeEventId, setActiveEventId] = useState<string>('');
  const [activeMode, setActiveMode] = useState<ActionMode>('investigate');

  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingMessage, setLoadingMessage] = useState<string>('Querying FalkorDB graph...');

  // Briefings
  const [investigationBriefing, setInvestigationBriefing] = useState<InvestigationExplanation | undefined>();
  const [impactBriefing, setImpactBriefing] = useState<ImpactExplanation | undefined>();
  const [connectBriefing, setConnectBriefing] = useState<ConnectExplanation | undefined>();

  // Evidence state
  const [edgeEvidence, setEdgeEvidence] = useState<EdgeEvidenceResponse | null>(null);
  const [nodeEvidence, setNodeEvidence] = useState<NodeEvidenceResponse | null>(null);

  // UI Panels
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [isConnectModalOpen, setIsConnectModalOpen] = useState<boolean>(false);

  // Connect points state
  const [connectStartId, setConnectStartId] = useState<string>('');
  const [connectTargetId, setConnectTargetId] = useState<string>('');

  // Toast notification
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  // Execution runner for current mode
  const executeAnalysis = useCallback(
    async (eventId: string, mode: ActionMode, explainEnabled: boolean) => {
      if (!eventId) return;

      try {
        setLoading(true);
        setLoadingMessage(
          explainEnabled
            ? 'Running FalkorDB traversal & LangGraph intelligence agent...'
            : 'Executing FalkorDB Cypher traversal...'
        );

        if (mode === 'investigate') {
          const res = await investigateEvent(eventId, explainEnabled);
          setGraphData(res.graph || { nodes: [], links: [] });
          setInvestigationBriefing(res.explanation);
          if (explainEnabled && res.explanation) {
            setIsDrawerOpen(true);
          }
        } else if (mode === 'impact') {
          const res = await getImpactRadius(eventId, explainEnabled);
          setGraphData(res.graph || { nodes: [], links: [] });
          setImpactBriefing(res.explanation);
          if (explainEnabled && res.explanation) {
            setIsDrawerOpen(true);
          }
        }
      } catch (err: any) {
        console.error('Analysis error:', err);
        showToast(err.message || 'Failed to query knowledge graph.');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Initial load: find latest event and render investigation graph
  useEffect(() => {
    const initApp = async () => {
      try {
        setLoading(true);
        setLoadingMessage('Initializing WorldGraph workspace...');
        const res = await searchGraph('', 10);
        if (res.events && res.events.length > 0) {
          const firstEvt = res.events[0];
          setActiveEventId(firstEvt.event_id);
          await executeAnalysis(firstEvt.event_id, 'investigate', false);
        }
      } catch (err: any) {
        console.error('Initial load error:', err);
      } finally {
        setLoading(false);
      }
    };
    initApp();
  }, [executeAnalysis]);

  // Handle Event selection from search / dropdown
  const handleSelectEvent = (eventId: string) => {
    setActiveEventId(eventId);
    executeAnalysis(eventId, activeMode, false);
  };

  // Handle Entity selection from search
  const handleSelectEntity = async (entityName: string) => {
    try {
      setLoading(true);
      setLoadingMessage(`Finding incidents linked to ${entityName}...`);
      const events = await getEntityEvents(entityName, 5);
      if (events && events.length > 0) {
        const topEvent = events[0];
        setActiveEventId(topEvent.event_id);
        showToast(`Loaded "${entityName}" incident: ${topEvent.title}`);
        await executeAnalysis(topEvent.event_id, activeMode, false);
      } else {
        // Inspect node evidence directly
        const ev = await getNodeEvidence(entityName);
        setNodeEvidence(ev);
        setEdgeEvidence(null);
        setIsDrawerOpen(true);
      }
    } catch (err: any) {
      console.error('Entity select error:', err);
      showToast(err.message || `Failed to fetch events for ${entityName}`);
    } finally {
      setLoading(false);
    }
  };

  // Handle Connect Dots execution
  const handleConnect = async (srcId: string, tgtId: string, explainVal: boolean = true) => {
    try {
      setLoading(true);
      setActiveMode('connect');
      setLoadingMessage('Finding shortest causal path between events & synthesizing explanation...');
      setNodeEvidence(null);
      setEdgeEvidence(null);

      const res = await connectTheDots(srcId, tgtId, explainVal);
      setGraphData(res.graph || { nodes: [], links: [] });
      setConnectBriefing(res.explanation);
      setIsDrawerOpen(true);

      if (!res.connection?.found) {
        showToast('No evidence-backed causal path found between these events.');
      } else {
        showToast(`Path discovered! Length: ${res.connection.path_length} hops.`);
      }
    } catch (err: any) {
      console.error('Connect dots error:', err);
      showToast(err.message || 'Failed to connect events.');
    } finally {
      setLoading(false);
    }
  };

  // Handle Node Click -> inspect node evidence
  const handleNodeClick = async (node: GraphNode) => {
    try {
      const nodeId = String(node.id);
      const res = await getNodeEvidence(nodeId);
      setNodeEvidence(res);
      setEdgeEvidence(null);
      setIsDrawerOpen(true);
    } catch (err) {
      console.error('Node click evidence error:', err);
    }
  };

  // Handle Link Click -> inspect edge evidence
  const handleLinkClick = async (link: GraphLink) => {
    try {
      const srcId = typeof link.source === 'object' ? String((link.source as any).id) : String(link.source);
      const tgtId = typeof link.target === 'object' ? String((link.target as any).id) : String(link.target);
      const rel = link.relationship || 'EDGE';

      const res = await getEdgeEvidence(srcId, tgtId, rel);
      setEdgeEvidence(res);
      setNodeEvidence(null);
      setIsDrawerOpen(true);
    } catch (err) {
      console.error('Link click evidence error:', err);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        background: 'var(--bg-light)',
      }}
    >
      {/* Frosted Top Bar: Search Bar & Search Button Only */}
      <TopBar
        activeEventId={activeEventId}
        loading={loading}
        onSelectEvent={handleSelectEvent}
        onSelectEntity={handleSelectEntity}
      />

      {/* Main Workspace */}
      <div style={{ flex: 1, display: 'flex', position: 'relative', overflow: 'hidden' }}>
        {/* FalkorDB Canvas */}
        <GraphCanvas
          data={graphData}
          loading={loading}
          loadingMessage={loadingMessage}
          connectStartId={connectStartId}
          onNodeClick={handleNodeClick}
          onLinkClick={handleLinkClick}
          onInvestigateNode={(id, aiExplain) => {
            setActiveEventId(id);
            setActiveMode('investigate');
            executeAnalysis(id, 'investigate', !!aiExplain);
          }}
          onImpactNode={(id, aiExplain) => {
            setActiveEventId(id);
            setActiveMode('impact');
            executeAnalysis(id, 'impact', !!aiExplain);
          }}
          onSetStartNode={(id, title) => {
            setConnectStartId(id);
            showToast(`Origin A set: "${title}". Right-click Target B to Connect.`);
          }}
          onSetTargetNode={(id, _title, aiExplain) => {
            setConnectTargetId(id);
            if (connectStartId) {
              const start = connectStartId;
              setConnectStartId('');
              handleConnect(start, id, aiExplain ?? true);
            } else {
              setIsConnectModalOpen(true);
            }
          }}
        />

        {/* Slide-out Intelligence & Evidence Drawer (Opens on left click of node/edge or AI explain) */}
        <SideDrawer
          isOpen={isDrawerOpen}
          activeMode={activeMode}
          investigationBriefing={investigationBriefing}
          impactBriefing={impactBriefing}
          connectBriefing={connectBriefing}
          edgeEvidence={edgeEvidence}
          nodeEvidence={nodeEvidence}
          onClose={() => setIsDrawerOpen(false)}
          onExploreEvent={(eid) => {
            setActiveEventId(eid);
            executeAnalysis(eid, 'investigate', true);
          }}
        />
      </div>

      {/* Connect Modal */}
      <ConnectModal
        isOpen={isConnectModalOpen}
        defaultStartId={connectStartId || activeEventId}
        defaultTargetId={connectTargetId}
        onClose={() => setIsConnectModalOpen(false)}
        onConnect={handleConnect}
      />

      {/* Toast Alert */}
      {toast && (
        <div
          className="glass-panel-elevated"
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            padding: '12px 18px',
            borderRadius: '12px',
            fontSize: '12.5px',
            color: '#1d1d1f',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            zIndex: 200,
            boxShadow: '0 12px 36px rgba(0, 0, 0, 0.12)',
            borderLeft: '4px solid #1d1d1f',
          }}
        >
          <i className="fa-solid fa-circle-info" style={{ color: '#1d1d1f' }}></i>
          <span>{toast}</span>
        </div>
      )}
    </div>
  );
};

export default App;
