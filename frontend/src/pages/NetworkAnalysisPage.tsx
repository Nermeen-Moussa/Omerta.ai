import React, { useEffect, useState } from 'react';
import {
  Share2,
  RefreshCw,
  Info,
  ArrowRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
} from 'lucide-react';
import { api } from '../api/client';
import type { GraphNode, GraphLink } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';

export const NetworkAnalysisPage: React.FC = () => {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [focusId, setFocusId] = useState('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [zoom, setZoom] = useState(1);

  const fetchGraph = async (focus?: string) => {
    setLoading(true);
    try {
      const res = await api.getNetworkGraph({
        focus_entity_id: focus || undefined,
        max_nodes: 45,
      });
      setNodes(res.nodes || []);
      setLinks(res.links || []);
      if (res.nodes?.length > 0 && !selectedNode) {
        setSelectedNode(res.nodes[0]);
      }
    } catch (err) {
      console.error('Failed to load network graph', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGraph();
  }, []);

  const handleSearchFocus = (e: React.FormEvent) => {
    e.preventDefault();
    fetchGraph(focusId.trim());
  };

  // Node position layout calculation (deterministic circle / cluster layout)
  const getNodePos = (idx: number, total: number) => {
    const angle = (idx / (total || 1)) * 2 * Math.PI;
    const radius = 220 + (idx % 2 === 0 ? 40 : -40);
    const cx = 450 + radius * Math.cos(angle);
    const cy = 300 + radius * Math.sin(angle);
    return { cx, cy };
  };

  const nodePosMap = new Map<string, { cx: number; cy: number }>();
  nodes.forEach((n, idx) => {
    nodePosMap.set(n.id, getNodePos(idx, nodes.length));
  });

  const getNodeColor = (type: string, risk?: string) => {
    if (risk === 'HIGH' || risk === 'CRITICAL') return '#ef4444';
    if (type === 'ACCOUNT') return '#38bdf8';
    if (type === 'DEVICE') return '#a855f7';
    if (type === 'IP_ADDRESS') return '#f59e0b';
    return '#64748b';
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
            <Share2 className="h-6 w-6 text-sky-600 dark:text-cyan-400" />
            Financial Crime Network & Relationship Analysis
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Visual relationship graph tracing shared devices, common IP endpoints, and multi-hop fund routing.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => fetchGraph(focusId)}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
            <span>Reset Topology</span>
          </button>
        </div>
      </div>

      {/* Focus Search & Legend Bar */}
      <div className="omerta-card p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <form onSubmit={handleSearchFocus} className="flex items-center gap-2 w-full md:w-96">
          <input
            type="text"
            value={focusId}
            onChange={(e) => setFocusId(e.target.value)}
            placeholder="Focus on Account (ACC-0001) or Device (DEV-0001)..."
            className="w-full px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
          />
          <button
            type="submit"
            className="px-3.5 py-2 bg-sky-50 dark:bg-sky-500/20 text-sky-800 dark:text-cyan-300 hover:bg-sky-100 dark:hover:bg-sky-500/30 border border-sky-300 dark:border-sky-500/40 text-xs font-bold rounded-lg shadow-xs"
          >
            Trace
          </button>
        </form>

        {/* Legend */}
        <div className="flex items-center gap-4 text-xs text-slate-700 dark:text-slate-300 flex-wrap font-medium">
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-sky-500" />
            <span>Bank Account</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-purple-500" />
            <span>Device</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-amber-500" />
            <span>IP Endpoint</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-rose-600 animate-pulse" />
            <span className="font-bold text-rose-700 dark:text-rose-400">High-Risk Node</span>
          </div>
        </div>
      </div>

      {/* Main Interactive Graph Canvas Frame */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* SVG Canvas (3 cols) */}
        <div className="lg:col-span-3 omerta-card overflow-hidden relative min-h-[550px] bg-slate-900 dark:bg-gradient-to-b dark:from-[#0a0f1d] dark:to-[#070b14] flex items-center justify-center border-slate-300 dark:border-slate-800">
          {/* Zoom controls */}
          <div className="absolute top-4 left-4 z-10 flex items-center gap-1.5 p-1.5 rounded-lg bg-slate-800/90 dark:bg-slate-900/80 border border-slate-700 dark:border-slate-800 shadow-md">
            <button
              onClick={() => setZoom((z) => Math.min(1.8, z + 0.15))}
              className="p-1.5 text-slate-200 hover:text-white rounded hover:bg-slate-700"
              title="Zoom In"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
            <button
              onClick={() => setZoom((z) => Math.max(0.6, z - 0.15))}
              className="p-1.5 text-slate-200 hover:text-white rounded hover:bg-slate-700"
              title="Zoom Out"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <button
              onClick={() => setZoom(1)}
              className="p-1.5 text-slate-200 hover:text-white rounded hover:bg-slate-700"
              title="Reset Zoom"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          </div>

          {loading ? (
            <div className="text-center text-slate-300 dark:text-slate-400">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2 text-sky-400 dark:text-cyan-400" />
              <span>Projecting entity graph topology...</span>
            </div>
          ) : (
            <svg
              viewBox="0 0 900 600"
              className="w-full h-full cursor-grab active:cursor-grabbing transition-transform duration-200"
              style={{ transform: `scale(${zoom})` }}
            >
              <defs>
                <marker
                  id="arrow"
                  viewBox="0 0 10 10"
                  refX="18"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
                </marker>
                <marker
                  id="arrow-suspicious"
                  viewBox="0 0 10 10"
                  refX="18"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                </marker>
              </defs>

              {/* Links */}
              {links.map((link, idx) => {
                const sPos = nodePosMap.get(link.source);
                const tPos = nodePosMap.get(link.target);
                if (!sPos || !tPos) return null;
                return (
                  <g key={idx}>
                    <line
                      x1={sPos.cx}
                      y1={sPos.cy}
                      x2={tPos.cx}
                      y2={tPos.cy}
                      stroke={link.is_suspicious ? '#ef4444' : '#475569'}
                      strokeWidth={link.is_suspicious ? 2.5 : 1.5}
                      strokeDasharray={link.type === 'CONNECTED_IP' ? '4,4' : undefined}
                      markerEnd={link.is_suspicious ? 'url(#arrow-suspicious)' : 'url(#arrow)'}
                    />
                  </g>
                );
              })}

              {/* Nodes */}
              {nodes.map((node, idx) => {
                const pos = nodePosMap.get(node.id) || getNodePos(idx, nodes.length);
                const isSelected = selectedNode?.id === node.id;
                const nodeColor = getNodeColor(node.type, node.risk_level);

                return (
                  <g
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className="cursor-pointer transition-transform hover:scale-110"
                  >
                    {/* Pulsing ring for high risk */}
                    {(node.risk_level === 'HIGH' || node.risk_level === 'CRITICAL') && (
                      <circle
                        cx={pos.cx}
                        cy={pos.cy}
                        r={24}
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth={1.5}
                        className="animate-ping origin-center opacity-75"
                      />
                    )}

                    {/* Selection highlight ring */}
                    {isSelected && (
                      <circle
                        cx={pos.cx}
                        cy={pos.cy}
                        r={22}
                        fill="none"
                        stroke="#00d2ff"
                        strokeWidth={2.5}
                        strokeDasharray="3,3"
                      />
                    )}

                    {/* Node Core Circle */}
                    <circle
                      cx={pos.cx}
                      cy={pos.cy}
                      r={15}
                      fill={nodeColor}
                      stroke="#0a0f1d"
                      strokeWidth={3}
                    />

                    {/* Node Label Text */}
                    <text
                      x={pos.cx}
                      y={pos.cy + 25}
                      textAnchor="middle"
                      fill="#ffffff"
                      fontSize={10}
                      fontWeight="bold"
                      fontFamily="monospace"
                    >
                      {node.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        {/* Selected Entity Inspector Drawer (1 col) */}
        <div className="omerta-card p-5 space-y-4">
          <div className="pb-3 border-b border-slate-200 dark:border-slate-800">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
              <Info className="h-4 w-4 text-sky-600 dark:text-cyan-400" />
              <span>Entity Inspector</span>
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">Selected entity topology and attributes</p>
          </div>

          {selectedNode ? (
            <div className="space-y-4 text-xs">
              <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5">
                <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-bold">Identifier</span>
                <p className="text-base font-bold text-slate-900 dark:text-white font-mono">{selectedNode.id}</p>
                <div className="flex items-center gap-2 pt-1">
                  <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-semibold text-slate-800 dark:text-slate-300 border border-slate-300 dark:border-slate-700">
                    {selectedNode.type}
                  </span>
                  <RiskBadge level={selectedNode.risk_level || 'LOW'} size="sm" />
                </div>
              </div>

              <div className="space-y-2">
                <h4 className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Attributes</h4>
                {Object.entries(selectedNode.details || {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between p-2 rounded bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800">
                    <span className="text-slate-600 dark:text-slate-400 capitalize font-medium">{k.replace(/_/g, ' ')}:</span>
                    <span className="text-slate-900 dark:text-white font-semibold font-mono">{String(v)}</span>
                  </div>
                ))}
              </div>

              <div className="pt-2">
                <button
                  onClick={() => fetchGraph(selectedNode.id)}
                  className="w-full py-2 px-3 rounded-lg bg-sky-50 dark:bg-sky-500/20 text-sky-800 dark:text-cyan-300 hover:bg-sky-100 dark:hover:bg-sky-500/30 border border-sky-300 dark:border-sky-500/30 text-xs font-bold flex items-center justify-center gap-1.5 shadow-xs"
                >
                  <span>Re-center Graph on this Entity</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ) : (
            <div className="text-center py-10 text-slate-500 dark:text-slate-400 text-xs">
              Click any node on the graph canvas to inspect its relationships and risk flags.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
