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
  const { data } = await requestWithHeaders<T>(path, options);
  return data;
}

/** Igual que `request`, pero conserva las cabeceras de la respuesta. */
async function requestWithHeaders<T>(
  path: string,
  options: RequestInit = {},
): Promise<{ data: T; headers: Headers }> {
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

  if (response.status === 204) {
    return { data: undefined as T, headers: response.headers };
  }
  const text = await response.text();
  if (!text) {
    return { data: undefined as T, headers: response.headers };
  }
  return { data: JSON.parse(text) as T, headers: response.headers };
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
  /** Fecha en que quedo saldada, no la de emision (TASK-0102). */
  paid_at?: string | null;
  /** Total cobrado: distingue una factura saldada de una con pago parcial. */
  paid_amount?: string;
  possible_duplicate?: boolean;
  days_in_queue?: number | null;
  days_overdue?: number | null;
}

export interface Page<T> {
  items: T[];
  /** Total real en el servidor, no el de esta pagina. */
  total: number;
}

/**
 * Listado de una sola familia: la vista del padre y la ficha de staff.
 *
 * Pide el maximo que admite la API en vez del tamano de pagina por defecto:
 * son vistas de UNA familia, y 200 facturas son mas de quince anos de cuota
 * mensual. El tablero, que si puede tener miles, usa `getFamilyInvoicePage`.
 */
export function getFamilyInvoices(
  token: string,
  status?: FamilyInvoiceStatus,
  familyId?: string,
): Promise<FamilyInvoice[]> {
  return getFamilyInvoicePage(token, { status, familyId, limit: 200 }).then((page) => page.items);
}

/**
 * Pagina del listado, con el total que viene en `X-Total-Count` (TASK-0126).
 *
 * Antes se pedia la tabla entera: con 2.068 facturas eran 13,6 segundos hasta
 * ver la primera tarjeta y 443.093 px de pagina. Si la cabecera no viene -los
 * mocks de e2e no la ponen- se cae al tamano de la propia lista, que es lo
 * correcto cuando no hay paginacion detras.
 */
