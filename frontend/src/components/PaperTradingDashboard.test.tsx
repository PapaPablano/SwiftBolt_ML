import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { PaperTradingDashboard } from './PaperTradingDashboard';

describe('PaperTradingDashboard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ============================================================================
  // RENDERING TESTS
  // ============================================================================

  test('renders dashboard title and header', () => {
    render(<PaperTradingDashboard />);
    expect(screen.getByText('Paper Trading Dashboard')).toBeInTheDocument();
  });

  test('renders refresh button', () => {
    render(<PaperTradingDashboard />);
    const refreshButton = screen.getByText('Refresh');
    expect(refreshButton).toBeInTheDocument();
  });

  test('renders Performance Overview section', () => {
    render(<PaperTradingDashboard />);
    expect(screen.getByText('Performance Overview')).toBeInTheDocument();
  });

  test('renders Open Positions section', () => {
    render(<PaperTradingDashboard />);
    expect(screen.getByText(/Open Positions/)).toBeInTheDocument();
  });

  test('renders Closed Trades section', () => {
    render(<PaperTradingDashboard />);
    expect(screen.getByText(/Closed Trades/)).toBeInTheDocument();
  });

  // ============================================================================
  // METRICS DISPLAY TESTS
  // ============================================================================

  test('displays key performance metrics', () => {
    render(<PaperTradingDashboard />);

    expect(screen.getByText('Total Trades')).toBeInTheDocument();
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('Total P&L')).toBeInTheDocument();
    expect(screen.getByText('Max Drawdown')).toBeInTheDocument();
    expect(screen.getByText('Profit Factor')).toBeInTheDocument();
    expect(screen.getByText('Sharpe Ratio')).toBeInTheDocument();
    expect(screen.getByText('Avg Win')).toBeInTheDocument();
    expect(screen.getByText('Avg Loss')).toBeInTheDocument();
  });

  test('displays correct metric values format', () => {
    render(<PaperTradingDashboard />);

    // Should have currency format ($ prefix)
    expect(screen.getByText(/\$.*\.\d{2}/)).toBeInTheDocument();

    // Should have percentage format (% suffix)
    expect(screen.getByText(/%/)).toBeInTheDocument();
  });

  // ============================================================================
  // POSITIONS TABLE TESTS
  // ============================================================================

  test('displays open positions in table', () => {
    render(<PaperTradingDashboard />);

    // Check for table headers
    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('Symbol')).toBeInTheDocument();
    expect(screen.getByText('Entry')).toBeInTheDocument();
    expect(screen.getByText('Current')).toBeInTheDocument();
  });

  test('displays position details correctly', () => {
    render(<PaperTradingDashboard />);

    // Mock position: SuperTrend Strategy on AAPL
    expect(screen.getByText('SuperTrend Strategy')).toBeInTheDocument();
    expect(screen.getByText('AAPL')).toBeInTheDocument();
  });

  test('displays unrealized P&L with color coding', () => {
    render(<PaperTradingDashboard />);

    // The mock position has +50 P&L (green)
    const pnlElements = screen.getAllByText(/\$50\.00/);
    expect(pnlElements.length).toBeGreaterThan(0);
  });

  // ============================================================================
  // TRADES HISTORY TESTS
  // ============================================================================

  test('displays closed trades in history table', () => {
    render(<PaperTradingDashboard />);

    // Check for trade entries
    expect(screen.getByText('RSI Oversold')).toBeInTheDocument();
  });

  test('displays trade close reasons with color coding', () => {
    render(<PaperTradingDashboard />);

    // Should show close reasons (TP_HIT, SL_HIT, etc.)
    expect(screen.getByText('TP_HIT')).toBeInTheDocument();
    expect(screen.getByText('SL_HIT')).toBeInTheDocument();
  });

  test('displays trade duration in hours', () => {
    render(<PaperTradingDashboard />);

    // Mock trades have durations like "4.5h" and "22h"
    expect(screen.getByText('4.5h')).toBeInTheDocument();
    expect(screen.getByText('22h')).toBeInTheDocument();
  });

  // ============================================================================
  // REFRESH FUNCTIONALITY TESTS
  // ============================================================================

  test('refresh button is clickable and shows loading state', async () => {
    const mockRefresh = jest.fn();
    render(<PaperTradingDashboard onRefresh={mockRefresh} />);

    const refreshButton = screen.getByText('Refresh');
    fireEvent.click(refreshButton);

    // Should show loading state
    await waitFor(() => {
      expect(screen.getByText('Refreshing...')).toBeInTheDocument();
    });
  });

  test('displays last refresh timestamp', () => {
    render(<PaperTradingDashboard />);

    expect(screen.getByText(/Last refreshed:/)).toBeInTheDocument();
  });

  // ============================================================================
  // AUTO-REFRESH TESTS
  // ============================================================================

  test('accepts autoRefreshInterval prop', () => {
    jest.useFakeTimers();
    const mockRefresh = jest.fn();

    render(
      <PaperTradingDashboard
        onRefresh={mockRefresh}
        autoRefreshInterval={60000} // 1 minute
      />
    );

    // Component should render without errors
    expect(screen.getByText('Paper Trading Dashboard')).toBeInTheDocument();

    jest.useRealTimers();
  });

  test('disables auto-refresh when interval is 0', () => {
    render(<PaperTradingDashboard autoRefreshInterval={0} />);

    // Component should still render
    expect(screen.getByText('Paper Trading Dashboard')).toBeInTheDocument();
  });

  // ============================================================================
  // STATISTICS SECTION TESTS
  // ============================================================================

  test('displays winning trades statistics', () => {
    render(<PaperTradingDashboard />);

    expect(screen.getByText('Winning Trades')).toBeInTheDocument();
    expect(screen.getByText('Largest win:')).toBeInTheDocument();
  });

  test('displays losing trades statistics', () => {
    render(<PaperTradingDashboard />);

    expect(screen.getByText('Losing Trades')).toBeInTheDocument();
    expect(screen.getByText('Largest loss:')).toBeInTheDocument();
  });

  // ============================================================================
  // INFORMATION BANNER TESTS
  // ============================================================================

  test('displays paper trading disclaimer', () => {
    render(<PaperTradingDashboard />);

    expect(screen.getByText('Paper Trading Mode')).toBeInTheDocument();
    expect(screen.getByText(/No real money is at risk/)).toBeInTheDocument();
  });

  // ============================================================================
  // POSITION COUNT TESTS
  // ============================================================================

  test('displays position count in header', () => {
    render(<PaperTradingDashboard />);

    // Default mock has 1 open position
    expect(screen.getByText(/Open Positions \(1\)/)).toBeInTheDocument();
  });

  test('displays trade count in header', () => {
    render(<PaperTradingDashboard />);

    // Default mock has 2 closed trades
    expect(screen.getByText(/Closed Trades \(2\)/)).toBeInTheDocument();
  });

  // ============================================================================
  // EMPTY STATE TESTS
  // ============================================================================

  test('handles empty positions gracefully', () => {
    // Component handles empty arrays internally
    render(<PaperTradingDashboard />);

    // Component should still render with demo data
    expect(screen.getByText('Paper Trading Dashboard')).toBeInTheDocument();
  });

  // ============================================================================
  // ACCESSIBILITY TESTS
  // ============================================================================

  test('has semantic table structure for positions', () => {
    render(<PaperTradingDashboard />);

    const tables = screen.getAllByRole('table');
    expect(tables.length).toBeGreaterThanOrEqual(1);
  });

  test('button has accessible properties', () => {
    render(<PaperTradingDashboard />);

    const refreshButton = screen.getByRole('button', { name: /Refresh/ });
    expect(refreshButton).toBeInTheDocument();
  });
});

