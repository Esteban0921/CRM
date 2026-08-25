const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export type UserRole = 'parent' | 'staff' | 'admin';

export interface MeResponse {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  family_id: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}) as { detail?: string });
    throw new ApiError(response.status, body.detail ?? 'No se pudo completar la solicitud');
  }

  return response.json() as Promise<T>;
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export function getMe(token: string): Promise<MeResponse> {
  return request<MeResponse>('/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export type FamilyInvoiceStatus = 'pending_review' | 'sent' | 'paid' | 'overdue';

export interface FamilyInvoice {
  id: string;
  document_id: string;
  family_id: string | null;
  student_id: string | null;
  contract_id: string | null;
  amount: string | null;
  currency: string;
  issue_date: string | null;
  due_date: string | null;
  status: FamilyInvoiceStatus;
  extracted_data: Record<string, unknown> | null;
  confidence: number | null;
}

export function getFamilyInvoices(
  token: string,
  status?: FamilyInvoiceStatus,
): Promise<FamilyInvoice[]> {
  const query = status ? `?status=${status}` : '';
  return request<FamilyInvoice[]>(`/family-invoices${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function updateFamilyInvoice(
  token: string,
  invoiceId: string,
  payload: Partial<Pick<FamilyInvoice, 'status' | 'family_id'>>,
): Promise<FamilyInvoice> {
  return request<FamilyInvoice>(`/family-invoices/${invoiceId}`, {
    method: 'PATCH',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}
