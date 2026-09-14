import { clearStoredToken } from './auth-storage';

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

  if (response.status === 401 && !path.startsWith('/auth/login') && typeof window !== 'undefined') {
    clearStoredToken();
    if (!window.location.pathname.startsWith('/login')) {
      window.location.assign('/login?expired=1');
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}) as { detail?: string });
    const detail = body.detail;
    const message = typeof detail === 'string' ? detail : 'No se pudo completar la solicitud';
    throw new ApiError(response.status, message);
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
  family_name: string | null;
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

function authed(token: string, options: RequestInit = {}): RequestInit {
  return { ...options, headers: { ...options.headers, Authorization: `Bearer ${token}` } };
}

export type FamilyStatus = 'active' | 'inactive';

export interface Family {
  id: string;
  name: string;
  address: string | null;
  status: FamilyStatus;
}

export function getFamilies(token: string): Promise<Family[]> {
  return request<Family[]>('/families', authed(token));
}

export function getFamily(token: string, familyId: string): Promise<Family> {
  return request<Family>(`/families/${familyId}`, authed(token));
}

export function createFamily(
  token: string,
  payload: { name: string; address?: string },
): Promise<Family> {
  return request<Family>(
    '/families',
    authed(token, { method: 'POST', body: JSON.stringify(payload) }),
  );
}

export function updateFamily(
  token: string,
  familyId: string,
  payload: Partial<{ name: string; address: string | null; status: FamilyStatus }>,
): Promise<Family> {
  return request<Family>(
    `/families/${familyId}`,
    authed(token, { method: 'PATCH', body: JSON.stringify(payload) }),
  );
}

export function exportFamily(token: string, familyId: string): Promise<Record<string, unknown>> {
  return request(`/families/${familyId}/export`, authed(token));
}

export function anonymizeFamily(token: string, familyId: string): Promise<void> {
  return request(`/families/${familyId}/anonymize`, authed(token, { method: 'POST' }));
}

export type StudentStatus = 'active' | 'inactive';

export interface Student {
  id: string;
  family_id: string;
  name: string;
  birth_date: string | null;
  school: string | null;
  status: StudentStatus;
}

export function getStudents(token: string, familyId: string): Promise<Student[]> {
  return request<Student[]>(`/students?family_id=${familyId}`, authed(token));
}

export function createStudent(
  token: string,
  payload: { family_id: string; name: string; birth_date?: string; school?: string },
): Promise<Student> {
  return request<Student>(
    '/students',
    authed(token, { method: 'POST', body: JSON.stringify(payload) }),
  );
}

export type NoteEntityType = 'family' | 'student';

export interface Note {
  id: string;
  entity_type: NoteEntityType;
  entity_id: string;
  body: string;
  created_by: string;
  created_at: string;
}

export function getNotes(
  token: string,
  entityType: NoteEntityType,
  entityId: string,
): Promise<Note[]> {
  return request<Note[]>(`/notes?entity_type=${entityType}&entity_id=${entityId}`, authed(token));
}

export function createNote(
  token: string,
  payload: { entity_type: NoteEntityType; entity_id: string; body: string },
): Promise<Note> {
  return request<Note>('/notes', authed(token, { method: 'POST', body: JSON.stringify(payload) }));
}

export function deleteNote(token: string, noteId: string): Promise<void> {
  return request(`/notes/${noteId}`, authed(token, { method: 'DELETE' }));
}

export type TaskStatus = 'pending' | 'done' | 'cancelled';

export interface Task {
  id: string;
  family_id: string;
  title: string;
  description: string | null;
  due_date: string | null;
  status: TaskStatus;
  assigned_to: string | null;
  created_by: string;
}

export function getTasks(token: string, familyId: string): Promise<Task[]> {
  return request<Task[]>(`/tasks?family_id=${familyId}`, authed(token));
}

