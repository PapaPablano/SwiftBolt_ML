# 🏗️ SwiftBolt_ML Project Reorganization Plan

**Status:** In Progress  
**Goal:** Production-grade project structure with clear separation of concerns, comprehensive testing, and automated CI/CD

---

## 📊 Current Structure Analysis

### ✅ **What's Working Well**
- Clear separation: `client-macos/`, `ml/`, `supabase/`, `backend/`
- ML code organized in `ml/src/` with logical modules
- Supabase functions properly structured
- iOS app follows standard Xcode conventions

### ⚠️ **Issues Identified**
1. **Duplicate folders**: `backend/supabase/` AND `supabase/` at root
2. **Missing documentation structure**: No `docs/` with architecture guides
3. **No CI/CD**: Missing `.github/workflows/`
4. **Incomplete testing**: `ml/tests/` exists but needs expansion
5. **No infrastructure as code**: Missing Terraform/Docker configs
6. **Scattered documentation**: 100+ `.md` files at root level
7. **No code quality configs**: Missing `pyproject.toml`, `.swiftformat`
8. **No contribution guidelines**: Missing `CONTRIBUTING.md`

---

## 🎯 Target Structure

```
SwiftBolt_ML/
├── .github/
│   ├── workflows/              # CI/CD pipelines
│   │   ├── test-ml.yml
│   │   ├── test-ios.yml
│   │   ├── deploy-supabase.yml
│   │   └── lint-and-format.yml
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── model_improvement.md
│   └── pull_request_template.md
│
├── client-macos/              # iOS/macOS SwiftUI app
│   ├── SwiftBoltML/
│   │   ├── App/
│   │   ├── Models/
│   │   ├── Services/
│   │   ├── ViewModels/
│   │   ├── Views/
│   │   └── Utilities/
│   ├── SwiftBoltMLTests/      # Unit tests for iOS
│   ├── SwiftBoltMLUITests/    # UI tests
│   └── .swiftformat           # Swift code formatting
│
├── ml/                        # Machine Learning & Python backend
│   ├── src/
│   │   ├── models/            # ARIMA-GARCH, XGBoost, ensemble
│   │   ├── features/          # Feature engineering
│   │   ├── data/              # Data pipelines
│   │   ├── strategies/        # Trading strategies
│   │   ├── backtesting/       # Strategy validation
│   │   ├── monitoring/        # Model performance tracking
│   │   ├── api/               # FastAPI endpoints (if needed)
│   │   └── utils/             # Helper functions
│   ├── tests/
│   │   ├── unit/              # Unit tests for models
│   │   ├── integration/       # Integration tests (Alpaca, Supabase)
│   │   └── fixtures/          # Test data
│   ├── notebooks/             # Jupyter notebooks for analysis
│   ├── scripts/               # Standalone scripts (backfill, etc.)
│   ├── config/                # Configuration files
│   ├── requirements.txt       # Python dependencies
│   ├── requirements-dev.txt   # Dev dependencies (pytest, black, mypy)
│   ├── pyproject.toml         # Python project config
│   └── pytest.ini             # Pytest configuration
│
├── supabase/                  # Supabase backend (consolidated)
│   ├── functions/             # Edge functions
│   │   ├── _shared/           # Shared utilities
│   │   ├── chart-data-v2/
│   │   ├── sync-market-calendar/
│   │   ├── sync-corporate-actions/
│   │   └── [other functions]/
│   ├── migrations/            # Database migrations
│   └── config.toml            # Supabase config
│
├── infrastructure/            # Infrastructure as Code
│   ├── docker/
│   │   ├── Dockerfile.ml      # ML service container
│   │   └── docker-compose.yml
│   ├── terraform/             # Cloud infrastructure
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── scripts/               # Deployment scripts
│       ├── deploy-supabase.sh
│       └── setup-dev-env.sh
│
├── docs/                      # Comprehensive documentation
│   ├── ARCHITECTURE.md        # System design, data flow diagrams
│   ├── ML_MODELS.md           # Model selection, hyperparameters
│   ├── API_REFERENCE.md       # API endpoints documentation
│   ├── SETUP.md               # Development environment setup
│   ├── DEPLOYMENT.md          # Production deployment guide
│   ├── TRADING_LOGIC.md       # Strategy documentation
│   ├── MIGRATION_GUIDE.md     # Alpaca migration details
│   ├── PERFORMANCE.md         # Benchmarks and metrics
│   └── images/                # Architecture diagrams
│
├── examples/                  # Example usage
│   ├── backtest_strategy.py
│   ├── live_trading_demo.py
│   ├── ios_integration_guide.md
│   └── data/                  # Sample data for examples
│
├── .gitignore                 # Comprehensive gitignore
├── .env.example               # Environment variable template
├── README.md                  # Project overview
├── CONTRIBUTING.md            # Contribution guidelines
├── CHANGELOG.md               # Version history
├── LICENSE                    # License file
└── pyproject.toml             # Root Python config
```

