import type { CaseStatus, DashboardAnalyticsResponse, EvidenceItemResponse, EvidencePackageResponse, HealthResponse, InvestigationResponse, ModelInfoResponse, ModelMetricsResponse, PageResponse, RecommendationResponse, RiskCaseResponse, RiskSummaryResponse, TransactionDetailResponse, TransactionListItem } from '../types/api';

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); this.name = 'ApiError'; }
}

async function request<T>(path: string, signal?: AbortSignal, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`${baseUrl}${path}`, { headers: { Accept: 'application/json', ...init.headers }, signal, ...init }); }
  catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, 'Unable to reach the API. Check the backend service and API URL.');
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => undefined);
    const detail = typeof body === 'object' && body !== null && 'detail' in body && typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`;
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export interface TransactionQuery { page?: number; pageSize?: number; search?: string; status?: string; currency?: string; sortBy?: 'created_at' | 'amount' | 'status' | 'currency'; sortDir?: 'asc' | 'desc' }
const transactionParams = (query: TransactionQuery) => { const params = new URLSearchParams({ page: String(query.page ?? 1), page_size: String(query.pageSize ?? 25), sort_by: query.sortBy ?? 'created_at', sort_dir: query.sortDir ?? 'desc' }); if (query.search) params.set('search', query.search); if (query.status) params.set('status', query.status); if (query.currency) params.set('currency', query.currency); return params.toString(); };

export const api = {
  getHealth: (signal?: AbortSignal) => request<HealthResponse>('/api/v1/health', signal),
  getRiskSummary: (signal?: AbortSignal) => request<RiskSummaryResponse>('/api/v1/risk/summary', signal),
  getDashboardAnalytics: (signal?: AbortSignal) => request<DashboardAnalyticsResponse>('/api/v1/risk/dashboard', signal),
  getModelInfo: (signal?: AbortSignal) => request<ModelInfoResponse>('/api/v1/model/info', signal),
  getModelMetrics: (signal?: AbortSignal) => request<ModelMetricsResponse>('/api/v1/model/metrics', signal),
  getTransactions: (page = 1, pageSize = 25, signal?: AbortSignal) => request<PageResponse<TransactionListItem>>(`/api/v1/transactions?page=${page}&page_size=${pageSize}`, signal),
  searchTransactions: (query: TransactionQuery, signal?: AbortSignal) => request<PageResponse<TransactionListItem>>(`/api/v1/transactions?${transactionParams(query)}`, signal),
  getTransaction: (transactionId: string, signal?: AbortSignal) => request<TransactionDetailResponse>(`/api/v1/transactions/${transactionId}`, signal),
  createCase: (transactionId: string, signal?: AbortSignal) => request<RiskCaseResponse>('/api/v1/cases', signal, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ transaction_id: transactionId }) }),
  getCase: (caseId: string, signal?: AbortSignal) => request<RiskCaseResponse>(`/api/v1/cases/${caseId}`, signal),
  updateCase: (caseId: string, status: CaseStatus, signal?: AbortSignal) => request<RiskCaseResponse>(`/api/v1/cases/${caseId}`, signal, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }) }),
  getEvidence: (caseId: string, signal?: AbortSignal) => request<EvidenceItemResponse[]>(`/api/v1/cases/${caseId}/evidence`, signal),
  investigateCase: (caseId: string, signal?: AbortSignal) => request<InvestigationResponse>(`/api/v1/cases/${caseId}/investigate`, signal, { method: 'POST' }),
  generateEvidencePackage: (caseId: string, signal?: AbortSignal) => request<EvidencePackageResponse>(`/api/v1/cases/${caseId}/evidence`, signal, { method: 'POST' }),
  generateRecommendation: (caseId: string, signal?: AbortSignal) => request<RecommendationResponse>(`/api/v1/cases/${caseId}/recommendation`, signal, { method: 'POST' }),
};
