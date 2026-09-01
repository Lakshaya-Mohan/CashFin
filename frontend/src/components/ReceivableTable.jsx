import React from 'react';
import { formatCurrency, formatDate } from '../utils/formatters';

export const ReceivableTable = ({ receivables = [] }) => {
  if (!receivables || receivables.length === 0) {
    return <div style={{ color: '#9ca3af', padding: '1.5rem', textAlign: 'center' }}>No expected receivables found</div>;
  }

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>Expected Date</th>
            <th>Customer / Debtor</th>
            <th>Description</th>
            <th>Face Amount</th>
            <th>Confidence</th>
            <th>Adjusted Value</th>
          </tr>
        </thead>
        <tbody>
          {receivables.map((r) => {
            const conf = parseFloat(r.confidence || 1.0);
            const rawAmt = parseFloat(r.amount);
            const adjAmt = rawAmt * conf;

            return (
              <tr key={r.id}>
                <td style={{ fontWeight: '500' }}>{formatDate(r.expected_date)}</td>
                <td style={{ fontWeight: '600', color: '#fff' }}>
                  {r.customer_name || r.description || `Receivable #${r.id}`}
                </td>
                <td style={{ color: '#9ca3af' }}>{r.description || '-'}</td>
                <td style={{ fontWeight: '700', color: '#34d399' }}>
                  {formatCurrency(rawAmt)}
                </td>
                <td>
                  <span style={{
                    padding: '0.2rem 0.5rem',
                    background: conf >= 0.8 ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                    color: conf >= 0.8 ? '#10b981' : '#f59e0b',
                    borderRadius: '4px',
                    fontSize: '0.8rem',
                    fontWeight: '600'
                  }}>
                    {(conf * 100).toFixed(0)}%
                  </span>
                </td>
                <td style={{ fontWeight: '600', color: '#6ee7b7' }}>
                  {formatCurrency(adjAmt)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
