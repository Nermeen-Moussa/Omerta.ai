export type UserRole =
  | 'CUSTOMER'
  | 'ADMINISTRATOR'
  | 'SUB_ADMINISTRATOR'
  | 'FRAUD_ANALYST'
  | 'SENIOR_INVESTIGATOR'
  | 'INVESTIGATOR'
  | 'AUDITOR'
  | 'COMPLIANCE_AUDITOR';

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
}

export type RiskLevel = 'LOW' | 'MODERATE' | 'REQUIRES_REVIEW' | 'HIGH' | 'CRITICAL';
export type ReviewStatus = 'NOT_REQUIRED' | 'REQUIRES_REVIEW' | 'IN_REVIEW' | 'COMPLETED' | 'DISMISSED';

export interface CustomerProfile {
  id: string;
  omerta_user_number: string;
  name: string;
  email: string;
  phone?: string;
  declared_country: string;
  preferred_currency: string;
  device_consent: boolean;
  status: string;
  verification_status?: string;
  verification_tier?: string;
  risk_level?: RiskLevel;
  member_since?: string;
}

export interface LedgerEntry {
  entry_id: string;
  entry_type: 'OPENING_BALANCE' | 'DEBIT' | 'CREDIT' | 'ADMIN_ADJUSTMENT';
  amount: number;
  currency: string;
  balance_after: number;
  description: string;
  created_at: string;
}

export interface CustomerAccount {
  id?: number;
  account_id: string;
  account_type: string;
  currency: string;
  balance: number;
  formatted_balance?: string;
  status: string;
  created_at?: string;
  recent_ledger?: LedgerEntry[];
}

export interface RecipientLookupResult {
  found: boolean;
  omerta_user_number: string;
  phone_masked?: string;
  phone?: string;
  display_name: string;
  country: string;
  supported_currencies: string[];
  preferred_currency: string;
}

export interface TransferReceipt {
  transfer_id: string;
  transaction_reference?: string;
  status: string;
  amount: number;
  currency: string;
  formatted_amount: string;
  note?: string;
  created_at: string;
  sender: {
    name: string;
    omerta_user_number: string;
    account_id: string;
  };
  recipient: {
    name: string;
    omerta_user_number: string;
    account_id: string;
  };
  fee: string;
  is_demo: boolean;
  disclaimer: string;
}

export interface CustomerTransaction {
  transaction_id: string;
  direction: 'INCOMING' | 'OUTGOING';
  counterparty: string;
  amount: number;
  currency: string;
  status: string;
  timestamp: string;
  type: string;
  account_number?: string;
}

export interface CustomerSession {
  session_id: string;
  device_label: string;
  browser?: string;
  os?: string;
  platform: string;
  ip_address?: string;
  user_agent?: string;
  observed_country: string;
  is_vpn: boolean;
  is_active: boolean;
  started_at: string;
  security_notice?: string;
}

export interface RegisterFormData {
  full_name: string;
  email: string;
  username: string;
  password: string;
  confirm_password: string;
  country: string;
  preferred_currency: string;
  initial_balance: number;
  device_consent: boolean;
}

export interface AccountItem {
  id: number;
  external_id: string;
  customer_name: string;
  customer_id?: number;
  account_type: string;
  currency: string;
  balance: number;
  country?: string;
  status: string;
  created_at: string;
  risk_level?: RiskLevel | string;
  alerts_count?: number;
  ledger_count?: number;
}

export interface CustomerItem {
  id: number;
  external_id: string;
  name: string;
  email?: string;
  phone?: string;
  omerta_user_number?: string;
  customer_type: string;
  country: string;
  risk_level: RiskLevel | string;
  status: string;
  created_at: string;
  account_count?: number;
  accounts_count?: number;
  total_balance?: number;
  alerts_count?: number;
  device_consent?: boolean;
}

