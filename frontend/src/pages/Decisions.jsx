import React, { useEffect, useState } from 'react';
import { evaluateDecision } from '../api/decisions';
import { DecisionCard } from '../components/DecisionCard';
import { Timeline } from '../components/Timeline';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { ShieldCheck, Sliders } from 'lucide-react';

export const Decisions = ({ companyId }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [decision, setDecision] = useState(null);

  // Form parameters
  const [buffer, setBuffer] = useState(25000);
  const [receivableMode, setReceivableMode] = useState('RAW');
  const [forecastMode, setForecastMode] = useState('CONFIRMED_ONLY');

  const fetchDecision = async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);

    try {
      const res = await evaluateDecision(companyId, {
        minimum_cash_buffer: buffer,
        receivable_mode: receivableMode,
        forecast_mode: forecastMode,
      });
      setDecision(res);
    } catch (err) {
      setError(err.message || 'Unable to evaluate payment decisions.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDecision();
  }, [companyId]);

  const handleSubmit = (e) => {
    e.preventDefault();
    fetchDecision();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div>
          <h1 className="page-title">Decision Center</h1>
          <p className="page-subtitle">Deterministic obligation payment optimization and deferral analysis</p>
        </div>
      </div>

      {/* Control Panel Card */}
      <div className="card" style={{ background: '#131b2e' }}>
        <div className="card-title" style={{ fontSize: '1rem', marginBottom: '1.25rem' }}>
          <Sliders size={18} style={{ color: '#38bdf8' }} />
          <span>Decision Engine Parameters</span>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem', alignItems: 'end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Minimum Cash Buffer (₹)</label>
            <input
              type="number"
              min="0"
              step="1000"
              value={buffer}
              onChange={(e) => setBuffer(Number(e.target.value))}
              className="form-control"
            />
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Receivable Handling Mode</label>
            <select
              value={receivableMode}
              onChange={(e) => setReceivableMode(e.target.value)}
              className="form-control"
            >
              <option value="RAW">RAW (Face Value)</option>
              <option value="CONFIDENCE_ADJUSTED">CONFIDENCE_ADJUSTED (Risk Weighted)</option>
            </select>
          </div>

          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Forecast Inclusion Mode</label>
            <select
              value={forecastMode}
              onChange={(e) => setForecastMode(e.target.value)}
              className="form-control"
            >
              <option value="CONFIRMED_ONLY">CONFIRMED_ONLY (Known Inflows/Outflows)</option>
              <option value="FORECAST_INCLUDED">FORECAST_INCLUDED (Include ML Predictions)</option>
              <option value="CONSERVATIVE">CONSERVATIVE (Uncertainty Adjusted)</option>
            </select>
          </div>

          <div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }}>
              <ShieldCheck size={18} />
              <span>Evaluate Strategy</span>
            </button>
          </div>
        </form>
      </div>

      {loading ? (
        <LoadingState message="Evaluating payment strategy via Deterministic Decision Engine..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchDecision} />
      ) : (
        <>
          {/* Decision Summary & Breakdown */}
          <DecisionCard decisionResult={decision} />

          {/* Chronological Audit Simulation Timeline */}
          <div className="card">
            <h2 className="card-title">Chronological Cash Simulation Audit Timeline</h2>
            <p style={{ fontSize: '0.85rem', color: '#9ca3af', marginBottom: '1rem' }}>
              Step-by-step cash balance audit trail for the recommended payment strategy.
            </p>
            <Timeline timeline={decision?.timeline || []} />
          </div>
        </>
      )}
    </div>
  );
};
