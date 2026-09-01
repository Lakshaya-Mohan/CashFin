import React from 'react';
import { CheckCircle2, AlertTriangle, AlertOctagon } from 'lucide-react';

export const RiskBadge = ({ daysToZero, daysToBufferBreach }) => {
  if (daysToZero !== null && daysToZero !== undefined) {
    return (
      <div className="badge badge-critical" title="Cash projected to breach zero">
        <AlertOctagon size={14} />
        <span>Critical Risk (Zero Cash in {daysToZero}d)</span>
      </div>
    );
  }

  if (daysToBufferBreach !== null && daysToBufferBreach !== undefined) {
    return (
      <div className="badge badge-warning" title="Cash projected to breach minimum buffer">
        <AlertTriangle size={14} />
        <span>Warning (Buffer Breach in {daysToBufferBreach}d)</span>
      </div>
    );
  }

  return (
    <div className="badge badge-healthy" title="Cash projected to remain above buffer">
      <CheckCircle2 size={14} />
      <span>Healthy Liquidity</span>
    </div>
  );
};