export interface DeviceItem {
  id: number;
  external_id: string;
  device_type: string;
  platform: string;
  is_emulator: boolean;
  is_rooted: boolean;
  session_count?: number;
  accounts_count?: number;
  risk_level?: RiskLevel | string;
  status?: string;
  first_seen?: string;
  first_seen_at?: string;
  last_seen?: string;
}

export interface CaseItem {
  id: number;
  external_id: string;
  title: string;
  status: string;
  severity: string;
  assigned_to?: string;
  alert_id?: string;
  transaction_id?: string;
  created_at: string;
  updated_at?: string;
  summary?: string;
  evidence_count?: number;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  risk_score?: number;
  risk_level?: RiskLevel | string;
  properties?: Record<string, any>;
  details?: Record<string, any>;
  x?: number;
  y?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  type: string;
  label?: string;
  weight?: number;
  is_suspicious?: boolean;
  properties?: Record<string, any>;
}

export interface TransactionItem {
  id: number;
  external_id: string;
  account_id: number;
  source_account: string;
  customer_name: string;
  recipient_account: string;
  amount: number;
  currency: string;
  transaction_type: string;
  status: string;
  timestamp: string;
  device: string;
  ip_country: string;
  ip_address?: string;
  is_new_device: boolean;
  is_new_ip: boolean;
  risk_score: number;
  risk_level: RiskLevel;
  review_status: ReviewStatus;
}

export interface RiskSignalItem {
  id: number;
  signal_name: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  description: string;
  source: string;
  confidence: number;
  evidence_reference?: string;
  detected_at: string;
}

export interface RiskAssessmentData {
  id?: number;
  external_id: string;
  risk_score: number;
  risk_level: RiskLevel;
  requires_human_review: boolean;
  status: string;
  version: string;
  correlation_id: string;
  summary: string;
  assessed_at: string;
}

export interface TransactionDetail {
  overview: {
    id: number;
    external_id: string;
    amount: number;
    currency: string;
    transaction_type: string;
    status: string;
    timestamp: string;
    is_new_device?: boolean;
    is_new_ip?: boolean;
    source_account: {
      id: number;
      external_id: string;
      customer_name: string;
      account_type: string;
      balance: number;
    };
    recipient_account: {
      id: number;
      external_id: string;
      customer_name: string;
      account_type: string;
    };
    customer?: {
      id: number;
      external_id: string;
      name: string;
      customer_type: string;
      country: string;
      risk_level: RiskLevel;
    };
    device?: {
      id: number;
      external_id: string;
      device_type: string;
      platform: string;
      is_emulator: boolean;
      is_rooted: boolean;
    };
    ip_address?: {
      id: number;
      address: string;
      country: string;
      is_vpn: boolean;
      is_proxy?: boolean;
    };
    session?: {
      id: number;
      external_id: string;
      user_agent: string;
      is_vpn: boolean;
      is_emulator: boolean;
      started_at: string;
    };
  };
  assessment?: RiskAssessmentData;
  risk_assessment?: RiskAssessmentData;
  signals: RiskSignalItem[];
  timeline: Array<{
    event?: string;
    title?: string;
    timestamp: string;
    status?: string;
    description: string;
  }>;
  related_cases?: Array<{
    id: number;
    external_id: string;
    title: string;
    status: string;
    severity: string;
    assigned_to?: string;
  }>;
  related_entities?: {
    account_customer_name: string;
    recipient_customer_name: string;
    device_external_id?: string;
    ip_address?: string;
    recent_account_transfers_count: number;
  };
  report?: {
    title?: string;
    executive_summary?: string;
    summary?: string;
    recommended_action: string;
    risk_level?: RiskLevel;
    confidence: number;
    risk_factors?: string[];
    key_findings?: string[];
    generated_at?: string;
  };
  investigation_report?: {
    title?: string;
    summary: string;
    recommended_action: string;
    risk_level: RiskLevel;
    confidence: number;
    key_findings?: string[];
    risk_factors?: string[];
    generated_at?: string;
  };
}
