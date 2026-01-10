# Contributing to SwiftBolt_ML

Thank you for your interest in contributing to SwiftBolt_ML! This document provides guidelines and instructions for contributing.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for Supabase functions)
- Xcode 15+ (for iOS development)
- Supabase CLI
- Git

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/SwiftBolt_ML.git
   cd SwiftBolt_ML
   ```

2. **Set up Python environment**
   ```bash
   cd ml
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Run tests to verify setup**
   ```bash
   cd ml
   pytest tests/
   ```

---

## 📋 Code Standards

### Python

#### Style Guide
- **Formatting**: Use Black with 100 character line length
- **Imports**: Use isort for consistent import ordering
- **Type Hints**: Required for all function signatures
- **Docstrings**: Required for all public APIs (Google style)

#### Example
```python
from typing import List, Optional
import pandas as pd


def calculate_returns(
    prices: pd.DataFrame,
    period: int = 1,
    method: str = "simple"
) -> pd.DataFrame:
    """Calculate returns from price data.
    
    Args:
        prices: DataFrame with OHLC price data
        period: Number of periods for return calculation
        method: Return calculation method ('simple' or 'log')
    
    Returns:
        DataFrame with calculated returns
    
    Raises:
        ValueError: If method is not 'simple' or 'log'
    """
    if method not in ["simple", "log"]:
        raise ValueError(f"Invalid method: {method}")
    
    # Implementation here
    pass
```

#### Running Linters
```bash
# Format code
black ml/src ml/tests

# Sort imports
isort ml/src ml/tests

# Type checking
mypy ml/src

# Linting
flake8 ml/src ml/tests
```

### Swift

