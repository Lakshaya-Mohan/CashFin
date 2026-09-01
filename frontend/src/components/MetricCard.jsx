import React from 'react';

export const MetricCard = ({ label, value, subtext, icon: Icon, accentColor = '#3b82f6' }) => {
  return (
    <div className="card metric-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span className="metric-label">{label}</span>
        {Icon && (
          <div style={{
            background: `${accentColor}18`,
            padding: '0.4rem',
            borderRadius: '6px',
            color: accentColor,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Icon size={18} />
          </div>
        )}
      </div>
      <div className="metric-value">{value}</div>
      {subtext && <div className="metric-subtext">{subtext}</div>}
    </div>
  );
};