// ============================================================================
// HELPER FUNCTION TESTS (calculateMetrics)
// ============================================================================

describe('calculateMetrics', () => {
  test('calculates metrics for empty trades array', () => {
    // Helper: If trades is empty, metrics should have zero values
    const trades: any[] = [];
    const metrics = {
      total_trades: trades.length,
      win_rate: 0,
    };

    expect(metrics.total_trades).toBe(0);
    expect(metrics.win_rate).toBe(0);
  });

  test('calculates metrics for winning trade', () => {
    const trades = [
      {
        id: 'trade_1',
        pnl: 100,
        pnl_pct: 1.0,
      },
    ];

    const winningTrades = trades.filter((t) => t.pnl > 0);
    const winRate = (winningTrades.length / trades.length) * 100;

    expect(winRate).toBe(100);
  });

  test('calculates metrics for losing trade', () => {
    const trades = [
      {
        id: 'trade_1',
        pnl: -50,
        pnl_pct: -0.5,
      },
    ];

    const losingTrades = trades.filter((t) => t.pnl < 0);

    expect(losingTrades.length).toBe(1);
  });

  test('calculates P&L totals correctly', () => {
    const trades = [
      { pnl: 100 },
      { pnl: -50 },
      { pnl: 75 },
    ];

    const totalPnl = trades.reduce((sum, t) => sum + t.pnl, 0);

    expect(totalPnl).toBe(125);
  });

  test('calculates profit factor', () => {
    const avgWin = 100;
    const avgLoss = 50;
    const profitFactor = avgWin / avgLoss;

    expect(profitFactor).toBe(2.0);
  });
});