---

## 📋 Implementation Phases

### **Phase 1: Foundation** (30 min)
- [x] Create comprehensive `.gitignore`
- [ ] Create `docs/` structure with key documents
- [ ] Add `CONTRIBUTING.md`
- [ ] Add `CHANGELOG.md`
- [ ] Create `.env.example`
- [ ] Add `pyproject.toml` for Python tooling

### **Phase 2: CI/CD** (45 min)
- [ ] Create `.github/workflows/test-ml.yml`
- [ ] Create `.github/workflows/test-ios.yml`
- [ ] Create `.github/workflows/deploy-supabase.yml`
- [ ] Create `.github/workflows/lint-and-format.yml`
- [ ] Add issue templates
- [ ] Add PR template

### **Phase 3: Testing** (60 min)
- [ ] Expand `ml/tests/unit/` with model tests
- [ ] Add `ml/tests/integration/` for API tests
- [ ] Create test fixtures
- [ ] Add pytest configuration
- [ ] Set up coverage reporting
- [ ] Add iOS unit tests structure

### **Phase 4: Documentation** (45 min)
- [ ] Write `docs/ARCHITECTURE.md`
- [ ] Write `docs/ML_MODELS.md`
- [ ] Write `docs/API_REFERENCE.md`
- [ ] Write `docs/SETUP.md`
- [ ] Write `docs/DEPLOYMENT.md`
- [ ] Create architecture diagrams

### **Phase 5: Code Quality** (30 min)
- [ ] Configure Black, mypy, flake8 in `pyproject.toml`
- [ ] Add `.swiftformat` for iOS
- [ ] Set up pre-commit hooks
- [ ] Add linting to CI/CD
- [ ] Configure coverage thresholds

### **Phase 6: Infrastructure** (60 min)
- [ ] Create `infrastructure/docker/` configs
- [ ] Add Terraform configs (if using cloud)
- [ ] Create deployment scripts
- [ ] Document infrastructure setup

### **Phase 7: Cleanup** (30 min)
- [ ] Consolidate duplicate folders
- [ ] Move scattered `.md` files to `docs/`
- [ ] Archive old/unused files
- [ ] Update all import paths
- [ ] Verify all tests pass

---

## 🚀 Quick Start Implementation

### Step 1: Enhanced .gitignore
```gitignore
# Environment
.env
.env.local
.env.*.local
*.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
.venv
pip-log.txt
pip-delete-this-directory.txt
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
dist/
build/

# Jupyter
.ipynb_checkpoints
*.ipynb_checkpoints

# macOS
.DS_Store
*.swp
*~
.AppleDouble
.LSOverride

# Xcode
build/
DerivedData/
*.xcodeproj/project.xcworkspace/
*.xcodeproj/xcuserdata/
*.xcworkspace/xcuserdata/
*.pbxuser
*.mode1v3
*.mode2v3
*.perspectivev3

# Node
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Supabase
.branches/
.temp/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
*.log
logs/

# Terraform
*.tfstate
*.tfstate.backup
.terraform/

# Data (don't commit large datasets)
*.csv
*.parquet
*.h5
ml/data/*.csv
ml/data/*.parquet
!ml/data/examples/*.csv
```