export async function getFamilyInvoicePage(
  token: string,
  options: {
    status?: FamilyInvoiceStatus;
    familyId?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<Page<FamilyInvoice>> {
  const params = new URLSearchParams();
  if (options.status) params.set('status', options.status);
  if (options.familyId) params.set('family_id', options.familyId);
  if (options.limit !== undefined) params.set('limit', String(options.limit));
  if (options.offset !== undefined) params.set('offset', String(options.offset));
  const query = params.toString() ? `?${params.toString()}` : '';
  const { data, headers } = await requestWithHeaders<FamilyInvoice[]>(`/family-invoices${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const items = data ?? [];
  const rawTotal = headers.get('X-Total-Count');
  const total = rawTotal === null ? items.length : Number(rawTotal);
  return { items, total: Number.isFinite(total) ? total : items.length };
}

/**
 * `FamilyInvoiceUpdate` del backend siempre acepto importe y fechas, pero el
 * cliente solo dejaba mandar `status` y `family_id`: no habia ningun sitio en
 * toda la interfaz donde corregir lo que el extractor saco mal, que es
 * justamente el trabajo de la cola de revision (TASK-0127).
 */
export type PaymentMethod = 'transfer' | 'direct_debit' | 'card' | 'cash' | 'other';

export interface Payment {
  id: string;
  invoice_id: string;
  amount: string;
  currency: string;
  paid_on: string;
  method: PaymentMethod;
  reference: string | null;
  note: string | null;
  created_at: string;
}

/**
 * Registra un cobro sobre una factura (TASK-0157).
 *
 * Un pago parcial no la salda: la factura sigue viva y su deuda es el resto.
 * Eso es justo lo que no se podia expresar cuando «pagada» era solo un estado.
 */
export function addPayment(
  token: string,
  invoiceId: string,
  payload: {
    amount: string;
    paid_on?: string;
    method?: PaymentMethod;
    reference?: string;
    note?: string;
  },
): Promise<Payment> {
  return request<Payment>(`/family-invoices/${invoiceId}/payments`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
}

export function getPayments(token: string, invoiceId: string): Promise<Payment[]> {
  return request<Payment[]>(`/family-invoices/${invoiceId}/payments`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function updateFamilyInvoice(
  token: string,
  invoiceId: string,
  payload: Partial<
    Pick<FamilyInvoice, 'status' | 'family_id' | 'amount' | 'issue_date' | 'due_date'>
  >,
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
  outstanding_amount?: string;
  overdue_amount?: string;
  unbilled?: boolean;
  currency?: string;
}

export function getFamilies(token: string, q?: string): Promise<Family[]> {
  const query = q && q.trim().length >= 2 ? `?q=${encodeURIComponent(q.trim())}` : '';
  return request<Family[]>(`/families${query}`, authed(token));
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
  family_name: string | null;
  title: string;
  description: string | null;
  due_date: string | null;
  status: TaskStatus;
  assigned_to: string | null;
  created_by: string;
}

export function getTasks(token: string, familyId?: string): Promise<Task[]> {
  const query = familyId ? `?family_id=${familyId}` : '';
  return request<Task[]>(`/tasks${query}`, authed(token));
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

export function createUser(
  token: string,
  payload: {
    email: string;
    password: string;
    name: string;
    role: UserRole;
    family_id?: string;
  },
): Promise<MeResponse> {
  return request<MeResponse>(
    '/users',
    authed(token, { method: 'POST', body: JSON.stringify(payload) }),
  );
}

export function getUsers(token: string, familyId?: string): Promise<MeResponse[]> {
  const query = familyId ? `?family_id=${familyId}` : '';
  return request<MeResponse[]>(`/users${query}`, authed(token));
}

export function createSupplier(
  token: string,
  payload: {
    name: string;
    tax_id?: string;
    email?: string;
    category?: SupplierCategory;
  },
): Promise<Supplier> {
  return request<Supplier>(
    '/suppliers',
    authed(token, { method: 'POST', body: JSON.stringify(payload) }),
  );
}

export function updateSupplier(
  token: string,
  supplierId: string,
  payload: Partial<Pick<Supplier, 'name' | 'tax_id' | 'email' | 'category'>>,
): Promise<Supplier> {
  return request<Supplier>(
    `/suppliers/${supplierId}`,
    authed(token, { method: 'PATCH', body: JSON.stringify(payload) }),
  );
}

export interface FamilyBilling {
  outstanding_amount: string;
  overdue_amount: string;
  overdue_count: number;
  sent_count: number;
  paid_count: number;
  due_soon_count?: number;
  due_soon_amount?: string;
  currency: string;
}

export interface StaffBillingSummary {
  pending_review_count: number;
  overdue_count: number;
  families_with_debt: number;
  families_count: number;
  overdue_amount: string;
  outstanding_amount: string;
  year_month: string;
  expected_amount: string;
  collected_amount: string;
  due_soon_count: number;
  due_soon_amount: string;
  pending_tasks: number;
  failed_emails: number;
  unbilled_families: number;
  currency: string;
}

export interface UnbilledFamily {
  id: string;
  name: string;
  expected_amount: string;
  currency: string;
}

export function getUnbilledFamilies(token: string): Promise<UnbilledFamily[]> {
  return request<UnbilledFamily[]>('/billing/unbilled', authed(token));
}

export function createUnbilledTasks(
  token: string,
): Promise<{ created: number; skipped: number; year_month: string }> {
  return request('/billing/unbilled/tasks', authed(token, { method: 'POST' }));
}

export interface InboxItem {
  kind: string;
  title: string;
  href: string;
  count: number;
}

export function getNotificationInbox(token: string): Promise<InboxItem[]> {
  return request<InboxItem[]>('/notifications/inbox', authed(token));
}

export function getMyNotifications(token: string): Promise<InboxItem[]> {
  return request<InboxItem[]>('/notifications/mine', authed(token));
}

export interface ReminderOutcome {
  queued: number;
  already_queued: number;
  families: number;
  families_without_recipient: number;
  pending_in_outbox: number;
}

export interface FlushOutcome {
  sent: number;
  failed: number;
  pending: number;
  transport_available: boolean;
  errors: string[];
}

export function sendDueSoonReminders(token: string): Promise<ReminderOutcome> {
  return request('/notifications/due-soon-reminders', authed(token, { method: 'POST' }));
}

/**
 * Vacia la bandeja de salida contra el SMTP real (TASK-0105).
 *
 * Encolar y enviar son dos pasos distintos a proposito: el endpoint de
 * recordatorios no toca el SMTP, asi que no puede afirmar que algo haya salido.
 * Este si, y dice cuantos salieron, cuantos fallaron y si habia transporte.
 */
export function flushNotifications(token: string): Promise<FlushOutcome> {
  return request('/notifications/flush', authed(token, { method: 'POST' }));
}

export function bulkUpdateFamilyInvoices(
  token: string,
  payload: { ids: string[]; status?: FamilyInvoiceStatus; family_id?: string },
): Promise<{ updated: number; failed: { id: string; detail: string }[] }> {
  return request(
    '/family-invoices/bulk',
    authed(token, { method: 'POST', body: JSON.stringify(payload) }),
  );
}

export function claimInvoicePayment(token: string, invoiceId: string): Promise<Task> {
  return request(`/family-invoices/${invoiceId}/claim-payment`, authed(token, { method: 'POST' }));
}

export function confirmInvoicePayment(token: string, invoiceId: string): Promise<FamilyInvoice> {
  return request(
    `/family-invoices/${invoiceId}/confirm-payment`,
    authed(token, { method: 'POST' }),
  );
}

export const PAYMENT_CLAIM_TITLE = 'El padre indica que ha pagado';

export function invoiceIdFromClaim(description: string | null | undefined): string | null {
  const match = description?.match(/^invoice:([0-9a-f-]{36})/i);
  return match?.[1] ?? null;
}

export interface FamilyMonthRow {
  id: string;
  name: string;
  expected_amount: string;
  collected_amount: string;
  outstanding_amount: string;
  overdue_amount: string;
  unbilled: boolean;
  currency: string;
}

export interface MonthReport {
  year_month: string;
  families: FamilyMonthRow[];
}

export function getMonthReport(token: string): Promise<MonthReport> {
  return request<MonthReport>('/billing/month-report', authed(token));
}

export interface AtRiskFamily {
  id: string;
  name: string;
  overdue_amount: string;
  overdue_count: number;
  pending_tasks: number;
}

export function getAtRiskFamilies(token: string): Promise<AtRiskFamily[]> {
  return request<AtRiskFamily[]>('/billing/at-risk', authed(token));
}

export interface IngestedEmail {
  id: string;
  gmail_id: string;
  subject: string | null;
  from_address: string | null;
  processing_status: 'pending' | 'processing' | 'processed' | 'failed' | 'ignored';
  error_message: string | null;
  created_at: string;
  document_count: number;
}

export function getEmails(token: string, status?: string): Promise<IngestedEmail[]> {
  const query = status ? `?status=${status}` : '';
  return request<IngestedEmail[]>(`/emails${query}`, authed(token));
}

export function getFamilyBilling(token: string, familyId: string): Promise<FamilyBilling> {
  return request<FamilyBilling>(`/families/${familyId}/billing`, authed(token));
}

export function getBillingSummary(token: string): Promise<StaffBillingSummary> {
  return request<StaffBillingSummary>('/billing/summary', authed(token));
}

export function sendOverdueReminders(token: string): Promise<ReminderOutcome> {
  return request('/notifications/overdue-reminders', authed(token, { method: 'POST' }));
}

export type DocumentType =
  'family_invoice' | 'supplier_invoice' | 'credit_note' | 'other' | 'unknown';

export interface StoredDocument {
  id: string;
  document_type: DocumentType;
  original_filename: string | null;
  mime_type: string | null;
  created_at: string;
}

export function getDocuments(
  token: string,
  documentType?: DocumentType,
): Promise<StoredDocument[]> {
  const query = documentType ? `?document_type=${documentType}` : '';
  return request<StoredDocument[]>(`/documents${query}`, authed(token));
}

export async function downloadDocument(
  token: string,
  documentId: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_URL}/documents/${documentId}/file`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 401 && typeof window !== 'undefined') {
    clearStoredToken();
    if (!window.location.pathname.startsWith('/login')) {
      window.location.assign('/login?expired=1');
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, 'No se pudo descargar el documento');
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') ?? '';
  const match = /filename="?([^"]+)"?/i.exec(disposition);
  return { blob, filename: match?.[1] ?? 'factura.pdf' };
}

export type SearchHitType = 'family' | 'student' | 'family_invoice' | 'supplier';

export interface SearchHit {
  type: SearchHitType;
  id: string;
  title: string;
  subtitle: string | null;
  family_id: string | null;
}

export function search(token: string, q: string): Promise<{ hits: SearchHit[] }> {
  return request(`/search?q=${encodeURIComponent(q)}`, authed(token));
}

export interface ActivityEvent {
  at: string;
  kind: 'audit' | 'note';
  title: string;
  detail: string | null;
  actor_name: string | null;
}

export function getFamilyActivity(token: string, familyId: string): Promise<ActivityEvent[]> {
  return request(`/families/${familyId}/activity`, authed(token));
}

export async function downloadFamilyInvoicesCsv(
  token: string,
  status?: FamilyInvoiceStatus,
): Promise<{ blob: Blob; filename: string }> {
  const query = status ? `?status=${status}` : '';
  const response = await fetch(`${API_URL}/family-invoices/export.csv${query}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 401 && typeof window !== 'undefined') {
    clearStoredToken();
    if (!window.location.pathname.startsWith('/login')) {
      window.location.assign('/login?expired=1');
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, 'No se pudo exportar el CSV');
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') ?? '';
  const match = /filename="?([^"]+)"?/i.exec(disposition);
  return { blob, filename: match?.[1] ?? 'facturas.csv' };
}

export async function downloadMonthReportCsv(
  token: string,
): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_URL}/billing/month-report.csv`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (response.status === 401 && typeof window !== 'undefined') {
    clearStoredToken();
    if (!window.location.pathname.startsWith('/login')) {
      window.location.assign('/login?expired=1');
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, 'No se pudo exportar el CSV');
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') ?? '';
  const match = /filename="?([^"]+)"?/i.exec(disposition);
  return { blob, filename: match?.[1] ?? 'cierre.csv' };
}
