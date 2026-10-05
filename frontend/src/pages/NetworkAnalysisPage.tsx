import React, { useEffect, useState, useMemo, useRef } from 'react';
import {
  Share2,
  RefreshCw,
  Info,
  ArrowRight,
  ArrowDownLeft,
  ArrowUpRight,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Search,
  ShieldAlert,
  Smartphone,
  Globe,
  User,
  CreditCard,
  AlertTriangle,
  Zap,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import type { GraphNode, GraphLink, InflowSourceItem, OutflowDestinationItem } from '../types';
import { RiskBadge } from '../components/common/RiskBadge';

interface SearchSuggestion {
  id: string;
  title: string;
  subtitle: string;
  type: string;
  risk_level: string;
  query_value: string;
}

export const NetworkAnalysisPage: React.FC = () => {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [links, setLinks] = useState<GraphLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFocus, setActiveFocus] = useState<string>('');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [zoom, setZoom] = useState(1);
  const [activeFilter, setActiveFilter] = useState<'ALL' | 'TRANSFER' | 'INFRASTRUCTURE'>('ALL');
  const [hoveredLink, setHoveredLink] = useState<GraphLink | null>(null);

  // Auto-complete suggestions state
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  const fetchGraph = async (focus?: string) => {
    setLoading(true);
    setShowSuggestions(false);
    try {
      const res = await api.getNetworkGraph({
        focus_entity_id: focus ? focus.trim() : undefined,
        max_nodes: 50,
      });
      const returnedNodes: GraphNode[] = res.nodes || [];
      const returnedLinks: GraphLink[] = res.links || [];

      setNodes(returnedNodes);
      setLinks(returnedLinks);
      setActiveFocus(focus || '');

      // Select matching focused node or first node
      if (returnedNodes.length > 0) {
        if (focus) {
          const fLower = focus.toLowerCase();
          const matched = returnedNodes.find(
            (n) =>
              n.id.toLowerCase() === fLower ||
              n.customer_name?.toLowerCase().includes(fLower) ||
              n.label.toLowerCase().includes(fLower) ||
              n.omerta_user_number?.toLowerCase().includes(fLower)
          );
          setSelectedNode(matched || returnedNodes[0]);
        } else if (!selectedNode || !returnedNodes.some((n) => n.id === selectedNode.id)) {
          setSelectedNode(returnedNodes[0]);
        }
      } else {
        setSelectedNode(null);
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

  // Debounced live search suggestions
  useEffect(() => {
    if (!searchTerm || searchTerm.trim().length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    const timer = setTimeout(async () => {
      setLoadingSuggestions(true);
      try {
        const results = await api.getNetworkSearchSuggestions(searchTerm.trim());
        setSuggestions(results || []);
        setShowSuggestions(true);
      } catch (err) {
        console.error('Failed to load search suggestions', err);
      } finally {
        setLoadingSuggestions(false);
      }
    }, 150);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Click outside listener for suggestions dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setShowSuggestions(false);
    if (searchTerm.trim()) {
      fetchGraph(searchTerm.trim());
    } else {
      fetchGraph();
    }
  };

  const handleSelectSuggestion = (suggestion: SearchSuggestion) => {
    setSearchTerm(suggestion.query_value);
    setShowSuggestions(false);
    fetchGraph(suggestion.query_value);
  };

  const handleQuickPreset = (query: string) => {
    setSearchTerm(query);
    setShowSuggestions(false);
    fetchGraph(query);
  };

  // Node position layout calculation (deterministic layout)
  const nodePosMap = useMemo(() => {
    const map = new Map<string, { cx: number; cy: number }>();
    if (nodes.length === 0) return map;

    // Check if we have a central focus
    const focusNodeId = selectedNode?.id || (nodes.length > 0 ? nodes[0].id : null);
    
    // Categorize nodes relative to focus
    const focusNode = nodes.find((n) => n.id === focusNodeId);
    const otherNodes = nodes.filter((n) => n.id !== focusNodeId);

    if (focusNode) {
      map.set(focusNode.id, { cx: 450, cy: 300 });

      // Identify inbound senders, outbound recipients, and infrastructure
      const inboundSources = new Set(
        links
          .filter((l) => l.target === focusNode.id && l.type === 'TRANSFER')
          .map((l) => l.source)
      );
      const outboundTargets = new Set(
        links
          .filter((l) => l.source === focusNode.id && l.type === 'TRANSFER')
          .map((l) => l.target)
      );

      const leftNodes = otherNodes.filter((n) => inboundSources.has(n.id));
      const rightNodes = otherNodes.filter((n) => outboundTargets.has(n.id) && !inboundSources.has(n.id));
      const remainingNodes = otherNodes.filter((n) => !inboundSources.has(n.id) && !outboundTargets.has(n.id));

      // Place Left Nodes (Inflow sources)
      leftNodes.forEach((n, idx) => {
        const step = leftNodes.length > 1 ? (idx / (leftNodes.length - 1 || 1)) * 340 - 170 : 0;
        map.set(n.id, { cx: 200 - (idx % 2 === 0 ? 30 : 0), cy: 300 + step });
      });

      // Place Right Nodes (Outflow destinations)
      rightNodes.forEach((n, idx) => {
        const step = rightNodes.length > 1 ? (idx / (rightNodes.length - 1 || 1)) * 340 - 170 : 0;
        map.set(n.id, { cx: 700 + (idx % 2 === 0 ? 30 : 0), cy: 300 + step });
      });

      // Place remaining nodes in orbit
      remainingNodes.forEach((n, idx) => {
        const angle = (idx / (remainingNodes.length || 1)) * 2 * Math.PI;
        const radius = n.type === 'DEVICE' ? 180 : n.type === 'IP_ADDRESS' ? 260 : 220;
        const cx = 450 + radius * Math.cos(angle);
        const cy = 300 + radius * Math.sin(angle);
        map.set(n.id, { cx, cy });
      });
    } else {
      nodes.forEach((n, idx) => {
        const angle = (idx / (nodes.length || 1)) * 2 * Math.PI;
        const radius = 220 + (idx % 2 === 0 ? 35 : -35);
        map.set(n.id, {
          cx: 450 + radius * Math.cos(angle),
          cy: 300 + radius * Math.sin(angle),
        });
      });
    }

    return map;
  }, [nodes, links, selectedNode?.id]);

  const filteredLinks = useMemo(() => {
    if (activeFilter === 'TRANSFER') {
      return links.filter((l) => l.type === 'TRANSFER');
    }
    if (activeFilter === 'INFRASTRUCTURE') {
      return links.filter((l) => l.type === 'USED_DEVICE' || l.type === 'CONNECTED_IP');
    }
    return links;
  }, [links, activeFilter]);

  const getNodeColor = (type: string, risk?: string) => {
    if (risk === 'CRITICAL') return '#ef4444';
    if (risk === 'HIGH') return '#f97316';
    if (type === 'ACCOUNT') return '#0284c7';
    if (type === 'DEVICE') return '#9333ea';
    if (type === 'IP_ADDRESS') return '#d97706';
    return '#64748b';
  };

  const formatCurrency = (amt?: number, curr = 'EGP') => {
    if (amt === undefined || amt === null) return `0.00 ${curr}`;
    return `${Number(amt).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${curr}`;
  };

  // Extract risk factors / diagnostics safely
  const selectedRiskFactors: string[] = useMemo(() => {
    if (!selectedNode) return [];
    const details = selectedNode.details || {};
    return Array.isArray(details.risk_factors) ? details.risk_factors : [];
  }, [selectedNode]);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
            <Share2 className="h-6 w-6 text-sky-600 dark:text-cyan-400" />
            <span>Financial Crime & Multi-Hop Network Topology</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Real-time visual relationship graph tracing inbound money sources, outbound funds routing, shared hardware IDs, and AML syndicate clusters.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => fetchGraph(activeFocus)}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors shadow-sm"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-sky-500 dark:text-cyan-400' : ''}`} />
            <span>Refresh Topology</span>
          </button>
        </div>
      </div>

      {/* Investigation Search Bar & Presets */}
      <div className="omerta-card p-4 space-y-3">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <div ref={searchContainerRef} className="relative w-full md:w-auto flex-1 max-w-2xl">
            <form onSubmit={handleSearch} className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onFocus={() => {
                    if (suggestions.length > 0) setShowSuggestions(true);
                  }}
                  placeholder="Search any Customer (e.g. Abdelrahman, Mohamed El-Sayed), Omerta ID, Account (ACC-0001), Device, or IP..."
                  className="w-full pl-9 pr-8 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-xs text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:border-sky-500 dark:focus:border-cyan-400"
                />
                {searchTerm && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchTerm('');
                      setSuggestions([]);
                      setShowSuggestions(false);
                      fetchGraph('');
                    }}
                    className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600 dark:hover:text-white"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
              <button
                type="submit"
                className="px-4 py-2 bg-sky-600 dark:bg-sky-500/20 text-white dark:text-cyan-300 hover:bg-sky-700 dark:hover:bg-sky-500/30 border border-transparent dark:border-sky-500/40 text-xs font-bold rounded-lg shadow-sm transition-colors shrink-0"
              >
                Investigate
              </button>
            </form>

            {/* Google-like Live Search Suggestions Dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute left-0 right-0 top-full mt-1.5 z-50 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xl overflow-hidden max-h-80 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800 animate-in fade-in slide-in-from-top-1 duration-150">
                <div className="p-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-slate-50 dark:bg-slate-900/60 flex items-center justify-between">
                  <span>Matched System Entities ({suggestions.length})</span>
                  {loadingSuggestions && <RefreshCw className="h-3 w-3 animate-spin text-cyan-400" />}
                </div>
                {suggestions.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSelectSuggestion(item)}
                    className="w-full text-left p-3 hover:bg-slate-50 dark:hover:bg-slate-800/80 transition-colors flex items-center justify-between gap-3 group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 group-hover:bg-sky-100 dark:group-hover:bg-sky-950 group-hover:text-sky-600 dark:group-hover:text-cyan-400 transition-colors shrink-0">
                        {item.type === 'ACCOUNT' && <User className="h-4 w-4" />}
                        {item.type === 'DEVICE' && <Smartphone className="h-4 w-4" />}
                        {item.type === 'IP_ADDRESS' && <Globe className="h-4 w-4" />}
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-900 dark:text-white truncate group-hover:text-sky-600 dark:group-hover:text-cyan-400 transition-colors">
                          {item.title}
                        </p>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                          {item.subtitle}
                        </p>
                      </div>
                    </div>
                    <div className="shrink-0 flex items-center gap-2">
                      <RiskBadge level={item.risk_level} size="sm" />
                      <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-sky-500 dark:group-hover:text-cyan-400 group-hover:translate-x-0.5 transition-transform" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Layer Filters */}
          <div className="flex items-center gap-1.5 p-1 bg-slate-100 dark:bg-slate-900/80 rounded-lg border border-slate-200 dark:border-slate-800 text-xs font-medium">
            <button
              onClick={() => setActiveFilter('ALL')}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeFilter === 'ALL'
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-xs font-bold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              All Links ({links.length})
            </button>
            <button
              onClick={() => setActiveFilter('TRANSFER')}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeFilter === 'TRANSFER'
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-xs font-bold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Money Flows ({links.filter((l) => l.type === 'TRANSFER').length})
            </button>
            <button
              onClick={() => setActiveFilter('INFRASTRUCTURE')}
              className={`px-3 py-1 rounded-md transition-colors ${
                activeFilter === 'INFRASTRUCTURE'
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-xs font-bold'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              Device & IP Bindings ({links.filter((l) => l.type !== 'TRANSFER').length})
            </button>
          </div>
        </div>

        {/* Quick Investigation Presets */}
        <div className="flex items-center gap-2 text-xs flex-wrap pt-1 border-t border-slate-100 dark:border-slate-800/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 flex items-center gap-1">
            <Zap className="h-3 w-3 text-amber-500" />
            Quick Presets:
          </span>
          <button
            onClick={() => handleQuickPreset('Mohamed El-Sayed')}
            className="px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800/80 hover:bg-sky-50 dark:hover:bg-sky-950/40 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 text-[11px] font-semibold transition-colors"
          >
            👤 Mohamed El-Sayed (ACC-0001)
          </button>
          <button
            onClick={() => handleQuickPreset('Kareem Fathy')}
            className="px-2.5 py-1 rounded-md bg-rose-50 dark:bg-rose-950/40 hover:bg-rose-100 dark:hover:bg-rose-900/60 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 text-[11px] font-semibold transition-colors"
          >
            🚨 Kareem Fathy [Mule Node ACC-7001]
          </button>
          <button
            onClick={() => handleQuickPreset('DEV-0098')}
            className="px-2.5 py-1 rounded-md bg-purple-50 dark:bg-purple-950/40 hover:bg-purple-100 dark:hover:bg-purple-900/60 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800 text-[11px] font-semibold transition-colors"
          >
            📱 DEV-0098 [Shared Emulated Device]
          </button>
          <button
            onClick={() => handleQuickPreset('Layla Hassan')}
            className="px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800/80 hover:bg-sky-50 dark:hover:bg-sky-950/40 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 text-[11px] font-semibold transition-colors"
          >
            👤 Layla Hassan (ACC-2001)
          </button>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* SVG Canvas Area (8 cols) */}
        <div className="lg:col-span-8 omerta-card overflow-hidden relative min-h-[600px] bg-slate-900 dark:bg-gradient-to-b dark:from-[#0a0f1d] dark:to-[#070b14] flex flex-col border-slate-300 dark:border-slate-800">
          {/* Canvas Top Bar */}
          <div className="p-3 border-b border-slate-800 flex items-center justify-between z-10 bg-slate-900/90 backdrop-blur-sm">
            {/* Legend */}
            <div className="flex items-center gap-3.5 text-[11px] text-slate-300 flex-wrap font-medium">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-sky-500 shadow-sm shadow-sky-500/50" />
                <span>Bank Account</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-purple-500 shadow-sm shadow-purple-500/50" />
                <span>Device</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" />
                <span>IP Endpoint</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500 animate-pulse shadow-sm shadow-rose-500/50" />
                <span className="font-bold text-rose-400">High / Critical Risk</span>
              </div>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center gap-1 p-1 rounded-lg bg-slate-800 border border-slate-700">
              <button
                onClick={() => setZoom((z) => Math.min(2.0, z + 0.15))}
                className="p-1 text-slate-200 hover:text-white rounded hover:bg-slate-700"
                title="Zoom In"
              >
                <ZoomIn className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setZoom((z) => Math.max(0.5, z - 0.15))}
                className="p-1 text-slate-200 hover:text-white rounded hover:bg-slate-700"
                title="Zoom Out"
              >
                <ZoomOut className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setZoom(1)}
                className="p-1 text-slate-200 hover:text-white rounded hover:bg-slate-700"
                title="Reset Zoom"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* SVG Body */}
          <div className="relative flex-1 flex items-center justify-center p-4">
            {loading ? (
              <div className="text-center text-slate-400">
                <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-2 text-sky-400 dark:text-cyan-400" />
                <p className="text-sm font-semibold">Tracing multi-hop relationships & fund vectors...</p>
              </div>
            ) : nodes.length === 0 ? (
              <div className="text-center text-slate-400 max-w-sm">
                <Info className="h-8 w-8 mx-auto mb-2 text-slate-500" />
                <p className="text-sm font-semibold">No entities matching &ldquo;{activeFocus}&rdquo;</p>
                <p className="text-xs text-slate-500 mt-1">Try searching by Customer Name (e.g. Mohamed El-Sayed, Abdelrahman) or Account ID (ACC-0001).</p>
              </div>
            ) : (
              <svg
                viewBox="0 0 900 600"
                className="w-full h-full cursor-grab active:cursor-grabbing transition-transform duration-150"
                style={{ transform: `scale(${zoom})` }}
              >
                <defs>
                  {/* Standard Transfer Arrow */}
                  <marker
                    id="arrow-cyan"
                    viewBox="0 0 10 10"
                    refX="22"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
                  </marker>
                  {/* Suspicious / High-Risk Arrow */}
                  <marker
                    id="arrow-suspicious"
                    viewBox="0 0 10 10"
                    refX="22"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                  </marker>
                  {/* Device Binding Arrow */}
                  <marker
                    id="arrow-device"
                    viewBox="0 0 10 10"
                    refX="20"
                    refY="5"
                    markerWidth="5"
                    markerHeight="5"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#a855f7" />
                  </marker>
                  {/* IP Arrow */}
                  <marker
                    id="arrow-ip"
                    viewBox="0 0 10 10"
                    refX="20"
                    refY="5"
                    markerWidth="5"
                    markerHeight="5"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
                  </marker>
                </defs>

                {/* Grid backdrop styling */}
                <pattern id="grid-pattern" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="0.5" opacity="0.3" />
                </pattern>
                <rect width="900" height="600" fill="url(#grid-pattern)" />

                {/* Graph Links */}
                {filteredLinks.map((link, idx) => {
                  const sPos = nodePosMap.get(link.source);
                  const tPos = nodePosMap.get(link.target);
                  if (!sPos || !tPos) return null;

                  const isHovered = hoveredLink === link;
                  const isSuspicious = link.is_suspicious;
                  const strokeColor = isSuspicious
                    ? '#ef4444'
                    : link.type === 'TRANSFER'
                    ? '#38bdf8'
                    : link.type === 'USED_DEVICE'
                    ? '#a855f7'
                    : '#f59e0b';

                  const markerId = isSuspicious
                    ? 'url(#arrow-suspicious)'
                    : link.type === 'TRANSFER'
                    ? 'url(#arrow-cyan)'
                    : link.type === 'USED_DEVICE'
                    ? 'url(#arrow-device)'
                    : 'url(#arrow-ip)';

                  // Midpoint for link label
                  const midX = (sPos.cx + tPos.cx) / 2;
                  const midY = (sPos.cy + tPos.cy) / 2;

                  return (
                    <g
                      key={idx}
                      onMouseEnter={() => setHoveredLink(link)}
                      onMouseLeave={() => setHoveredLink(null)}
                      className="cursor-pointer group"
                    >
                      <line
                        x1={sPos.cx}
                        y1={sPos.cy}
                        x2={tPos.cx}
                        y2={tPos.cy}
                        stroke={strokeColor}
                        strokeWidth={isHovered ? 3.5 : isSuspicious ? 2.5 : 1.5}
                        strokeDasharray={
                          link.type === 'CONNECTED_IP'
                            ? '4,4'
                            : link.type === 'USED_DEVICE'
                            ? '6,3'
                            : undefined
                        }
                        markerEnd={markerId}
                        opacity={isHovered ? 1 : 0.85}
                      />

                      {/* Link Amount or Type Label on Money Transfers */}
                      {link.type === 'TRANSFER' && link.amount && (
                        <g transform={`translate(${midX}, ${midY - 8})`}>
                          <rect
                            x={-42}
                            y={-10}
                            width={84}
                            height={18}
                            rx={4}
                            fill="#0f172a"
                            stroke={isSuspicious ? '#ef4444' : '#0284c7'}
                            strokeWidth={1}
                            opacity={0.9}
                          />
                          <text
                            textAnchor="middle"
                            y={3}
                            fill={isSuspicious ? '#fca5a5' : '#7dd3fc'}
                            fontSize={9}
                            fontWeight="bold"
                            fontFamily="monospace"
                          >
                            {link.label}
                          </text>
                        </g>
                      )}
                    </g>
                  );
                })}

                {/* Graph Nodes */}
                {nodes.map((node) => {
                  const pos = nodePosMap.get(node.id) || { cx: 450, cy: 300 };
                  const isSelected = selectedNode?.id === node.id;
                  const isHighRisk = node.risk_level === 'HIGH' || node.risk_level === 'CRITICAL';
                  const nodeColor = getNodeColor(node.type, node.risk_level);

                  return (
                    <g
                      key={node.id}
                      onClick={() => setSelectedNode(node)}
                      className="cursor-pointer transition-transform hover:scale-110"
                    >
                      {/* Pulsing ring for critical/high risk */}
                      {isHighRisk && (
                        <circle
                          cx={pos.cx}
                          cy={pos.cy}
                          r={28}
                          fill="none"
                          stroke="#ef4444"
                          strokeWidth={2}
                          className="animate-ping origin-center opacity-60"
                        />
                      )}

                      {/* Selection Highlight Ring */}
                      {isSelected && (
                        <circle
                          cx={pos.cx}
                          cy={pos.cy}
                          r={25}
                          fill="none"
                          stroke="#00d2ff"
                          strokeWidth={2.5}
                          strokeDasharray="4,4"
                          className="animate-spin origin-center"
                          style={{ animationDuration: '8s' }}
                        />
                      )}

                      {/* Node Outer Halo */}
                      <circle
                        cx={pos.cx}
                        cy={pos.cy}
                        r={18}
                        fill={nodeColor}
                        opacity={0.25}
                      />

                      {/* Node Core Circle */}
                      <circle
                        cx={pos.cx}
                        cy={pos.cy}
                        r={14}
                        fill={nodeColor}
                        stroke="#0a0f1d"
                        strokeWidth={2.5}
                      />

                      {/* Node Primary Identifier */}
                      <text
                        x={pos.cx}
                        y={pos.cy + 24}
                        textAnchor="middle"
                        fill="#ffffff"
                        fontSize={10}
                        fontWeight="bold"
                        fontFamily="monospace"
                      >
                        {node.id}
                      </text>

                      {/* Node Secondary Label (e.g. Customer Name) */}
                      {node.customer_name && (
                        <text
                          x={pos.cx}
                          y={pos.cy + 36}
                          textAnchor="middle"
                          fill="#94a3b8"
                          fontSize={9}
                          fontWeight="medium"
                        >
                          {node.customer_name}
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            )}
          </div>

          {/* Canvas Bottom Stats Bar */}
          <div className="px-4 py-2 bg-slate-900/90 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
            <div>
              Active View: <span className="text-white font-bold">{nodes.length} Entities</span>,{' '}
              <span className="text-white font-bold">{filteredLinks.length} Connections</span>
            </div>
            {activeFocus && (
              <div className="text-cyan-400 font-mono">
                Focus Anchor: <span className="font-bold">{activeFocus}</span>
              </div>
            )}
          </div>
        </div>

        {/* Selected Entity Deep Inspector (4 cols) */}
        <div className="lg:col-span-4 omerta-card p-5 space-y-4 flex flex-col justify-between max-h-[750px] overflow-y-auto">
          <div className="space-y-4">
            {/* Inspector Header */}
            <div className="pb-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-2">
                  <Info className="h-4 w-4 text-sky-600 dark:text-cyan-400" />
                  <span>Entity Deep Inspector</span>
                </h3>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                  Topology, fund routing, and AML signals
                </p>
              </div>

              {selectedNode && (
                <button
                  onClick={() => fetchGraph(selectedNode.id)}
                  title="Re-center graph on this entity"
                  className="p-1.5 rounded-md bg-slate-100 dark:bg-slate-800 hover:bg-sky-50 dark:hover:bg-sky-900 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {selectedNode ? (
              <div className="space-y-4 text-xs">
                {/* Node Identity Card */}
                <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">
                      {selectedNode.type} IDENTIFIER
                    </span>
                    <RiskBadge level={selectedNode.risk_level || 'LOW'} size="sm" />
                  </div>
                  <p className="text-base font-bold text-slate-900 dark:text-white font-mono flex items-center gap-2">
                    {selectedNode.type === 'ACCOUNT' && <CreditCard className="h-4 w-4 text-sky-500" />}
                    {selectedNode.type === 'DEVICE' && <Smartphone className="h-4 w-4 text-purple-500" />}
                    {selectedNode.type === 'IP_ADDRESS' && <Globe className="h-4 w-4 text-amber-500" />}
                    <span>{selectedNode.id}</span>
                  </p>

                  {/* Customer Details if Account */}
                  {selectedNode.customer_name && (
                    <div className="pt-2 border-t border-slate-200 dark:border-slate-800/80 space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 dark:text-slate-400 flex items-center gap-1 font-medium">
                          <User className="h-3 w-3 text-slate-400" />
                          Account Holder:
                        </span>
                        <span className="text-slate-900 dark:text-white font-bold">
                          {selectedNode.customer_name}
                        </span>
                      </div>
                      {selectedNode.omerta_user_number && selectedNode.omerta_user_number !== 'N/A' && (
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-500 dark:text-slate-400 font-medium">Omerta User ID:</span>
                          <span className="text-sky-600 dark:text-cyan-400 font-mono font-bold">
                            {selectedNode.omerta_user_number}
                          </span>
                        </div>
                      )}
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 dark:text-slate-400 font-medium">Current Balance:</span>
                        <span className="text-emerald-600 dark:text-emerald-400 font-bold font-mono">
                          {formatCurrency(selectedNode.balance, selectedNode.currency)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Inflow vs Outflow Fund Summary (If Account) */}
                {selectedNode.type === 'ACCOUNT' && (
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/40">
                      <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-400 flex items-center gap-1 uppercase">
                        <ArrowDownLeft className="h-3 w-3" />
                        Total Inflow
                      </span>
                      <p className="text-xs font-bold text-emerald-900 dark:text-emerald-300 font-mono mt-0.5">
                        {formatCurrency(selectedNode.inflow_total ?? selectedNode.details?.inflow_total, selectedNode.currency)}
                      </p>
                      <span className="text-[10px] text-emerald-600 dark:text-emerald-400/80">
                        {selectedNode.inflow_count ?? selectedNode.details?.inflow_count ?? 0} transfer(s)
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-sky-50 dark:bg-sky-950/20 border border-sky-200 dark:border-sky-800/40">
                      <span className="text-[10px] font-bold text-sky-700 dark:text-cyan-400 flex items-center gap-1 uppercase">
                        <ArrowUpRight className="h-3 w-3" />
                        Total Outflow
                      </span>
                      <p className="text-xs font-bold text-sky-900 dark:text-cyan-300 font-mono mt-0.5">
                        {formatCurrency(selectedNode.outflow_total ?? selectedNode.details?.outflow_total, selectedNode.currency)}
                      </p>
                      <span className="text-[10px] text-sky-600 dark:text-cyan-400/80">
                        {selectedNode.outflow_count ?? selectedNode.details?.outflow_count ?? 0} transfer(s)
                      </span>
                    </div>
                  </div>
                )}

                {/* 1. Money Received Breakdown ("From Where Got Money") */}
                {selectedNode.type === 'ACCOUNT' && (
                  <div className="space-y-2">
                    <h4 className="text-[11px] font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                        <ArrowDownLeft className="h-3.5 w-3.5" />
                        Inflow Sources (&ldquo;From Where Got Money&rdquo;)
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {(selectedNode.inflow_sources || selectedNode.details?.inflow_sources || []).length} sources
                      </span>
                    </h4>

                    {((selectedNode.inflow_sources || selectedNode.details?.inflow_sources || []) as InflowSourceItem[]).length > 0 ? (
                      <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                        {((selectedNode.inflow_sources || selectedNode.details?.inflow_sources || []) as InflowSourceItem[]).map((inf, i) => (
                          <div
                            key={i}
                            onClick={() => fetchGraph(inf.sender_account)}
                            className="p-2 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-sky-400 dark:hover:border-cyan-500 cursor-pointer transition-colors"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-900 dark:text-white font-mono text-[11px]">
                                {inf.sender_account}
                              </span>
                              <span className="font-bold text-emerald-600 dark:text-emerald-400 font-mono">
                                +{formatCurrency(inf.amount, inf.currency)}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                              <span>Sender: {inf.sender_name}</span>
                              <span className="font-mono">{inf.timestamp ? new Date(inf.timestamp).toLocaleDateString() : 'Confirmed'}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-dashed border-slate-200 dark:border-slate-800 text-center text-slate-400 text-[11px] space-y-1">
                        <p className="font-semibold text-slate-500 dark:text-slate-300">No inbound peer transfers yet</p>
                        <p className="text-[10px]">Opening balance was initialized upon registration.</p>
                      </div>
                    )}
                  </div>
                )}

                {/* 2. Money Sent Breakdown ("Where Money Went") */}
                {selectedNode.type === 'ACCOUNT' && (
                  <div className="space-y-2">
                    <h4 className="text-[11px] font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center justify-between">
                      <span className="flex items-center gap-1.5 text-sky-600 dark:text-cyan-400">
                        <ArrowUpRight className="h-3.5 w-3.5" />
                        Outflow Destinations (&ldquo;Where Money Went&rdquo;)
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {(selectedNode.outflow_destinations || selectedNode.details?.outflow_destinations || []).length} destinations
                      </span>
                    </h4>

                    {((selectedNode.outflow_destinations || selectedNode.details?.outflow_destinations || []) as OutflowDestinationItem[]).length > 0 ? (
                      <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                        {((selectedNode.outflow_destinations || selectedNode.details?.outflow_destinations || []) as OutflowDestinationItem[]).map((outf, i) => (
                          <div
                            key={i}
                            onClick={() => fetchGraph(outf.recipient_account)}
                            className="p-2 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-sky-400 dark:hover:border-cyan-500 cursor-pointer transition-colors"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-900 dark:text-white font-mono text-[11px]">
                                {outf.recipient_account}
                              </span>
                              <span className="font-bold text-sky-600 dark:text-cyan-400 font-mono">
                                -{formatCurrency(outf.amount, outf.currency)}
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 mt-0.5">
                              <span>Recipient: {outf.recipient_name}</span>
                              <span className="font-mono">{outf.timestamp ? new Date(outf.timestamp).toLocaleDateString() : 'Confirmed'}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-dashed border-slate-200 dark:border-slate-800 text-center text-slate-400 text-[11px]">
                        No outbound peer transfers dispatched
                      </div>
                    )}
                  </div>
                )}

                {/* 3. Device / IP Node Specific Attributes */}
                {selectedNode.type !== 'ACCOUNT' && (
                  <div className="space-y-2">
                    <h4 className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Infrastructure Attributes
                    </h4>
                    {Object.entries(selectedNode.details || {}).map(([k, v]) => {
                      if (k === 'risk_factors' || k === 'inflow_sources' || k === 'outflow_destinations') return null;
                      return (
                        <div
                          key={k}
                          className="flex justify-between p-2 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800"
                        >
                          <span className="text-slate-600 dark:text-slate-400 capitalize font-medium">
                            {k.replace(/_/g, ' ')}:
                          </span>
                          <span className="text-slate-900 dark:text-white font-semibold font-mono">
                            {Array.isArray(v) ? v.join(', ') : String(v)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* 4. AML Risk Diagnostics & Triggers */}
                {selectedRiskFactors.length > 0 && (
                  <div className="space-y-2 pt-1">
                    <h4 className="text-[11px] font-bold text-rose-600 dark:text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      AML Risk Diagnostics ({selectedRiskFactors.length})
                    </h4>
                    <div className="space-y-1.5">
                      {selectedRiskFactors.map((factor, idx) => (
                        <div
                          key={idx}
                          className="p-2 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 text-[11px] text-rose-800 dark:text-rose-300 flex items-start gap-1.5"
                        >
                          <ShieldAlert className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
                          <span>{factor}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-slate-400 text-xs">
                Click any node on the graph canvas or search for any user/customer to inspect relationships and fund flows.
              </div>
            )}
          </div>

          {/* Action Button */}
          {selectedNode && (
            <div className="pt-3 border-t border-slate-200 dark:border-slate-800">
              <button
                onClick={() => fetchGraph(selectedNode.id)}
                className="w-full py-2.5 px-3 rounded-lg bg-sky-600 dark:bg-sky-500/20 text-white dark:text-cyan-300 hover:bg-sky-700 dark:hover:bg-sky-500/30 border border-transparent dark:border-sky-500/40 text-xs font-bold flex items-center justify-center gap-2 shadow-sm transition-colors"
              >
                <span>Re-center Graph on {selectedNode.id}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
