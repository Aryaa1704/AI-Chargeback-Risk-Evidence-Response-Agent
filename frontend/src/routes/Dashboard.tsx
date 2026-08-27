import { useCallback, useEffect } from 'react';
import { api } from '../api/client';
import { Alert, Button, Card, EmptyState, ErrorState, LoadingState, RiskBadge } from '../components/ui';
import type { DashboardAnalyticsResponse } from '../types/api';
import { useApiData } from './data';

const percent = (value: unknown) => typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '—';
const metric = (data: DashboardAnalyticsResponse, key: string) => percent(data.model_metrics.metrics[key]);

function Donut({ data }: { data: DashboardAnalyticsResponse['risk_distribution'] }) {
  const total = data.reduce((sum, item) => sum + item.count, 0);
  if (!total) return <EmptyState title="No predictions yet" detail="Risk-level counts appear after ML predictions are persisted." />;
  let offset = 0;
  const colors: Record<string, string> = { HIGH: '#f43f5e', MEDIUM: '#f59e0b', LOW: '#14b8a6' };
  return <div className="chart-pair"><svg className="donut" viewBox="0 0 42 42" role="img" aria-label="Risk distribution donut chart">{data.map((item) => { const length = (item.count / total) * 100; const segment = <circle key={item.risk_level} cx="21" cy="21" r="15.915" fill="transparent" stroke={colors[item.risk_level] ?? '#64748b'} strokeWidth="6" strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={-offset} />; offset += length; return segment; })}<circle cx="21" cy="21" r="10" fill="#101d30" /></svg><div className="legend">{data.map((item) => <span key={item.risk_level}><RiskBadge level={item.risk_level} /> {item.count}</span>)}</div></div>;
}

function Histogram({ data }: { data: DashboardAnalyticsResponse['risk_score_histogram'] }) {
  const max = Math.max(1, ...data.map((item) => item.count));
  return <div className="histogram" aria-label="Risk-score distribution histogram">{data.map((item) => <div key={item.bucket_start} className="histogram__bar"><span style={{ height: `${(item.count / max) * 100}%` }} /><small>{item.bucket_start}-{item.bucket_end}</small><strong>{item.count}</strong></div>)}</div>;
}

function Trend({ data }: { data: DashboardAnalyticsResponse['transaction_volume_trend'] }) {
  const max = Math.max(1, ...data.map((item) => item.count));
  return <div className="trend" aria-label="Transaction volume trend over time">{data.map((item) => <div key={item.date}><span style={{ height: `${(item.count / max) * 100}%` }} title={`${item.date}: ${item.count}`} /><small>{item.date.slice(5)}</small></div>)}</div>;
}

function ConfusionMatrix({ matrix }: { matrix: unknown }) {
  const values = Array.isArray(matrix) ? matrix as number[][] : [[0, 0], [0, 0]];
  return <div className="matrix" aria-label="Confusion matrix"><div /><strong>Pred no CB</strong><strong>Pred CB</strong><strong>Actual no CB</strong><span>{values[0]?.[0] ?? 0}</span><span>{values[0]?.[1] ?? 0}</span><strong>Actual CB</strong><span>{values[1]?.[0] ?? 0}</span><span>{values[1]?.[1] ?? 0}</span></div>;
}

export function Dashboard() {
  const load = useCallback((signal: AbortSignal) => api.getDashboardAnalytics(signal), []);
  const { data, error, retry } = useApiData(load);
  useEffect(() => { const id = window.setInterval(retry, 30000); return () => window.clearInterval(id); }, [retry]);
  const investigate = async (transactionId: string) => { const created = await api.createCase(transactionId); window.history.pushState({}, '', `/cases?case_id=${created.case_id}`); window.dispatchEvent(new PopStateEvent('popstate')); };
  const openHeroTransaction = () => { window.history.pushState({}, '', '/transactions?search=TX-DEMO-001'); window.dispatchEvent(new PopStateEvent('popstate')); };
  return <><header className="page-heading"><p className="eyebrow">Operations overview</p><h1>Risk operations</h1><p>Live, database-derived review context for synthetic demo data.</p></header>{!data && !error && <LoadingState label="Loading live dashboard…" />}{error && <ErrorState message={error} onRetry={retry} />}{data && <><div className="hero-demo card"><div><p className="eyebrow">5-minute demo path</p><h2>Hero transaction TX-DEMO-001</h2><p>Synthetic high-risk case with high amount, failed status, cross-border merchant context, and prior customer disputes.</p></div><div className="action-row"><Button onClick={openHeroTransaction}>Open hero transaction</Button><Button onClick={() => void investigate('TX-DEMO-001')}>Investigate now</Button></div></div><div className="dashboard-toolbar"><Alert kind="info">Synthetic demo data. Updated {new Date(data.generated_at).toLocaleString()}. Auto-refreshes every 30 seconds.</Alert><button className="button" onClick={retry}>Refresh</button></div><div className="metric-grid metric-grid--five"><Card title="Total Transactions"><strong className="metric">{data.kpis.total_transactions}</strong><span>Database records</span></Card><Card title="High-Risk"><strong className="metric">{data.kpis.high_risk}</strong><span>Persisted HIGH predictions</span></Card><Card title="Medium-Risk"><strong className="metric">{data.kpis.medium_risk}</strong><span>Persisted MEDIUM predictions</span></Card><Card title="Predicted Chargebacks"><strong className="metric">{data.kpis.predicted_chargebacks}</strong><span>Audited ML predictions</span></Card><Card title="Average Risk Score"><strong className="metric">{data.kpis.average_risk_score === null ? '—' : data.kpis.average_risk_score.toFixed(1)}</strong><span>Prediction average</span></Card></div><div className="dashboard-grid"><Card title="Risk distribution"><Donut data={data.risk_distribution} /></Card><Card title="Risk-score distribution"><Histogram data={data.risk_score_histogram} /></Card><Card title="Transaction volume trend"><Trend data={data.transaction_volume_trend} /></Card><Card title="Model performance"><p className="heldout-label">Evaluated on held-out test set</p><div className="metrics-list"><span>Precision <strong>{metric(data, 'precision')}</strong></span><span>Recall <strong>{metric(data, 'recall')}</strong></span><span>F1 <strong>{metric(data, 'f1')}</strong></span><span>Accuracy <strong>{metric(data, 'accuracy')}</strong></span><span>ROC-AUC <strong>{metric(data, 'roc_auc')}</strong></span></div></Card><Card title="Confusion matrix"><ConfusionMatrix matrix={data.model_metrics.metrics.confusion_matrix} /></Card></div><Card title="Recent high-risk cases">{data.recent_high_risk_cases.length ? <div className="table-scroll"><table><thead><tr><th>Transaction</th><th>Risk</th><th>Amount</th><th>Status</th><th>Predicted</th><th /></tr></thead><tbody>{data.recent_high_risk_cases.map((item) => <tr key={`${item.transaction_id}-${item.predicted_at}`}><td>{item.transaction_id}</td><td><RiskBadge level={item.risk_level} /> {item.risk_score.toFixed(1)}</td><td>{item.currency} {item.amount}</td><td>{item.status}</td><td>{new Date(item.predicted_at).toLocaleString()}</td><td><button className="button" onClick={() => void investigate(item.transaction_id)}>Investigate</button></td></tr>)}</tbody></table></div> : <EmptyState title="No high-risk predictions" detail="Run ML predictions to populate the investigation queue." />}</Card><Alert kind="warning">Dashboard recommendations are review cues only. No refunds, reversals, transfers, or account actions are executed.</Alert></>}</>;
}
