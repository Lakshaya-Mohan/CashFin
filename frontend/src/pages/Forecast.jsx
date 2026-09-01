import React, { useEffect, useState } from 'react';
import { getForecast } from '../api/forecast';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { MetricCard } from '../components/MetricCard';
import { formatCurrency, formatDate } from '../utils/formatters';
import { TrendingUp, Cpu, ArrowUpRight, ArrowDownRight, Info } from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

export const Forecast = ({ companyId }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [horizon, setHorizon] = useState(14);

  const fetchForecast = async () => {
    if (!companyId) return;
    setLoading(true);
    setError(null);

    try {
      const res = await getForecast(companyId, { horizon_days: horizon });
      setForecast(res);
    } catch (err) {
      setError(err.message || 'Forecast unavailable: model has not been trained.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecast();
  }, [companyId, horizon]);

  const chartData = (forecast?.events || []).map((e) => {
    const amt = parseFloat(e.predicted_amount);
    return {
      date: e.date,
      inflow: amt > 0 ? amt : 0,
      outflow: amt < 0 ? Math.abs(amt) : 0,
      netFlow: amt,
    };
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div>
          <h1 className="page-title">AI Cash-Flow Forecast</h1>
          <p className="page-subtitle">Machine learning predictions derived from historical transaction patterns</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <label style={{ fontSize: '0.85rem', color: '#9ca3af' }}>Horizon:</label>
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="form-control"
            style={{ width: 'auto', padding: '0.4rem 0.8rem' }}
          >
            <option value={7}>7 Days</option>
            <option value={14}>14 Days</option>
            <option value={30}>30 Days</option>
          </select>
        </div>
      </div>

      {/* Mandatory AI/ML Disclaimer Card */}
      <div
        className="card"
        style={{
          background: 'rgba(59, 130, 246, 0.08)',
          borderColor: 'rgba(59, 130, 246, 0.3)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '1rem',
        }}
      >
        <Info size={24} style={{ color: '#3b82f6', flexShrink: 0, marginTop: '0.15rem' }} />
        <div>
          <div style={{ fontWeight: '700', color: '#60a5fa', marginBottom: '0.25rem' }}>
            AI/ML Forecast — Not Confirmed Cash
          </div>
          <div style={{ fontSize: '0.88rem', color: '#d1d5db', lineHeight: '1.4' }}>
            Forecasts estimate uncertain future cash movements based on learned behavioral patterns. Payment decisions are determined separately by the deterministic decision engine. The ML model NEVER decides payment strategy.
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingState message="Generating machine learning cash-flow forecast..." />
      ) : error ? (
        <ErrorState message={error} onRetry={fetchForecast} />
      ) : (
        <>
          {/* Model Metrics Strip */}
          <div className="grid-4">
            <MetricCard
              label="Active Model"
              value={forecast?.model_name || 'RandomForestRegressor'}
              subtext={`Version ${forecast?.model_version || '1.0'}`}
              icon={Cpu}
              accentColor="#8b5cf6"
            />
            <MetricCard
              label="Forecast Horizon"
              value={`${forecast?.horizon_days || horizon} Days`}
              subtext={`Generated as of ${formatDate(forecast?.generated_at)}`}
              icon={TrendingUp}
              accentColor="#3b82f6"
            />
            <MetricCard
              label="Predicted Inflows"
              value={formatCurrency(forecast?.total_predicted_inflow)}
              subtext="Projected incoming flow"
              icon={ArrowUpRight}
              accentColor="#10b981"
            />
            <MetricCard
              label="Predicted Outflows"
              value={formatCurrency(forecast?.total_predicted_outflow)}
              subtext="Projected outgoing flow"
              icon={ArrowDownRight}
              accentColor="#ef4444"
            />
          </div>

          {/* Predicted Flow Bar Chart */}
          <div className="card">
            <h2 className="card-title">Daily Predicted Net Cash Flow</h2>
            <div style={{ width: '100%', height: '300px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 20, left: 20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2d42" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(val) => formatDate(val).split(' ')[0] + ' ' + formatDate(val).split(' ')[1]}
                    stroke="#6b7280"
                    fontSize={12}
                  />
                  <YAxis
                    tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
                    stroke="#6b7280"
                    fontSize={12}
                  />
                  <Tooltip
                    formatter={(value) => [formatCurrency(value), 'Amount']}
                    labelFormatter={(label) => formatDate(label)}
                    contentStyle={{ background: '#0d131f', borderColor: '#1f2d42', color: '#fff' }}
                  />
                  <Bar dataKey="inflow" name="Predicted Inflow" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="outflow" name="Predicted Outflow" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Forecast Events Table */}
          <div className="card">
            <h2 className="card-title">Forecast Event Details & Uncertainty Ranges</h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Event Classification</th>
                    <th>Predicted Amount</th>
                    <th>Historical MAE Uncertainty</th>
                    <th>Conservative Estimate</th>
                  </tr>
                </thead>
                <tbody>
                  {(forecast?.events || []).map((e, idx) => {
                    const isOutflow = e.event_type === 'OUTFLOW';
                    return (
                      <tr key={idx}>
                        <td style={{ fontWeight: '500' }}>{formatDate(e.date)}</td>
                        <td>
                          <span className={`badge ${isOutflow ? 'badge-critical' : 'badge-healthy'}`}>
                            {e.event_type}
                          </span>
                        </td>
                        <td style={{ fontWeight: '700', color: isOutflow ? '#f87171' : '#34d399' }}>
                          {formatCurrency(e.predicted_amount)}
                        </td>
                        <td style={{ color: '#9ca3af' }}>
                          {e.historical_mae ? `± ${formatCurrency(e.historical_mae)}` : '-'}
                        </td>
                        <td style={{ fontWeight: '600', color: '#e5e7eb' }}>
                          {e.conservative_amount !== null ? formatCurrency(e.conservative_amount) : '-'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
