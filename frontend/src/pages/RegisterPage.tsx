import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Building,
  User,
  Mail,
  Lock,
  Wallet,
  AlertCircle,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface CountryOption {
  code: string;
  name: string;
  flag: string;
  dialCode: string;
  currency: string;
  samplePhone: string;
}

const COUNTRIES: CountryOption[] = [
  { code: 'EG', name: 'Egypt', flag: '🇪🇬', dialCode: '+20', currency: 'EGP', samplePhone: '010 1234 5678' },
  { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦', dialCode: '+966', currency: 'SAR', samplePhone: '50 123 4567' },
  { code: 'AE', name: 'United Arab Emirates', flag: '🇦🇪', dialCode: '+971', currency: 'AED', samplePhone: '50 123 4567' },
  { code: 'US', name: 'United States', flag: '🇺🇸', dialCode: '+1', currency: 'USD', samplePhone: '(555) 234-5678' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧', dialCode: '+44', currency: 'GBP', samplePhone: '7911 123456' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪', dialCode: '+49', currency: 'EUR', samplePhone: '151 12345678' },
  { code: 'FR', name: 'France', flag: '🇫🇷', dialCode: '+33', currency: 'EUR', samplePhone: '6 12 34 56 78' },
  { code: 'CA', name: 'Canada', flag: '🇨🇦', dialCode: '+1', currency: 'CAD', samplePhone: '(555) 012-3456' },
  { code: 'KW', name: 'Kuwait', flag: '🇰🇼', dialCode: '+965', currency: 'KWD', samplePhone: '9123 4567' },
  { code: 'QA', name: 'Qatar', flag: '🇶🇦', dialCode: '+974', currency: 'QAR', samplePhone: '3312 3456' },
];

export const RegisterPage: React.FC = () => {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [selectedCountry, setSelectedCountry] = useState<CountryOption>(COUNTRIES[0]);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    username: '',
    password: '',
    confirm_password: '',
    preferred_currency: 'EGP',
    initial_balance: 50000,
    device_consent: true,
  });

  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleCountryChange = (countryCode: string) => {
    const c = COUNTRIES.find((item) => item.code === countryCode) || COUNTRIES[0];
    setSelectedCountry(c);
    setFormData((prev) => ({
      ...prev,
      preferred_currency: c.currency,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.device_consent) {
      setError('You must accept the Banking Terms of Service, Privacy Policy, and Device Security Consent to open an account.');
      return;
    }
    if (formData.password !== formData.confirm_password) {
      setError('Password and confirmation do not match.');
      return;
    }
    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    const fullPhone = phoneNumber.trim()
      ? (phoneNumber.startsWith('+') ? phoneNumber.trim() : `${selectedCountry.dialCode} ${phoneNumber.trim()}`)
      : `${selectedCountry.dialCode} 10${Math.floor(10000000 + Math.random() * 90000000)}`;

    setIsLoading(true);
    setError(null);

    try {
      await register({
        full_name: formData.full_name,
        email: formData.email,
        username: formData.username,
        password: formData.password,
        confirm_password: formData.confirm_password,
        phone: fullPhone,
        country: selectedCountry.code,
        preferred_currency: formData.preferred_currency,
        initial_balance: formData.initial_balance,
        device_consent: formData.device_consent,
      });
      navigate('/customer/dashboard');
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please check your inputs and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#080D19] text-[#F4F7FC] flex flex-col justify-between relative overflow-hidden font-sans">
      {/* Subtle Background Glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(57,120,246,0.12),rgba(0,0,0,0))] pointer-events-none" />

      {/* Header Branding */}
      <header className="px-6 sm:px-8 py-6 flex items-center justify-between relative z-10">
        <Link to="/" className="flex items-center gap-3">
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
        </Link>

        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#27C58B] animate-pulse" />
          <span className="text-xs font-mono text-[#A7B4C8]">System Active</span>
        </div>
      </header>

      {/* Main Registration Box */}
      <main className="flex-1 flex items-center justify-center px-4 py-8 relative z-10">
        <div className="w-full max-w-lg bg-[#101A2B] border border-[#25344A] rounded-2xl p-6 sm:p-8 space-y-6 shadow-2xl">
          {/* Brand Header */}
          <div className="text-center space-y-1.5">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#F4F7FC]">
              Create Your Banking Account
            </h1>
            <p className="text-xs text-[#A7B4C8] max-w-md mx-auto">
              Open your verified account and receive your unique Omerta identifier for instant transfers.
            </p>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-[#F06470]/10 border border-[#F06470]/30 text-xs text-[#F06470] flex items-center gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Full Name & Username */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                  Full Legal Name
                </label>
                <div className="relative">
                  <input
                    type="text"
                    required
                    placeholder="e.g. Mostafa Mahmoud"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                    className="w-full pl-9 pr-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                  />
                  <User className="absolute left-3 top-3 h-4 w-4 text-[#71819A]" />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                  Username
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. mostafa_m"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value.toLowerCase() })}
                  className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                />
              </div>
            </div>

            {/* Email Address */}
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                Email Address
              </label>
              <div className="relative">
                <input
                  type="email"
                  required
                  placeholder="name@example.com"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="w-full pl-9 pr-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                />
                <Mail className="absolute left-3 top-3 h-4 w-4 text-[#71819A]" />
              </div>
            </div>

            {/* Country Selector & Mobile Phone Number */}
            <div className="space-y-1.5">
              <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8]">
                Country &amp; Mobile Phone Number
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
                {/* Country Dropdown */}
                <div className="sm:col-span-5 relative">
                  <select
                    value={selectedCountry.code}
                    onChange={(e) => handleCountryChange(e.target.value)}
                    className="w-full pl-8 pr-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] font-medium focus:outline-none focus:border-[#3978F6] transition-colors cursor-pointer"
                  >
                    {COUNTRIES.map((c) => (
                      <option key={c.code} value={c.code} className="bg-[#101A2B] text-[#F4F7FC]">
                        {c.flag} {c.name} ({c.dialCode})
                      </option>
                    ))}
                  </select>
                  <span className="absolute left-2.5 top-2.5 text-sm pointer-events-none">
                    {selectedCountry.flag}
                  </span>
                </div>

                {/* Phone Number Input */}
                <div className="sm:col-span-7 relative flex">
                  <span className="inline-flex items-center px-3 bg-[#152238] border border-r-0 border-[#25344A] rounded-l-xl text-xs font-mono font-bold text-[#29C5D9]">
                    {selectedCountry.dialCode}
                  </span>
                  <input
                    type="tel"
                    placeholder={selectedCountry.samplePhone}
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-r-xl text-xs font-mono text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                  />
                </div>
              </div>
              <p className="text-[11px] text-[#71819A]">
                Your mobile phone number will be linked for direct transfers.
              </p>
            </div>

            {/* Password and Confirm */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    placeholder="Min 8 characters"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full pl-9 pr-9 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                  />
                  <Lock className="absolute left-3 top-3 h-4 w-4 text-[#71819A]" />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-2.5 top-3 text-[#71819A] hover:text-[#F4F7FC]"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4 text-[#A7B4C8]" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-[#A7B4C8] mb-1">
                  Confirm Password
                </label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="Repeat password"
                  value={formData.confirm_password}
                  onChange={(e) => setFormData({ ...formData, confirm_password: e.target.value })}
                  className="w-full px-3 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6] transition-colors"
                />
              </div>
            </div>

            {/* Initial Balance */}
            <div className="p-4 rounded-xl bg-[#080D19] border border-[#25344A] space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-[#F4F7FC] flex items-center gap-1.5">
                  <Wallet className="h-4 w-4 text-[#3978F6]" />
                  <span>Initial Opening Balance</span>
                </label>
                <span className="font-mono font-bold text-base text-[#27C58B]">
                  {formData.initial_balance.toLocaleString()} {formData.preferred_currency}
                </span>
              </div>

              <input
                type="range"
                min="5000"
                max="250000"
                step="5000"
                value={formData.initial_balance}
                onChange={(e) => setFormData({ ...formData, initial_balance: parseInt(e.target.value) || 50000 })}
                className="w-full accent-[#3978F6] cursor-pointer"
              />

              <div className="flex items-center justify-between text-[11px] text-[#71819A]">
                <span>5,000 {formData.preferred_currency}</span>
                <span>100,000 {formData.preferred_currency}</span>
                <span>250,000 {formData.preferred_currency}</span>
              </div>
            </div>

            {/* Privacy and Security Consent */}
            <div className="p-3.5 rounded-xl bg-[#080D19] border border-[#25344A] flex items-start gap-2.5">
              <input
                type="checkbox"
                id="consent-check"
                required
                checked={formData.device_consent}
                onChange={(e) => setFormData({ ...formData, device_consent: e.target.checked })}
                className="mt-0.5 h-4 w-4 rounded bg-[#101A2B] border-[#25344A] text-[#3978F6] focus:ring-0 cursor-pointer"
              />
              <label htmlFor="consent-check" className="text-[11px] text-[#A7B4C8] leading-tight cursor-pointer">
                I accept the <span className="text-[#3978F6] font-semibold">Banking Terms of Service</span>, <span className="text-[#3978F6] font-semibold">Privacy Policy</span>, and consent to Omerta.ai collecting device &amp; session security telemetry to safeguard my account and transfers.
              </label>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-sm font-bold text-[#F4F7FC] transition-all shadow-lg shadow-blue-500/25 flex items-center justify-center gap-2 cursor-pointer"
            >
              {isLoading ? (
                <span>Opening Account...</span>
              ) : (
                <>
                  <span>Create Account</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <div className="text-center pt-3 border-t border-[#25344A] space-y-2">
            <p className="text-xs text-[#A7B4C8]">
              Already registered?{' '}
              <Link to="/login" className="text-[#3978F6] hover:underline font-bold">
                Sign In to Account
              </Link>
            </p>
            <div className="flex items-center justify-center gap-1 text-[11px] text-[#71819A]">
              <ShieldCheck className="w-3.5 h-3.5 text-[#27C58B]" />
              <span>Verified Banking Security Protocol</span>
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
