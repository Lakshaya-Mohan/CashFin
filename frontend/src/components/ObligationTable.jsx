import React from 'react';
import { formatCurrency, formatDate } from '../utils/formatters';

const ActionBadge = ({ action }) => {
  if (!action) return null;
  const act = action.toUpperCase();
  if (act === 'PAY') {
    return <span className="badge badge-healthy">PAY</span>;
  }
  if (act === 'DEFER') {
    return <span className="badge badge-warning">DEFER</span>;
  }
  if (act === 'NEGOTIATE') {
    return <span className="badge badge-blue">NEGOTIATE</span>;
  }
  return <span className="badge">{action}</span>;
};

export const ObligationTable = ({ obligations = [], decisionMap = {} }) => {
  if (!obligations || obligations.length === 0) {
    return <div style={{ color: '#9ca3af', padding: '1.5rem', textAlign: 'center' }}>No upcoming obligations found</div>;
  }

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>Due Date</th>
            <th>Counterparty / Vendor</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Urgency</th>
            <th>Penalty Risk</th>
            <th>Flexibility</th>
            <th>Recommendation</th>
          </tr>
        </thead>
        <tbody>
          {obligations.map((item) => {
            const payableId = item.id || item.payable_id;
            const recAction = decisionMap[payableId]?.action || item.recommended_action;
            const cpName = item.counterparty_name || item.counterparty?.name || item.vendor_name || `Payable #${payableId}`;

            return (
              <tr key={payableId}>
                <td style={{ fontWeight: '500' }}>{formatDate(item.due_date)}</td>
                <td style={{ fontWeight: '600', color: '#fff' }}>{cpName}</td>
                <td style={{ color: '#9ca3af' }}>{item.description || '-'}</td>
                <td style={{ fontWeight: '700', color: '#f87171' }}>
                  {formatCurrency(item.amount)}
                </td>
                <td>
                  <span style={{ color: item.urgency >= 4 ? '#ef4444' : '#9ca3af', fontWeight: '600' }}>
                    {item.urgency ? `${item.urgency}/5` : '-'}
                  </span>
                </td>
                <td>
                  <span style={{ color: item.penalty_risk >= 4 ? '#ef4444' : '#9ca3af', fontWeight: '600' }}>
                    {item.penalty_risk ? `${item.penalty_risk}/5` : '-'}
                  </span>
                </td>
                <td>
                  <span style={{ color: item.flexibility >= 4 ? '#10b981' : '#9ca3af', fontWeight: '600' }}>
                    {item.flexibility ? `${item.flexibility}/5` : '-'}
                  </span>
                </td>
                <td>
                  {recAction ? <ActionBadge action={recAction} /> : <span style={{ color: '#6b7280' }}>Pending</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
