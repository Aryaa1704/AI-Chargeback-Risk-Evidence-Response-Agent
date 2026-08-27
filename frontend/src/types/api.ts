export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH';
export type CaseStatus = 'NEW' | 'INVESTIGATING' | 'READY_FOR_REVIEW' | 'APPROVED' | 'REJECTED' | 'CLOSED';

export interface HealthResponse { status: string; service: string }
export interface RiskSummaryResponse { total_transactions: number; total_predictions: number; risk_level_counts: Record<string, number>; average_risk_score: number | null }
export interface ModelInfoResponse { model_version: string; model_type: string; dataset_version: string; feature_count: number; selection_criterion: string; held_out_test_policy: string }
export interface ModelMetricsResponse { model_version: string; model_type: string; dataset_version: string; evaluated_at: string; metrics: Record<string, unknown> }
export interface TransactionListItem { transaction_id: string; customer_id: string; merchant_id: string; amount: string; currency: string; status: string; created_at: string }
export interface TransactionDetailResponse extends TransactionListItem { id: string; device_id: string | null; updated_at: string; customer_email: string; customer_name: string; merchant_name: string; merchant_category: string; disputes_count: number }
export interface PageResponse<T> { items: T[]; page: number; page_size: number; total: number }
export interface DashboardKpis { total_transactions: number; high_risk: number; medium_risk: number; predicted_chargebacks: number; average_risk_score: number | null }
export interface RiskDistributionPoint { risk_level: string; count: number }
export interface RiskScoreBucket { bucket_start: number; bucket_end: number; count: number }
export interface TransactionVolumePoint { date: string; count: number }
export interface RecentHighRiskCase { transaction_id: string; risk_score: number; risk_level: string; model_version: string; predicted_at: string; amount: string; currency: string; status: string }
export interface DashboardAnalyticsResponse { generated_at: string; synthetic_data: true; kpis: DashboardKpis; risk_distribution: RiskDistributionPoint[]; risk_score_histogram: RiskScoreBucket[]; transaction_volume_trend: TransactionVolumePoint[]; model_metrics: ModelMetricsResponse; recent_high_risk_cases: RecentHighRiskCase[] }
export interface RiskFactorResponse { transformed_feature: string; source_feature: string; feature_value: number; contribution: number; attribution_method: string }
export interface RiskPredictResponse { prediction_id: string; transaction_id: string; probability: number; risk_score: number; risk_level: string; model_version: string; model_derived_risk_factors: RiskFactorResponse[] }
export interface EvidenceItemResponse { id: string; evidence_type: string; source: string; source_id: string; factual_content: string; retrieved_at: string; verification_status: string }
export interface InvestigationResponse { risk_summary: string; evidence_references: string[]; risk_factors: string[]; recommendation: 'MANUAL_REVIEW' | 'GATHER_MORE_EVIDENCE' | 'CONTEST_DISPUTE'; confidence: number; requires_human_review: true }
export interface AgentToolCallResponse { tool_name: string; arguments: Record<string, unknown>; evidence_references: string[] }
export interface PersistedInvestigationResponse { model_name: string; tool_calls: AgentToolCallResponse[]; evidence_references: string[]; result: InvestigationResponse; created_at: string }
export interface EvidenceClaimResponse { content: string; source: string; source_id: string }
export interface EvidencePackageResponse { case_id: string; package_id: string; version: number; generated_at: string; transaction_evidence: EvidenceClaimResponse[]; customer_history: EvidenceClaimResponse[]; previous_disputes: EvidenceClaimResponse[]; risk_analysis: EvidenceClaimResponse[]; recommended_response: string }
export interface RecommendationResponse { case_id: string; recommendation_id: string; evidence_package_id: string; version: number; generated_at: string; category: string; rationale: string; human_approval_required: true; financial_action_executed: false }
export interface RiskCaseHistoryResponse { id: string; event_type: string; from_status: string | null; to_status: string | null; assigned_reviewer: string | null; occurred_at: string }
export interface RiskCaseResponse { case_id: string; transaction_id: string; prediction_id: string; risk_score: string; risk_level: string; prediction: string; status: CaseStatus; assigned_reviewer: string | null; created_at: string; updated_at: string; history: RiskCaseHistoryResponse[]; latest_investigation: PersistedInvestigationResponse | null; latest_evidence_package: EvidencePackageResponse | null; latest_recommendation: RecommendationResponse | null }