#### Style Guide
- Follow [Swift API Design Guidelines](https://swift.org/documentation/api-design-guidelines/)
- Use SwiftFormat for consistent formatting
- Add documentation comments for public APIs
- Use meaningful variable names

#### Example
```swift
/// Fetches real-time market data for a given symbol
/// - Parameters:
///   - symbol: Stock ticker symbol (e.g., "AAPL")
///   - timeframe: Chart timeframe (e.g., .day, .hour)
/// - Returns: Array of OHLC bars
/// - Throws: APIError if request fails
func fetchMarketData(
    symbol: String,
    timeframe: Timeframe
) async throws -> [OHLCBar] {
    // Implementation
}
```

### TypeScript (Supabase Functions)

#### Style Guide
- Use TypeScript strict mode
- Add JSDoc comments for exported functions
- Handle errors explicitly
- Use async/await for asynchronous operations

---

## 🧪 Testing

### Test Coverage Requirements
- **Minimum**: 70% overall coverage (enforced by CI)
- **Target**: 80%+ for critical paths
- **Models**: 90%+ for ML model code

### Writing Tests

#### Python Unit Tests
```python
import pytest
from ml.src.models.arima_model import ARIMAModel


class TestARIMAModel:
    """Test suite for ARIMA model."""
    
    @pytest.fixture
    def sample_data(self):
        """Provide sample time series data."""
        return pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100),
            'close': np.random.randn(100).cumsum() + 100
        })
    
    def test_model_fit(self, sample_data):
        """Test that model fits without errors."""
        model = ARIMAModel(order=(1, 1, 1))
        model.fit(sample_data['close'])
        assert model.is_fitted
    
    def test_model_predict(self, sample_data):
        """Test prediction output shape."""
        model = ARIMAModel(order=(1, 1, 1))
        model.fit(sample_data['close'])
        predictions = model.predict(steps=5)
        assert len(predictions) == 5
```

#### Integration Tests
```python
import pytest


@pytest.mark.integration
class TestAlpacaIntegration:
    """Integration tests for Alpaca API."""
    
    def test_fetch_bars(self, alpaca_client):
        """Test fetching OHLC bars from Alpaca."""
        bars = alpaca_client.get_bars("AAPL", "1Day", limit=10)
        assert len(bars) == 10
        assert all(hasattr(bar, 'close') for bar in bars)
```

### Running Tests
```bash
# Run all tests
pytest ml/tests/

# Run specific test file
pytest ml/tests/unit/test_arima_model.py

# Run with coverage
pytest ml/tests/ --cov=ml/src --cov-report=html

# Run only unit tests
pytest ml/tests/unit/

# Run only integration tests (slower)
pytest ml/tests/integration/ -m integration
```

---

## 🔄 Git Workflow

### Branch Naming
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring
- `test/description` - Test additions/improvements

### Commit Messages
Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(models): add GARCH volatility model

Implement GARCH(1,1) model for volatility forecasting.
Includes parameter estimation and prediction methods.

Closes #123
```

```
fix(alpaca): handle rate limit errors gracefully

Add exponential backoff retry logic for Alpaca API calls
when rate limit is exceeded.
```

### Pull Request Process

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code following style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Run tests and linters**
   ```bash
   black ml/src ml/tests
   mypy ml/src
   pytest ml/tests/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat(scope): description"
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create Pull Request**
   - Use the PR template
   - Link related issues
   - Request review from maintainers

7. **Address review feedback**
   - Make requested changes
   - Push updates to the same branch
   - Re-request review

8. **Merge**
   - Squash commits if needed
   - Delete branch after merge

---

## 📚 Documentation

### When to Update Docs

Update documentation when you:
- Add new features or APIs
- Change existing behavior
- Add new dependencies
- Modify architecture
- Update deployment process

### Documentation Locations

- **Code**: Inline comments and docstrings
- **API**: `docs/API_REFERENCE.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **Setup**: `docs/SETUP.md`
- **Deployment**: `docs/DEPLOYMENT.md`
- **Models**: `docs/ML_MODELS.md`

---

## 🏗️ Architecture Decisions

### When to Discuss First

Create a GitHub Issue for discussion before implementing:
- New ML models or strategies
- Major architectural changes
- New external dependencies
- Database schema changes
- Breaking API changes

### Decision Documentation

Document major decisions in:
1. GitHub Issue discussion
2. `docs/ARCHITECTURE.md` updates
3. Code comments explaining "why"

---

## 🐛 Bug Reports

### Before Submitting

1. Check existing issues
2. Verify it's reproducible
3. Test on latest version
4. Gather relevant information

### Bug Report Template

```markdown
**Describe the bug**
Clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Environment**
- OS: [e.g., macOS 14.0]
- Python version: [e.g., 3.10.5]
- SwiftBolt_ML version: [e.g., 1.0.0]

**Additional context**
Logs, screenshots, etc.
```

---

## ✨ Feature Requests

### Feature Request Template

```markdown
**Problem Statement**
What problem does this solve?

**Proposed Solution**
How should it work?

**Alternatives Considered**
Other approaches you've thought about.

**Additional Context**
Examples, mockups, references.
```

---

## 📊 Performance Guidelines

### Benchmarking

When optimizing performance:
1. Measure before optimizing
2. Document baseline metrics
3. Test with realistic data sizes
4. Verify accuracy isn't degraded

### Performance Targets

- **API Response**: < 500ms for chart data
- **Predictions**: < 2s for single symbol
- **Backfill**: > 100 bars/second
- **iOS App**: 60 FPS, < 100MB memory

---

## 🔒 Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead:
1. Email: security@yourdomain.com
2. Include detailed description
3. Wait for response before disclosure

### Security Best Practices

- Never commit API keys or secrets
- Use environment variables
- Validate all user inputs
- Sanitize database queries
- Keep dependencies updated

---

## 📝 Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Release Checklist

- [ ] All tests passing
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Version bumped in relevant files
- [ ] Git tag created
- [ ] Release notes written

---

## 🙏 Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the community
- Show empathy towards others

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Personal or political attacks
- Publishing others' private information
- Other unprofessional conduct

---

## 📞 Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Chat**: Join our Discord (if available)
- **Email**: contact@yourdomain.com

---

## 🎉 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in relevant documentation

Thank you for contributing to SwiftBolt_ML! 🚀
