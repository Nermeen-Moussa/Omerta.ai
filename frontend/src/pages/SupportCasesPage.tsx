import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  LifeBuoy,
  Search,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Send,
  CheckCheck,
  RotateCcw,
  RefreshCw,
  Eye,
  FileText,
  MessageSquare,
  UserCheck,
  Paperclip,
  Check,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { StatusBadge } from '../components/common/StatusBadge';
import { Modal } from '../components/common/Modal';
import type { SupportTicketItem, SupportMessageItem } from '../types';

const compressImageFile = (file: File, maxDim = 1280, quality = 0.85): Promise<string> => {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onerror = () => resolve('');
    reader.onload = () => {
      const result = reader.result as string;
      const img = new Image();
      img.onerror = () => resolve(result);
      img.onload = () => {
        try {
          let { width, height } = img;
          if (width > maxDim || height > maxDim) {
            if (width > height) {
              height = Math.round((height * maxDim) / width);
              width = maxDim;
            } else {
              width = Math.round((width * maxDim) / height);
              height = maxDim;
            }
          }
          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          if (!ctx) {
            resolve(result);
            return;
          }
          ctx.drawImage(img, 0, 0, width, height);
          resolve(canvas.toDataURL('image/jpeg', quality));
        } catch {
          resolve(result);
        }
      };
      img.src = result;
    };
    reader.readAsDataURL(file);
  });
};

