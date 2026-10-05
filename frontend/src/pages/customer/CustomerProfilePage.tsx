import React, { useState, useEffect } from 'react';
import {
  UserCheck,
  Copy,
  Check,
  Globe,
  Wallet,
  ShieldCheck,
  Mail,
  Calendar,
  Phone,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import type { CustomerProfile } from '../../types';

const COUNTRY_NAMES: Record<string, { label: string; flag: string }> = {
  EG: { label: 'Egypt (EG)', flag: '🇪🇬' },
  SA: { label: 'Saudi Arabia (SA)', flag: '🇸🇦' },
  AE: { label: 'United Arab Emirates (AE)', flag: '🇦🇪' },
  US: { label: 'United States (US)', flag: '🇺🇸' },
  GB: { label: 'United Kingdom (GB)', flag: '🇬🇧' },
  DE: { label: 'Germany (DE)', flag: '🇩🇪' },
  FR: { label: 'France (FR)', flag: '🇫🇷' },
  CA: { label: 'Canada (CA)', flag: '🇨🇦' },
  KW: { label: 'Kuwait (KW)', flag: '🇰🇼' },
  QA: { label: 'Qatar (QA)', flag: '🇶🇦' },
};

export const CustomerProfilePage: React.FC = () => {
  const { user, customer } = useAuth();
  const [profile, setProfile] = useState<CustomerProfile | null>(null);
  const [copied, setCopied] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchProfile = async () => {
      setIsLoading(true);
      try {
        const res = await api.getCustomerProfile();
        setProfile(res);
      } catch {
        setProfile(customer);
      } finally {
        setIsLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const handleCopyUserNumber = () => {
    const num = profile?.omerta_user_number || customer?.omerta_user_number;
    if (num) {
      navigator.clipboard.writeText(num);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const currentProfile = profile || customer;
  const countryCode = currentProfile?.declared_country || 'EG';
  const countryInfo = COUNTRY_NAMES[countryCode] || { label: `${countryCode}`, flag: '🌐' };

  if (isLoading && !currentProfile) {
    return (
      <div className="py-20 flex flex-col items-center justify-center text-[#A7B4C8]">
        <Loader2 className="h-8 w-8 animate-spin text-[#29C5D9] mb-3" />
        <p className="text-xs font-semibold">Loading verified customer profile...</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-2">
          <UserCheck className="h-6 w-6 text-[#3978F6]" />
          <span>Customer Profile</span>
        </h1>
        <p className="text-xs text-[#A7B4C8] mt-1">
          Your verified banking identity, phone credentials, and unique Omerta transfer identifier
        </p>
      </div>

      {/* Main Profile Card */}
      <div className="p-6 omerta-card bg-[#101A2B] border-[#25344A] space-y-6 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#25344A]">
          <div className="flex items-center gap-4">
            <div className="h-14 w-14 rounded-2xl bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] text-slate-950 font-black flex items-center justify-center text-xl shadow-lg shadow-cyan-500/20">
              {currentProfile?.name?.charAt(0) || user?.full_name?.charAt(0) || 'C'}
            </div>
            <div>
              <h2 className="text-lg font-bold text-[#F4F7FC]">{currentProfile?.name || user?.full_name}</h2>
              <p className="text-xs text-[#71819A] flex items-center gap-1.5 mt-0.5">
                <Mail className="h-3.5 w-3.5 text-[#3978F6]" />
                <span className="text-[#A7B4C8]">{currentProfile?.email || user?.email}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-3 py-1 rounded-full bg-[#27C58B]/15 text-[#27C58B] border border-[#27C58B]/30 text-xs font-bold uppercase flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>{currentProfile?.status || 'ACTIVE'}</span>
            </span>
          </div>
        </div>

        {/* Unique Omerta User Number Box */}
        <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#A7B4C8]">
                Unique Omerta User Number
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#3978F6]/20 text-[#3978F6] border border-[#3978F6]/40">
                P2P Transfer ID
              </span>
            </div>
            <p className="font-mono text-lg font-black text-[#29C5D9] tracking-wider">
              {currentProfile?.omerta_user_number || 'OMR-1092-4821'}
            </p>
            <p className="text-[11px] text-[#71819A]">
              Share this identifier or your registered mobile phone with other users to receive transfers.
            </p>
          </div>

          <button
            onClick={handleCopyUserNumber}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-xs text-[#F4F7FC] font-semibold transition-colors shrink-0 shadow-sm"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-[#27C58B]" />
                <span className="text-[#27C58B]">Copied!</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 text-[#3978F6]" />
                <span>Copy Number</span>
              </>
            )}
          </button>
        </div>

        {/* Profile Attributes */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Registered Mobile Phone */}
          <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#71819A] flex items-center gap-1.5">
              <Phone className="h-3.5 w-3.5 text-[#29C5D9]" /> Registered Mobile Phone
            </span>
            <p className="text-sm font-bold font-mono text-[#F4F7FC] flex items-center gap-2">
              <span>{countryInfo.flag}</span>
              <span>{currentProfile?.phone || '+20 10 1111 2222'}</span>
            </p>
            <p className="text-[10px] text-[#71819A]">
              Verified mobile identifier for direct phone-to-phone transfers.
            </p>
          </div>

          {/* Account Verification Tier */}
          <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#71819A] flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-[#27C58B]" /> Verification Status
            </span>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-[#27C58B]">Tier 1 Verified</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#27C58B]/10 text-[#27C58B] border border-[#27C58B]/30">
                Full Demo Access
              </span>
            </div>
            <p className="text-[10px] text-[#71819A]">
              Standard banking tier with peer-to-peer sending & receiving limits.
            </p>
          </div>

          {/* Declared Country */}
          <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#71819A] flex items-center gap-1.5">
              <Globe className="h-3.5 w-3.5 text-[#3978F6]" /> Declared Country
            </span>
            <p className="text-sm font-bold text-[#F4F7FC] flex items-center gap-2">
              <span>{countryInfo.flag}</span>
              <span>{countryInfo.label}</span>
            </p>
            <p className="text-[10px] text-[#71819A]">
              Primary banking jurisdiction for simulated regional clearing.
            </p>
          </div>

          {/* Preferred Currency */}
          <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#71819A] flex items-center gap-1.5">
              <Wallet className="h-3.5 w-3.5 text-[#29C5D9]" /> Preferred Currency
            </span>
            <p className="text-sm font-bold text-[#F4F7FC]">
              {currentProfile?.preferred_currency || 'EGP'}
            </p>
            <p className="text-[10px] text-[#71819A]">
              Default denom for new accounts and transfer calculations.
            </p>
          </div>

          {/* Member Since */}
          <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-1.5 sm:col-span-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#71819A] flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5 text-[#A7B4C8]" /> Member Since
            </span>
            <p className="text-sm font-bold text-[#F4F7FC]">
              {currentProfile?.member_since
                ? new Date(currentProfile.member_since).toLocaleDateString(undefined, {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })
                : 'January 2026'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
