import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Send,
  Search,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ShieldCheck,
  ArrowLeft,
  Copy,
  Check,
  RotateCcw,
  Lock,
  Eye,
  EyeOff,
  ChevronDown,
  AlertTriangle,
  RefreshCw,
  LogOut,
  Smartphone,
  Hash,
} from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { collectNetworkTelemetry } from '../../utils/telemetry';
import { Modal } from '../../components/common/Modal';
import type { CustomerAccount, RecipientLookupResult, TransferReceipt } from '../../types';

interface CountryOption {
  code: string;
  name: string;
  dialCode: string;
  flag: string;
}

const COUNTRY_OPTIONS: CountryOption[] = [
  { code: 'EG', name: 'Egypt', dialCode: '+20', flag: '🇪🇬' },
  { code: 'SA', name: 'Saudi Arabia', dialCode: '+966', flag: '🇸🇦' },
  { code: 'AE', name: 'United Arab Emirates', dialCode: '+971', flag: '🇦🇪' },
  { code: 'KW', name: 'Kuwait', dialCode: '+965', flag: '🇰🇼' },
  { code: 'QA', name: 'Qatar', dialCode: '+974', flag: '🇶🇦' },
  { code: 'BH', name: 'Bahrain', dialCode: '+973', flag: '🇧🇭' },
  { code: 'OM', name: 'Oman', dialCode: '+968', flag: '🇴🇲' },
  { code: 'JO', name: 'Jordan', dialCode: '+962', flag: '🇯🇴' },
  { code: 'LB', name: 'Lebanon', dialCode: '+961', flag: '🇱🇧' },
  { code: 'IQ', name: 'Iraq', dialCode: '+964', flag: '🇮🇶' },
  { code: 'US', name: 'United States', dialCode: '+1', flag: '🇺🇸' },
  { code: 'GB', name: 'United Kingdom', dialCode: '+44', flag: '🇬🇧' },
  { code: 'DE', name: 'Germany', dialCode: '+49', flag: '🇩🇪' },
  { code: 'FR', name: 'France', dialCode: '+33', flag: '🇫🇷' },
  { code: 'IT', name: 'Italy', dialCode: '+39', flag: '🇮🇹' },
  { code: 'TR', name: 'Turkey', dialCode: '+90', flag: '🇹🇷' },
  { code: 'JP', name: 'Japan', dialCode: '+81', flag: '🇯🇵' },
];

