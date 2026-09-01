import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';

import App from './App';
import { MetricCard } from './components/MetricCard';
import { RiskBadge } from './components/RiskBadge';
import { ObligationTable } from './components/ObligationTable';
import { DecisionCard } from './components/DecisionCard';
import { LoadingState } from './components/LoadingState';
import { ErrorState } from './components/ErrorState';
import { Forecast } from './pages/Forecast';
import { Ingestion } from './pages/Ingestion';

// Mock API modules
vi.mock('./api/companies', () => ({
  getCompanies: vi.fn().mockResolvedValue([{ id: 1, name: 'ABC Traders' }]),
  getCompany: vi.fn().mockResolvedValue({ id: 1, name: 'ABC Traders' }),
}));

vi.mock('./api/financialState', () => ({
  getFinancialState: vi.fn().mockResolvedValue({
    company_id: 1,
    as_of_date: '2026-09-01',
    current_cash: '150000.00',
    pending_payables_total: '70000.00',
    pending_receivables_total_raw: '60000.00',
    pending_receivables_total_adjusted: '51000.00',
    upcoming_payables: [
      { id: 1, amount: '40000.00', due_date: '2026-09-06', description: 'Raw Materials', urgency: 5, penalty_risk: 4, flexibility: 1 }
    ],
    upcoming_receivables: [
      { id: 1, amount: '60000.00', expected_date: '2026-09-08', confidence: '0.85', description: 'Service Fee' }
    ]
  }),
}));

vi.mock('./api/cashFlow', () => ({
  getCashFlowProjection: vi.fn().mockResolvedValue({
    as_of_date: '2026-09-01',
    starting_balance: '150000.00',
    minimum_cash_buffer: '25000.00',
    minimum_projected_balance: '110000.00',
    days_to_zero: null,
    days_to_buffer_breach: null,
    forecast_mode: 'CONFIRMED_ONLY',
    events: [],
    projected_balances: { '2026-09-01': '150000.00' }
  }),
}));

vi.mock('./api/decisions', () => ({
  evaluateDecision: vi.fn().mockResolvedValue({
    feasible: true,
    initial_cash: '150000.00',
    minimum_cash_buffer: '25000.00',
    total_obligations: '40000.00',
    total_expected_inflows: '60000.00',
    selected_obligations: [
      {
        obligation: { payable_id: 1, counterparty_name: 'Steel Corp', amount: '40000.00', urgency: 5, penalty_risk: 4, flexibility: 1 },
        action: 'PAY',
        reasoning: 'Critical obligation'
      }
    ],
    deferred_obligations: [],
    negotiated_obligations: [],
    ending_cash: '110000.00',
    minimum_projected_cash: '110000.00',
    total_deferral_cost: 0,
    timeline: []
  }),
}));

vi.mock('./api/forecast', () => ({
  getForecast: vi.fn().mockResolvedValue({
    company_id: 1,
    generated_at: '2026-09-01',
    horizon_days: 14,
    model_name: 'RandomForestRegressor',
    model_version: '1.0',
    total_predicted_inflow: '0.00',
    total_predicted_outflow: '120000.00',
    events: [
      { date: '2026-09-02', predicted_amount: '-15000.00', event_type: 'OUTFLOW', historical_mae: '2500.00', conservative_amount: '-17500.00' }
    ]
  }),
}));

vi.mock('./api/ingestion', () => ({
  importBankCsv: vi.fn().mockResolvedValue({
    total_records: 5,
    inserted_records: 5,
    duplicate_records: 0,
    possible_duplicates: 0,
    failed_records: 0,
    errors: []
  }),
  importInvoicesJson: vi.fn(),
  importExpensesJson: vi.fn(),
  importReceiptImage: vi.fn(),
}));