### Step 2: pyproject.toml
```toml
[project]
name = "swiftbolt-ml"
version = "1.0.0"
description = "Algorithmic trading platform with ML-powered predictions"
authors = [{name = "Eric Peterson"}]
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "scikit-learn>=1.3.0",
    "xgboost>=2.0.0",
    "statsmodels>=0.14.0",
    "alpaca-py>=0.8.0",
    "supabase>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "black>=23.7.0",
    "mypy>=1.5.0",
    "flake8>=6.1.0",
    "pre-commit>=3.3.0",
]

[tool.black]
line-length = 100
target-version = ['py310']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.venv
  | build
  | dist
)/
'''

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
check_untyped_defs = true
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["ml/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--cov=ml/src --cov-report=html --cov-report=term-missing --cov-fail-under=80"

[tool.coverage.run]
source = ["ml/src"]
omit = [
    "*/tests/*",
    "*/venv/*",
    "*/__pycache__/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

### Step 3: CONTRIBUTING.md
```markdown
# Contributing to SwiftBolt_ML

## Development Setup

1. Clone the repository
2. Install Python dependencies: `pip install -r ml/requirements-dev.txt`
3. Install pre-commit hooks: `pre-commit install`
4. Copy `.env.example` to `.env` and configure

## Code Standards

### Python
- Use Black for formatting (100 char line length)
- Type hints required for all functions
- Docstrings required for public APIs
- Minimum 80% test coverage

### Swift
- Follow Swift API Design Guidelines
- Use SwiftFormat for consistency
- Add unit tests for business logic

### Commits
- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Keep commits atomic and focused
- Reference issues in commit messages

## Testing

### Python
```bash
cd ml
pytest tests/ --cov=src
```

### iOS
```bash
cd client-macos
xcodebuild test -scheme SwiftBoltML
```

## Pull Request Process

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes with tests
3. Run linters: `black ml/src && mypy ml/src`
4. Push and create PR
5. Ensure CI passes
6. Request review

## Architecture Decisions

Major changes should:
1. Be discussed in GitHub Issues first
2. Include architecture documentation updates
3. Have comprehensive tests
4. Update relevant docs in `docs/`
```

---

## 📊 Success Metrics

After reorganization, the project should have:

- ✅ **Clear structure** - Any developer can navigate in <5 minutes
- ✅ **Automated testing** - CI runs on every PR
- ✅ **Code quality** - Linting and formatting enforced
- ✅ **Documentation** - Architecture, setup, and API docs complete
- ✅ **Reproducibility** - New devs can set up in <15 minutes
- ✅ **Professional** - Follows industry best practices

---

## 🎯 Priority Order

1. **High Priority** (Do First)
   - Enhanced `.gitignore`
   - `pyproject.toml` with tooling configs
   - CI/CD for Python tests
   - `docs/ARCHITECTURE.md`
   - `CONTRIBUTING.md`

2. **Medium Priority** (Do Next)
   - Expand test suite
   - iOS CI/CD
   - API documentation
   - Infrastructure configs

3. **Low Priority** (Nice to Have)
   - GitHub issue templates
   - Example scripts
   - Performance documentation
   - Terraform configs

---

## 🔄 Migration Strategy

To avoid disrupting current work:

1. **Create new structure alongside existing** (no breaking changes)
2. **Update imports gradually** (one module at a time)
3. **Keep old structure until verified** (safety net)
4. **Test thoroughly** (ensure nothing breaks)
5. **Archive old files** (don't delete immediately)

---

**Ready to implement?** Let me know which phase to start with!
