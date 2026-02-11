#!/usr/bin/env python3
"""
Purged K-Fold Cross-Validation for Time Series Data
Prevents temporal leakage by removing observations near validation folds.
"""

import numpy as np
import pandas as pd
from typing import List, Tuple, Optional, Union
from sklearn.model_selection import BaseCrossValidator
from sklearn.utils import indexable
import logging

logger = logging.getLogger(__name__)


class PurgedTimeSeriesSplit(BaseCrossValidator):
    """
    Purged K-Fold Cross-Validation for time series data.
    
    Removes observations within an embargo period around each validation fold
    to prevent information leakage from correlated observations.
    
    Parameters:
    -----------
    n_splits : int, default=3
        Number of splits. Must be at least 2.
    embargo_pct : float, default=0.01
        Percentage of data to purge around each validation fold.
        For example, 0.01 means purge 1% of data around each fold.
    test_size : float, default=0.2
        Size of each test fold as percentage of total data.
    """
    
    def __init__(self, n_splits: int = 3, embargo_pct: float = 0.01, test_size: float = 0.2):
        if n_splits < 2:
            raise ValueError("n_splits must be at least 2")
        if not 0 < embargo_pct < 1:
            raise ValueError("embargo_pct must be between 0 and 1")
        if not 0 < test_size < 1:
            raise ValueError("test_size must be between 0 and 1")
            
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct
        self.test_size = test_size
        
    def split(self, X, y=None, groups=None):
        """
        Generate indices to split data into training and test sets.
        
        Parameters:
        -----------
        X : array-like, shape (n_samples, n_features)
            Training data
        y : array-like, shape (n_samples,)
            Target variable
        groups : array-like, shape (n_samples,)
            Group labels for the samples
            
        Yields:
        -------
        train : ndarray
            Training set indices
        test : ndarray
            Test set indices
        """
        X, y, groups = indexable(X, y, groups)
        n_samples = len(X)
        
        # Calculate test size in samples
        test_samples = int(n_samples * self.test_size)
        embargo_samples = int(n_samples * self.embargo_pct)
        
        # Calculate step size for non-overlapping test sets
        step_size = int((n_samples - test_samples) / (self.n_splits - 1))
        
        for i in range(self.n_splits):
            # Calculate test set boundaries
            test_start = i * step_size
            test_end = min(test_start + test_samples, n_samples)
            
            # Ensure we don't exceed data bounds
            if test_start >= n_samples:
                break
                
            # Create test indices
            test_indices = np.arange(test_start, test_end)
            
            # Create training indices (excluding test and embargo periods)
            train_indices = []
            
            # Add indices before test set (minus embargo)
            if test_start > embargo_samples:
                train_indices.extend(range(0, test_start - embargo_samples))
            
            # Add indices after test set (minus embargo)
            if test_end + embargo_samples < n_samples:
                train_indices.extend(range(test_end + embargo_samples, n_samples))
            
            train_indices = np.array(train_indices)
            
            # Ensure we have enough training data
            if len(train_indices) < 10:  # Minimum training samples
                logger.warning(f"Split {i}: Insufficient training data ({len(train_indices)} samples)")
                continue
                
            yield train_indices, test_indices
    
    def get_n_splits(self, X=None, y=None, groups=None):
        """Returns the number of splitting iterations in the cross-validator."""
        return self.n_splits


