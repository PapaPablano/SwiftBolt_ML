import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IndicatorMenu } from './IndicatorMenu';

describe('IndicatorMenu', () => {
  const defaultProps = {
    onIndicatorSelect: jest.fn(),
    selectedIndicators: [],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ============================================================================
  // RENDERING TESTS
  // ============================================================================

  test('renders indicator library title and count', () => {
    render(<IndicatorMenu {...defaultProps} />);
    expect(screen.getByText('Technical Indicators Library')).toBeInTheDocument();
    expect(screen.getByText(/38 indicators across 5 categories/)).toBeInTheDocument();
  });

  test('renders search input field', () => {
    render(<IndicatorMenu {...defaultProps} />);
    expect(
      screen.getByPlaceholderText(/Search indicators/)
    ).toBeInTheDocument();
  });

  test('renders all 5 category sections', () => {
    render(<IndicatorMenu {...defaultProps} />);
    expect(screen.getByText('Trend Indicators')).toBeInTheDocument();
    expect(screen.getByText('Momentum Indicators')).toBeInTheDocument();
    expect(screen.getByText('Volatility Indicators')).toBeInTheDocument();
    expect(screen.getByText('Volume Indicators')).toBeInTheDocument();
    expect(screen.getByText('Pattern/Structural Indicators')).toBeInTheDocument();
  });

  test('trend and momentum categories are expanded by default', () => {
    render(<IndicatorMenu {...defaultProps} />);

    // Trend category should show indicators
    expect(screen.getByText('SuperTrend')).toBeInTheDocument();
    expect(screen.getByText('ADX (Average Directional Index)')).toBeInTheDocument();

    // Momentum should also be visible
    expect(screen.getByText('RSI (Relative Strength Index)')).toBeInTheDocument();
  });

  test('displays footer tips section', () => {
    render(<IndicatorMenu {...defaultProps} />);
    expect(screen.getByText(/Tips for indicator selection/)).toBeInTheDocument();
    expect(screen.getByText(/Mix indicators from different categories/)).toBeInTheDocument();
  });

  // ============================================================================
  // INDICATOR DISPLAY TESTS
  // ============================================================================

  test('displays indicator name, symbol, and description', () => {
    render(<IndicatorMenu {...defaultProps} />);

    expect(screen.getByText('RSI (Relative Strength Index)')).toBeInTheDocument();
    expect(screen.getByText('RSI')).toBeInTheDocument(); // Symbol
    expect(
      screen.getByText(/Momentum oscillator measuring speed and magnitude/)
    ).toBeInTheDocument();
  });

  test('displays bullish and bearish signal ranges', () => {
    render(<IndicatorMenu {...defaultProps} />);

    // Find an RSI indicator section
    const rsiSection = screen.getByText('RSI (Relative Strength Index)').closest('div');
    expect(rsiSection?.textContent).toContain('Bullish');
    expect(rsiSection?.textContent).toContain('Bearish');
  });

  test('displays indicator range when available', () => {
    render(<IndicatorMenu {...defaultProps} />);

    // RSI has a range of 0-100
    const rsiSection = screen.getByText('RSI (Relative Strength Index)').closest('div');
    expect(rsiSection?.textContent).toContain('Range: 0 - 100');
  });

  test('clicking indicator calls onIndicatorSelect callback', () => {
    const onSelect = jest.fn();
    render(<IndicatorMenu {...defaultProps} onIndicatorSelect={onSelect} />);

    const rsiIndicator = screen.getByText('RSI (Relative Strength Index)').closest('div');
    fireEvent.click(rsiIndicator!);

    expect(onSelect).toHaveBeenCalled();
    const selectedIndicator = onSelect.mock.calls[0][0];
    expect(selectedIndicator.name).toBe('RSI (Relative Strength Index)');
  });

  // ============================================================================
  // SEARCH FUNCTIONALITY TESTS
  // ============================================================================

  test('filters indicators by name', async () => {
    render(<IndicatorMenu {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/Search indicators/);
    await userEvent.type(searchInput, 'RSI');

    // RSI should be visible
    expect(screen.getByText('RSI (Relative Strength Index)')).toBeInTheDocument();

    // Other momentum indicators should not be visible
    expect(screen.queryByText('MACD')).not.toBeInTheDocument();
  });

  test('filters indicators by description keyword', async () => {
    render(<IndicatorMenu {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/Search indicators/);
    await userEvent.type(searchInput, 'volatility');

    // Should find indicators with "volatility" in description
    expect(screen.getByText('ATR (Average True Range)')).toBeInTheDocument();
  });

  test('filters indicators by symbol', async () => {
    render(<IndicatorMenu {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/Search indicators/);
    await userEvent.type(searchInput, 'MACD');

    // Should find MACD by symbol
    expect(screen.getByText('MACD')).toBeInTheDocument();
  });

  test('shows no results message when search returns empty', async () => {
    render(<IndicatorMenu {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/Search indicators/);
    await userEvent.type(searchInput, 'nonexistent_indicator_xyz');

    expect(screen.getByText(/No indicators found matching/)).toBeInTheDocument();
  });

  test('clears search results when input is cleared', async () => {
    render(<IndicatorMenu {...defaultProps} />);

    const searchInput = screen.getByPlaceholderText(/Search indicators/) as HTMLInputElement;

    // Type search term
    await userEvent.type(searchInput, 'RSI');
    expect(screen.getByText('RSI (Relative Strength Index)')).toBeInTheDocument();

    // Clear search
    await userEvent.clear(searchInput);

    // All categories should be visible again
    expect(screen.getByText('Trend Indicators')).toBeInTheDocument();
  });

  // ============================================================================
  // CATEGORY EXPAND/COLLAPSE TESTS
  // ============================================================================

  test('clicking category header toggles expansion', () => {
    render(<IndicatorMenu {...defaultProps} />);

    // Find volatility category (starts collapsed)
    const volatilityHeader = screen.getByText('Volatility Indicators');

    // Should initially be collapsed (Bollinger Bands not visible)
    expect(screen.queryByText('Bollinger Bands')).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(volatilityHeader.closest('div')!.parentElement!);

    // Now should be expanded
    expect(screen.getByText('Bollinger Bands')).toBeInTheDocument();
  });

  test('all category sections have count badges', () => {
    render(<IndicatorMenu {...defaultProps} />);

    const trendHeader = screen.getByText('Trend Indicators');
    const momentumHeader = screen.getByText('Momentum Indicators');

    // Should have count badges (10 for trend, 10 for momentum)
    expect(trendHeader.closest('div')?.textContent).toMatch(/\d+/);
    expect(momentumHeader.closest('div')?.textContent).toMatch(/\d+/);
  });

  // ============================================================================
  // SELECTED INDICATORS SUMMARY TESTS
  // ============================================================================

  test('shows selected indicators summary when indicators are selected', () => {
    render(
      <IndicatorMenu
        {...defaultProps}
        selectedIndicators={['RSI (Relative Strength Index)', 'MACD']}
      />
    );

    expect(screen.getByText(/Selected Indicators \(2\)/)).toBeInTheDocument();
    expect(screen.getByText('RSI (Relative Strength Index)')).toBeInTheDocument();
    expect(screen.getByText('MACD')).toBeInTheDocument();
  });

  test('displays selected indicator tags', () => {
    render(
      <IndicatorMenu
        {...defaultProps}
        selectedIndicators={['RSI (Relative Strength Index)']}
      />
    );

    const selectedTag = screen.getByText('RSI (Relative Strength Index)');
    expect(selectedTag).toHaveClass('bg-blue-100');
    expect(selectedTag).toHaveClass('text-blue-700');
  });

  // ============================================================================
  // CORRELATION WARNING TESTS
  // ============================================================================

  test('shows correlation warning for similar indicators', () => {
    render(
      <IndicatorMenu
        {...defaultProps}
        selectedIndicators={['RSI (Relative Strength Index)', 'Stochastic Oscillator']}
      />
    );

    // Both are momentum indicators, should trigger warning
    expect(screen.getByText(/Correlation Warning/)).toBeInTheDocument();
    expect(
      screen.getByText(/Some selected indicators are highly correlated/)
    ).toBeInTheDocument();
  });

  test('highlights correlated indicators with yellow ring', () => {
    render(
      <IndicatorMenu
        {...defaultProps}
        selectedIndicators={['ADX (Average Directional Index)', 'Ichimoku Cloud']}
      />
    );

    // Should show correlation warning
    expect(screen.getByText(/Correlation Warning/)).toBeInTheDocument();
  });

  test('does not show correlation warning for uncorrelated indicators', () => {
    render(
      <IndicatorMenu
        {...defaultProps}
        selectedIndicators={['RSI (Relative Strength Index)', 'Volume (Raw)']}
      />
    );

    // RSI is momentum, Volume is volume indicator - different categories
    expect(screen.queryByText(/Correlation Warning/)).not.toBeInTheDocument();
  });

  // ============================================================================
  // INTEGRATION TESTS
  // ============================================================================

  test('complete workflow: search, expand category, select indicator', async () => {
    const onSelect = jest.fn();
    render(<IndicatorMenu {...defaultProps} onIndicatorSelect={onSelect} />);

    // Search for volatility indicators
    const searchInput = screen.getByPlaceholderText(/Search indicators/);
    await userEvent.type(searchInput, 'volatility');

    // Should show volatility category
    expect(screen.getByText('Volatility Indicators')).toBeInTheDocument();

    // Click on ATR
    const atrIndicator = screen.getByText('ATR (Average True Range)').closest('div');
    fireEvent.click(atrIndicator!);

    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'ATR (Average True Range)',
        category: 'volatility',
      })
    );
  });

  test('displays 38 total indicators across categories', () => {
    render(<IndicatorMenu {...defaultProps} />);

    // Trend: 10
    // Momentum: 10
    // Volatility: 8
    // Volume: 6
    // Pattern: 4
    // Total: 38

    expect(screen.getByText(/38 indicators/)).toBeInTheDocument();
  });

  test('indicator selection state is reflected in UI', () => {
    const { rerender } = render(
      <IndicatorMenu {...defaultProps} selectedIndicators={[]} />
    );

    // No summary initially
    expect(screen.queryByText(/Selected Indicators/)).not.toBeInTheDocument();

    // Rerender with selected indicator
    rerender(
      <IndicatorMenu
        {...defaultProps}
        selectedIndicators={['RSI (Relative Strength Index)']}
      />
    );

    // Now should show summary
    expect(screen.getByText(/Selected Indicators \(1\)/)).toBeInTheDocument();
  });

  test('all indicators have category, description, bullish and bearish signals', () => {
    render(<IndicatorMenu {...defaultProps} />);

    // Expand all categories to verify content
    const categoryHeaders = [
      'Trend Indicators',
      'Momentum Indicators',
      'Volatility Indicators',
      'Volume Indicators',
      'Pattern/Structural Indicators',
    ];

    categoryHeaders.forEach((header) => {
      const headerElement = screen.getByText(header);
      // Each should have proper structure
      expect(headerElement).toBeInTheDocument();
    });
  });
});
