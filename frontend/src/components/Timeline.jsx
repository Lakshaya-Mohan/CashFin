import React from 'react';
import { formatCurrency, formatDate } from '../utils/formatters';

export const Timeline = ({ timeline = [] }) => {
  if (!timeline || timeline.length === 0) {
    return <div style={{ color: '#9ca3af', padding: '1.5rem', textAlign: 'center' }}>No simulation timeline available</div>;
  }

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Event Description</th>
            <th>Type</th>
            <th>Amount</th>
            <th>Cash Before</th>
            <th>Cash After</th>
          </tr>
        </thead>
        <tbody>
          {timeline.map((entry, idx) => {
            const isOutflow = entry.event_type === 'OUTFLOW';
            return (
              <tr key={idx}>
                <td style={{ fontWeight: '500' }}>{formatDate(entry.event_date)}</td>
                <td style={{ color: '#fff', fontWeight: '500' }}>{entry.description}</td>
                <td>
                  <span className={`badge ${isOutflow ? 'badge-critical' : 'badge-healthy'}`}>
                    {entry.event_type}
                  </span>
                </td>
                <td style={{ fontWeight: '700', color: isOutflow ? '#f87171' : '#34d399' }}>
                  {isOutflow ? '-' : '+'}{formatCurrency(Math.abs(entry.amount))}
                </td>
                <td style={{ color: '#9ca3af' }}>{formatCurrency(entry.cash_before)}</td>
                <td style={{ fontWeight: '600', color: entry.cash_after < 0 ? '#ef4444' : '#fff' }}>
                  {formatCurrency(entry.cash_after)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
