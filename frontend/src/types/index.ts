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
  national_id_number?: string;
  identity_status?: 'UNVERIFIED' | 'PENDING' | 'VERIFIED' | 'REJECTED';
  transfer_status?: 'ACTIVE' | 'BLOCKED' | 'SUSPENDED';
  transfer_failed_attempts?: number;
  transfer_blocked_at?: string;
  transfer_unblocked_at?: string;
  is_transfer_locked?: boolean;
  require_transfer_password_change?: boolean;
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
  transfer_password?: string;
  confirm_transfer_password?: string;
  national_id_number?: string;
  phone?: string;
  country: string;
  preferred_currency: string;
  initial_balance: number;
  device_consent: boolean;
}

export type TicketIssueType =
  | 'TRANSFER_BLOCKED'
  | 'FORGOTTEN_TRANSFER_PASSWORD'
  | 'TRANSFER_PASSWORD_LOCK'
  | 'IDENTITY_VERIFICATION'
  | 'ACCOUNT_SECURITY'
  | 'TRANSACTION_ISSUE'
  | 'OTHER'
  | string;

export type TicketStatus = 'OPEN' | 'IN_PROGRESS' | 'WAITING_ON_CUSTOMER' | 'RESOLVED' | 'CLOSED' | string;
export type TicketPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT' | 'CRITICAL' | string;
export type MessageSenderRole = 'CUSTOMER' | 'ADMINISTRATOR' | 'FRAUD_ANALYST' | 'SENIOR_INVESTIGATOR' | 'AUDITOR' | 'SYSTEM' | string;
export type IdentityVerificationStatus = 'NOT_VERIFIED' | 'PENDING' | 'PENDING_REVIEW' | 'VERIFIED' | 'REJECTED' | 'NOT_REQUIRED' | 'SUBMITTED' | 'UNDER_REVIEW' | 'EXPIRED' | string;

export interface SupportMessageItem {
  id: number;
  ticket_id: number;
  sender_user_id: number | null;
  sender_name: string;
  sender_role: MessageSenderRole;
  message_text: string;
  attachment_url?: string | null;
  attachment_name?: string | null;
  attachment_type?: string;
  is_internal_note?: boolean;
  created_at: string;
}

export interface IdentityVerificationItem {
  id: number;
  ticket_id: number;
  customer_id: number;
  national_id_number: string;
  document_type: string;
  document_front_url: string;
  document_back_url?: string | null;
  status: IdentityVerificationStatus;
  reviewed_by_user_id?: number | null;
  reviewer_notes?: string | null;
  reviewed_at?: string | null;
  created_at: string;
}

export interface SupportTicketItem {
  id: number;
  ticket_id?: string;
  ticket_number: string;
  customer_id: number;
  customer_name?: string;
  customer_email?: string;
  omerta_user_number?: string;
  account_id?: number | null;
  account_number?: string | null;
  issue_type: TicketIssueType;
  ticket_type?: string;
  requires_identity_verification?: boolean;
  subject: string;
  description: string;
  status: TicketStatus;
  priority: TicketPriority;
  assigned_to_user_id?: number | null;
  assigned_to_name?: string | null;
  transfer_blocked: boolean;
  identity_verification_id?: number | null;
  identity_status?: IdentityVerificationStatus | null;
  national_id_number?: string | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  messages_count?: number;
  messages?: SupportMessageItem[];
  identity_verification?: IdentityVerificationItem | null;
  customer?: {
    id?: string | null;
    name?: string | null;
    omerta_user_number?: string | null;
    email?: string | null;
    phone?: string | null;
    transfer_status?: string | null;
    identity_status?: string | null;
    national_id_number?: string | null;
    require_transfer_password_change?: boolean;
    failed_attempts?: number;
  };
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
  account_count?: number;
  is_shared?: boolean;
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

export interface InflowSourceItem {
  sender_name: string;
  sender_account: string;
  amount: number;
  currency: string;
  timestamp: string;
  risk_score?: number;
  risk_level?: string;
}

export interface OutflowDestinationItem {
  recipient_name: string;
  recipient_account: string;
  amount: number;
  currency: string;
  timestamp: string;
  risk_score?: number;
  risk_level?: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  risk_score?: number;
  risk_level?: RiskLevel | string;
  customer_name?: string;
  omerta_user_number?: string;
  balance?: number;
  currency?: string;
  inflow_total?: number;
  inflow_count?: number;
  inflow_sources?: InflowSourceItem[];
  outflow_total?: number;
  outflow_count?: number;
  outflow_destinations?: OutflowDestinationItem[];
  net_flow?: number;
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
  amount?: number;
  currency?: string;
  timestamp?: string;
  weight?: number;
  risk_score?: number;
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
