import React from 'react';
import { AlertTriangle } from 'lucide-react';

export const ErrorState = ({ message = 'Unable to load financial data. Please check that the backend is running.', onRetry }) => {
  return (
    <div className="error-banner">
      <AlertTriangle size={20} style={{ flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: '600', marginBottom: '0.15rem' }}>Connection / API Error</div>
        <div style={{ fontSize: '0.85rem' }}>{message}</div>
      </div>
      {onRetry && (
        <button className="btn btn-secondary" onClick={onRetry} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>
          Retry
        </button>
      )}
    </div>
  );
};