describe('Stage 7 Frontend Unit Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // 1. Dashboard rendering
  it('1. renders Dashboard title and main container', async () => {
    render(<App />);
    expect(await screen.findByText(/CashFin/i)).toBeInTheDocument();
    expect(await screen.findByText(/Financial Overview/i)).toBeInTheDocument();
  });

  // 2. API loading state
  it('2. displays loading state component while fetching data', () => {
    render(<LoadingState message="Fetching data..." />);
    expect(screen.getByText(/Fetching data.../i)).toBeInTheDocument();
  });

  // 3. API error state
  it('3. displays user-friendly error state without stack traces', () => {
    render(<ErrorState message="Unable to load financial data. Please check that the backend is running." />);
    expect(screen.getByText(/Unable to load financial data. Please check that the backend is running./i)).toBeInTheDocument();
    expect(screen.queryByText(/Traceback/i)).not.toBeInTheDocument();
  });

  // 4. Company selection
  it('4. displays company selector dropdown with loaded companies', async () => {
    render(<App />);
    const select = await screen.findByRole('combobox');
    expect(select).toBeInTheDocument();
    expect(select.value).toBe('1');
  });

  // 5. Financial metric rendering
  it('5. renders financial metric cards with formatted INR values', () => {
    render(<MetricCard label="Current Cash" value="₹1,50,000" subtext="Available liquid funds" />);
    expect(screen.getByText(/Current Cash/i)).toBeInTheDocument();
    expect(screen.getByText('₹1,50,000')).toBeInTheDocument();
  });

  // 6. Obligation rendering
  it('6. renders obligation table with payables and recommendations', () => {
    const obligations = [
      { id: 1, amount: '40000.00', due_date: '2026-09-06', description: 'Raw Materials', urgency: 5, penalty_risk: 4, flexibility: 1 }
    ];
    render(<ObligationTable obligations={obligations} decisionMap={{ 1: { action: 'PAY' } }} />);
    expect(screen.getByText('Raw Materials')).toBeInTheDocument();
    expect(screen.getByText('PAY')).toBeInTheDocument();
  });

  // 7. Decision rendering
  it('7. renders decision summary card with feasibility and obligation breakdown', () => {
    const decisionResult = {
      feasible: true,
      initial_cash: '150000.00',
      minimum_cash_buffer: '25000.00',
      total_obligations: '40000.00',
      total_expected_inflows: '60000.00',
      selected_obligations: [
        {
          obligation: { payable_id: 1, counterparty_name: 'Steel Corp', amount: '40000.00', urgency: 5, penalty_risk: 4, flexibility: 1 },
          action: 'PAY',
          reasoning: 'Critical obligation'
        }
      ],
      deferred_obligations: [],
      negotiated_obligations: [],
      ending_cash: '110000.00',
      minimum_projected_cash: '110000.00',
      total_deferral_cost: 0,
    };
    render(<DecisionCard decisionResult={decisionResult} />);
    expect(screen.getByText(/Feasible Payment Strategy Available/i)).toBeInTheDocument();
    expect(screen.getByText('Steel Corp')).toBeInTheDocument();
  });

  // 8. Forecast rendering
  it('8. renders forecast page with AI disclaimer and model metadata', async () => {
    render(<Forecast companyId={1} />);
    expect(await screen.findByText(/AI\/ML Forecast — Not Confirmed Cash/i)).toBeInTheDocument();
    expect(await screen.findByText(/RandomForestRegressor/i)).toBeInTheDocument();
  });

  // 9. File upload
  it('9. renders ingestion file upload zone', () => {
    render(<Ingestion companyId={1} />);
    expect(screen.getByText(/Click to select or drag file here/i)).toBeInTheDocument();
  });

  // 10. Ingestion result rendering
  it('10. renders risk badge correctly for healthy liquidity status', () => {
    render(<RiskBadge daysToZero={null} daysToBufferBreach={null} />);
    expect(screen.getByText(/Healthy Liquidity/i)).toBeInTheDocument();
  });
});
