import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail, ArrowRight, ShieldCheck, ArrowLeft, CheckCircle2, AlertCircle, Copy, Check } from 'lucide-react';
import { api } from '../api/client';

export const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successData, setSuccessData] = useState<any | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const res = await api.forgotPassword(email.trim());
      setSuccessData(res);
    } catch (err: any) {
      setError(err.message || 'Failed to submit password reset request.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#080D19] flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center h-12 w-12 rounded-2xl bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] text-slate-950 font-black shadow-lg shadow-cyan-500/20 mb-2">
            <ShieldCheck className="h-7 w-7 stroke-[2.5]" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC]">
            Reset Your Password
          </h1>
          <p className="text-xs text-[#A7B4C8]">
            Enter your account email or username to receive a secure password reset link.
          </p>
        </div>

        {/* Card */}
        <div className="p-6 omerta-card bg-[#101A2B] border-[#25344A] rounded-2xl shadow-2xl space-y-5">
          {!successData ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3.5 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="space-y-1.5">
                <label className="block text-xs font-bold uppercase tracking-wider text-[#A7B4C8]">
                  Account Email Address or Username
                </label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#71819A]" />
                  <input
                    type="text"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="e.g. user@gmail.com, ziad@omerta.ai, or ziad_k"
                    className="w-full pl-10 pr-3.5 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading || !email.trim()}
                className="w-full py-3 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-[#F4F7FC] text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25 cursor-pointer"
              >
                {loading ? (
                  <span>Dispatching Email via Security Relay...</span>
                ) : (
                  <>
                    <span>Send Password Reset Email</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>
          ) : (
            <div className="space-y-4 text-center">
              <div className="mx-auto w-12 h-12 rounded-full bg-[#27C58B]/20 border border-[#27C58B]/40 flex items-center justify-center text-[#27C58B]">
                <CheckCircle2 className="h-6 w-6 stroke-[2.5]" />
              </div>

              <div>
                <h3 className="text-sm font-bold text-[#F4F7FC]">
                  Password Reset Email Dispatched
                </h3>
                <p className="text-xs text-[#A7B4C8] mt-1">
                  {successData.message}
                </p>
              </div>

              {successData.simulated_email && (
                <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] text-left space-y-3">
                  <div className="flex items-center justify-between text-[11px] border-b border-[#25344A] pb-2">
                    <span className="font-bold text-[#29C5D9]">✉️ Real Email Transmission</span>
                    <span className="text-[#27C58B] font-mono font-bold">Valid for 15 mins</span>
                  </div>

                  <div className="space-y-1.5 text-xs">
                    <div className="text-[#A7B4C8]">
                      <span className="font-semibold text-[#F4F7FC]">From:</span>{' '}
                      <span className="text-[#29C5D9] font-mono font-bold">abdomostafa13571234@gmail.com</span>
                    </div>
                    <div className="text-[#A7B4C8]">
                      <span className="font-semibold text-[#F4F7FC]">To:</span>{' '}
                      <span className="text-emerald-400 font-mono font-bold">{successData.simulated_email.to}</span>
                    </div>
                    <div className="text-[#A7B4C8]">
                      <span className="font-semibold text-[#F4F7FC]">Subject:</span> {successData.simulated_email.subject}
                    </div>
                  </div>

                  <div className="pt-2 flex flex-col gap-2">
                    <a
                      href={successData.simulated_email.reset_url}
                      className="w-full py-2.5 rounded-lg bg-[#27C58B] hover:bg-[#27C58B]/90 text-slate-950 text-xs font-bold text-center transition-colors block shadow-md shadow-emerald-500/20"
                    >
                      🔑 Open Password Reset Form &rarr;
                    </a>

                    <button
                      type="button"
                      onClick={() => handleCopy(successData.simulated_email.reset_url)}
                      className="py-1.5 px-3 rounded-lg bg-[#152238] hover:bg-[#1B2B43] text-[11px] text-[#A7B4C8] flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                    >
                      {copiedLink ? <Check className="h-3.5 w-3.5 text-[#27C58B]" /> : <Copy className="h-3.5 w-3.5" />}
                      <span>{copiedLink ? 'Copied Reset URL!' : 'Copy Verification Reset URL'}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="pt-2 border-t border-[#25344A] text-center">
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#29C5D9] hover:underline"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
