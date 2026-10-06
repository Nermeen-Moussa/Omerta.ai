import React, { useState, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  LifeBuoy,
  Plus,
  Send,
  Paperclip,
  ShieldCheck,
  AlertTriangle,
  Clock,
  CheckCheck,
  Upload,
  FileText,
  CheckCircle2,
  RefreshCw,
  HelpCircle,
  Eye,
  Check,
  ArrowRight,
  Shield,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Modal } from '../../components/common/Modal';
import type { SupportTicketItem, SupportMessageItem } from '../../types';

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

export const CustomerSupportPage: React.FC = () => {
  const { customer, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [tickets, setTickets] = useState<SupportTicketItem[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<SupportTicketItem | null>(null);
  const [ticketTab, setTicketTab] = useState<'UNSOLVED' | 'SOLVED'>('UNSOLVED');
  const [isSending, setIsSending] = useState(false);
  const [messageText, setMessageText] = useState('');

  // New Ticket Modal State
  const [isNewTicketModalOpen, setIsNewTicketModalOpen] = useState(false);
  const [newTicketData, setNewTicketData] = useState({
    issue_type: searchParams.get('reason') === 'TRANSFER_BLOCKED' ? 'TRANSFER_BLOCKED' : 'FORGOTTEN_TRANSFER_PASSWORD',
    subject: searchParams.get('reason') === 'TRANSFER_BLOCKED' ? 'Transfer Password Blocked — Requesting Identity Verification' : 'Forgotten Transfer Password — Identity Verification & Reset Request',
    description: searchParams.get('reason') === 'TRANSFER_BLOCKED'
      ? 'I entered my transfer password incorrectly 3 times. Please review my submitted National ID and restore my money transfer privileges.'
      : 'I have forgotten my transfer password and cannot send money. Please verify my National ID to allow me to set a new transfer password and restore transfer privileges.',
    priority: 'HIGH',
  });
  const [modalIdFront, setModalIdFront] = useState<string | null>(null);
  const [modalIdBack, setModalIdBack] = useState<string | null>(null);
  const [modalNationalId, setModalNationalId] = useState<string>('');
  const [newTicketLoading, setNewTicketLoading] = useState(false);
  const [newTicketError, setNewTicketError] = useState<string | null>(null);

  // Identity Upload Section State
  const [idFrontPreview, setIdFrontPreview] = useState<string | null>(null);
  const [idBackPreview, setIdBackPreview] = useState<string | null>(null);
  const [nationalIdInput, setNationalIdInput] = useState<string>('');
  const [idUploading, setIdUploading] = useState(false);
  const [idUploadSuccess, setIdUploadSuccess] = useState(false);
  const [idUploadError, setIdUploadError] = useState<string | null>(null);

  // Multi-Attachment for chat messages
  const [chatAttachments, setChatAttachments] = useState<{ url: string; name: string }[]>([]);

  // Zoomed image modal
  const [zoomedImage, setZoomedImage] = useState<string | null>(null);

  // Chat scroll anchor
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const fetchTickets = async (autoSelectId?: number | string) => {
    try {
      const res = await api.getCustomerSupportTickets();
      setTickets(res);
      if (res.length > 0) {
        if (autoSelectId) {
          const found = res.find((t: any) => t.id === autoSelectId || t.ticket_id === autoSelectId || t.ticket_number === autoSelectId);
          if (found) {
            setSelectedTicket(found);
            await fetchSelectedTicketDetails(found.id || found.ticket_id || found.ticket_number);
          }
        } else if (!selectedTicket) {
          // Default to first active unsolved ticket if available
          const firstUnsolved = res.find((t: any) => t.status !== 'RESOLVED' && t.status !== 'CLOSED');
          const toSelect = firstUnsolved || res[0];
          setSelectedTicket(toSelect);
          await fetchSelectedTicketDetails(toSelect.id || toSelect.ticket_id || toSelect.ticket_number);
        } else {
          const refreshed = res.find((t: any) => t.id === selectedTicket.id || t.ticket_id === (selectedTicket.ticket_id || selectedTicket.id));
          if (refreshed) {
            setSelectedTicket(refreshed);
          }
        }
      }
    } catch {
      // Fallback
    }
  };

  const fetchSelectedTicketDetails = async (ticketId: number | string) => {
    if (!ticketId || ticketId === 'undefined') return;
    try {
      const ticket = await api.getCustomerSupportTicket(ticketId);
      setSelectedTicket(ticket);
    } catch {
      // Silent error during polling
    }
  };

  const handleSelectTicket = async (ticket: SupportTicketItem) => {
    setSelectedTicket(ticket);
    const tId = ticket.id || (ticket as any).ticket_id || ticket.ticket_number;
    if (tId && tId !== 'undefined') {
      await fetchSelectedTicketDetails(tId);
    }
  };

  useEffect(() => {
    fetchTickets();
    if (searchParams.get('reason') === 'TRANSFER_BLOCKED') {
      setIsNewTicketModalOpen(true);
    }
  }, []);

  // Periodic polling for real-time conversation updates
  useEffect(() => {
    const tId = selectedTicket?.id || (selectedTicket as any)?.ticket_id || selectedTicket?.ticket_number;
    if (!tId || tId === 'undefined') return;
    const interval = setInterval(() => {
      fetchSelectedTicketDetails(tId);
    }, 4000);
    return () => clearInterval(interval);
  }, [selectedTicket?.id, (selectedTicket as any)?.ticket_id, selectedTicket?.ticket_number]);

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    setNewTicketError(null);
    if (!newTicketData.subject.trim() || !newTicketData.description.trim()) {
      setNewTicketError('Subject and description are required.');
      return;
    }

    setNewTicketLoading(true);
    try {
      const res = await api.createSupportTicket({
        issue_type: newTicketData.issue_type,
        subject: newTicketData.subject,
        description: newTicketData.description,
        priority: newTicketData.priority,
      });

      const newTicketId = res.id || res.ticket_id || res.ticket_number;

      // If user uploaded National ID in modal, immediately submit ID verification
      if (modalIdFront && newTicketId) {
        try {
          const natId = (modalNationalId.trim() || customer?.national_id_number || '29801011234567').replace(/[^0-9]/g, '');
          await api.uploadSupportIdDocument(newTicketId, {
            national_id_number: natId.length >= 6 ? natId : (customer?.national_id_number || '29801011234567'),
            document_type: 'NATIONAL_ID',
            document_front_url: modalIdFront,
            document_back_url: modalIdBack || undefined,
          });
        } catch {
          // Non-blocking if document upload errors
        }
      }

      setIsNewTicketModalOpen(false);
      setModalIdFront(null);
      setModalIdBack(null);
      setModalNationalId('');
      setNewTicketData({
        issue_type: 'FORGOTTEN_TRANSFER_PASSWORD',
        subject: '',
        description: '',
        priority: 'HIGH',
      });
      setTicketTab('UNSOLVED');
      await fetchTickets(newTicketId);
    } catch (err: any) {
      setNewTicketError(err.message || 'Failed to create support ticket.');
    } finally {
      setNewTicketLoading(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const tId = selectedTicket?.id || (selectedTicket as any)?.ticket_id || selectedTicket?.ticket_number;
    if (!tId || (!messageText.trim() && chatAttachments.length === 0)) return;

    setIsSending(true);
    try {
      const joinedUrls = chatAttachments.map((a) => a.url).join('|||');
      const joinedNames = chatAttachments.map((a) => a.name).join('|||');

      await api.sendSupportMessage(tId, {
        message_text: messageText.trim() || 'Uploaded attachment',
        attachment_url: joinedUrls || undefined,
        attachment_name: joinedNames || undefined,
        attachment_type: chatAttachments.length > 0 ? 'IMAGE' : 'NONE',
      });

      setMessageText('');
      setChatAttachments([]);
      await fetchSelectedTicketDetails(tId);
    } catch (err: any) {
      alert(err.message || 'Failed to send message.');
    } finally {
      setIsSending(false);
    }
  };

  const handleMultiChatFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const newAttachments: { url: string; name: string }[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const compressed = await compressImageFile(file);
      newAttachments.push({ url: compressed, name: file.name });
    }
    setChatAttachments((prev) => [...prev, ...newAttachments]);
  };

  const handleIdPhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>, target: 'front' | 'back') => {
    const file = e.target.files?.[0];
    if (!file) return;

    const compressed = await compressImageFile(file);
    if (target === 'front') {
      setIdFrontPreview(compressed);
    } else if (target === 'back') {
      setIdBackPreview(compressed);
    }
  };

  const handleModalPhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>, target: 'front' | 'back') => {
    const file = e.target.files?.[0];
    if (!file) return;

    const compressed = await compressImageFile(file);
    if (target === 'front') {
      setModalIdFront(compressed);
    } else if (target === 'back') {
      setModalIdBack(compressed);
    }
  };

  const handleUploadIdDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTicket) return;
    setIdUploadError(null);

    const ticketId = selectedTicket.id || (selectedTicket as any).ticket_id || selectedTicket.ticket_number;
    if (!ticketId || ticketId === 'undefined') {
      setIdUploadError('No valid support ticket selected. Please select a case from your cases list.');
      return;
    }

    if (!idFrontPreview) {
      setIdUploadError('Please attach a clear photo of the front side of your National ID / Passport.');
      return;
    }

    setIdUploading(true);
    try {
      const natId = (nationalIdInput.trim() || customer?.national_id_number || '29801011234567').replace(/[^0-9]/g, '');
      await api.uploadSupportIdDocument(ticketId, {
        national_id_number: natId.length >= 6 ? natId : (customer?.national_id_number || '29801011234567'),
        document_type: 'NATIONAL_ID',
        document_front_url: idFrontPreview,
        document_back_url: idBackPreview || undefined,
      });

      setIdUploadSuccess(true);
      setTimeout(() => {
        setIdUploadSuccess(false);
      }, 5000);
      await fetchSelectedTicketDetails(ticketId);
      await fetchTickets(ticketId);
    } catch (err: any) {
      setIdUploadError(err.message || 'Failed to submit ID verification.');
    } finally {
      setIdUploading(false);
    }
  };

  // Separate unsolved vs solved tickets
  const unsolvedTickets = tickets.filter((t) => t.status !== 'RESOLVED' && t.status !== 'CLOSED');
  const solvedTickets = tickets.filter((t) => t.status === 'RESOLVED' || t.status === 'CLOSED');
  const displayedTickets = ticketTab === 'UNSOLVED' ? unsolvedTickets : solvedTickets;

  const handleSwitchTab = (tab: 'UNSOLVED' | 'SOLVED') => {
    setTicketTab(tab);
    const target = tab === 'UNSOLVED' ? unsolvedTickets : solvedTickets;
    if (target.length > 0) {
      handleSelectTicket(target[0]);
    } else {
      setSelectedTicket(null);
    }
  };

  const isCaseResolved = selectedTicket?.status === 'RESOLVED' || selectedTicket?.status === 'CLOSED';

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
          <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-2">
            <LifeBuoy className="h-6 w-6 text-[#29C5D9]" />
            <span>Support &amp; Security Helpdesk</span>
          </h1>
          <p className="text-xs text-[#A7B4C8] mt-1">
            Direct dialogue with Compliance Officers for identity verification, transfer recovery, and security reviews.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setNewTicketError(null);
            setIsNewTicketModalOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 text-[#F4F7FC] text-xs font-bold transition-all shadow-md shadow-blue-500/20 cursor-pointer self-start sm:self-auto"
        >
          <Plus className="h-4 w-4 stroke-[3]" />
          <span>New Support Ticket</span>
        </button>
      </div>

      {/* Main Support Workspace: Ticket List + WhatsApp Chat */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[600px]">
        {/* LEFT COLUMN: Segmented Ticket Queue (Unsolved vs Solved) (4 cols) */}
        <div className="lg:col-span-4 omerta-card flex flex-col overflow-hidden">
          {/* Header & Tabs */}
          <div className="p-3 border-b border-[#25344A] bg-[#101A2B] space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-[#29C5D9]" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#F4F7FC]">Your Cases</h2>
              </div>
              <button
                onClick={() => fetchTickets()}
                className="p-1.5 rounded text-[#A7B4C8] hover:text-[#F4F7FC] hover:bg-[#152238] transition-colors"
                title="Refresh tickets"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* UNSOLVED vs SOLVED Segmented Controls */}
            <div className="grid grid-cols-2 gap-1.5 p-1 rounded-xl bg-[#080D19] border border-[#25344A]">
              <button
                type="button"
                onClick={() => handleSwitchTab('UNSOLVED')}
                className={`py-1.5 px-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                  ticketTab === 'UNSOLVED'
                    ? 'bg-[#3978F6] text-white shadow-sm'
                    : 'text-[#A7B4C8] hover:text-[#F4F7FC] hover:bg-[#152238]/60'
                }`}
              >
                <span>Active (Unsolved)</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${ticketTab === 'UNSOLVED' ? 'bg-white/20' : 'bg-[#152238]'}`}>
                  {unsolvedTickets.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleSwitchTab('SOLVED')}
                className={`py-1.5 px-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                  ticketTab === 'SOLVED'
                    ? 'bg-[#27C58B] text-slate-950 shadow-sm font-black'
                    : 'text-[#A7B4C8] hover:text-[#F4F7FC] hover:bg-[#152238]/60'
                }`}
              >
                <span>Solved (Resolved)</span>
                <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${ticketTab === 'SOLVED' ? 'bg-slate-950/20 text-slate-950' : 'bg-[#152238]'}`}>
                  {solvedTickets.length}
                </span>
              </button>
            </div>
          </div>

          {/* Ticket List Stream */}
          <div className="flex-1 overflow-y-auto divide-y divide-[#25344A]/60 max-h-[560px]">
            {displayedTickets.length === 0 ? (
              <div className="p-8 text-center text-xs text-[#71819A] space-y-2">
                <HelpCircle className="h-8 w-8 mx-auto text-[#71819A]/50" />
                <p>
                  {ticketTab === 'UNSOLVED'
                    ? 'No open unsolved tickets. All customer cases are resolved!'
                    : 'No resolved tickets yet.'}
                </p>
                {ticketTab === 'UNSOLVED' && (
                  <button
                    onClick={() => setIsNewTicketModalOpen(true)}
                    className="text-[#3978F6] hover:underline font-semibold text-xs cursor-pointer block mx-auto pt-1"
                  >
                    Open a new ticket
                  </button>
                )}
              </div>
            ) : (
              displayedTickets.map((t: SupportTicketItem) => {
                const isSelected = selectedTicket?.id === t.id || selectedTicket?.ticket_number === t.ticket_number;
                const isResolved = t.status === 'RESOLVED' || t.status === 'CLOSED';

                return (
                  <div
                    key={t.id || t.ticket_number}
                    onClick={() => handleSelectTicket(t)}
                    className={`p-4 cursor-pointer transition-colors text-xs ${
                      isSelected
                        ? 'bg-[#152238] border-l-4 border-l-[#3978F6]'
                        : 'hover:bg-[#101A2B]/60'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono font-bold text-[#29C5D9]">{t.ticket_number}</span>
                      <StatusBadge status={t.status} />
                    </div>

                    <h4 className="font-semibold text-[#F4F7FC] line-clamp-1 mb-1">{t.subject}</h4>

                    <div className="flex items-center gap-2 text-[10px] text-[#71819A] mb-2">
                      <span className="px-1.5 py-0.5 rounded bg-[#080D19] border border-[#25344A] text-[#A7B4C8] font-mono">
                        {t.issue_type}
                      </span>
                      {t.transfer_blocked && (
                        <span className="px-1.5 py-0.5 rounded bg-[#F06470]/15 text-[#F06470] font-bold border border-[#F06470]/30">
                          Transfer Blocked
                        </span>
                      )}
                      {isResolved && (
                        <span className="px-1.5 py-0.5 rounded bg-[#27C58B]/15 text-[#27C58B] font-bold border border-[#27C58B]/30 flex items-center gap-1">
                          <Check className="w-3 h-3" />
                          <span>Solved</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-[#71819A]">
                      <span>{new Date(t.created_at).toLocaleDateString()}</span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: WhatsApp-Style Live Chat & Clean ID Upload (8 cols) */}
        <div className="lg:col-span-8 omerta-card flex flex-col justify-between overflow-hidden min-h-[600px]">
          {selectedTicket ? (
            <>
              {/* Ticket Top Bar */}
              <div className="p-4 border-b border-[#25344A] bg-[#101A2B] flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-[#29C5D9]">{selectedTicket.ticket_number}</span>
                    <StatusBadge status={selectedTicket.status} />
                    <span className="px-2 py-0.5 rounded-full bg-[#152238] border border-[#25344A] text-[10px] font-bold text-[#A7B4C8]">
                      Priority: {selectedTicket.priority}
                    </span>
                  </div>
                  <h3 className="text-sm font-bold text-[#F4F7FC]">{selectedTicket.subject}</h3>
                </div>

                <div className="flex items-center gap-2 text-xs">
                  <div className="text-right">
                    <span className="text-[10px] uppercase font-bold text-[#71819A] block">Assigned Staff</span>
                    <span className="font-semibold text-[#F4F7FC]">
                      {selectedTicket.assigned_to_name || 'Omerta Compliance Desk'}
                    </span>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] flex items-center justify-center text-slate-950 font-bold">
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                </div>
              </div>

              {/* RESOLVED CASE CONGRATULATORY BANNER */}
              {isCaseResolved && (
                <div className="m-4 p-4 rounded-xl bg-gradient-to-r from-[#27C58B]/15 via-[#29C5D9]/10 to-[#27C58B]/15 border border-[#27C58B]/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-md">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-[#27C58B]/20 text-[#27C58B] flex items-center justify-center shrink-0">
                      <CheckCircle2 className="w-5 h-5 stroke-[2.5]" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-[#F4F7FC]">Case Solved &amp; Verified</h4>
                      <p className="text-[11px] text-[#A7B4C8]">
                        Compliance officers have verified your identity. Transfer privileges are restored!
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate('/customer')}
                    className="px-4 py-2 rounded-xl bg-[#27C58B] hover:bg-[#27C58B]/90 text-slate-950 font-black text-xs flex items-center gap-1.5 shadow-md cursor-pointer shrink-0"
                  >
                    <span>Go to Dashboard</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* ACTION REQUIRED BANNER: NATIONAL ID VERIFICATION */}
              {!isCaseResolved &&
                (selectedTicket.issue_type === 'TRANSFER_BLOCKED' ||
                  selectedTicket.issue_type === 'FORGOTTEN_TRANSFER_PASSWORD' ||
                  selectedTicket.issue_type === 'TRANSFER_PASSWORD_LOCK' ||
                  selectedTicket.issue_type === 'IDENTITY_VERIFICATION' ||
                  selectedTicket.ticket_type === 'TRANSFER_BLOCKED' ||
                  selectedTicket.ticket_type === 'FORGOTTEN_TRANSFER_PASSWORD' ||
                  selectedTicket.ticket_type === 'TRANSFER_PASSWORD_LOCK' ||
                  selectedTicket.ticket_type === 'IDENTITY_VERIFICATION' ||
                  selectedTicket.requires_identity_verification ||
                  selectedTicket.transfer_blocked ||
                  customer?.is_transfer_locked ||
                  customer?.transfer_status === 'BLOCKED') &&
                selectedTicket.identity_status !== 'VERIFIED' && (
                  <div className="m-4 mb-0 p-3.5 rounded-xl bg-gradient-to-r from-[#F4B942]/15 via-[#29C5D9]/10 to-[#F4B942]/15 border border-[#F4B942]/40 flex items-center justify-between gap-3 text-xs shadow-sm">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[#F4B942]/20 text-[#F4B942] flex items-center justify-center shrink-0">
                        <AlertTriangle className="w-4 h-4 stroke-[2.5]" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-[#F4F7FC]">Action Required: National ID Verification</h4>
                        <p className="text-[11px] text-[#A7B4C8]">
                          To reset your forgotten transfer password and restore transfer privileges, please upload your National ID in the box below.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

              {/* IDENTITY VERIFICATION UPLOAD BOX (Clean, private, user-friendly without exposing DB records) */}
              {!isCaseResolved &&
                (selectedTicket.issue_type === 'TRANSFER_BLOCKED' ||
                  selectedTicket.issue_type === 'FORGOTTEN_TRANSFER_PASSWORD' ||
                  selectedTicket.issue_type === 'TRANSFER_PASSWORD_LOCK' ||
                  selectedTicket.issue_type === 'IDENTITY_VERIFICATION' ||
                  selectedTicket.ticket_type === 'TRANSFER_BLOCKED' ||
                  selectedTicket.ticket_type === 'FORGOTTEN_TRANSFER_PASSWORD' ||
                  selectedTicket.ticket_type === 'TRANSFER_PASSWORD_LOCK' ||
                  selectedTicket.ticket_type === 'IDENTITY_VERIFICATION' ||
                  selectedTicket.requires_identity_verification ||
                  selectedTicket.transfer_blocked ||
                  selectedTicket.identity_verification ||
                  customer?.is_transfer_locked ||
                  customer?.transfer_status === 'BLOCKED') && (
                  <div className="m-4 p-4 rounded-xl bg-[#080D19] border border-[#29C5D9]/30 space-y-3">
                    <div className="flex items-center justify-between border-b border-[#25344A] pb-2">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 text-[#29C5D9]" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[#F4F7FC]">
                          Identity &amp; Account Ownership Verification
                        </h4>
                      </div>
                      {selectedTicket.identity_status && (
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                            selectedTicket.identity_status === 'VERIFIED'
                              ? 'bg-[#27C58B]/15 text-[#27C58B] border-[#27C58B]/30'
                              : selectedTicket.identity_status === 'REJECTED'
                              ? 'bg-[#F06470]/15 text-[#F06470] border-[#F06470]/30'
                              : 'bg-[#F4B942]/15 text-[#F4B942] border-[#F4B942]/30'
                          }`}
                        >
                          ID: {selectedTicket.identity_status}
                        </span>
                      )}
                    </div>

                    {/* Privacy & Security Notice */}
                    <div className="p-3 rounded-lg bg-[#101A2B] border border-[#25344A] text-xs text-[#A7B4C8] flex items-center gap-2.5">
                      <Shield className="w-4 h-4 text-[#29C5D9] shrink-0" />
                      <span>
                        🔒 <strong>End-to-End Encrypted Verification:</strong> Upload clear photos of your National ID or Passport (Front &amp; Back). Compliance officers will review your documents to verify account ownership and restore transfer services.
                      </span>
                    </div>

                    {idUploadSuccess ? (
                      <div className="p-3 rounded-lg bg-[#27C58B]/10 border border-[#27C58B]/30 text-[#27C58B] text-xs flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 shrink-0" />
                        <span>Identity documents uploaded successfully! Compliance officers will review your submission shortly.</span>
                      </div>
                    ) : (
                      <form onSubmit={handleUploadIdDocument} className="space-y-3 text-xs">
                        {idUploadError && (
                          <div className="p-2.5 rounded-lg bg-[#F06470]/10 border border-[#F06470]/30 text-[#F06470] text-[11px] flex items-center gap-2">
                            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                            <span>{idUploadError}</span>
                          </div>
                        )}

                        {/* National ID Number Input */}
                        <div>
                          <label className="block text-[10px] font-bold uppercase text-[#71819A] mb-1">
                            National ID Number (14 Digits)
                          </label>
                          <input
                            type="text"
                            maxLength={14}
                            value={nationalIdInput}
                            onChange={(e) => setNationalIdInput(e.target.value)}
                            placeholder={customer?.national_id_number || "e.g. 29801011234567"}
                            className="w-full px-3.5 py-2.5 bg-[#101A2B] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] font-mono placeholder-[#71819A] focus:outline-none focus:border-[#29C5D9] transition-colors"
                          />
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
                          {/* Front ID Upload */}
                          <div>
                            <label className="block text-[10px] font-bold uppercase text-[#71819A] mb-1">
                              ID / Passport Front Photo {idFrontPreview && '✓'}
                            </label>
                            <label className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-[#101A2B] hover:bg-[#152238] border border-[#25344A] rounded-xl text-xs text-[#A7B4C8] hover:text-[#F4F7FC] cursor-pointer transition-colors">
                              <Upload className="w-4 h-4 text-[#29C5D9]" />
                              <span className="truncate">{idFrontPreview ? 'Front Photo Attached' : 'Attach Front Photo'}</span>
                              <input
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => handleIdPhotoUpload(e, 'front')}
                              />
                            </label>
                          </div>

                          {/* Back ID Upload */}
                          <div>
                            <label className="block text-[10px] font-bold uppercase text-[#71819A] mb-1">
                              ID / Passport Back Photo {idBackPreview && '✓'}
                            </label>
                            <label className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-[#101A2B] hover:bg-[#152238] border border-[#25344A] rounded-xl text-xs text-[#A7B4C8] hover:text-[#F4F7FC] cursor-pointer transition-colors">
                              <Upload className="w-4 h-4 text-[#29C5D9]" />
                              <span className="truncate">{idBackPreview ? 'Back Photo Attached' : 'Attach Back Photo'}</span>
                              <input
                                type="file"
                                accept="image/*"
                                className="hidden"
                                onChange={(e) => handleIdPhotoUpload(e, 'back')}
                              />
                            </label>
                          </div>
                        </div>

                        {/* Image Preview Thumbnails */}
                        {(idFrontPreview || idBackPreview) && (
                          <div className="flex items-center gap-4 pt-1">
                            {idFrontPreview && (
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] text-[#71819A]">Front:</span>
                                <img
                                  src={idFrontPreview}
                                  alt="Front Preview"
                                  onClick={() => setZoomedImage(idFrontPreview)}
                                  className="h-14 w-22 object-cover rounded-lg border border-[#25344A] cursor-pointer hover:border-[#29C5D9] transition-all hover:scale-105"
                                  title="Click to view full image"
                                />
                              </div>
                            )}
                            {idBackPreview && (
                              <div className="flex items-center gap-2">
                                <span className="text-[10px] text-[#71819A]">Back:</span>
                                <img
                                  src={idBackPreview}
                                  alt="Back Preview"
                                  onClick={() => setZoomedImage(idBackPreview)}
                                  className="h-14 w-22 object-cover rounded-lg border border-[#25344A] cursor-pointer hover:border-[#29C5D9] transition-all hover:scale-105"
                                  title="Click to view full image"
                                />
                              </div>
                            )}
                          </div>
                        )}

                        {/* Submit Button */}
                        <button
                          type="submit"
                          disabled={idUploading || !idFrontPreview}
                          className="w-full py-2.5 bg-[#29C5D9] hover:bg-[#29C5D9]/90 disabled:opacity-50 text-slate-950 font-bold rounded-xl text-xs transition-all shadow-md flex items-center justify-center gap-1.5 cursor-pointer mt-2"
                        >
                          {idUploading ? (
                            <span>Submitting Documents...</span>
                          ) : (
                            <>
                              <ShieldCheck className="w-4 h-4" />
                              <span>Submit ID Verification to Compliance</span>
                            </>
                          )}
                        </button>
                      </form>
                    )}
                  </div>
                )}

              {/* WhatsApp-Style Chat Message Stream */}
              <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-[#0b141a]/90 max-h-[420px]">
                {/* Fallback Initial Description Bubble only if no message records exist */}
                {(!selectedTicket.messages || selectedTicket.messages.length === 0) && selectedTicket.description && (
                  <div className="flex justify-end items-end gap-2">
                    <div className="max-w-md rounded-2xl rounded-tr-xs bg-[#005c4b] border border-[#005c4b] text-xs p-3 space-y-1 shadow-md text-[#F4F7FC]">
                      <div className="flex items-center justify-between gap-2 text-[10px] text-[#29C5D9] font-bold">
                        <span>You (Inquiry)</span>
                        <span className="text-white/60 font-mono text-[9px]">
                          {new Date(selectedTicket.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-white leading-relaxed whitespace-pre-wrap text-[11px]">{selectedTicket.description}</p>
                      <div className="flex justify-end items-center gap-1 pt-0.5">
                        <CheckCheck className="w-3.5 h-3.5 text-[#29C5D9]" />
                      </div>
                    </div>

                    {/* Customer Avatar */}
                    <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-[#005c4b] to-[#29C5D9] text-slate-950 font-bold text-[11px] flex items-center justify-center shrink-0">
                      {customer?.name?.charAt(0) || user?.full_name?.charAt(0) || 'U'}
                    </div>
                  </div>
                )}

                {/* Stream of Message Replies */}
                {selectedTicket.messages?.map((msg: SupportMessageItem) => {
                  const isMe = msg.sender_role === 'CUSTOMER';
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

                  // Multi-photo parsing if multiple URLs separated by |||
                  const imageUrls = msg.attachment_url?.split('|||').filter(Boolean) || [];

                  return (
                    <div
                      key={msg.id}
                      className={`flex items-end gap-2 ${isMe ? 'justify-end' : 'justify-start'}`}
                    >
                      {!isMe && (
                        <div className="w-7 h-7 rounded-full bg-[#182229] border border-[#27C58B]/40 text-[#27C58B] flex items-center justify-center shrink-0">
                          <ShieldCheck className="w-4 h-4" />
                        </div>
                      )}

                      <div
                        className={`max-w-md rounded-2xl text-xs shadow-lg transition-all overflow-hidden ${
                          isMe
                            ? 'rounded-tr-xs bg-[#005c4b] text-white'
                            : 'rounded-tl-xs bg-[#202c33] border border-[#25344A] text-[#F4F7FC]'
                        }`}
                      >
                        {/* Top Sender Bar */}
                        <div className="px-3.5 pt-2 pb-1 flex items-center justify-between gap-3 text-[10px]">
                          <span
                            className={`font-bold flex items-center gap-1 ${
                              isMe ? 'text-[#29C5D9]' : 'text-[#3978F6]'
                            }`}
                          >
                            {!isMe && <ShieldCheck className="w-3.5 h-3.5 text-[#27C58B]" />}
                            {msg.sender_name} {!isMe && `[${msg.sender_role}]`}
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
                        {isMe && (
                          <div className="px-3 pb-1.5 flex justify-end items-center gap-1 text-[9px] text-[#29C5D9]">
                            <CheckCheck className="w-3.5 h-3.5 text-[#29C5D9]" />
                          </div>
                        )}
                      </div>

                      {isMe && (
                        <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-[#005c4b] to-[#29C5D9] text-slate-950 font-bold text-[11px] flex items-center justify-center shrink-0">
                          {customer?.name?.charAt(0) || user?.full_name?.charAt(0) || 'U'}
                        </div>
                      )}
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Chat Message Input Bar */}
              <div className="p-3.5 border-t border-[#25344A] bg-[#101A2B]">
                {/* Multi-attachment preview strip */}
                {chatAttachments.length > 0 && (
                  <div className="mb-2.5 flex items-center gap-2 overflow-x-auto pb-1">
                    {chatAttachments.map((att, idx) => (
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
                          onClick={() => setChatAttachments((prev) => prev.filter((_, i) => i !== idx))}
                          className="p-1 text-[#F06470] hover:bg-[#F06470]/20 rounded-full transition-colors cursor-pointer"
                          title="Remove image"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                    <span className="text-[10px] text-[#A7B4C8]">
                      {chatAttachments.length} photo(s) selected
                    </span>
                  </div>
                )}

                <form onSubmit={handleSendMessage} className="flex items-center gap-2">
                  <label
                    title="Attach multiple photos / documents"
                    className="p-2.5 rounded-xl bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-[#A7B4C8] hover:text-[#F4F7FC] cursor-pointer transition-colors"
                  >
                    <Paperclip className="w-4 h-4" />
                    <input
                      type="file"
                      multiple
                      accept="image/*"
                      className="hidden"
                      onChange={handleMultiChatFiles}
                    />
                  </label>

                  <input
                    type="text"
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    placeholder="Type a message to Compliance &amp; Audit..."
                    className="flex-1 px-4 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                  />

                  <button
                    type="submit"
                    disabled={isSending || (!messageText.trim() && chatAttachments.length === 0)}
                    className="p-2.5 rounded-xl bg-[#29C5D9] hover:bg-[#29C5D9]/90 disabled:opacity-50 text-slate-950 font-bold transition-all shadow-md shadow-cyan-500/20 cursor-pointer"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-xs text-[#71819A] space-y-3">
              <LifeBuoy className="h-12 w-12 text-[#71819A]/40" />
              <p className="text-sm font-semibold text-[#F4F7FC]">Select a ticket or open a new one</p>
              <p className="max-w-sm">
                Get real-time assistance with transfer security hold, forgotten transfer password, or KYC identity verification.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* NEW SUPPORT TICKET MODAL */}
      {isNewTicketModalOpen && (
        <Modal
          isOpen={isNewTicketModalOpen}
          onClose={() => setIsNewTicketModalOpen(false)}
          title="Open New Support &amp; Security Ticket"
          subtitle="Connect with Compliance &amp; Audit Officers"
          maxWidth="md"
        >
          <form onSubmit={handleCreateTicket} className="space-y-4 text-xs">
            {newTicketError && (
              <div className="p-3 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{newTicketError}</span>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                Issue Category
              </label>
              <select
                value={newTicketData.issue_type}
                onChange={(e) => {
                  const val = e.target.value;
                  let sub = newTicketData.subject;
                  let desc = newTicketData.description;
                  if (val === 'FORGOTTEN_TRANSFER_PASSWORD') {
                    sub = 'Forgotten Transfer Password — Identity Verification & Reset Request';
                    desc = 'I have forgotten my transfer password and cannot send money. Please verify my National ID to allow me to set a new transfer password and restore transfer privileges.';
                  } else if (val === 'TRANSFER_BLOCKED') {
                    sub = 'Transfer Password Blocked — Requesting Identity Verification';
                    desc = 'I entered my transfer password incorrectly 3 times. Please review my submitted National ID and restore my money transfer privileges.';
                  } else if (val === 'IDENTITY_VERIFICATION') {
                    sub = 'Identity Verification (KYC Update)';
                    desc = 'I am submitting my updated National ID documents for compliance verification.';
                  }
                  setNewTicketData({ ...newTicketData, issue_type: val, subject: sub, description: desc });
                }}
                className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] focus:outline-none focus:border-[#3978F6] cursor-pointer"
              >
                <option value="FORGOTTEN_TRANSFER_PASSWORD">Forgotten Transfer Password (Send Money Reset)</option>
                <option value="TRANSFER_BLOCKED">Transfer Password Blocked (3 Strikes Security Hold)</option>
                <option value="IDENTITY_VERIFICATION">Identity Verification (KYC Update)</option>
                <option value="ACCOUNT_SECURITY">Account Security &amp; Unauthorized Access</option>
                <option value="TRANSACTION_ISSUE">Transaction / Payment Dispute</option>
                <option value="OTHER">Other Inquiry</option>
              </select>
            </div>

            {/* IDENTITY VERIFICATION BANNER & ATTACHMENT IN MODAL */}
            {(newTicketData.issue_type === 'FORGOTTEN_TRANSFER_PASSWORD' ||
              newTicketData.issue_type === 'TRANSFER_BLOCKED' ||
              newTicketData.issue_type === 'IDENTITY_VERIFICATION' ||
              newTicketData.issue_type === 'ACCOUNT_SECURITY') && (
              <div className="p-3.5 rounded-xl bg-gradient-to-r from-[#29C5D9]/15 via-[#3978F6]/10 to-[#29C5D9]/15 border border-[#29C5D9]/40 space-y-3 text-xs">
                <div className="flex items-center gap-2 text-[#29C5D9] font-bold">
                  <ShieldCheck className="w-4 h-4 text-[#29C5D9] shrink-0" />
                  <span>National ID Verification Required for Transfer Recovery</span>
                </div>
                <p className="text-[11px] text-[#A7B4C8] leading-relaxed">
                  To reset your transfer password or restore sending money, Compliance Officers must verify your National ID. You can attach your ID front &amp; back photos right now below, or upload them in the ticket chat after opening.
                </p>

                {/* Optional National ID Number Input */}
                <div>
                  <label className="block text-[10px] font-bold uppercase text-[#71819A] mb-1">
                    National ID Number (14 Digits)
                  </label>
                  <input
                    type="text"
                    maxLength={14}
                    value={modalNationalId}
                    onChange={(e) => setModalNationalId(e.target.value)}
                    placeholder={customer?.national_id_number || "e.g. 29801011234567"}
                    className="w-full px-3 py-2 bg-[#101A2B] border border-[#25344A] rounded-lg text-xs text-[#F4F7FC] font-mono placeholder-[#71819A] focus:outline-none focus:border-[#29C5D9]"
                  />
                </div>

                {/* Front & Back Photo Attachments */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 items-end">
                  <div>
                    <label className="block text-[10px] font-bold uppercase text-[#71819A] mb-1">
                      ID Front Photo {modalIdFront && '✓'}
                    </label>
                    <label className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-[#101A2B] hover:bg-[#152238] border border-[#25344A] rounded-lg text-[11px] text-[#A7B4C8] hover:text-[#F4F7FC] cursor-pointer transition-colors">
                      <Upload className="w-3.5 h-3.5 text-[#29C5D9]" />
                      <span className="truncate">{modalIdFront ? 'Front Attached' : 'Attach Front ID'}</span>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => handleModalPhotoUpload(e, 'front')}
                      />
                    </label>
                  </div>

                  <div>
                    <label className="block text-[10px] font-bold uppercase text-[#71819A] mb-1">
                      ID Back Photo {modalIdBack && '✓'}
                    </label>
                    <label className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-[#101A2B] hover:bg-[#152238] border border-[#25344A] rounded-lg text-[11px] text-[#A7B4C8] hover:text-[#F4F7FC] cursor-pointer transition-colors">
                      <Upload className="w-3.5 h-3.5 text-[#29C5D9]" />
                      <span className="truncate">{modalIdBack ? 'Back Attached' : 'Attach Back ID'}</span>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={(e) => handleModalPhotoUpload(e, 'back')}
                      />
                    </label>
                  </div>
                </div>

                {/* Thumbnails if attached */}
                {(modalIdFront || modalIdBack) && (
                  <div className="flex items-center gap-3 pt-1">
                    {modalIdFront && (
                      <div className="flex items-center gap-1.5 text-[10px] text-[#27C58B]">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Front Photo Ready</span>
                      </div>
                    )}
                    {modalIdBack && (
                      <div className="flex items-center gap-1.5 text-[10px] text-[#27C58B]">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Back Photo Ready</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                Subject
              </label>
              <input
                type="text"
                required
                value={newTicketData.subject}
                onChange={(e) => setNewTicketData({ ...newTicketData, subject: e.target.value })}
                placeholder="Brief summary of your issue"
                className="w-full px-3.5 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                Description &amp; Context
              </label>
              <textarea
                required
                rows={3}
                value={newTicketData.description}
                onChange={(e) => setNewTicketData({ ...newTicketData, description: e.target.value })}
                placeholder="Explain the issue in detail. If your transfer password is blocked or forgotten, let us know so we can initiate National ID verification."
                className="w-full px-3.5 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsNewTicketModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={newTicketLoading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-white font-bold shadow-lg shadow-blue-500/25 cursor-pointer"
              >
                {newTicketLoading ? (
                  <span>Opening Ticket...</span>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    <span>Open Ticket</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* ZOOMED IMAGE / DOCUMENT MODAL */}
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
                alt="Document Full View"
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
