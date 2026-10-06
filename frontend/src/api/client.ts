/**
 * Omerta.ai API Client with JWT Authorization & Interceptors
 */

const API_BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data: any) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('omerta_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData: any = {};
    try {
      errorData = await response.json();
    } catch {
      errorData = { message: response.statusText };
    }
    const message =
      typeof errorData.detail === 'string'
        ? errorData.detail
        : errorData.detail?.message || errorData.message || 'API Request Failed';

    const errorDetail = errorData.detail;
    const isTransferPasswordError =
      errorDetail?.error === 'INVALID_PASSWORD' ||
      (typeof errorDetail?.message === 'string' && errorDetail.message.includes('Attempt'));

    if (
      response.status === 401 &&
      !endpoint.includes('/auth/login') &&
      !endpoint.includes('/auth/register') &&
      !isTransferPasswordError
    ) {
      // Session revoked or token expired
      window.dispatchEvent(
        new CustomEvent('omerta_unauthorized', {
          detail: { message: message || 'Your session was terminated.' },
        })
      );
    }

    throw new ApiError(response.status, message, errorData);
  }

  if (response.headers.get('content-type')?.includes('application/json')) {
    return (await response.json()) as T;
  }

  return (await response.text()) as unknown as T;
}

export const api = {
  // Authentication & Self-Registration
  register: (data: any) =>
    apiRequest<{ access_token: string; user: any; customer: any; session?: any }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  login: (credentials: {
    username: string;
    password: string;
    force_login?: boolean;
    is_vpn?: boolean;
    client_ip?: string;
    country?: string;
    isp?: string;
    org?: string;
    browser_timezone?: string;
    ip_timezone?: string;
  }) =>
    apiRequest<{ access_token: string; user: any; customer?: any; session?: any }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    }),
  forgotPassword: (email: string) =>
    apiRequest<{ success: boolean; message: string; simulated_email?: any }>('/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),
  resetPassword: (data: { token: string; new_password: string; confirm_password: string }) =>
    apiRequest<{ success: boolean; message: string }>('/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getMe: () => apiRequest('/auth/me'),

  // Customer Banking Endpoints
  getCustomerDashboard: () => apiRequest('/customer/dashboard'),
  getCustomerProfile: () => apiRequest('/customer/profile'),
  getCustomerAccounts: () => apiRequest<any[]>('/customer/accounts'),
  createCustomerAccount: (data: { account_type: string; currency: string; initial_balance: number }) =>
    apiRequest('/customer/accounts', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  lookupRecipient: (identifier: string) =>
    apiRequest(`/customer/recipient/lookup?identifier=${encodeURIComponent(identifier)}`),
  initiateTransfer: (data: {
    sender_account_id: string;
    recipient_user_number: string;
    amount: number;
    currency: string;
    note?: string;
    password?: string;
    idempotency_key?: string;
    is_vpn?: boolean;
    client_ip?: string;
    country?: string;
    isp?: string;
    org?: string;
    browser_timezone?: string;
    ip_timezone?: string;
  }) =>
    apiRequest('/customer/transfers', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getCustomerTransfers: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/customer/transfers?${q.toString()}`);
  },
  getTransferReceipt: (transferId: string) =>
    apiRequest(`/customer/transfers/${encodeURIComponent(transferId)}`),
  getCustomerTransactions: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/customer/transactions?${q.toString()}`);
  },
  getCustomerSessions: () => apiRequest<any[]>('/customer/security/sessions'),
  revokeCustomerSession: (sessionId: string) =>
    apiRequest(`/customer/security/sessions/${encodeURIComponent(sessionId)}/revoke`, {
      method: 'POST',
    }),
  updateCustomerConsent: (device_consent: boolean) =>
    apiRequest('/customer/security/consent', {
      method: 'POST',
      body: JSON.stringify({ device_consent }),
    }),
  sendTelemetryHeartbeat: (telemetryData: any) =>
    apiRequest<any>('/auth/telemetry/heartbeat', {
      method: 'POST',
      body: JSON.stringify(telemetryData),
    }),
  changeTransferPassword: (data: {
    new_transfer_password: string;
    confirm_transfer_password: string;
    current_transfer_password?: string;
  }) =>
    apiRequest('/customer/transfer-password/change', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Customer Support & Security Cases (Helpdesk & WhatsApp-style Chat)
  getCustomerSupportTickets: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/support/tickets?${q.toString()}`);
  },
  getCustomerSupportTicket: (ticketId: number | string) => apiRequest(`/support/tickets/${ticketId}`),
  createSupportTicket: (data: {
    issue_type: string;
    subject: string;
    description: string;
    account_id?: string;
    priority?: string;
    attachment_url?: string;
    attachment_name?: string;
    attachment_type?: string;
  }) =>
    apiRequest('/support/tickets', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  sendSupportMessage: (
    ticketId: number | string,
    data: {
      message_text: string;
      attachment_url?: string;
      attachment_name?: string;
      attachment_type?: string;
    }
  ) =>
    apiRequest(`/support/tickets/${ticketId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  uploadSupportIdDocument: (
    ticketId: number | string,
    data: {
      national_id_number: string;
      document_type?: string;
      document_front_url: string;
      document_back_url?: string;
    }
  ) =>
    apiRequest(`/support/tickets/${ticketId}/upload-id`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // Admin & Auditor Support Cases Control Center
  getAdminSupportCases: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/support/admin/cases?${q.toString()}`);
  },
  getAdminSupportCase: (ticketId: number | string) => apiRequest(`/support/admin/cases/${ticketId}`),
  adminSendSupportMessage: (
    ticketId: number | string,
    data: {
      message_text: string;
      attachment_url?: string;
      attachment_name?: string;
      attachment_type?: string;
    }
  ) =>
    apiRequest(`/support/admin/cases/${ticketId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  adminVerifyIdentityDecision: (
    caseId: number | string,
    data: {
      decision: 'VERIFIED' | 'REJECTED';
      reviewer_notes: string;
    }
  ) =>
    apiRequest(`/support/admin/cases/${caseId}/verify-identity`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  adminRestoreTransferAccess: (
    caseId: number | string,
    data: {
      confirmation: boolean;
      reason?: string;
    }
  ) =>
    apiRequest(`/support/admin/cases/${caseId}/restore-transfer`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  adminUpdateTicketStatus: (
    ticketId: number | string,
    data: {
      status: string;
      assigned_to_user_id?: number;
    }
  ) =>
    apiRequest(`/support/admin/cases/${ticketId}/status`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),


  // Admin Control Center Endpoints
  getAdminDashboard: () => apiRequest('/admin/dashboard'),
  getAdminUsers: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/admin/users?${q.toString()}`);
  },
  getAdminUserDetail: (identifier: string) =>
    apiRequest(`/admin/users/${encodeURIComponent(identifier)}`),
  getAdminStaff: () => apiRequest<any[]>('/admin/staff'),
  createAdminStaff: (data: {
    full_name: string;
    email: string;
    username: string;
    password: string;
    role: string;
    privileges: string[];
  }) =>
    apiRequest('/admin/staff', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteAdminStaff: (userId: string) =>
    apiRequest(`/admin/staff/${encodeURIComponent(userId)}`, {
      method: 'DELETE',
    }),
  updateUserStatus: (userId: string, is_active: boolean, reason: string) =>
    apiRequest(`/admin/users/${encodeURIComponent(userId)}/status`, {
      method: 'POST',
      body: JSON.stringify({ is_active, reason }),
    }),
  getAdminAccounts: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/admin/accounts?${q.toString()}`);
  },
  applyAccountAdjustment: (accountId: string, adjustment_amount: number, reason: string) =>
    apiRequest(`/admin/accounts/${encodeURIComponent(accountId)}/adjustment`, {
      method: 'POST',
      body: JSON.stringify({ adjustment_amount, reason }),
    }),
  recordTransactionReview: (transactionId: string, disposition: string, rationale: string) =>
    apiRequest(`/admin/transactions/${encodeURIComponent(transactionId)}/review`, {
      method: 'POST',
      body: JSON.stringify({ disposition, rationale }),
    }),
  getProblemCustomers: () => apiRequest<any[]>('/admin/problem-customers'),
  resolveCustomerRisk: (customerId: string, reason = 'Customer identity verified and risk cleared.', reset_risk_to = 'LOW') =>
    apiRequest(`/admin/problem-customers/${encodeURIComponent(customerId)}/resolve-risk`, {
      method: 'POST',
      body: JSON.stringify({ reason, reset_risk_to }),
    }),
  notifyCustomer: (customerId: string, data: { channel: string; subject: string; message: string }) =>
    apiRequest(`/admin/problem-customers/${encodeURIComponent(customerId)}/notify`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getProblemCustomerAgenticSummary: (customerId: string) =>
    apiRequest<any>(`/admin/problem-customers/${encodeURIComponent(customerId)}/agentic-summary`),
  approvePendingTransaction: (transactionId: string, rationale = 'Analyst approved and released funds.') =>
    apiRequest(`/admin/transactions/${encodeURIComponent(transactionId)}/approve`, {
      method: 'POST',
      body: JSON.stringify({ rationale }),
    }),
  rejectPendingTransaction: (transactionId: string, rationale = 'Flagged as high-risk unauthorized attempt.') =>
    apiRequest(`/admin/transactions/${encodeURIComponent(transactionId)}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rationale }),
    }),
  previewAgenticSarReport: (targetId: string) =>
    apiRequest(`/admin/agentic/generate-sar-report?case_or_txn_id=${encodeURIComponent(targetId)}`, {
      method: 'POST',
    }),

  // Intelligence & Existing Platform Endpoints
  getDashboardSummary: () => apiRequest('/dashboard/summary'),
  getDashboardCharts: () => apiRequest('/dashboard/charts'),
  getRecentActivity: (limit = 8) => apiRequest(`/dashboard/recent-activity?limit=${limit}`),

  getTransactions: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/transactions?${q.toString()}`);
  },
  getTransactionDetail: (id: string | number) => apiRequest(`/transactions/${id}`),
  createTransaction: (data: any) =>
    apiRequest('/transactions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getRiskMonitoringQueue: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/risk/monitoring?${q.toString()}`);
  },
  assessTransaction: (transaction_id: number) =>
    apiRequest('/risk/assess', {
      method: 'POST',
      body: JSON.stringify({ transaction_id }),
    }),

  getCustomers: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/customers?${q.toString()}`);
  },
  getCustomerDetail: (id: string | number) => apiRequest(`/customers/${id}`),
  getCustomer360: (id: string | number) => apiRequest(`/customers/${id}`),

  getAccounts: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/accounts?${q.toString()}`);
  },
  getAccountDetail: (id: string | number) => apiRequest(`/accounts/${id}`),

  getDevices: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/devices?${q.toString()}`);
  },
  getDeviceDetail: (id: string | number) => apiRequest(`/devices/${id}`),

  getNetworkGraph: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/network/graph?${q.toString()}`);
  },

  getNetworkSearchSuggestions: (query: string) => {
    return apiRequest(`/network/search-suggestions?q=${encodeURIComponent(query)}`);
  },

  getCases: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/cases?${q.toString()}`);
  },
  getCaseDetail: (caseId: string) => apiRequest(`/cases/${caseId}`),
  addCaseNote: (caseId: string, author: string, note_text: string) =>
    apiRequest(`/cases/${caseId}/notes`, {
      method: 'POST',
      body: JSON.stringify({ author, note_text }),
    }),
  recordDisposition: (
    caseId: string,
    analyst_id: string,
    disposition: string,
    rationale: string
  ) =>
    apiRequest(`/cases/${caseId}/disposition`, {
      method: 'POST',
      body: JSON.stringify({ analyst_id, disposition, rationale }),
    }),
  recordCaseDisposition: (
    caseId: string | number,
    data: { disposition: string; rationale: string; analyst_id?: string; new_status?: string }
  ) =>
    apiRequest(`/cases/${caseId}/disposition`, {
      method: 'POST',
      body: JSON.stringify({
        analyst_id: data.analyst_id || 'analyst-1',
        disposition: data.disposition,
        rationale: data.rationale,
      }),
    }),
  adminReviewTransaction: (
    transactionId: string | number,
    data: { review_status: string; disposition_rationale: string }
  ) =>
    apiRequest(`/admin/transactions/${transactionId}/review`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getReportsSummary: () => apiRequest('/reports/summary'),
  getReportTypes: () => apiRequest('/reports/types'),
  generateReport: (reportType: string) =>
    apiRequest(`/reports/generate?report_type=${encodeURIComponent(reportType)}`),
  getAuditLogs: (params: Record<string, any> = {}) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') q.append(k, String(v));
    });
    return apiRequest(`/audit/logs?${q.toString()}`);
  },
  getSettings: () => apiRequest('/settings'),
  updateThresholds: (thresholds: any) =>
    apiRequest('/settings', {
      method: 'PUT',
      body: JSON.stringify(thresholds),
    }),
};
