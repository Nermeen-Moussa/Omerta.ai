import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Lock,
  Mail,
  ArrowRight,
  AlertCircle,
  Building,
  Eye,
  EyeOff,
  ShieldCheck,
} from 'lucide-react';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasActiveSessionConflict, setHasActiveSessionConflict] = useState<boolean>(false);

  const doLogin = async (force: boolean = false) => {
    if (!username.trim() || !password.trim()) {
      setError('Please enter your email/username and password.');
      return;
    }

    setLoading(true);
    setError(null);
    setHasActiveSessionConflict(false);

    try {
      const res = await login(username.trim(), password, force);
      const userRole = res?.user?.role || 'CUSTOMER';
      if (userRole === 'CUSTOMER') {
        navigate('/customer/dashboard');
      } else {
        navigate('/admin/dashboard');
      }
    } catch (err: any) {
      const errMsg = err.message || 'Invalid credentials or login failure.';
      setError(errMsg);
      if (
        errMsg.toLowerCase().includes('active session') ||
        errMsg.toLowerCase().includes('concurrent') ||
        err.data?.detail?.error === 'CONCURRENT_SESSION_DENIED'
      ) {
        setHasActiveSessionConflict(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    doLogin(false);
  };

  const handleForceLogin = () => {
    doLogin(true);
  };

  return (
    <div className="min-h-screen w-full bg-[#080D19] text-[#F4F7FC] flex flex-col justify-between relative overflow-hidden font-sans">
      {/* Subtle Background Glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(57,120,246,0.12),rgba(0,0,0,0))] pointer-events-none" />

      {/* Header Branding */}
      <header className="px-6 sm:px-8 py-6 flex items-center justify-between relative z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] flex items-center justify-center text-slate-950 font-black shadow-lg shadow-cyan-500/20">
            <Building className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div>
            <div className="text-xl font-bold tracking-tight text-[#F4F7FC] flex items-center gap-1.5">
              Omerta<span className="text-[#29C5D9]">.ai</span>
            </div>
            <div className="text-[10px] text-[#A7B4C8] tracking-wider uppercase font-semibold">
              Digital Banking Intelligence
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#27C58B] animate-pulse" />
          <span className="text-xs font-mono text-[#A7B4C8]">System Active</span>
        </div>
      </header>

      {/* Main Form Center */}
      <main className="flex-1 flex items-center justify-center px-4 py-8 relative z-10">
        <div className="w-full max-w-md bg-[#101A2B] border border-[#25344A] rounded-2xl p-6 sm:p-8 space-y-6 shadow-2xl">
          {/* Header */}
          <div className="text-center space-y-1.5">
            <div className="mx-auto w-12 h-12 rounded-2xl bg-[#152238] border border-[#25344A] flex items-center justify-center mb-2">
              <Lock className="w-6 h-6 text-[#3978F6]" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-[#F4F7FC]">
              Sign in to your account
            </h1>
            <p className="text-xs text-[#A7B4C8]">
              Enter your verified credentials to access your portal
            </p>
          </div>

          {error && (
            <div className="p-4 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] space-y-2">
              <div className="flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{error}</span>
              </div>
              {hasActiveSessionConflict && (
                <button
                  type="button"
                  onClick={handleForceLogin}
                  disabled={loading}
                  className="w-full mt-2 py-2 px-3 rounded-lg bg-[#F06470]/20 hover:bg-[#F06470]/30 text-[#F4F7FC] font-semibold text-xs border border-[#F06470]/40 transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <ShieldCheck className="w-4 h-4 text-[#29C5D9]" />
                  <span>Terminate Other Session &amp; Sign In Here</span>
                </button>
              )}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-[#A7B4C8] uppercase tracking-wider block">
                Email or Username
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="name@example.com or username"
                  className="w-full pl-10 pr-4 py-3 bg-[#080D19] border border-[#25344A] rounded-xl text-sm text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                  autoFocus
                />
                <Mail className="absolute left-3.5 top-3.5 h-4 w-4 text-[#71819A]" />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-[#A7B4C8] uppercase tracking-wider">
                  Password
                </label>
                <Link
                  to="/forgot-password"
                  className="text-xs font-semibold text-[#29C5D9] hover:underline"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter account password"
                  className="w-full pl-10 pr-10 py-3 bg-[#080D19] border border-[#25344A] rounded-xl text-sm text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                />
                <Lock className="absolute left-3.5 top-3.5 h-4 w-4 text-[#71819A]" />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-3.5 text-[#71819A] hover:text-[#F4F7FC] cursor-pointer"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-sm font-bold text-[#F4F7FC] transition-all shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2 cursor-pointer mt-2"
            >
              {loading ? (
                <span>Authenticating...</span>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="pt-4 border-t border-[#25344A] text-center space-y-3">
            <p className="text-xs text-[#A7B4C8]">
              Don't have an account yet?{' '}
              <Link to="/register" className="text-[#3978F6] hover:underline font-bold">
                Open New Account
              </Link>
            </p>

            <div className="flex items-center justify-center gap-1.5 text-[11px] text-[#71819A]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#27C58B]" />
              <span>256-Bit Encrypted Banking Portal</span>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="px-6 py-4 text-center text-xs text-[#71819A] border-t border-[#1E2D4A] relative z-10">
        Omerta.ai • Digital Banking &amp; Financial Crime Intelligence Platform
      </footer>
    </div>
  );
};
