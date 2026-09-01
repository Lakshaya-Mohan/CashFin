import React, { useEffect, useState } from 'react';
import { getFinancialState } from '../api/financialState';
import { getCashFlowProjection } from '../api/cashFlow';
import { evaluateDecision } from '../api/decisions';
import { MetricCard } from '../components/MetricCard';
import { RiskBadge } from '../components/RiskBadge';
import { CashFlowChart } from '../components/CashFlowChart';
import { ObligationTable } from '../components/ObligationTable';
import { ReceivableTable } from '../components/ReceivableTable';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { formatCurrency } from '../utils/formatters';
import { Wallet, ArrowDownRight, ArrowUpRight, Shield, Activity } from 'lucide-react';

export const Dashboard = ({ companyId }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [financialState, setFinancialState] = useState(null);
  const [projection, setProjection] = useState(null);
  const [decision, setDecision] = useState(null);

  const fetchData = async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);

    try {
      const [stateRes, projRes, decRes] = await Promise.all([
        getFinancialState(companyId),
        getCashFlowProjection(companyId, { horizon_days: 30, minimum_cash_buffer: 25000 }),
        evaluateDecision(companyId, { minimum_cash_buffer: 25000 }).catch(() => null),
      ]);

      setFinancialState(stateRes);
      setProjection(projRes);
      setDecision(decRes);
    } catch (err) {
      setError(err.message || 'Unable to load financial data. Please check that the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [companyId]);

  if (loading) return <LoadingState message="Loading company financial dashboard..." />;
  if (error) return <ErrorState message={error} onRetry={fetchData} />;

  const decisionMap = {};
  if (decision) {
    (decision.selected_obligations || []).forEach((o) => { decisionMap[o.obligation.payable_id] = o; });
    (decision.deferred_obligations || []).forEach((o) => { decisionMap[o.obligation.payable_id] = o; });
    (decision.negotiated_obligations || []).forEach((o) => { decisionMap[o.obligation.payable_id] = o; });
  }

  const minProjCash = projection?.minimum_projected_balance ?? financialState?.current_cash;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Header & Liquidity Risk Banner */}
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div>
          <h1 className="page-title">Financial Overview</h1>
          <p className="page-subtitle">Real-time financial state and projected liquidity buffer</p>
        </div>
        <div>
          <RiskBadge
            daysToZero={projection?.days_to_zero}
            daysToBufferBreach={projection?.days_to_buffer_breach}
          />
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid-4">
        <MetricCard
          label="Current Cash"
          value={formatCurrency(financialState?.current_cash)}
          subtext="Available liquid funds"
          icon={Wallet}
          accentColor="#3b82f6"
        />
        <MetricCard
          label="Pending Payables"
          value={formatCurrency(financialState?.pending_payables_total)}
          subtext={`${financialState?.upcoming_payables?.length || 0} upcoming obligation(s)`}
          icon={ArrowDownRight}
          accentColor="#ef4444"
        />
        <MetricCard
          label="Expected Receivables"
          value={formatCurrency(financialState?.pending_receivables_total_raw)}
          subtext={`Adjusted: ${formatCurrency(financialState?.pending_receivables_total_adjusted)}`}
          icon={ArrowUpRight}
          accentColor="#10b981"
        />
        <MetricCard
          label="Min Projected Cash"
          value={formatCurrency(minProjCash)}
          subtext={`Buffer Floor: ${formatCurrency(projection?.minimum_cash_buffer || 25000)}`}
          icon={Shield}
          accentColor={minProjCash < 25000 ? '#ef4444' : '#f59e0b'}
        />
      </div>

      {/* Cash Flow Chart Card */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div className="card-title" style={{ marginBottom: 0 }}>
            <Activity size={20} style={{ color: '#38bdf8' }} />
            <span>30-Day Cash Flow Projection</span>
          </div>
          <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
            Horizon: 30 Days | Mode: {projection?.forecast_mode || 'CONFIRMED_ONLY'}
          </span>
        </div>
        <CashFlowChart projection={projection} />
      </div>

      {/* Tables Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div className="card">
          <h2 className="card-title">Upcoming Obligations & Payment Recommendations</h2>
          <ObligationTable
            obligations={financialState?.upcoming_payables || []}
            decisionMap={decisionMap}
          />
        </div>

        <div className="card">
          <h2 className="card-title">Expected Receivables</h2>
          <ReceivableTable receivables={financialState?.upcoming_receivables || []} />
        </div>
      </div>
    </div>
  );
};