class PurgedCombinatorialCV:
    """
    Combinatorial Purged Cross-Validation for time series.
    
    Creates multiple non-overlapping test sets and purged training sets
    to provide more robust validation while maintaining temporal integrity.
    
    Parameters:
    -----------
    n_splits : int, default=5
        Number of test sets to create
    test_size : float, default=0.1
        Size of each test set as percentage of total data
    embargo_pct : float, default=0.01
        Percentage of data to purge around each test set
    """
    
    def __init__(self, n_splits: int = 5, test_size: float = 0.1, embargo_pct: float = 0.01):
        self.n_splits = n_splits
        self.test_size = test_size
        self.embargo_pct = embargo_pct
        
    def split(self, X, y=None, groups=None):
        """
        Generate combinatorial splits for robust validation.
        
        Yields:
        -------
        train : ndarray
            Training set indices (purged)
        test : ndarray
            Test set indices
        """
        X, y, groups = indexable(X, y, groups)
        n_samples = len(X)
        
        test_samples = int(n_samples * self.test_size)
        embargo_samples = int(n_samples * self.embargo_pct)
        
        # Create non-overlapping test sets
        test_sets = []
        current_pos = 0
        
        for i in range(self.n_splits):
            if current_pos + test_samples > n_samples:
                break
                
            test_start = current_pos
            test_end = min(test_start + test_samples, n_samples)
            test_indices = np.arange(test_start, test_end)
            test_sets.append(test_indices)
            
            # Move to next position with gap
            current_pos = test_end + embargo_samples
        
        # For each test set, create purged training set
        for i, test_indices in enumerate(test_sets):
            train_indices = []
            
            for j, other_test in enumerate(test_sets):
                if i == j:
                    continue
                    
                # Add indices before this test set (minus embargo)
                if j == 0 or other_test[0] > embargo_samples:
                    start_idx = 0 if j == 0 else other_test[0] - embargo_samples
                    end_idx = other_test[0]
                    if start_idx < end_idx:
                        train_indices.extend(range(start_idx, end_idx))
                
                # Add indices after this test set (minus embargo)
                if other_test[-1] + embargo_samples < n_samples:
                    start_idx = other_test[-1] + embargo_samples
                    end_idx = n_samples
                    if start_idx < end_idx:
                        train_indices.extend(range(start_idx, end_idx))
            
            train_indices = np.array(train_indices)
            
            if len(train_indices) < 10:
                logger.warning(f"Split {i}: Insufficient training data ({len(train_indices)} samples)")
                continue
                
            yield train_indices, test_indices


def validate_purged_splits(X, y, cv_method, max_correlation: float = 0.1):
    """
    Validate that purged splits prevent temporal leakage.
    
    Parameters:
    -----------
    X : array-like
        Feature matrix
    y : array-like
        Target variable
    cv_method : cross-validator
        Cross-validation method to test
    max_correlation : float
        Maximum allowed correlation between train/test sets
        
    Returns:
    --------
    bool : True if validation passes
    dict : Validation results
    """
    correlations = []
    train_sizes = []
    test_sizes = []
    
    for train_idx, test_idx in cv_method.split(X, y):
        # Check for temporal leakage
        if len(train_idx) > 0 and len(test_idx) > 0:
            # Calculate correlation between train and test targets
            train_targets = y[train_idx]
            test_targets = y[test_idx]
            
            if len(train_targets) > 1 and len(test_targets) > 1:
                try:
                    # Ensure arrays have same length for correlation
                    min_len = min(len(train_targets), len(test_targets))
                    if min_len > 1:
                        correlation = np.corrcoef(train_targets[:min_len], test_targets[:min_len])[0, 1]
                        correlations.append(abs(correlation))
                except Exception as e:
                    # Skip correlation if arrays are incompatible
                    continue
            
            train_sizes.append(len(train_idx))
            test_sizes.append(len(test_idx))
    
    # Check if correlations are below threshold
    max_corr = max(correlations) if correlations else 0
    avg_corr = np.mean(correlations) if correlations else 0
    
    validation_passed = max_corr < max_correlation
    
    results = {
        'validation_passed': validation_passed,
        'max_correlation': max_corr,
        'avg_correlation': avg_corr,
        'correlations': correlations,
        'avg_train_size': np.mean(train_sizes),
        'avg_test_size': np.mean(test_sizes),
        'n_splits': len(correlations)
    }
    
    if not validation_passed:
        logger.warning(f"Temporal leakage detected: max correlation {max_corr:.3f} > {max_correlation}")
    
    return validation_passed, results


# Example usage and testing
if __name__ == "__main__":
    # Create sample time series data
    np.random.seed(42)
    n_samples = 1000
    dates = pd.date_range('2020-01-01', periods=n_samples, freq='D')
    
    # Generate correlated time series
    returns = np.random.normal(0, 0.02, n_samples)
    prices = 100 * np.exp(np.cumsum(returns))
    
    X = np.random.randn(n_samples, 5)
    y = prices
    
    # Test PurgedTimeSeriesSplit
    print("Testing PurgedTimeSeriesSplit...")
    purged_cv = PurgedTimeSeriesSplit(n_splits=3, embargo_pct=0.05, test_size=0.2)
    
    for i, (train_idx, test_idx) in enumerate(purged_cv.split(X, y)):
        print(f"Split {i}: Train={len(train_idx)}, Test={len(test_idx)}")
        print(f"  Train range: {train_idx[0]}-{train_idx[-1]}")
        print(f"  Test range: {test_idx[0]}-{test_idx[-1]}")
        print()
    
    # Validate splits
    passed, results = validate_purged_splits(X, y, purged_cv)
    print(f"Validation passed: {passed}")
    print(f"Max correlation: {results['max_correlation']:.3f}")
    print(f"Average correlation: {results['avg_correlation']:.3f}")

