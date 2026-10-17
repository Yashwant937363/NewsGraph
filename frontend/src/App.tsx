import React, { useState, useEffect, useCallback } from 'react';
import type {
  GraphData,
  GraphStats,
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
  const [explain, setExplain] = useState<boolean>(false);

  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], links: [] });
  const [stats, setStats] = useState<GraphStats>({
    total_nodes: 0,
    total_edges: 0,
    countries_count: 0,
    companies_count: 0,
    industries_count: 0,
  });

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

  // Helper to calculate basic stats from graph
  const computeStats = (data: GraphData): GraphStats => {
    const nodes = data.nodes || [];
    const links = data.links || [];
    let countries = 0;
    let companies = 0;
    let industries = 0;

    nodes.forEach((n) => {
      const labels = n.labels || [];
      if (labels.includes('Country')) countries++;
      if (labels.includes('Company')) companies++;
      if (labels.includes('Industry')) industries++;
    });

    return {
      total_nodes: nodes.length,
      total_edges: links.length,
      countries_count: countries,
      companies_count: companies,
      industries_count: industries,
    };
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
          setStats(res.stats || computeStats(res.graph));
          setInvestigationBriefing(res.explanation);
          if (explainEnabled && res.explanation) {
            setIsDrawerOpen(true);
          }
        } else if (mode === 'impact') {
          const res = await getImpactRadius(eventId, explainEnabled);
          setGraphData(res.graph || { nodes: [], links: [] });
          setStats(computeStats(res.graph));
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
    executeAnalysis(eventId, activeMode, explain);
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
        await executeAnalysis(topEvent.event_id, activeMode, explain);
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

  // Handle Mode Change (Investigate / Impact / Connect)
  const handleModeChange = (newMode: ActionMode) => {
    setActiveMode(newMode);
    if (activeEventId) {
      executeAnalysis(activeEventId, newMode, explain);
    }
  };

  // Handle Connect Dots execution
  const handleConnect = async (srcId: string, tgtId: string) => {
    try {
      setLoading(true);
      setActiveMode('connect');
      setLoadingMessage('Finding shortest causal path between events...');

      const res = await connectTheDots(srcId, tgtId, explain);
      setGraphData(res.graph || { nodes: [], links: [] });
      setStats(computeStats(res.graph));
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
        background: 'var(--bg-dark)',
      }}
    >
      {/* Frosted Top Bar */}
      <TopBar
        activeEventId={activeEventId}
        activeMode={activeMode}
        explain={explain}
        stats={stats}
        loading={loading}
        onSelectEvent={handleSelectEvent}
        onSelectEntity={handleSelectEntity}
        onModeChange={handleModeChange}
        onExplainChange={setExplain}
        onRunAction={() => executeAnalysis(activeEventId, activeMode, explain)}
        onOpenConnectModal={() => setIsConnectModalOpen(true)}
      />

      {/* Main Workspace */}
      <div style={{ flex: 1, display: 'flex', position: 'relative', overflow: 'hidden' }}>
        {/* FalkorDB Canvas */}
        <GraphCanvas
          data={graphData}
          loading={loading}
          loadingMessage={loadingMessage}
          onNodeClick={handleNodeClick}
          onLinkClick={handleLinkClick}
          onInvestigateNode={(id) => {
            setActiveEventId(id);
            setActiveMode('investigate');
            executeAnalysis(id, 'investigate', explain);
          }}
          onImpactNode={(id) => {
            setActiveEventId(id);
            setActiveMode('impact');
            executeAnalysis(id, 'impact', explain);
          }}
          onSetStartNode={(id, title) => {
            setConnectStartId(id);
            showToast(`Origin A set: "${title}". Right-click Target B to Connect.`);
          }}
          onSetTargetNode={(id) => {
            setConnectTargetId(id);
            if (connectStartId) {
              handleConnect(connectStartId, id);
            } else {
              setIsConnectModalOpen(true);
            }
          }}
        />

        {/* Slide-out Intelligence & Evidence Drawer */}
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
            executeAnalysis(eid, 'investigate', explain);
          }}
        />

        {/* Drawer Toggle Handle (if drawer is closed) */}
        {!isDrawerOpen && (
          <button
            onClick={() => setIsDrawerOpen(true)}
            className="glass-panel"
            style={{
              position: 'absolute',
              top: '20px',
              right: '20px',
              borderRadius: '8px',
              padding: '8px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '12px',
              color: '#93c5fd',
              cursor: 'pointer',
              zIndex: 20,
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
            }}
          >
            <i className="fa-solid fa-sidebar"></i>
            <span>Open Briefing</span>
          </button>
        )}
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
            borderRadius: '10px',
            fontSize: '12.5px',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            zIndex: 200,
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.6)',
            borderLeft: '4px solid var(--accent-blue)',
          }}
        >
          <i className="fa-solid fa-circle-info" style={{ color: 'var(--accent-blue)' }}></i>
          <span>{toast}</span>
        </div>
      )}
    </div>
  );
};

export default App;
