import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { formatCurrency, formatDate } from '../utils/formatters';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div style={{
        background: '#0d131f',
        border: '1px solid #1f2d42',
        padding: '0.75rem 1rem',
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.5)'
      }}>
        <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginBottom: '0.25rem' }}>
          {formatDate(label)}
        </div>
        <div style={{ fontSize: '1rem', fontWeight: '700', color: '#38bdf8' }}>
          Balance: {formatCurrency(data.balance)}
        </div>
        {data.eventCount > 0 && (
          <div style={{ fontSize: '0.75rem', color: '#e5e7eb', marginTop: '0.35rem' }}>
            {data.eventCount} event(s) on this date
          </div>
        )}
        {data.hasPredicted && (
          <div style={{ fontSize: '0.7rem', color: '#f59e0b', marginTop: '0.15rem' }}>
            Includes AI Forecasted Flow
          </div>
        )}
      </div>
    );
  }
  return null;
};

export const CashFlowChart = ({ projection }) => {
  if (!projection || !projection.projected_balances) {
    return <div style={{ color: '#9ca3af', padding: '2rem', textAlign: 'center' }}>No projection data available</div>;
  }

  // Transform projected_balances dict into array for Recharts
  const eventsByDate = {};
  if (projection.events) {
    projection.events.forEach((e) => {
      if (!eventsByDate[e.date]) eventsByDate[e.date] = [];
      eventsByDate[e.date].push(e);
    });
  }

  const chartData = Object.entries(projection.projected_balances).map(([d, bal]) => {
    const dayEvents = eventsByDate[d] || [];
    const hasPredicted = dayEvents.some((ev) => ev.is_predicted);
    return {
      date: d,
      balance: parseFloat(bal),
      buffer: parseFloat(projection.minimum_cash_buffer || 0),
      eventCount: dayEvents.length,
      hasPredicted,
    };
  });

  return (
    <div style={{ width: '100%', height: '320px' }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 10, right: 20, left: 20, bottom: 0 }}>
          <defs>
            <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
            </linearGradient>
          </defs>
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
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            y={parseFloat(projection.minimum_cash_buffer || 0)}
            stroke="#ef4444"
            strokeDasharray="4 4"
            label={{ value: 'Min Buffer Floor', fill: '#ef4444', fontSize: 11, position: 'insideTopRight' }}
          />
          <Area
            type="monotone"
            dataKey="balance"
            stroke="#38bdf8"
            strokeWidth={2.5}
            fillOpacity={1}
            fill="url(#balanceGradient)"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
};
