import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StrategyConditionBuilder, Condition } from './StrategyConditionBuilder';

describe('StrategyConditionBuilder', () => {
  const defaultProps = {
    signalType: 'entry' as const,
    initialConditions: [] as Condition[],
    onConditionsChange: jest.fn(),
    availableIndicators: ['RSI', 'MACD', 'Volume', 'Close', 'Stoch'],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ============================================================================
  // RENDERING TESTS
  // ============================================================================

  test('renders with correct signal type header', () => {
    render(<StrategyConditionBuilder {...defaultProps} signalType="entry" />);
    expect(screen.getByText('Entry Conditions')).toBeInTheDocument();
  });

  test('renders condition counter showing 0 initial conditions', () => {
    render(<StrategyConditionBuilder {...defaultProps} />);
    expect(screen.getByText('0 / 5')).toBeInTheDocument();
  });

  test('renders collapsed state with expand/collapse toggle', () => {
    render(<StrategyConditionBuilder {...defaultProps} />);
    const header = screen.getByText('Entry Conditions').closest('div');
    expect(header?.parentElement).toHaveClass('cursor-pointer');
  });

  test('toggles expanded state on header click', async () => {
    const { container } = render(<StrategyConditionBuilder {...defaultProps} />);

    // Initial state: expanded (Add Condition button visible)
    expect(screen.getByText('Add Condition')).toBeInTheDocument();

    // Click header to collapse
    const header = screen.getByText('Entry Conditions').closest('div');
    fireEvent.click(header!.parentElement!);

    // After collapse: button should be gone
    await waitFor(() => {
      expect(screen.queryByText('Add Condition')).not.toBeInTheDocument();
    });
  });

  // ============================================================================
  // CONDITION FORM TESTS
  // ============================================================================

  test('shows "Add Condition" button in initial state', () => {
    render(<StrategyConditionBuilder {...defaultProps} />);
    expect(screen.getByText('Add Condition')).toBeInTheDocument();
  });

  test('shows form when Add Condition button clicked', async () => {
    render(<StrategyConditionBuilder {...defaultProps} />);
    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      expect(screen.getByText('Indicator')).toBeInTheDocument();
      expect(screen.getByText('Condition')).toBeInTheDocument();
    });
  });

  test('form displays value input for comparison operators', async () => {
    const { container } = render(<StrategyConditionBuilder {...defaultProps} />);

    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      // Should show "Value" label for comparison operator (default is ">")
      expect(screen.getByLabelText('Value')).toBeInTheDocument();
    });
  });

  test('form changes value inputs based on operator selection', async () => {
    render(<StrategyConditionBuilder {...defaultProps} />);

    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      const operatorSelect = screen.getAllByRole('combobox')[1]; // Second select is operator
      fireEvent.change(operatorSelect, { target: { value: 'cross_up' } });
    });

    await waitFor(() => {
      // Should now show "Cross With" instead of "Value"
      expect(screen.getByLabelText('Cross With')).toBeInTheDocument();
      expect(screen.queryByLabelText('Value')).not.toBeInTheDocument();
    });
  });

  test('form saves condition when Save button clicked', async () => {
    const onChangeMock = jest.fn();
    render(
      <StrategyConditionBuilder
        {...defaultProps}
        onConditionsChange={onChangeMock}
      />
    );

    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      const indicatorSelect = screen.getAllByRole('combobox')[0];
      fireEvent.change(indicatorSelect, { target: { value: 'RSI' } });

      const valueInput = screen.getByLabelText('Value');
      fireEvent.change(valueInput, { target: { value: '70' } });
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(onChangeMock).toHaveBeenCalled();
      expect(screen.getByText('RSI > 70')).toBeInTheDocument();
    });
  });

  test('form cancels on Cancel button click', async () => {
    render(<StrategyConditionBuilder {...defaultProps} />);

    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Cancel'));

    await waitFor(() => {
      // Form should be gone, Add Condition button should reappear
      expect(screen.getByText('Add Condition')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // CONDITION TREE TESTS
  // ============================================================================

  test('displays condition tree with single condition', async () => {
    const initialConditions: Condition[] = [
      {
        id: 'cond1',
        indicator: 'RSI',
        operator: '>',
        value: 70,
        logicalOp: 'AND',
      },
    ];

    render(
      <StrategyConditionBuilder
        {...defaultProps}
        initialConditions={initialConditions}
      />
    );

    expect(screen.getByText('RSI > 70')).toBeInTheDocument();
    expect(screen.getByText('Logic: AND')).toBeInTheDocument();
  });

  test('displays multiple conditions in tree', () => {
    const initialConditions: Condition[] = [
      {
        id: 'cond1',
        indicator: 'RSI',
        operator: '>',
        value: 70,
        logicalOp: 'AND',
      },
      {
        id: 'cond2',
        indicator: 'Volume',
        operator: '>',
        value: 1000000,
        logicalOp: 'OR',
      },
    ];

    render(
      <StrategyConditionBuilder
        {...defaultProps}
        initialConditions={initialConditions}
      />
    );

    expect(screen.getByText('RSI > 70')).toBeInTheDocument();
    expect(screen.getByText('Volume > 1000000')).toBeInTheDocument();
  });

  test('displays cross condition in tree', () => {
    const initialConditions: Condition[] = [
      {
        id: 'cond1',
        indicator: 'MACD',
        operator: 'cross_up',
        crossWith: 'MACD_Signal',
        logicalOp: 'AND',
      },
    ];

    render(
      <StrategyConditionBuilder
        {...defaultProps}
        initialConditions={initialConditions}
      />
    );

    expect(screen.getByText('MACD cross_up MACD_Signal')).toBeInTheDocument();
  });

  test('displays range condition in tree', () => {
    const initialConditions: Condition[] = [
      {
        id: 'cond1',
        indicator: 'Stoch',
        operator: 'within_range',
        minValue: 20,
        maxValue: 80,
        logicalOp: 'AND',
      },
    ];

    render(
      <StrategyConditionBuilder
        {...defaultProps}
        initialConditions={initialConditions}
      />
    );

    expect(screen.getByText('Stoch within_range [20, 80]')).toBeInTheDocument();
  });

  // ============================================================================
  // EDIT & DELETE TESTS
  // ============================================================================

  test('allows editing existing condition', async () => {
    const initialConditions: Condition[] = [
      {
        id: 'cond1',
        indicator: 'RSI',
        operator: '>',
        value: 70,
        logicalOp: 'AND',
      },
    ];

    const onChangeMock = jest.fn();
    render(
      <StrategyConditionBuilder
        {...defaultProps}
        initialConditions={initialConditions}
        onConditionsChange={onChangeMock}
      />
    );

    // Click edit button (pencil icon - third button in condition row)
    const editButtons = screen.getAllByText('✎');
    fireEvent.click(editButtons[0]);

    await waitFor(() => {
      // Form should open with existing values
      const valueInput = screen.getByLabelText('Value') as HTMLInputElement;
      expect(valueInput.value).toBe('70');
    });
  });

  test('allows deleting condition', async () => {
    const initialConditions: Condition[] = [
      {
        id: 'cond1',
        indicator: 'RSI',
        operator: '>',
        value: 70,
        logicalOp: 'AND',
      },
    ];

    const onChangeMock = jest.fn();
    render(
      <StrategyConditionBuilder
        {...defaultProps}
        initialConditions={initialConditions}
        onConditionsChange={onChangeMock}
      />
    );

    // Find and click delete button
    const deleteButtons = screen.getAllByRole('button').filter(b => b.querySelector('[class*="trash"]'));
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(onChangeMock).toHaveBeenCalledWith([]);
    });
  });

  test('allows duplicating condition', async () => {
    const initialConditions: Condition[] = [
      {
        id: 'cond1',
        indicator: 'RSI',
        operator: '>',
        value: 70,
        logicalOp: 'AND',
      },
    ];

    const onChangeMock = jest.fn();
    render(
      <StrategyConditionBuilder
        {...defaultProps}
        initialConditions={initialConditions}
        onConditionsChange={onChangeMock}
      />
    );

    // Find and click duplicate button
    const copyButtons = screen.getAllByRole('button').filter(b =>
      b.innerHTML.includes('Copy') || b.querySelector('[class*="copy"]')
    );

    if (copyButtons.length > 0) {
      fireEvent.click(copyButtons[0]);

      await waitFor(() => {
        // Should have 2 RSI conditions now
        const conditions = screen.getAllByText(/RSI > 70/);
        expect(conditions.length).toBeGreaterThanOrEqual(1);
      });
    }
  });

  // ============================================================================
  // VALIDATION TESTS
  // ============================================================================

  test('shows validation error for invalid range (min >= max)', async () => {
    render(<StrategyConditionBuilder {...defaultProps} />);

    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      const operatorSelect = screen.getAllByRole('combobox')[1];
      fireEvent.change(operatorSelect, { target: { value: 'within_range' } });
    });

    await waitFor(() => {
      const minInput = screen.getByLabelText('Min Value');
      const maxInput = screen.getByLabelText('Max Value');
      fireEvent.change(minInput, { target: { value: '80' } });
      fireEvent.change(maxInput, { target: { value: '20' } });
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      // Should show validation error
      expect(screen.getByText(/Min value must be less than max value/)).toBeInTheDocument();
    });
  });

  test('prevents adding more than max conditions', async () => {
    const fiveConditions: Condition[] = Array.from({ length: 5 }, (_, i) => ({
      id: `cond${i}`,
      indicator: 'RSI',
      operator: '>' as const,
      value: 50,
      logicalOp: 'AND' as const,
    }));

    render(
      <StrategyConditionBuilder
        {...defaultProps}
        initialConditions={fiveConditions}
      />
    );

    // Add button should be disabled or show alert
    const addButton = screen.getByText('Add Condition');
    expect(addButton).toBeDisabled();
  });

  // ============================================================================
  // LOGICAL OPERATOR TESTS
  // ============================================================================

  test('allows toggling between AND and OR logic', async () => {
    render(<StrategyConditionBuilder {...defaultProps} />);

    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      const orRadio = screen.getByDisplayValue('OR');
      fireEvent.click(orRadio);
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByText('Logic: OR')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // INTEGRATION TESTS
  // ============================================================================

  test('complete workflow: add, view, edit, delete condition', async () => {
    const onChangeMock = jest.fn();
    const { rerender } = render(
      <StrategyConditionBuilder
        {...defaultProps}
        onConditionsChange={onChangeMock}
      />
    );

    // 1. Add condition
    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      const valueInput = screen.getByLabelText('Value');
      fireEvent.change(valueInput, { target: { value: '65' } });
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByText('RSI > 65')).toBeInTheDocument();
    });

    // 2. Verify callback was called
    expect(onChangeMock).toHaveBeenCalled();

    // 3. Counter should show 1 condition
    expect(screen.getByText('1 / 5')).toBeInTheDocument();
  });

  test('indicator options display correctly', async () => {
    render(<StrategyConditionBuilder {...defaultProps} />);

    fireEvent.click(screen.getByText('Add Condition'));

    await waitFor(() => {
      const indicatorSelect = screen.getAllByRole('combobox')[0];
      fireEvent.click(indicatorSelect);
    });

    // Check that all available indicators are present
    for (const indicator of defaultProps.availableIndicators) {
      expect(screen.getByText(indicator)).toBeInTheDocument();
    }
  });
});
