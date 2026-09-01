import React from 'react';
import { formatCurrency } from '../utils/formatters';
import { CheckCircle, AlertOctagon, HelpCircle } from 'lucide-react';

export const DecisionCard = ({ decisionResult }) => {
  if (!decisionResult) {
    return null;
  }

  const {
    feasible,
    initial_cash,
    minimum_cash_buffer,
    total_obligations,
    total_expected_inflows,
    selected_obligations = [],
    deferred_obligations = [],
    negotiated_obligations = [],
    ending_cash,
    minimum_projected_cash,
    projected_shortfall,
    total_deferral_cost,
  } = decisionResult;

  const allDecisions = [
    ...selected_obligations.map((o) => ({ ...o, category: 'PAY' })),
    ...deferred_obligations.map((o) => ({ ...o, category: 'DEFER' })),
    ...negotiated_obligations.map((o) => ({ ...o, category: 'NEGOTIATE' })),
  ];

  const payCount = selected_obligations.length;
  const payTotal = selected_obligations.reduce((sum, o) => sum + parseFloat(o.obligation.amount), 0);
  const deferCount = deferred_obligations.length;
  const negotiateCount = negotiated_obligations.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Overview Status Banner */}
      <div
        className="card"
        style={{
          borderLeft: `4px solid ${feasible ? '#10b981' : '#ef4444'}`,
          background: 'linear-gradient(135deg, #111827 0%, #1a2336 100%)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
          {feasible ? (
            <CheckCircle size={24} style={{ color: '#10b981' }} />
          ) : (
            <AlertOctagon size={24} style={{ color: '#ef4444' }} />
          )}
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: '700', color: '#fff' }}>
              {feasible ? 'Feasible Payment Strategy Available' : 'Liquidity Deficit — Deferral/Negotiation Required'}
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#9ca3af', marginTop: '0.15rem' }}>
              {payCount > 0 && `Pay ${formatCurrency(payTotal)} across ${payCount} obligation(s). `}
              {deferCount > 0 && `Defer ${deferCount} obligation(s). `}
              {negotiateCount > 0 && `Negotiate ${negotiateCount} obligation(s).`}
            </p>
          </div>
        </div>

        {/* Financial Metrics Strip */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '1rem',
            paddingTop: '1rem',
            borderTop: '1px solid #1f2d42',
            marginTop: '1rem',
          }}
        >
          <div>
            <span style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase' }}>Initial Cash</span>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#fff' }}>{formatCurrency(initial_cash)}</div>
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase' }}>Total Obligations</span>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#f87171' }}>{formatCurrency(total_obligations)}</div>
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase' }}>Expected Inflows</span>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#34d399' }}>{formatCurrency(total_expected_inflows)}</div>
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase' }}>Minimum Buffer</span>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#f59e0b' }}>{formatCurrency(minimum_cash_buffer)}</div>
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase' }}>Ending Cash</span>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#38bdf8' }}>{formatCurrency(ending_cash)}</div>
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase' }}>Min Projected Cash</span>
            <div style={{ fontSize: '1.1rem', fontWeight: '700', color: minimum_projected_cash < minimum_cash_buffer ? '#ef4444' : '#10b981' }}>
              {formatCurrency(minimum_projected_cash)}
            </div>
          </div>
        </div>
      </div>

      {/* Decision Breakdown per Obligation */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <h4 style={{ fontSize: '1.05rem', fontWeight: '600', color: '#fff' }}>Obligation Decisions & Structured Rationale</h4>
        {allDecisions.map((item, idx) => {
          const { obligation, action, reasoning, decision_factors = [], deferral_cost } = item;
          const badgeClass = action === 'PAY' ? 'badge-healthy' : action === 'DEFER' ? 'badge-warning' : 'badge-blue';

          return (
            <div
              key={idx}
              className="card"
              style={{
                background: '#131b2e',
                borderColor: '#1e293b',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.85rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span style={{ fontSize: '1.1rem', fontWeight: '700', color: '#fff' }}>
                    {obligation.counterparty_name}
                  </span>
                  <span style={{ fontSize: '0.85rem', color: '#9ca3af', marginLeft: '0.75rem' }}>
                    {obligation.description || `Payable #${obligation.payable_id}`}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <span style={{ fontSize: '1.15rem', fontWeight: '700', color: '#fff' }}>
                    {formatCurrency(obligation.amount)}
                  </span>
                  <span className={`badge ${badgeClass}`}>{action}</span>
                </div>
              </div>

              {/* Decision Factors */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', background: '#0d131f', padding: '0.75rem', borderRadius: '6px' }}>
                <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                  Urgency: <strong>{obligation.urgency}/5</strong>
                </span>
                <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                  Penalty Risk: <strong>{obligation.penalty_risk}/5</strong>
                </span>
                <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                  Flexibility: <strong>{obligation.flexibility}/5</strong>
                </span>
                {deferral_cost !== null && deferral_cost !== undefined && (
                  <span style={{ fontSize: '0.8rem', color: '#f59e0b' }}>
                    Deferral Cost Index: <strong>{deferral_cost.toFixed(2)}</strong>
                  </span>
                )}
              </div>

              {/* Reasoning */}
              {reasoning && (
                <div style={{ fontSize: '0.85rem', color: '#d1d5db', lineHeight: '1.4' }}>
                  <strong>Engine Rationale:</strong> {reasoning}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