export function createTask(
  token: string,
  payload: { family_id: string; title: string; description?: string; due_date?: string },
): Promise<Task> {
  return request<Task>('/tasks', authed(token, { method: 'POST', body: JSON.stringify(payload) }));
}

export function updateTask(
  token: string,
  taskId: string,
  payload: Partial<Pick<Task, 'status'>>,
): Promise<Task> {
  return request<Task>(
    `/tasks/${taskId}`,
    authed(token, { method: 'PATCH', body: JSON.stringify(payload) }),
  );
}

export function updateStudent(
  token: string,
  studentId: string,
  payload: Partial<Pick<Student, 'name' | 'birth_date' | 'school' | 'status'>>,
): Promise<Student> {
  return request<Student>(
    `/students/${studentId}`,
    authed(token, { method: 'PATCH', body: JSON.stringify(payload) }),
  );
}

export type ContractStatus = 'active' | 'paused' | 'cancelled';

export interface Contract {
  id: string;
  student_id: string;
  service_type: string;
  monthly_fee: string;
  start_date: string;
  end_date: string | null;
  status: ContractStatus;
}

export function getContracts(token: string, studentId?: string): Promise<Contract[]> {
  const query = studentId ? `?student_id=${studentId}` : '';
  return request<Contract[]>(`/contracts${query}`, authed(token));
}

export function createContract(
  token: string,
  payload: {
    student_id: string;
    service_type: string;
    monthly_fee: string;
    start_date: string;
    end_date?: string;
  },
): Promise<Contract> {
  return request<Contract>(
    '/contracts',
    authed(token, { method: 'POST', body: JSON.stringify(payload) }),
  );
}

export function updateContract(
  token: string,
  contractId: string,
  payload: Partial<Pick<Contract, 'service_type' | 'monthly_fee' | 'end_date' | 'status'>>,
): Promise<Contract> {
  return request<Contract>(
    `/contracts/${contractId}`,
    authed(token, { method: 'PATCH', body: JSON.stringify(payload) }),
  );
}

export type SupplierInvoiceStatus = 'pending_review' | 'approved' | 'paid';
export type SupplierCategory = 'fuel' | 'maintenance' | 'insurance' | 'other';

export interface Supplier {
  id: string;
  name: string;
  tax_id: string | null;
  email: string | null;
  category: SupplierCategory;
}

export interface SupplierInvoice {
  id: string;
  document_id: string;
  supplier_id: string | null;
  supplier_name: string | null;
  category: SupplierCategory;
  amount: string | null;
  currency: string;
  issue_date: string | null;
  due_date: string | null;
  status: SupplierInvoiceStatus;
  extracted_data: Record<string, unknown> | null;
  confidence: number | null;
}

export function getSuppliers(token: string): Promise<Supplier[]> {
  return request<Supplier[]>('/suppliers', authed(token));
}

export function getSupplierInvoices(
  token: string,
  status?: SupplierInvoiceStatus,
): Promise<SupplierInvoice[]> {
  const query = status ? `?status=${status}` : '';
  return request<SupplierInvoice[]>(`/supplier-invoices${query}`, authed(token));
}

export function updateSupplierInvoice(
  token: string,
  invoiceId: string,
  payload: Partial<Pick<SupplierInvoice, 'status' | 'supplier_id'>>,
): Promise<SupplierInvoice> {
  return request<SupplierInvoice>(
    `/supplier-invoices/${invoiceId}`,
    authed(token, { method: 'PATCH', body: JSON.stringify(payload) }),
  );
}

export interface IngestionRunResult {
  processed: number;
  skipped_already_processed: number;
  failed: string[];
}

export function runIngestion(token: string, useDemoInbox = true): Promise<IngestionRunResult> {
  return request<IngestionRunResult>(
    '/ingestion/run',
    authed(token, { method: 'POST', body: JSON.stringify({ use_demo_inbox: useDemoInbox }) }),
  );
}