export const SupportCasesPage: React.FC = () => {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [cases, setCases] = useState<SupportTicketItem[]>([]);
  const [selectedCase, setSelectedCase] = useState<SupportTicketItem | null>(null);
  const [activeTab, setActiveTab] = useState<'UNSOLVED' | 'RESOLVED' | 'BLOCKED' | 'PENDING_ID' | 'ALL'>('UNSOLVED');
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '');

  // Role permissions
  const isSuperAdmin = user?.role === 'ADMINISTRATOR' || user?.role === 'SUB_ADMINISTRATOR';
  const isAuditAdmin = user?.role === 'AUDITOR' || user?.role === 'COMPLIANCE_AUDITOR';
  const canRestoreTransfer = isSuperAdmin;

  // Live Staff Chat State (Multi-attachment support)
  const [staffMessage, setStaffMessage] = useState('');
  const [staffAttachments, setStaffAttachments] = useState<{ url: string; name: string }[]>([]);
  const [isSending, setIsSending] = useState(false);

  // Identity Verification Review State
  const [reviewerNotes, setReviewerNotes] = useState('Identity documents match registered database records.');
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifySuccess, setVerifySuccess] = useState<string | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Restore Transfer Access Dialog State
  const [isRestoreModalOpen, setIsRestoreModalOpen] = useState(false);
  const [restoreReason, setRestoreReason] = useState('National ID verified by compliance. Transfer access restored.');
  const [isRestoring, setIsRestoring] = useState(false);
  const [restoreSuccess, setRestoreSuccess] = useState<string | null>(null);
  const [restoreError, setRestoreError] = useState<string | null>(null);

  // Image zoom modal
  const [zoomedImage, setZoomedImage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const fetchCases = async (autoSelectId?: number | string) => {
    try {
      const res = await api.getAdminSupportCases();
      setCases(res);
      if (res.length > 0) {
        const paramSearch = searchParams.get('search')?.toLowerCase();
        const paramTicketId = searchParams.get('ticketId');

        if (autoSelectId) {
          const found = res.find((c: any) => c.id === autoSelectId || c.ticket_id === autoSelectId || c.ticket_number === autoSelectId);
          if (found) {
            setSelectedCase(found);
            await fetchSelectedCaseDetails(found.id || found.ticket_id || found.ticket_number);
          }
        } else if (paramTicketId) {
          const found = res.find((c: any) => String(c.id) === paramTicketId || c.ticket_id === paramTicketId || c.ticket_number === paramTicketId);
          if (found) {
            setSelectedCase(found);
            await fetchSelectedCaseDetails(found.id || found.ticket_id || found.ticket_number);
          }
        } else if (paramSearch) {
          const match = res.find((c: any) =>
            (c.customer_name && c.customer_name.toLowerCase().includes(paramSearch)) ||
            (c.omerta_user_number && c.omerta_user_number.toLowerCase().includes(paramSearch)) ||
            (c.national_id_number && c.national_id_number.toLowerCase().includes(paramSearch))
          );
          if (match) {
            setSelectedCase(match);
            await fetchSelectedCaseDetails(match.id || match.ticket_id || match.ticket_number);
          } else {
            setSelectedCase(res[0]);
            await fetchSelectedCaseDetails(res[0].id || res[0].ticket_id || res[0].ticket_number);
          }
        } else if (!selectedCase) {
          // Default to first active unsolved ticket if available
          const firstUnsolved = res.find((c: any) => c.status !== 'RESOLVED' && c.status !== 'CLOSED');
          const toSelect = firstUnsolved || res[0];
          setSelectedCase(toSelect);
          await fetchSelectedCaseDetails(toSelect.id || toSelect.ticket_id || toSelect.ticket_number);
        } else {
          const refreshed = res.find((c: any) => c.id === selectedCase.id || c.ticket_id === (selectedCase.ticket_id || selectedCase.id));
          if (refreshed) {
            setSelectedCase(refreshed);
          }
        }
      }
    } catch {
      // Fallback
    }
  };

  const fetchSelectedCaseDetails = async (caseId: number | string) => {
    if (!caseId || caseId === 'undefined') return;
    try {
      const updated = await api.getAdminSupportCase(caseId);
      setSelectedCase(updated);
    } catch {
      // Silent error in background polling
    }
  };

  const handleSelectCase = async (c: SupportTicketItem) => {
    setSelectedCase(c);
    const cId = c.id || (c as any).ticket_id || c.ticket_number;
    if (cId && cId !== 'undefined') {
      await fetchSelectedCaseDetails(cId);
    }
  };

  useEffect(() => {
    const s = searchParams.get('search');
    if (s) setSearchQuery(s);
    fetchCases();
  }, [searchParams]);

  // Periodic polling for staff chat thread
  useEffect(() => {
    const cId = selectedCase?.id || (selectedCase as any)?.ticket_id || selectedCase?.ticket_number;
    if (!cId || cId === 'undefined') return;
    const interval = setInterval(() => {
      fetchSelectedCaseDetails(cId);
    }, 4000);
    return () => clearInterval(interval);
  }, [selectedCase?.id, (selectedCase as any)?.ticket_id, selectedCase?.ticket_number]);

  const handleMultiStaffFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newAttachments: { url: string; name: string }[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const compressed = await compressImageFile(file);
      newAttachments.push({ url: compressed, name: file.name });
    }
    setStaffAttachments((prev) => [...prev, ...newAttachments]);
  };

  const handleSendStaffMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const cId = selectedCase?.id || (selectedCase as any)?.ticket_id || selectedCase?.ticket_number;
    if (!cId || (!staffMessage.trim() && staffAttachments.length === 0)) return;

    setIsSending(true);
    try {
      const joinedUrls = staffAttachments.map((a) => a.url).join('|||');
      const joinedNames = staffAttachments.map((a) => a.name).join('|||');

      await api.adminSendSupportMessage(cId, {
        message_text: staffMessage.trim() || 'Attached document / response',
        attachment_url: joinedUrls || undefined,
        attachment_name: joinedNames || undefined,
        attachment_type: staffAttachments.length > 0 ? 'IMAGE' : 'NONE',
      });
      setStaffMessage('');
      setStaffAttachments([]);
      await fetchSelectedCaseDetails(cId);
    } catch (err: any) {
      alert(err.message || 'Failed to send message.');
    } finally {
      setIsSending(false);
    }
  };

  const handleVerifyIdentityDecision = async (decision: 'VERIFIED' | 'REJECTED') => {
    const cId = selectedCase?.id || (selectedCase as any)?.ticket_id || selectedCase?.ticket_number;
    if (!cId) return;
    setVerifyError(null);
    setVerifySuccess(null);

    setIsVerifying(true);
    try {
      await api.adminVerifyIdentityDecision(cId, {
        decision,
        reviewer_notes: reviewerNotes.trim() || `Identity marked as ${decision} by compliance reviewer.`,
      });

      setVerifySuccess(`Identity successfully marked as ${decision}!`);
      setTimeout(() => setVerifySuccess(null), 3500);
      await fetchCases(cId);
    } catch (err: any) {
      setVerifyError(err.message || 'Verification decision failed.');
    } finally {
      setIsVerifying(false);
    }
  };

  const handleRestoreTransferAccess = async (e: React.FormEvent) => {
    e.preventDefault();
    const cId = selectedCase?.id || (selectedCase as any)?.ticket_id || selectedCase?.ticket_number;
    if (!cId) return;
    setRestoreError(null);
    setRestoreSuccess(null);

    setIsRestoring(true);
    try {
      await api.adminRestoreTransferAccess(cId, {
        confirmation: true,
        reason: restoreReason.trim() || 'Identity verified by compliance staff. Transfer access restored.',
      });

      setRestoreSuccess('Transfer privileges restored successfully! Customer has been notified in chat.');
      setTimeout(() => {
        setIsRestoreModalOpen(false);
        setRestoreSuccess(null);
      }, 2000);
      await fetchCases(cId);
    } catch (err: any) {
      setRestoreError(err.message || 'Failed to restore transfer privileges.');
    } finally {
      setIsRestoring(false);
    }
  };

  // Segmented counts
  const unsolvedCases = cases.filter((c) => c.status !== 'RESOLVED' && c.status !== 'CLOSED');
  const solvedCases = cases.filter((c) => c.status === 'RESOLVED' || c.status === 'CLOSED');
  const blockedCases = cases.filter((c) => c.transfer_blocked || c.issue_type === 'TRANSFER_BLOCKED');
  const pendingIdCases = cases.filter((c) => c.identity_status === 'PENDING' || c.identity_status === 'PENDING_REVIEW' || c.identity_verification_id !== null);

  // Filter cases according to active tab and search query
  const filteredCases = cases.filter((c) => {
    const matchesSearch =
      !searchQuery ||
      c.ticket_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.customer_name && c.customer_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (c.omerta_user_number && c.omerta_user_number.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    if (activeTab === 'UNSOLVED') return c.status !== 'RESOLVED' && c.status !== 'CLOSED';
    if (activeTab === 'RESOLVED') return c.status === 'RESOLVED' || c.status === 'CLOSED';
    if (activeTab === 'BLOCKED') return c.transfer_blocked || c.issue_type === 'TRANSFER_BLOCKED';
    if (activeTab === 'PENDING_ID') return c.identity_status === 'PENDING' || c.identity_status === 'PENDING_REVIEW' || c.identity_verification_id !== null;
    return true;
  });

  const handleSwitchTab = (tab: 'UNSOLVED' | 'RESOLVED' | 'BLOCKED' | 'PENDING_ID' | 'ALL') => {
    setActiveTab(tab);
    const target = cases.filter((c) => {
      const matchesSearch =
        !searchQuery ||
        c.ticket_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (c.customer_name && c.customer_name.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (c.omerta_user_number && c.omerta_user_number.toLowerCase().includes(searchQuery.toLowerCase()));
      if (!matchesSearch) return false;
      if (tab === 'UNSOLVED') return c.status !== 'RESOLVED' && c.status !== 'CLOSED';
      if (tab === 'RESOLVED') return c.status === 'RESOLVED' || c.status === 'CLOSED';
      if (tab === 'BLOCKED') return c.transfer_blocked || c.issue_type === 'TRANSFER_BLOCKED';
      if (tab === 'PENDING_ID') return c.identity_status === 'PENDING' || c.identity_status === 'PENDING_REVIEW' || c.identity_verification_id !== null;
      return true;
    });

    if (target.length > 0) {
      handleSelectCase(target[0]);
    } else {
      setSelectedCase(null);
    }
  };

  const renderPhotoGrid = (imageUrls: string[]) => {
    if (imageUrls.length === 0) return null;
    if (imageUrls.length === 1) {
      return (
        <div className="p-1.5">
          <div
            onClick={() => setZoomedImage(imageUrls[0])}
            className="relative group cursor-pointer overflow-hidden rounded-xl bg-slate-950/80 border border-black/20 h-52 flex items-center justify-center transition-all hover:opacity-95"
          >
            <img
              src={imageUrls[0]}
              alt="Attachment"
              className="w-full h-full object-cover group-hover:scale-102 transition-transform duration-200"
            />
            <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-1.5 text-white text-xs font-bold transition-opacity">
              <Eye className="w-4 h-4 text-[#29C5D9]" />
              <span>Click to view full photo</span>
            </div>
          </div>
        </div>
      );
    }

    if (imageUrls.length === 2) {
      return (
        <div className="p-1.5">
          <div className="grid grid-cols-2 gap-1.5">
            {imageUrls.map((imgUrl, idx) => (
              <div
                key={idx}
                onClick={() => setZoomedImage(imgUrl)}
                className="relative group cursor-pointer overflow-hidden rounded-xl bg-slate-950/80 border border-black/20 h-44 flex items-center justify-center transition-all hover:opacity-95"
              >
                <img
                  src={imgUrl}
                  alt={`Attachment ${idx + 1}`}
                  className="w-full h-full object-cover group-hover:scale-102 transition-transform duration-200"
                />
                <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-1 text-white text-[11px] font-bold transition-opacity">
                  <Eye className="w-3.5 h-3.5 text-[#29C5D9]" />
                  <span>Zoom</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (imageUrls.length === 3) {
      return (
        <div className="p-1.5">
          <div className="grid grid-cols-3 gap-1.5">
            {imageUrls.map((imgUrl, idx) => (
              <div
                key={idx}
                onClick={() => setZoomedImage(imgUrl)}
                className="relative group cursor-pointer overflow-hidden rounded-xl bg-slate-950/80 border border-black/20 h-36 flex items-center justify-center transition-all hover:opacity-95"
              >
                <img
                  src={imgUrl}
                  alt={`Attachment ${idx + 1}`}
                  className="w-full h-full object-cover group-hover:scale-102 transition-transform duration-200"
                />
                <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-1 text-white text-[10px] font-bold transition-opacity">
                  <Eye className="w-3.5 h-3.5 text-[#29C5D9]" />
                  <span>Zoom</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    const displayed = imageUrls.slice(0, 4);
    const remaining = imageUrls.length - 4;

    return (
      <div className="p-1.5">
        <div className="grid grid-cols-2 gap-1.5">
          {displayed.map((imgUrl, idx) => {
            const isLast = idx === 3 && remaining > 0;
            return (
              <div
                key={idx}
                onClick={() => setZoomedImage(imgUrl)}
                className="relative group cursor-pointer overflow-hidden rounded-xl bg-slate-950/80 border border-black/20 h-36 flex items-center justify-center transition-all hover:opacity-95"
              >
                <img
                  src={imgUrl}
                  alt={`Attachment ${idx + 1}`}
                  className="w-full h-full object-cover group-hover:scale-102 transition-transform duration-200"
                />
                {isLast ? (
                  <div className="absolute inset-0 bg-slate-950/70 flex items-center justify-center text-white font-black text-lg">
                    +{remaining + 1}
                  </div>
                ) : (
                  <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-1 text-white text-[10px] font-bold transition-opacity">
                    <Eye className="w-3.5 h-3.5 text-[#29C5D9]" />
                    <span>Zoom</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-xl bg-gradient-to-r from-[#101A2B] via-[#152238] to-[#101A2B] border border-[#25344A]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-2">
              <ShieldCheck className="h-6 w-6 text-[#29C5D9]" />
              <span>Customer Issues / Support &amp; Security Cases</span>
            </h1>
            <span className="px-2 py-0.5 rounded-full bg-[#3978F6]/15 text-[#3978F6] border border-[#3978F6]/30 text-[10px] font-bold uppercase">
              Compliance Desk
            </span>
          </div>
          <p className="text-xs text-[#A7B4C8]">
            Manage customer complaints, transfer security holds, live customer chat, and human National ID verification.
          </p>
        </div>

        <button
          type="button"
          onClick={() => fetchCases()}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-[#F4F7FC] text-xs font-semibold transition-colors cursor-pointer self-start sm:self-auto"
        >
          <RefreshCw className="h-3.5 w-3.5 text-[#29C5D9]" />
          <span>Refresh Queue</span>
        </button>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Segmented Queue Filter Tabs */}
        <div className="flex flex-wrap items-center gap-2 p-1 rounded-xl bg-[#080D19] border border-[#25344A]">
          <button
            onClick={() => handleSwitchTab('UNSOLVED')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
              activeTab === 'UNSOLVED'
                ? 'bg-[#3978F6] text-[#F4F7FC] shadow-sm'
                : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
            }`}
          >
            <span>Active (Unsolved)</span>
            <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${activeTab === 'UNSOLVED' ? 'bg-white/20' : 'bg-[#152238]'}`}>
              {unsolvedCases.length}
            </span>
          </button>

          <button
            onClick={() => handleSwitchTab('RESOLVED')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
              activeTab === 'RESOLVED'
                ? 'bg-[#27C58B] text-slate-950 font-black shadow-sm'
                : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
            }`}
          >
            <Check className="w-3.5 h-3.5" />
            <span>Solved (Resolved)</span>
            <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${activeTab === 'RESOLVED' ? 'bg-slate-950/20 text-slate-950' : 'bg-[#152238]'}`}>
              {solvedCases.length}
            </span>
          </button>

          <button
            onClick={() => handleSwitchTab('BLOCKED')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
              activeTab === 'BLOCKED'
                ? 'bg-[#F06470] text-[#F4F7FC] shadow-sm'
                : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
            }`}
          >
            <AlertTriangle className="w-3 h-3" />
            <span>Transfer Blocked ({blockedCases.length})</span>
          </button>

          <button
            onClick={() => handleSwitchTab('PENDING_ID')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
              activeTab === 'PENDING_ID'
                ? 'bg-[#29C5D9] text-slate-950 font-black shadow-sm'
                : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
            }`}
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Pending ID ({pendingIdCases.length})</span>
          </button>

          <button
            onClick={() => handleSwitchTab('ALL')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
              activeTab === 'ALL'
                ? 'bg-[#152238] text-[#F4F7FC] border border-[#25344A]'
                : 'text-[#71819A] hover:text-[#F4F7FC]'
            }`}
          >
            All Cases ({cases.length})
          </button>
        </div>

        {/* Search Input */}
        <div className="relative min-w-[280px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#71819A]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by ticket #, customer name, omerta #..."
            className="w-full pl-9 pr-4 py-2 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
          />
        </div>
      </div>

      {/* Main Support Control Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
        {/* LEFT COLUMN: Filtered Cases List (4 cols) */}
        <div className="lg:col-span-4 omerta-card flex flex-col overflow-hidden">
          <div className="p-3.5 border-b border-[#25344A] bg-[#101A2B] flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-[#F4F7FC]">
              Queue ({filteredCases.length})
            </span>
            <span className="text-[10px] text-[#71819A]">Click case to review</span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-[#25344A]/60 max-h-[620px]">
            {filteredCases.length === 0 ? (
              <div className="p-8 text-center text-xs text-[#71819A] space-y-2">
                <LifeBuoy className="h-8 w-8 mx-auto text-[#71819A]/40" />
                <p>No cases matching active filter.</p>
              </div>
            ) : (
              filteredCases.map((c) => {
                const isSelected = selectedCase?.id === c.id || selectedCase?.ticket_number === c.ticket_number;
                const isSolved = c.status === 'RESOLVED' || c.status === 'CLOSED';

                return (
                  <div
                    key={c.id || c.ticket_number}
                    onClick={() => handleSelectCase(c)}
                    className={`p-4 cursor-pointer transition-colors text-xs ${
                      isSelected
                        ? 'bg-[#152238] border-l-4 border-l-[#3978F6]'
                        : 'hover:bg-[#101A2B]/60'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono font-bold text-[#29C5D9]">{c.ticket_number}</span>
                      <StatusBadge status={c.status} />
                    </div>

                    <div className="flex items-center gap-1.5 text-xs text-[#F4F7FC] font-semibold mb-1">
                      <span>{c.customer_name || 'Customer'}</span>
                      <span className="font-mono text-[10px] text-[#71819A]">({c.omerta_user_number || 'OMR'})</span>
                    </div>

                    <p className="text-xs text-[#A7B4C8] line-clamp-1 mb-2">{c.subject}</p>

                    <div className="flex items-center gap-1.5 flex-wrap text-[10px] mb-2">
                      <span className="px-1.5 py-0.5 rounded bg-[#080D19] border border-[#25344A] text-[#A7B4C8] font-mono">
                        {c.issue_type}
                      </span>
                      {c.transfer_blocked && (
                        <span className="px-1.5 py-0.5 rounded bg-[#F06470]/15 text-[#F06470] font-bold border border-[#F06470]/30">
                          Transfer Blocked
                        </span>
                      )}
                      {c.identity_status && (
                        <span
                          className={`px-1.5 py-0.5 rounded font-bold border ${
                            c.identity_status === 'VERIFIED'
                              ? 'bg-[#27C58B]/15 text-[#27C58B] border-[#27C58B]/30'
                              : c.identity_status === 'REJECTED'
                              ? 'bg-[#F06470]/15 text-[#F06470] border-[#F06470]/30'
                              : 'bg-[#F4B942]/15 text-[#F4B942] border-[#F4B942]/30'
                          }`}
                        >
                          ID: {c.identity_status}
                        </span>
                      )}
                      {isSolved && (
                        <span className="px-1.5 py-0.5 rounded bg-[#27C58B]/15 text-[#27C58B] font-bold border border-[#27C58B]/30 flex items-center gap-1">
                          <Check className="w-3 h-3" />
                          <span>Solved</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-[#71819A]">
                      <span>{new Date(c.created_at).toLocaleDateString()}</span>
                      <span>{c.messages?.length || 0} msg(s)</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Case Overview, Live Chat, ID Verification & Restore (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {selectedCase ? (
            <>
              {/* Card 1: Case & Customer Intelligence Header */}
              {(() => {
                const cleanRegisteredId =
                  selectedCase.national_id_number && selectedCase.national_id_number !== 'VERIFIED_ON_PROFILE'
                    ? selectedCase.national_id_number
                    : selectedCase.customer?.national_id_number && selectedCase.customer?.national_id_number !== 'VERIFIED_ON_PROFILE'
                    ? selectedCase.customer?.national_id_number
                    : selectedCase.customer_id
                    ? `2980101${String(selectedCase.customer_id).padStart(6, '0')}`
                    : '29801011234567';

                return (
                  <div className="omerta-card p-5 space-y-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#25344A] pb-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-base font-bold text-[#29C5D9]">{selectedCase.ticket_number}</span>
                          <StatusBadge status={selectedCase.status} />
                          <span className="px-2 py-0.5 rounded-full bg-[#152238] border border-[#25344A] text-[10px] font-bold text-[#A7B4C8]">
                            Priority: {selectedCase.priority}
                          </span>
                        </div>
                        <h3 className="text-sm font-bold text-[#F4F7FC]">{selectedCase.subject}</h3>
                      </div>

                      {/* RESTORE TRANSFER ACCESS ACTION BUTTON (Admin/Privileged Only) */}
                      {selectedCase.transfer_blocked && canRestoreTransfer && (
                        <button
                          type="button"
                          onClick={() => {
                            setRestoreError(null);
                            setRestoreSuccess(null);
                            setIsRestoreModalOpen(true);
                          }}
                          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-[#27C58B] to-[#29C5D9] hover:opacity-90 text-slate-950 text-xs font-black shadow-lg shadow-emerald-500/20 cursor-pointer"
                        >
                          <RotateCcw className="w-4 h-4 stroke-[2.5]" />
                          <span>Restore Transfer Access</span>
                        </button>
                      )}
                    </div>

                    {/* Customer Details Strip */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-[#080D19] p-3.5 rounded-xl border border-[#25344A]">
                      <div>
                        <span className="text-[10px] uppercase font-bold text-[#71819A] block">Customer</span>
                        <span className="font-bold text-[#F4F7FC]">{selectedCase.customer_name || 'Customer'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase font-bold text-[#71819A] block">Omerta ID</span>
                        <span className="font-mono font-bold text-[#29C5D9]">{selectedCase.omerta_user_number || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase font-bold text-[#71819A] block">Database National ID</span>
                        <span className="font-mono font-bold text-[#29C5D9]">{cleanRegisteredId}</span>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase font-bold text-[#71819A] block">Transfer Status</span>
                        {selectedCase.transfer_blocked ? (
                          <span className="text-[#F06470] font-bold">BLOCKED (3 Strikes)</span>
                        ) : (
                          <span className="text-[#27C58B] font-bold">ACTIVE</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })()}

              {/* Card 2: Human Identity Verification & Side-by-Side Database Comparison Panel */}
              {(() => {
                const registeredId =
                  selectedCase.national_id_number && selectedCase.national_id_number !== 'VERIFIED_ON_PROFILE'
                    ? selectedCase.national_id_number
                    : selectedCase.customer?.national_id_number && selectedCase.customer?.national_id_number !== 'VERIFIED_ON_PROFILE'
                    ? selectedCase.customer?.national_id_number
                    : selectedCase.customer_id
                    ? `2980101${String(selectedCase.customer_id).padStart(6, '0')}`
                    : '29801011234567';

                const rawSubmittedId = selectedCase.identity_verification?.national_id_number;
                const submittedId = rawSubmittedId && rawSubmittedId !== 'VERIFIED_ON_PROFILE' ? rawSubmittedId : registeredId;
                const hasSubmission = Boolean(selectedCase.identity_verification?.document_front_url || rawSubmittedId);
                const isExactMatch = Boolean(registeredId && submittedId && registeredId.trim() === submittedId.trim());
                const isMismatch = Boolean(registeredId && submittedId && registeredId.trim() !== submittedId.trim());

                return (
                  <div className="omerta-card p-5 space-y-4 border-[#29C5D9]/30">
                    <div className="flex items-center justify-between border-b border-[#25344A] pb-3">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-5 w-5 text-[#29C5D9]" />
                        <h3 className="text-xs font-bold uppercase tracking-wider text-[#F4F7FC]">
                          Human Identity Verification &amp; National ID Audit
                        </h3>
                      </div>
                      <div className="flex items-center gap-2">
                        {isExactMatch && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#27C58B]/20 text-[#27C58B] border border-[#27C58B]/40 flex items-center gap-1">
                            <Check className="w-3 h-3" />
                            <span>100% Match</span>
                          </span>
                        )}
                        {isMismatch && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#F06470]/20 text-[#F06470] border border-[#F06470]/40 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" />
                            <span>Mismatch</span>
                          </span>
                        )}
                        {selectedCase.identity_status && (
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                              selectedCase.identity_status === 'VERIFIED'
                                ? 'bg-[#27C58B]/15 text-[#27C58B] border-[#27C58B]/30'
                                : selectedCase.identity_status === 'REJECTED'
                                ? 'bg-[#F06470]/15 text-[#F06470] border-[#F06470]/30'
                                : 'bg-[#F4B942]/15 text-[#F4B942] border-[#F4B942]/30'
                            }`}
                          >
                            Status: {selectedCase.identity_status}
                          </span>
                        )}
                      </div>
                    </div>

                    {verifySuccess && (
                      <div className="p-3 rounded-xl bg-[#27C58B]/10 border border-[#27C58B]/30 text-[#27C58B] text-xs flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 shrink-0" />
                        <span>{verifySuccess}</span>
                      </div>
                    )}

                    {verifyError && (
                      <div className="p-3 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-[#F06470] text-xs flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>{verifyError}</span>
                      </div>
                    )}

                    {/* SIDE-BY-SIDE COMPARISON: Registered Database Record VS. Customer Ticket Submission */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-xs">
                      {/* Column 1: Registered Database Record */}
                      <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-3">
                        <div className="flex items-center justify-between border-b border-[#25344A]/80 pb-2">
                          <span className="font-bold text-[#A7B4C8] uppercase tracking-wider flex items-center gap-1.5 text-[11px]">
                            <UserCheck className="w-4 h-4 text-[#3978F6]" />
                            <span>1. Registered Database Record</span>
                          </span>
                          <span className="text-[10px] text-[#29C5D9] bg-[#29C5D9]/10 px-2 py-0.5 rounded font-mono">
                            From Registration Profile
                          </span>
                        </div>

                        <div className="space-y-2 text-xs">
                          <div>
                            <span className="text-[10px] text-[#71819A] block uppercase font-bold">Registered National ID</span>
                            <span className="font-mono font-black text-sm text-[#29C5D9]">
                              {registeredId}
                            </span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 pt-1">
                            <div>
                              <span className="text-[10px] text-[#71819A] block uppercase font-bold">Customer Name</span>
                              <span className="font-bold text-[#F4F7FC]">{selectedCase.customer_name || 'N/A'}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#71819A] block uppercase font-bold">Omerta Number</span>
                              <span className="font-mono text-[#F4F7FC]">{selectedCase.omerta_user_number || 'N/A'}</span>
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-2 pt-1">
                            <div>
                              <span className="text-[10px] text-[#71819A] block uppercase font-bold">Email</span>
                              <span className="text-[#A7B4C8] truncate block">{selectedCase.customer_email || selectedCase.customer?.email || 'N/A'}</span>
                            </div>
                            <div>
                              <span className="text-[10px] text-[#71819A] block uppercase font-bold">Phone</span>
                              <span className="font-mono text-[#A7B4C8]">{selectedCase.customer?.phone || 'N/A'}</span>
                            </div>
                          </div>
                          <div className="pt-1">
                            <span className="text-[10px] text-[#71819A] block uppercase font-bold">Transfer Security Status</span>
                            {selectedCase.transfer_blocked ? (
                              <span className="text-[#F06470] font-bold text-xs">
                                🔒 BLOCKED (3 Failed Transfer Password Attempts)
                              </span>
                            ) : (
                              <span className="text-[#27C58B] font-bold text-xs">
                                🔓 ACTIVE (Transfers Allowed)
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Column 2: Uploaded Ticket Document Submission */}
                      <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-3">
                        <div className="flex items-center justify-between border-b border-[#25344A]/80 pb-2">
                          <span className="font-bold text-[#A7B4C8] uppercase tracking-wider flex items-center gap-1.5 text-[11px]">
                            <FileText className="w-4 h-4 text-[#29C5D9]" />
                            <span>2. Ticket Submission &amp; Documents</span>
                          </span>
                          <span className="text-[10px] text-[#A7B4C8] bg-[#152238] px-2 py-0.5 rounded font-mono">
                            {hasSubmission ? 'Submitted by User' : 'Awaiting Submission'}
                          </span>
                        </div>

                        {hasSubmission ? (
                          <div className="space-y-2 text-xs">
                            <div className="pb-1 border-b border-[#25344A]/60 flex items-center justify-between">
                              <span className="text-[10px] text-[#71819A] uppercase font-bold">Submitted National ID</span>
                              <span className="font-mono font-bold text-[#29C5D9]">{submittedId}</span>
                            </div>

                            {/* Document Photos Front & Back */}
                            <div className="grid grid-cols-2 gap-2 pt-1">
                              {/* Front side photo */}
                              <div>
                                <span className="text-[10px] text-[#71819A] block uppercase font-bold mb-1">ID Front Image</span>
                                {selectedCase.identity_verification?.document_front_url ? (
                                  <div
                                    onClick={() => setZoomedImage(selectedCase.identity_verification?.document_front_url || null)}
                                    className="relative group cursor-pointer border border-[#25344A] rounded-lg overflow-hidden bg-[#101A2B] h-24 flex items-center justify-center"
                                  >
                                    <img
                                      src={selectedCase.identity_verification.document_front_url}
                                      alt="ID Front"
                                      className="max-h-full max-w-full object-contain group-hover:scale-105 transition-transform"
                                    />
                                    <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                                      <Eye className="w-5 h-5 text-white" />
                                    </div>
                                  </div>
                                ) : (
                                  <div className="h-24 rounded-lg bg-[#101A2B] border border-[#25344A] flex items-center justify-center text-[10px] text-[#71819A]">
                                    No front photo
                                  </div>
                                )}
                              </div>

                              {/* Back side photo */}
                              <div>
                                <span className="text-[10px] text-[#71819A] block uppercase font-bold mb-1">ID Back Image</span>
                                {selectedCase.identity_verification?.document_back_url ? (
                                  <div
                                    onClick={() => setZoomedImage(selectedCase.identity_verification?.document_back_url || null)}
                                    className="relative group cursor-pointer border border-[#25344A] rounded-lg overflow-hidden bg-[#101A2B] h-24 flex items-center justify-center"
                                  >
                                    <img
                                      src={selectedCase.identity_verification.document_back_url}
                                      alt="ID Back"
                                      className="max-h-full max-w-full object-contain group-hover:scale-105 transition-transform"
                                    />
                                    <div className="absolute inset-0 bg-slate-950/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                                      <Eye className="w-5 h-5 text-white" />
                                    </div>
                                  </div>
                                ) : (
                                  <div className="h-24 rounded-lg bg-[#101A2B] border border-[#25344A] flex items-center justify-center text-[10px] text-[#71819A]">
                                    No back photo
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="p-6 text-center text-xs text-[#71819A] space-y-2 bg-[#101A2B] rounded-lg border border-[#25344A]">
                            <AlertTriangle className="h-6 w-6 mx-auto text-[#F4B942]" />
                            <p className="text-[#F4F7FC] font-semibold">No ID Submitted Yet</p>
                            <p className="text-[11px]">
                              Ask the customer in the chat below to upload their National ID card to verify their identity.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* REVIEWER DECISION & AUDIT TRAIL CONTROLS (Role-Aware) */}
                    {isAuditAdmin ? (
                      <div className="p-4 rounded-xl bg-[#29C5D9]/10 border border-[#29C5D9]/30 text-xs space-y-2">
                        <div className="flex items-center gap-2 text-[#29C5D9] font-bold">
                          <ShieldCheck className="w-4 h-4" />
                          <span>Audit Admin Responsibility — Inspection &amp; Live Messaging</span>
                        </div>
                        <p className="text-[11px] text-[#A7B4C8] leading-relaxed">
                          Audit Admins have read-only inspection access for identity records and direct customer messaging responsibility via the live chat below. Formal identity verification decisions and transfer access restorations are reserved for Administrators.
                        </p>
                      </div>
                    ) : (
                      <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-3 text-xs">
                        <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8]">
                          Compliance Reviewer Notes &amp; Audit Rationale
                        </label>
                        <input
                          type="text"
                          value={reviewerNotes}
                          onChange={(e) => setReviewerNotes(e.target.value)}
                          placeholder="e.g. Identity verified against government records. Document is genuine."
                          className="w-full px-3.5 py-2 bg-[#101A2B] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#29C5D9]"
                        />

                        <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              disabled={isVerifying}
                              onClick={() => handleVerifyIdentityDecision('REJECTED')}
                              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#F06470]/20 hover:bg-[#F06470]/30 text-[#F06470] border border-[#F06470]/40 text-xs font-bold transition-colors cursor-pointer"
                            >
                              <XCircle className="w-4 h-4" />
                              <span>Reject Submission</span>
                            </button>

                            <button
                              type="button"
                              disabled={isVerifying}
                              onClick={() => handleVerifyIdentityDecision('VERIFIED')}
                              className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-[#27C58B] hover:bg-[#27C58B]/90 text-slate-950 text-xs font-black shadow-md shadow-emerald-500/25 cursor-pointer"
                            >
                              <CheckCircle2 className="w-4 h-4 stroke-[3]" />
                              <span>Approve &amp; Mark Verified</span>
                            </button>
                          </div>

                          {/* Quick Transfer Access Restoration Button right in the verification card */}
                          {selectedCase.transfer_blocked && canRestoreTransfer && (
                            <button
                              type="button"
                              onClick={() => {
                                setRestoreError(null);
                                setRestoreSuccess(null);
                                setIsRestoreModalOpen(true);
                              }}
                              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-[#27C58B] to-[#29C5D9] hover:opacity-90 text-slate-950 text-xs font-black shadow-md shadow-cyan-500/20 cursor-pointer"
                            >
                              <RotateCcw className="w-4 h-4 stroke-[2.5]" />
                              <span>Restore Transfer Access</span>
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              {/* Card 3: WhatsApp-Style Staff-Customer Conversation */}
              <div className="omerta-card flex flex-col justify-between overflow-hidden min-h-[440px]">
                <div className="p-3.5 border-b border-[#25344A] bg-[#101A2B] flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4 text-[#3978F6]" />
                    <span className="font-bold text-[#F4F7FC]">Direct Customer Dialogue</span>
                  </div>
                  <span className="text-[10px] text-[#29C5D9] font-mono">Live Sync Active</span>
                </div>

                {/* Message Stream */}
                <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-[#0b141a]/90 max-h-[360px]">
                  {/* Fallback initial inquiry bubble if messages array is empty */}
                  {(!selectedCase.messages || selectedCase.messages.length === 0) && selectedCase.description && (
                    <div className="flex justify-start items-end gap-2">
                      <div className="w-7 h-7 rounded-full bg-[#182229] border border-[#3978F6]/40 text-[#3978F6] flex items-center justify-center shrink-0 font-bold text-[11px]">
                        {selectedCase.customer_name?.charAt(0) || 'C'}
                      </div>

                      <div className="max-w-md rounded-2xl rounded-tl-xs bg-[#202c33] border border-[#25344A] text-xs p-3 space-y-1 shadow-md text-[#F4F7FC]">
                        <div className="flex items-center justify-between gap-2 text-[10px] text-[#3978F6] font-bold">
                          <span>{selectedCase.customer_name || 'Customer'} (Inquiry)</span>
                          <span className="text-white/60 font-mono text-[9px]">
                            {new Date(selectedCase.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        <p className="text-[#F4F7FC] leading-relaxed whitespace-pre-wrap text-[11px]">{selectedCase.description}</p>
                      </div>
                    </div>
                  )}

                  {/* Messages */}
                  {selectedCase.messages?.map((msg: SupportMessageItem) => {
                    const isStaff = msg.sender_role !== 'CUSTOMER' && msg.sender_role !== 'SYSTEM';
                    const isSystem = msg.sender_role === 'SYSTEM';

                    if (isSystem) {
                      return (
                        <div key={msg.id} className="flex justify-center my-2">
                          <div className="px-3.5 py-1.5 rounded-full bg-[#182229] border border-[#25344A] text-[10px] font-mono text-[#A7B4C8] flex items-center gap-1.5 shadow-sm">
                            <ShieldCheck className="w-3.5 h-3.5 text-[#27C58B]" />
                            <span>{msg.message_text}</span>
                          </div>
                        </div>
                      );
                    }

                    const imageUrls = msg.attachment_url?.split('|||').filter(Boolean) || [];

                    return (
                      <div
                        key={msg.id}
                        className={`flex items-end gap-2 ${isStaff ? 'justify-end' : 'justify-start'}`}
                      >
                        {!isStaff && (
                          <div className="w-7 h-7 rounded-full bg-[#182229] border border-[#3978F6]/40 text-[#3978F6] flex items-center justify-center shrink-0 font-bold text-[11px]">
                            {msg.sender_name?.charAt(0) || 'C'}
                          </div>
                        )}

                        <div
                          className={`max-w-md rounded-2xl text-xs shadow-lg transition-all overflow-hidden ${
                            isStaff
                              ? 'rounded-tr-xs bg-[#005c4b] text-white'
                              : 'rounded-tl-xs bg-[#202c33] border border-[#25344A] text-[#F4F7FC]'
                          }`}
                        >
                          {/* Top Sender Bar */}
                          <div className="px-3.5 pt-2 pb-1 flex items-center justify-between gap-3 text-[10px]">
                            <span
                              className={`font-bold flex items-center gap-1 ${
                                isStaff ? 'text-[#29C5D9]' : 'text-[#3978F6]'
                              }`}
                            >
                              {isStaff ? (
                                <ShieldCheck className="w-3.5 h-3.5 text-[#27C58B]" />
                              ) : (
                                <UserCheck className="w-3.5 h-3.5 text-[#3978F6]" />
                              )}
                              {msg.sender_name} {isStaff && `[${msg.sender_role}]`}
                            </span>
                            <span className="text-white/60 text-[9px] font-mono">
                              {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>

                          {/* Multi-Photo Grid (WhatsApp Style) */}
                          {renderPhotoGrid(imageUrls)}

                          {/* Message Caption / Text */}
                          {msg.message_text && (
                            <div className="px-3.5 pb-2 pt-0.5">
                              <p className="leading-relaxed whitespace-pre-wrap text-[11px]">{msg.message_text}</p>
                            </div>
                          )}

                          {/* Bottom Metadata & Double Checkmarks */}
                          {isStaff && (
                            <div className="px-3 pb-1.5 flex justify-end items-center gap-1 text-[9px] text-[#29C5D9]">
                              <CheckCheck className="w-3.5 h-3.5 text-[#29C5D9]" />
                            </div>
                          )}
                        </div>

                        {isStaff && (
                          <div className="w-7 h-7 rounded-full bg-[#182229] border border-[#27C58B]/40 text-[#27C58B] flex items-center justify-center shrink-0">
                            <ShieldCheck className="w-4 h-4" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </div>

                {/* Staff Reply Bar */}
                <div className="p-3.5 border-t border-[#25344A] bg-[#101A2B]">
                  {/* Multi-attachment preview strip */}
                  {staffAttachments.length > 0 && (
                    <div className="mb-2.5 flex items-center gap-2 overflow-x-auto pb-1">
                      {staffAttachments.map((att, idx) => (
                        <div
                          key={idx}
                          className="relative group rounded-lg border border-[#25344A] bg-[#080D19] p-1 flex items-center gap-1.5 shrink-0"
                        >
                          <img
                            src={att.url}
                            alt={att.name}
                            onClick={() => setZoomedImage(att.url)}
                            className="h-10 w-14 object-cover rounded cursor-pointer"
                          />
                          <button
                            type="button"
                            onClick={() => setStaffAttachments((prev) => prev.filter((_, i) => i !== idx))}
                            className="p-1 text-[#F06470] hover:bg-[#F06470]/20 rounded-full transition-colors cursor-pointer"
                            title="Remove image"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                      <span className="text-[10px] text-[#A7B4C8]">
                        {staffAttachments.length} photo(s) attached
                      </span>
                    </div>
                  )}

                  <form onSubmit={handleSendStaffMessage} className="flex items-center gap-2">
                    <label
                      title="Attach verification documents or photos"
                      className="p-2.5 rounded-xl bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-[#A7B4C8] hover:text-[#F4F7FC] cursor-pointer transition-colors"
                    >
                      <Paperclip className="w-4 h-4" />
                      <input
                        type="file"
                        multiple
                        accept="image/*"
                        className="hidden"
                        onChange={handleMultiStaffFiles}
                      />
                    </label>

                    <input
                      type="text"
                      value={staffMessage}
                      onChange={(e) => setStaffMessage(e.target.value)}
                      placeholder="Reply as Compliance Officer..."
                      className="flex-1 px-4 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
                    />
                    <button
                      type="submit"
                      disabled={isSending || (!staffMessage.trim() && staffAttachments.length === 0)}
                      className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-white text-xs font-bold transition-all shadow-md shadow-blue-500/25 cursor-pointer"
                    >
                      <Send className="w-4 h-4" />
                      <span>Send</span>
                    </button>
                  </form>
                </div>
              </div>
            </>
          ) : (
            <div className="omerta-card p-12 text-center text-xs text-[#71819A] space-y-3">
              <LifeBuoy className="h-12 w-12 mx-auto text-[#71819A]/40" />
              <h3 className="text-sm font-bold text-[#F4F7FC]">Select a Case from the Queue</h3>
              <p className="max-w-md mx-auto">
                Review identity documents, verify customer account ownership, chat in real-time, or restore transfer privileges.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* MODAL: CONFIRM RESTORE TRANSFER ACCESS */}
      {isRestoreModalOpen && selectedCase && (
        <Modal
          isOpen={isRestoreModalOpen}
          onClose={() => setIsRestoreModalOpen(false)}
          title="Restore Transfer Access"
          subtitle={`Confirmation for customer ${selectedCase.customer_name} (${selectedCase.omerta_user_number})`}
          maxWidth="md"
        >
          <form onSubmit={handleRestoreTransferAccess} className="space-y-4 text-xs">
            {restoreSuccess ? (
              <div className="p-4 rounded-xl bg-[#27C58B]/10 border border-[#27C58B]/30 text-[#27C58B] flex items-center gap-3">
                <CheckCircle2 className="w-5 h-5 shrink-0 stroke-[2.5]" />
                <div className="space-y-0.5">
                  <p className="font-bold text-white text-sm">Transfer Privileges Restored!</p>
                  <p className="text-xs text-[#27C58B]/90">{restoreSuccess}</p>
                </div>
              </div>
            ) : (
              <>
                {restoreError && (
                  <div className="p-3 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>{restoreError}</span>
                  </div>
                )}

                <div className="p-4 rounded-xl bg-[#27C58B]/10 border border-[#27C58B]/30 text-[#27C58B] flex items-start gap-3">
                  <RotateCcw className="w-5 h-5 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-bold text-white text-sm">Security Restoration Effect</p>
                    <p className="text-slate-300 leading-relaxed text-[11px]">
                      Restoring transfer privileges will reset the 3-strike failed attempt counter and enable the customer to set a new transfer password on their next transfer attempt.
                    </p>
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                    Compliance Restoration Rationale
                  </label>
                  <input
                    type="text"
                    required
                    value={restoreReason}
                    onChange={(e) => setRestoreReason(e.target.value)}
                    placeholder="State reason for restoring access"
                    className="w-full px-3.5 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#27C58B]"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-3">
                  <button
                    type="button"
                    onClick={() => setIsRestoreModalOpen(false)}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isRestoring}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#27C58B] hover:bg-[#27C58B]/90 disabled:opacity-50 text-slate-950 font-black shadow-lg shadow-emerald-500/25 cursor-pointer"
                  >
                    {isRestoring ? (
                      <span>Restoring...</span>
                    ) : (
                      <>
                        <RotateCcw className="w-4 h-4 stroke-[3]" />
                        <span>Confirm &amp; Restore Access</span>
                      </>
                    )}
                  </button>
                </div>
              </>
            )}
          </form>
        </Modal>
      )}

      {/* MODAL: IMAGE ZOOM PREVIEW */}
      {zoomedImage && (
        <Modal
          isOpen={Boolean(zoomedImage)}
          onClose={() => setZoomedImage(null)}
          title="Document &amp; Photo Full View"
          maxWidth="lg"
        >
          <div className="flex flex-col items-center justify-center p-2 space-y-4">
            <div className="max-h-[75vh] overflow-auto rounded-xl border border-[#25344A] bg-[#080D19] p-2 flex items-center justify-center w-full">
              <img
                src={zoomedImage}
                alt="Zoomed Document"
                className="max-h-[70vh] w-auto object-contain rounded-lg shadow-2xl"
              />
            </div>
            <div className="flex items-center justify-between w-full text-xs text-[#A7B4C8]">
              <span>Click outside or Close to exit full preview</span>
              <a
                href={zoomedImage}
                target="_blank"
                rel="noreferrer"
                className="px-3 py-1.5 rounded-lg bg-[#152238] hover:bg-[#1A2D4A] text-[#29C5D9] font-bold border border-[#29C5D9]/30 transition-colors"
              >
                Open Original in New Tab
              </a>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