export const SendMoneyPage: React.FC = () => {
  const { customer, logout } = useAuth();
  const navigate = useNavigate();

  // Multi-step transfer state: 1 = Recipient, 2 = Amount & Account, 3 = Confirm, 4 = Receipt
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  // Form states
  const [inputMode, setInputMode] = useState<'phone' | 'omerta_number'>('phone');
  const [selectedCountry, setSelectedCountry] = useState<CountryOption>(COUNTRY_OPTIONS[0]); // Default Egypt
  const [countryDropdownOpen, setCountryDropdownOpen] = useState(false);
  const [countrySearch, setCountrySearch] = useState('');

  const [phoneInput, setPhoneInput] = useState('');
  const [omertaNumberInput, setOmertaNumberInput] = useState('');

  const [lookupResult, setLookupResult] = useState<RecipientLookupResult | null>(null);
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);

  const [accounts, setAccounts] = useState<CustomerAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<CustomerAccount | null>(null);
  const [amount, setAmount] = useState<string>('');
  const [note, setNote] = useState<string>('');
  const [authPassword, setAuthPassword] = useState('');
  const [showAuthPassword, setShowAuthPassword] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<TransferReceipt | null>(null);
  const [copiedReceipt, setCopiedReceipt] = useState(false);

  // Security modals
  const [vpnModalOpen, setVpnModalOpen] = useState(false);
  const [vpnDetails, setVpnDetails] = useState<{ isp?: string; country?: string; org?: string; reason?: string } | null>(null);
  const [isRecheckingVpn, setIsRecheckingVpn] = useState(false);

  const [lockoutModalOpen, setLockoutModalOpen] = useState(false);
  const [lockoutMessage, setLockoutMessage] = useState<string>('');

  // Load customer accounts
  useEffect(() => {
    const fetchAccounts = async () => {
      try {
        const res = await api.getCustomerAccounts();
        setAccounts(res);
        if (res.length > 0) {
          setSelectedAccount(res[0]);
        }
      } catch {
        const fallback: CustomerAccount[] = [
          { account_id: 'ACC-1001', account_type: 'CHECKING', currency: 'EGP', balance: 50000.0, status: 'ACTIVE' },
        ];
        setAccounts(fallback);
        setSelectedAccount(fallback[0]);
      }
    };
    fetchAccounts();
  }, []);

  // Quick recipient lookup handler
  const handleLookup = async (targetValue?: string) => {
    let valueToQuery = '';
    if (targetValue) {
      valueToQuery = targetValue.trim();
    } else if (inputMode === 'phone') {
      const cleanPhoneDigits = phoneInput.replace(/\D/g, '').replace(/^0+/, '');
      if (!cleanPhoneDigits) {
        setLookupError('Please enter the recipient mobile phone number.');
        return;
      }
      valueToQuery = `${selectedCountry.dialCode}${cleanPhoneDigits}`;
    } else {
      valueToQuery = omertaNumberInput.trim().toUpperCase();
      if (!valueToQuery) {
        setLookupError('Please enter the recipient Omerta User Number (e.g. OMR-3847-1920).');
        return;
      }
    }

    const cleanUpper = valueToQuery.toUpperCase();
    if (
      cleanUpper === customer?.omerta_user_number ||
      (customer?.phone && valueToQuery.replace(/\s+/g, '') === customer.phone.replace(/\s+/g, ''))
    ) {
      setLookupError('You cannot transfer funds to your own account or phone number.');
      return;
    }

    setIsLookingUp(true);
    setLookupError(null);
    try {
      const res = await api.lookupRecipient(valueToQuery);
      setLookupResult(res);
      setStep(2);
    } catch (err: any) {
      setLookupError(err.message || 'Recipient not found. Please verify the mobile number or Omerta User Number.');
      setLookupResult(null);
    } finally {
      setIsLookingUp(false);
    }
  };

  // Quick preset buttons for amounts
  const handlePresetAmount = (fraction: number) => {
    if (!selectedAccount) return;
    const computed = (selectedAccount.balance * fraction).toFixed(2);
    setAmount(computed);
  };

  // Re-check VPN connection from modal
  const handleRecheckVpnConnection = async () => {
    setIsRecheckingVpn(true);
    try {
      const telemetry = await collectNetworkTelemetry('EG');
      if (!telemetry.is_vpn) {
        setVpnModalOpen(false);
        setVpnDetails(null);
        setSubmitError(null);
        // Automatically retry transfer execution
        handleExecuteTransfer();
      } else {
        setVpnDetails({
          isp: telemetry.isp,
          country: telemetry.country,
          org: telemetry.org,
          reason: telemetry.vpn_reason || 'Commercial VPN/Proxy tunnel still detected.',
        });
      }
    } finally {
      setIsRecheckingVpn(false);
    }
  };

  // Execute transfer
  const handleExecuteTransfer = async () => {
    if (!selectedAccount || !lookupResult || !amount) return;
    if (!authPassword) {
      setSubmitError('Please enter your account password to authorize the transfer.');
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      // Gather real network telemetry to detect VPN / Proxy anonymizers
      const telemetry = await collectNetworkTelemetry('EG');

      // Intercept active VPN and display popup modal
      if (telemetry.is_vpn) {
        setVpnDetails({
          isp: telemetry.isp,
          country: telemetry.country,
          org: telemetry.org,
          reason: telemetry.vpn_reason || 'Encrypted proxy or datacenter tunnel observed.',
        });
        setVpnModalOpen(true);
        setIsSubmitting(false);
        return;
      }

      const res = await api.initiateTransfer({
        sender_account_id: selectedAccount.account_id,
        recipient_user_number: lookupResult.omerta_user_number,
        amount: parseFloat(amount),
        currency: selectedAccount.currency,
        note: note.trim() || undefined,
        password: authPassword,
        is_vpn: telemetry.is_vpn,
        client_ip: telemetry.ip,
        country: telemetry.country,
        isp: telemetry.isp,
        org: telemetry.org,
        browser_timezone: telemetry.browser_timezone,
        ip_timezone: telemetry.ip_timezone,
      });

      setReceipt(res);
      setStep(4);
    } catch (err: any) {
      // Check for 3-failed password attempt account lockout
      if (
        err?.status === 403 &&
        (err?.message?.includes('INACTIVATED') || err?.message?.includes('3 consecutive') || err?.error === 'ACCOUNT_INACTIVATED_LOCKOUT')
      ) {
        setLockoutMessage(
          err.message ||
            'Security Alert: 3 consecutive incorrect password attempts detected. Your account has been inactivated and you have been logged out. An Administrator must review and reactivate your account in the Admin Control Center.'
        );
        setLockoutModalOpen(true);
      } else if (err?.message?.includes('VPN') || err?.error === 'VPN_TRANSFER_BLOCKED') {
        setVpnDetails({
          isp: 'VPN / Datacenter Gateway',
          country: 'Commercial Proxy',
          reason: err.message,
        });
        setVpnModalOpen(true);
      } else {
        setSubmitError(err.message || 'Transfer failed. Please check your available balance and try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAcknowledgeLockout = () => {
    setLockoutModalOpen(false);
    logout();
    navigate('/login');
  };

  const handleCopyReceipt = () => {
    if (receipt) {
      const text = `Omerta.ai Transfer Receipt\nID: ${receipt.transfer_id}\nAmount: ${receipt.formatted_amount}\nTo: ${receipt.recipient.name} (${receipt.recipient.omerta_user_number})\nDate: ${new Date(receipt.created_at).toLocaleString()}`;
      navigator.clipboard.writeText(text);
      setCopiedReceipt(true);
      setTimeout(() => setCopiedReceipt(false), 2000);
    }
  };

  const resetForm = () => {
    setPhoneInput('');
    setOmertaNumberInput('');
    setLookupResult(null);
    setAmount('');
    setNote('');
    setAuthPassword('');
    setSubmitError(null);
    setReceipt(null);
    setStep(1);
  };

  const filteredCountries = COUNTRY_OPTIONS.filter(
    (c) =>
      c.name.toLowerCase().includes(countrySearch.toLowerCase()) ||
      c.dialCode.includes(countrySearch) ||
      c.code.toLowerCase().includes(countrySearch.toLowerCase())
  );

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-in fade-in duration-200">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-2">
            <Send className="h-6 w-6 text-[#3978F6]" />
            <span>Send Money</span>
          </h1>
          <p className="text-xs text-[#A7B4C8] mt-1">
            Simulated peer-to-peer transfer by National Flag &amp; Mobile Number or Omerta User #
          </p>
        </div>

        {/* Step Indicator */}
        <div className="hidden sm:flex items-center gap-2 text-xs font-semibold text-[#A7B4C8]">
          <span className={`px-2.5 py-1 rounded-full ${step >= 1 ? 'bg-[#3978F6] text-[#F4F7FC]' : 'bg-[#152238] text-[#71819A]'}`}>1</span>
          <span className="text-[#25344A]">―</span>
          <span className={`px-2.5 py-1 rounded-full ${step >= 2 ? 'bg-[#3978F6] text-[#F4F7FC]' : 'bg-[#152238] text-[#71819A]'}`}>2</span>
          <span className="text-[#25344A]">―</span>
          <span className={`px-2.5 py-1 rounded-full ${step >= 3 ? 'bg-[#3978F6] text-[#F4F7FC]' : 'bg-[#152238] text-[#71819A]'}`}>3</span>
        </div>
      </div>

      {/* STEP 1: Enter Recipient with Flag Selector or Omerta ID */}
      {step === 1 && (
        <div className="p-6 omerta-card bg-[#101A2B] border-[#25344A] space-y-6 shadow-xl">
          {/* Mode Tabs: Mobile with Flag vs Omerta Number */}
          <div className="flex items-center gap-2 p-1 rounded-xl bg-[#080D19] border border-[#25344A]">
            <button
              type="button"
              onClick={() => {
                setInputMode('phone');
                setLookupError(null);
              }}
              className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer ${
                inputMode === 'phone'
                  ? 'bg-[#3978F6] text-[#F4F7FC] shadow-sm'
                  : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
              }`}
            >
              <Smartphone className="w-3.5 h-3.5" />
              <span>Mobile Phone (Flag Picker)</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setInputMode('omerta_number');
                setLookupError(null);
              }}
              className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 cursor-pointer ${
                inputMode === 'omerta_number'
                  ? 'bg-[#3978F6] text-[#F4F7FC] shadow-sm'
                  : 'text-[#A7B4C8] hover:text-[#F4F7FC]'
              }`}
            >
              <Hash className="w-3.5 h-3.5" />
              <span>Omerta User Number</span>
            </button>
          </div>

          {/* Phone Mode with National Flag Picker */}
          {inputMode === 'phone' ? (
            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-[#A7B4C8]">
                Select Recipient National Flag &amp; Enter Mobile Number
              </label>

              <div className="flex gap-2 items-center">
                {/* Flag / Country Dropdown Button */}
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setCountryDropdownOpen(!countryDropdownOpen)}
                    className="flex items-center gap-2 px-3.5 py-3 bg-[#080D19] hover:bg-[#152238] border border-[#25344A] rounded-xl text-xs font-bold text-[#F4F7FC] transition-colors cursor-pointer shrink-0"
                  >
                    <span className="text-xl leading-none">{selectedCountry.flag}</span>
                    <span className="font-mono text-[#29C5D9]">{selectedCountry.dialCode}</span>
                    <ChevronDown className="w-3.5 h-3.5 text-[#71819A]" />
                  </button>

                  {/* Flag Picker Modal Dropdown */}
                  {countryDropdownOpen && (
                    <div className="absolute left-0 top-full mt-2 w-72 max-h-64 overflow-y-auto bg-[#101A2B] border border-[#25344A] rounded-xl shadow-2xl z-50 p-2 space-y-1">
                      <div className="p-1 sticky top-0 bg-[#101A2B] z-10">
                        <input
                          type="text"
                          placeholder="Search country or code..."
                          value={countrySearch}
                          onChange={(e) => setCountrySearch(e.target.value)}
                          className="w-full px-2.5 py-1.5 bg-[#080D19] border border-[#25344A] rounded-lg text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
                          autoFocus
                        />
                      </div>
                      {filteredCountries.map((c) => (
                        <button
                          key={c.code}
                          type="button"
                          onClick={() => {
                            setSelectedCountry(c);
                            setCountryDropdownOpen(false);
                            setCountrySearch('');
                          }}
                          className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors cursor-pointer ${
                            selectedCountry.code === c.code
                              ? 'bg-[#3978F6]/20 text-[#29C5D9] font-bold'
                              : 'text-[#F4F7FC] hover:bg-[#152238]'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <span className="text-base">{c.flag}</span>
                            <span>{c.name}</span>
                          </div>
                          <span className="font-mono text-[11px] text-[#A7B4C8]">{c.dialCode}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Mobile Phone Input */}
                <div className="relative flex-1">
                  <input
                    type="tel"
                    value={phoneInput}
                    onChange={(e) => {
                      setPhoneInput(e.target.value);
                      setLookupError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleLookup();
                      }
                    }}
                    placeholder="e.g. 10 2222 3333 or 10 1111 2222"
                    className="w-full pl-4 pr-12 py-3 bg-[#080D19] border border-[#25344A] rounded-xl text-sm text-[#F4F7FC] placeholder-[#71819A] font-mono tracking-wider focus:outline-none focus:border-[#3978F6] transition-colors"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={() => handleLookup()}
                    className="absolute right-3 top-3 p-1 rounded-lg bg-[#152238] hover:bg-[#1B2B43] text-[#3978F6] cursor-pointer"
                  >
                    <Search className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <p className="text-[11px] text-[#71819A]">
                Selected destination: <span className="text-[#29C5D9] font-semibold">{selectedCountry.flag} {selectedCountry.name} ({selectedCountry.dialCode})</span>. You do not need to type the country code manually.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-[#A7B4C8]">
                Recipient Omerta User Number
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={omertaNumberInput}
                  onChange={(e) => {
                    setOmertaNumberInput(e.target.value);
                    setLookupError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleLookup();
                    }
                  }}
                  placeholder="e.g. OMR-3847-1920 or OMR-7193-8402"
                  className="w-full pl-4 pr-12 py-3 bg-[#080D19] border border-[#25344A] rounded-xl text-sm text-[#F4F7FC] placeholder-[#71819A] font-mono tracking-wider uppercase focus:outline-none focus:border-[#3978F6] transition-colors"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => handleLookup()}
                  className="absolute right-3 top-3 p-1 rounded-lg bg-[#152238] hover:bg-[#1B2B43] text-[#3978F6] cursor-pointer"
                >
                  <Search className="h-4 w-4" />
                </button>
              </div>
              <p className="text-[11px] text-[#71819A]">
                Enter unique Omerta User Number (e.g. <span className="text-[#29C5D9] font-mono">OMR-3847-1920</span> for Layla Hassan).
              </p>
            </div>
          )}

          {/* Direct Verification Info Box */}
          <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-2">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#29C5D9]">
              <ShieldCheck className="h-4 w-4" />
              <span>Direct Real-Time Banking Verification</span>
            </div>
            <p className="text-[11px] text-[#A7B4C8] leading-relaxed">
              Recipients are verified automatically against the Omerta PostgreSQL Ledger. Double-entry funds transfer will credit the recipient instantly upon confirmation.
            </p>
          </div>

          {lookupError && (
            <div className="p-3.5 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{lookupError}</span>
            </div>
          )}

          <button
            type="button"
            onClick={() => handleLookup()}
            disabled={isLookingUp || (inputMode === 'phone' ? !phoneInput.trim() : !omertaNumberInput.trim())}
            className="w-full py-3.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-[#F4F7FC] text-sm font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25 cursor-pointer"
          >
            {isLookingUp ? (
              <span>Verifying Recipient Profile...</span>
            ) : (
              <>
                <span>Verify Recipient &amp; Continue</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      )}

      {/* STEP 2: Amount & Account Selection */}
      {step === 2 && lookupResult && (
        <div className="p-6 omerta-card bg-[#101A2B] border-[#25344A] space-y-6 shadow-xl">
          {/* Verified Recipient Banner */}
          <div className="p-4 rounded-xl bg-[#080D19] border border-[#27C58B]/40 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-xl bg-[#27C58B]/15 text-[#27C58B] border border-[#27C58B]/30">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <div>
                <span className="text-xs font-bold text-[#F4F7FC] block">
                  Verified Recipient: {lookupResult.display_name}
                </span>
                <div className="flex items-center gap-2 text-[11px] text-[#A7B4C8] mt-0.5">
                  <span className="font-mono text-[#29C5D9]">{lookupResult.omerta_user_number}</span>
                  {lookupResult.phone_masked && (
                    <>
                      <span>•</span>
                      <span className="font-mono text-[#27C58B]">{lookupResult.phone_masked}</span>
                    </>
                  )}
                  <span>•</span>
                  <span>{lookupResult.country}</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => setStep(1)}
              className="text-xs text-[#3978F6] hover:underline font-semibold cursor-pointer"
            >
              Change
            </button>
          </div>

          {/* Source Account Selection */}
          <div className="space-y-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-[#A7B4C8]">
              From Account
            </label>
            <select
              value={selectedAccount?.account_id}
              onChange={(e) => {
                const acc = accounts.find((a) => a.account_id === e.target.value);
                if (acc) setSelectedAccount(acc);
              }}
              className="w-full px-3.5 py-3 bg-[#080D19] border border-[#25344A] rounded-xl text-sm text-[#F4F7FC] focus:outline-none focus:border-[#3978F6] cursor-pointer"
            >
              {accounts.map((acc) => (
                <option key={acc.account_id} value={acc.account_id} className="bg-[#101A2B] text-[#F4F7FC]">
                  {acc.account_type} ({acc.account_id}) — Available: {acc.balance.toLocaleString()} {acc.currency}
                </option>
              ))}
            </select>
          </div>

          {/* Amount Input */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <label className="font-bold uppercase tracking-wider text-[#A7B4C8]">Transfer Amount</label>
              <span className="text-[#A7B4C8]">
                Available: <strong className="text-[#F4F7FC] font-mono">{selectedAccount?.balance.toLocaleString()} {selectedAccount?.currency}</strong>
              </span>
            </div>

            <div className="relative">
              <input
                type="number"
                step="0.01"
                min="1"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="w-full pl-4 pr-16 py-3 bg-[#080D19] border border-[#25344A] rounded-xl text-xl text-[#F4F7FC] font-mono font-bold focus:outline-none focus:border-[#3978F6]"
                autoFocus
              />
              <span className="absolute right-4 top-3.5 text-sm font-bold text-[#29C5D9]">
                {selectedAccount?.currency}
              </span>
            </div>

            {/* Preset Amount Chips */}
            <div className="grid grid-cols-4 gap-2 pt-1">
              <button
                type="button"
                onClick={() => handlePresetAmount(0.1)}
                className="py-1.5 rounded-lg bg-[#080D19] hover:bg-[#152238] border border-[#25344A] text-xs font-semibold text-[#A7B4C8] transition-colors cursor-pointer"
              >
                10%
              </button>
              <button
                type="button"
                onClick={() => handlePresetAmount(0.25)}
                className="py-1.5 rounded-lg bg-[#080D19] hover:bg-[#152238] border border-[#25344A] text-xs font-semibold text-[#A7B4C8] transition-colors cursor-pointer"
              >
                25%
              </button>
              <button
                type="button"
                onClick={() => handlePresetAmount(0.5)}
                className="py-1.5 rounded-lg bg-[#080D19] hover:bg-[#152238] border border-[#25344A] text-xs font-semibold text-[#A7B4C8] transition-colors cursor-pointer"
              >
                50%
              </button>
              <button
                type="button"
                onClick={() => handlePresetAmount(1.0)}
                className="py-1.5 rounded-lg bg-[#080D19] hover:bg-[#152238] border border-[#3978F6]/40 text-xs font-bold text-[#3978F6] transition-colors cursor-pointer"
              >
                Max Balance
              </button>
            </div>
          </div>

          {/* Optional Note */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold uppercase tracking-wider text-[#A7B4C8]">
              Transfer Reference / Note (Optional)
            </label>
            <input
              type="text"
              maxLength={100}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Shared expenses, invoice payment, gift..."
              className="w-full px-3.5 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
            />
          </div>

          {submitError && (
            <div className="p-3.5 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="px-4 py-3 rounded-xl bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-xs font-semibold text-[#F4F7FC] flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>

            <button
              type="button"
              onClick={() => setStep(3)}
              disabled={Boolean(!amount || parseFloat(amount) <= 0 || (selectedAccount && parseFloat(amount) > selectedAccount.balance))}
              className="flex-1 py-3.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-[#F4F7FC] text-sm font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25 cursor-pointer"
            >
              <span>Review Details</span>
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: Review & Explicit Confirmation */}
      {step === 3 && lookupResult && selectedAccount && (
        <div className="p-6 omerta-card bg-[#101A2B] border-[#25344A] space-y-6 shadow-xl">
          <div className="text-center py-2">
            <span className="text-xs font-bold uppercase tracking-wider text-[#A7B4C8]">Total Transfer Amount</span>
            <div className="text-3xl font-black text-[#F4F7FC] font-mono my-1">
              {parseFloat(amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {selectedAccount.currency}
            </div>
            <span className="text-[11px] text-[#27C58B] font-semibold">Simulated Demo Transfer Fee: $0.00</span>
          </div>

          {/* Transfer Summary Table */}
          <div className="divide-y divide-[#25344A] border border-[#25344A] rounded-xl bg-[#080D19] text-xs">
            <div className="p-3.5 flex justify-between items-center">
              <span className="text-[#A7B4C8]">Recipient Name</span>
              <span className="font-bold text-[#F4F7FC]">{lookupResult.display_name}</span>
            </div>
            <div className="p-3.5 flex justify-between items-center">
              <span className="text-[#A7B4C8]">Recipient Identifier</span>
              <span className="font-mono font-bold text-[#29C5D9]">{lookupResult.omerta_user_number}</span>
            </div>
            {lookupResult.phone_masked && (
              <div className="p-3.5 flex justify-between items-center">
                <span className="text-[#A7B4C8]">Recipient Phone</span>
                <span className="font-mono font-bold text-[#27C58B]">{lookupResult.phone_masked}</span>
              </div>
            )}
            <div className="p-3.5 flex justify-between items-center">
              <span className="text-[#A7B4C8]">From Account</span>
              <span className="font-mono text-[#F4F7FC]">{selectedAccount.account_id}</span>
            </div>
            {note && (
              <div className="p-3.5 flex justify-between items-center">
                <span className="text-[#A7B4C8]">Note</span>
                <span className="text-[#F4F7FC] italic">{note}</span>
              </div>
            )}
            <div className="p-3.5 flex justify-between items-center">
              <span className="text-[#A7B4C8]">Ledger Integrity</span>
              <span className="text-[#27C58B] font-semibold flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4" /> Atomic Double-Entry Commit
              </span>
            </div>
          </div>

          {/* Security Authorization: Password Confirmation */}
          <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-2 text-left">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-[#A7B4C8] uppercase tracking-wider flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-[#29C5D9]" />
                <span>Security Verification — Enter Account Password</span>
              </label>
              <span className="text-[10px] text-[#29C5D9] font-semibold">Required</span>
            </div>
            <div className="relative">
              <input
                type={showAuthPassword ? 'text' : 'password'}
                required
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                placeholder="Enter your account password to authorize transfer"
                className="w-full pl-3.5 pr-10 py-2.5 bg-[#101A2B] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#27C58B]"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowAuthPassword(!showAuthPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#71819A] hover:text-[#F4F7FC] cursor-pointer"
              >
                {showAuthPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-[10px] text-[#71819A]">
              Warning: 3 consecutive incorrect attempts will permanently lock and inactivate your account until Administrator review.
            </p>
          </div>

          {submitError && (
            <div className="p-3.5 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setStep(2)}
              className="px-4 py-3 rounded-xl bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-xs font-semibold text-[#F4F7FC] flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>

            <button
              type="button"
              onClick={handleExecuteTransfer}
              disabled={isSubmitting}
              className="flex-1 py-3.5 rounded-xl bg-[#27C58B] hover:bg-[#27C58B]/90 disabled:opacity-50 text-slate-950 text-sm font-black transition-all flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/25 cursor-pointer"
            >
              {isSubmitting ? (
                <span>Committing Double-Entry Ledger...</span>
              ) : (
                <>
                  <Check className="h-4 w-4 stroke-[3]" />
                  <span>Authorize &amp; Send Money</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: Transfer Success Receipt */}
      {step === 4 && receipt && (
        <div className="p-6 omerta-card bg-[#101A2B] border-[#25344A] space-y-6 text-center animate-in zoom-in-95 duration-200 shadow-xl">
          <div className="mx-auto h-12 w-12 rounded-full bg-[#27C58B]/20 border border-[#27C58B]/40 flex items-center justify-center text-[#27C58B]">
            <Check className="h-6 w-6 stroke-[3]" />
          </div>

          <div>
            <h2 className="text-xl font-bold text-[#F4F7FC]">Transfer Executed Successfully</h2>
            <p className="text-xs text-[#A7B4C8] mt-0.5">
              Funds debited from sender and credited to recipient in PostgreSQL ledger.
            </p>
          </div>

          {/* Detailed Receipt Card */}
          <div className="p-5 rounded-xl bg-[#080D19] border border-[#25344A] text-left space-y-3.5">
            <div className="flex items-center justify-between border-b border-[#25344A] pb-3">
              <span className="text-xs text-[#A7B4C8]">Transfer Reference</span>
              <span className="font-mono font-bold text-xs text-[#F4F7FC]">{receipt.transfer_id}</span>
            </div>

            <div className="flex items-center justify-between border-b border-[#25344A] pb-3">
              <span className="text-xs text-[#A7B4C8]">Amount Transferred</span>
              <span className="font-mono font-bold text-base text-[#27C58B]">
                {receipt.formatted_amount}
              </span>
            </div>

            <div className="flex items-center justify-between border-b border-[#25344A] pb-3">
              <span className="text-xs text-[#A7B4C8]">Recipient</span>
              <div className="text-right">
                <span className="font-bold text-xs text-[#F4F7FC] block">{receipt.recipient.name}</span>
                <span className="font-mono text-[11px] text-[#29C5D9]">{receipt.recipient.omerta_user_number}</span>
              </div>
            </div>

            <div className="flex items-center justify-between border-b border-[#25344A] pb-3">
              <span className="text-xs text-[#A7B4C8]">Sender</span>
              <div className="text-right">
                <span className="font-bold text-xs text-[#F4F7FC] block">{receipt.sender.name}</span>
                <span className="font-mono text-[11px] text-[#A7B4C8]">{receipt.sender.omerta_user_number}</span>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-[#A7B4C8]">Timestamp</span>
              <span className="text-xs font-mono text-[#F4F7FC]">
                {new Date(receipt.created_at).toLocaleString()}
              </span>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <button
              onClick={handleCopyReceipt}
              className="px-4 py-2.5 rounded-xl bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-xs font-semibold text-[#F4F7FC] flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              {copiedReceipt ? <Check className="h-3.5 w-3.5 text-[#27C58B]" /> : <Copy className="h-3.5 w-3.5 text-[#3978F6]" />}
              <span>{copiedReceipt ? 'Copied' : 'Copy Receipt'}</span>
            </button>

            <button
              onClick={resetForm}
              className="px-4 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 text-xs font-bold text-[#F4F7FC] flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Send Another</span>
            </button>

            <button
              onClick={() => navigate('/customer/dashboard')}
              className="px-4 py-2.5 rounded-xl bg-[#152238] hover:bg-[#1B2B43] border border-[#25344A] text-xs font-semibold text-[#F4F7FC] transition-colors cursor-pointer"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      )}

      {/* MODAL 1: VPN / PROXY CONNECTION ACTIVE POPUP */}
      {vpnModalOpen && (
        <Modal
          isOpen={vpnModalOpen}
          onClose={() => setVpnModalOpen(false)}
          title="VPN / Proxy Connection Detected"
          subtitle="Compliance & Risk Policy Violation"
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0 text-amber-400 mt-0.5" />
              <div className="space-y-1">
                <p className="font-bold text-white text-sm">Please Close Your VPN First</p>
                <p className="text-amber-200/90 leading-relaxed">
                  For banking compliance, AML identity verification, and anti-fraud safeguards, transfers cannot be executed through commercial VPNs, proxies, or datacenter tunnel gateways.
                </p>
              </div>
            </div>

            {/* Observed Telemetry */}
            <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-slate-300">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Detected Network Telemetry</span>
              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400">Exit Country</span>
                <span className="font-mono text-cyan-400 font-bold">{vpnDetails?.country || 'External Exit'}</span>
              </div>
              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400">ISP / Gateway</span>
                <span className="text-white font-semibold">{vpnDetails?.isp || 'Encrypted Hosting Node'}</span>
              </div>
              {vpnDetails?.reason && (
                <div className="text-[11px] text-amber-400/90 pt-1">
                  Reason: {vpnDetails.reason}
                </div>
              )}
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed">
              Disconnect or disable your VPN in your operating system or browser, then click below to re-verify your connection.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setVpnModalOpen(false)}
                className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRecheckVpnConnection}
                disabled={isRecheckingVpn}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold shadow-lg shadow-blue-500/25 cursor-pointer"
              >
                <RefreshCw className={`w-4 h-4 ${isRecheckingVpn ? 'animate-spin' : ''}`} />
                <span>{isRecheckingVpn ? 'Re-Checking...' : 'Check Connection Again'}</span>
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* MODAL 2: 3-WRONG PASSWORD LOCKOUT & INACTIVATION MODAL */}
      {lockoutModalOpen && (
        <Modal
          isOpen={lockoutModalOpen}
          onClose={handleAcknowledgeLockout}
          title="Account Inactivated & Session Terminated"
          subtitle="Security Protocol Enforced (3 Failed Password Attempts)"
          maxWidth="md"
        >
          <div className="space-y-4 text-xs">
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-start gap-3">
              <Lock className="w-5 h-5 shrink-0 text-rose-400 mt-0.5" />
              <div className="space-y-1">
                <p className="font-bold text-white text-sm">Account Inactivated For Your Security</p>
                <p className="text-rose-200/90 leading-relaxed">
                  {lockoutMessage || 'You have entered your password incorrectly 3 times. Your account has been inactivated and your active login session has been terminated.'}
                </p>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2 text-slate-300">
              <span className="text-[10px] font-bold text-slate-400 uppercase">How to Restore Access</span>
              <ul className="list-disc pl-4 space-y-1 text-slate-300 text-[11px]">
                <li>An Administrator or Compliance Officer must review the security flag in the Admin Control Center.</li>
                <li>The Administrator will verify your identity by phone or registered email.</li>
                <li>Once the risk is resolved and your account is reactivated, you will be able to log back in.</li>
              </ul>
            </div>

            <div className="flex items-center justify-end pt-2">
              <button
                type="button"
                onClick={handleAcknowledgeLockout}
                className="w-full flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold shadow-lg shadow-rose-600/30 cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
                <span>Acknowledge &amp; Return to Login</span>
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
