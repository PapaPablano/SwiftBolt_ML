  1. Project Overview
                                                                             
  Name: SwiftBolt ML
  Stack:                                                                     
  - Python for Machine Learning (ML) pipeline
  - TypeScript/Deno for Supabase Edge Functions
  - PostgreSQL for Database Management
  - SwiftUI for macOS Research Workstation
  - React + TradingView Lightweight Charts for Frontend Dashboard
  - Docker for Containerization

  Description:
  SwiftBolt ML is an end-to-end market intelligence platform that ingests
  intraday/historical data via Supabase Edge Functions, processes it using
  Python ML pipelines (comprising LSTM, ARIMA-GARCH, XGBoost, TabPFN), and
  presents the results through a macOS SwiftUI client.

  2. Available Commands in a Table

  ┌───────────────────────────────────────────┬──────────────────────────┐
  │                  Command                  │       Description        │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Runs daily forecasts for │
  │ python ml/src/unified_forecast_job.py     │  1D, 5D, 10D, 20D        │
  │                                           │ horizons.                │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Runs intraday forecasts  │
  │ python ml/src/intraday_forecast_job.py    │ for 15m and 1h           │
  │                                           │ intervals.               │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Evaluates daily          │
  │ python ml/src/evaluation_job_daily.py     │ forecasts using          │
  │                                           │ walk-forward validation. │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Evaluates intraday       │
  │ python ml/src/evaluation_job_intraday.py  │ forecasts using          │
  │                                           │ walk-forward validation. │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ pytest ml/tests/ -m "not integration" -v  │ Runs unit tests for the  │
  │                                           │ ML pipeline.             │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ pytest ml/tests/ -v                       │ Runs all tests (unit and │
  │                                           │  integration).           │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ black src tests                           │ Formats Python code with │
  │                                           │  Black formatter.        │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ isort src tests                           │ Sorts imports using      │
  │                                           │ isort.                   │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ flake8 src tests --max-line-length=120    │ Lints Python code with   │
  │ --extend-ignore=E203,W503                 │ flake8.                  │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ mypy src --ignore-missing-imports         │ Checks type hints with   │
  │                                           │ mypy.                    │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Starts a local Supabase  │
  │ npx supabase start                        │ instance for             │
  │                                           │ development.             │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ npx supabase functions serve              │ Serves Edge Functions    │
  │                                           │ locally.                 │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ `./scripts/start-backend.sh [start        │ stop                     │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Lints TypeScript code    │
  │ deno lint supabase/functions/             │ for Supabase Edge        │
  │                                           │ Functions.               │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │ deno fmt supabase/functions/              │ Formats TypeScript code  │
  │                                           │ using deno fmt.          │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Installs dependencies    │
  │ npm install                               │ for the frontend React   │
  │                                           │ dashboard.               │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Runs a development       │
  │ npm run dev                               │ server for the frontend  │
  │                                           │ dashboard.               │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Builds the production    │
  │ npm run build                             │ version of the frontend  │
  │                                           │ dashboard.               │
  ├───────────────────────────────────────────┼──────────────────────────┤
  │                                           │ Starts the ML backend    │
  │ docker compose up --build                 │ API using Docker         │
  │                                           │ Compose.                 │
  └───────────────────────────────────────────┴──────────────────────────┘

  3. Project Structure as a Tree

  SwiftBolt_ML/
  ├── ml/
  │   ├── config/
  │   │   └── settings.py
  │   ├── src/
  │   │   ├── unified_forecast_job.py
  │   │   ├── intraday_forecast_job.py
  │   │   ├── evaluation_job_daily.py
  │   │   ├── evaluation_job_intraday.py
  │   │   ├── models/
  │   │   ├── features/
  │   │   └── data/
  │   │       └── supabase_db.py
  │   ├── tests/
  │   │   └── test_unified_forecast_job.py
  │   │   └── test_intraday_forecast_job.py
  │   │   └── test_evaluation_jobs.py
  ├── supabase/
  │   ├── functions/
  │   │   ├── _shared/
  │   │   ├── chart/
  │   │   ├── some_other_function/
  │   │   └── index.ts
  │   ├── migrations/
  │   │   ├── 20260101000000_initial_migration.sql
  │   │   ├── 20260102000000_another_migration.sql
  │   │   └── ...
  ├── client-macos/
  │   ├── SwiftBoltML.xcodeproj
  ├── frontend/
  │   ├── package.json
  │   ├── tsconfig.json
  │   ├── src/
  │   │   ├── App.tsx
  │   │   ├── some_component.tsx
  │   │   └── ...
  │   ├── public/
  │   ├── vite.config.ts
  │   └── ...
  ├── backend/
  │   ├── Dockerfile
  │   ├── docker-compose.yml
  │   ├── requirements.txt
  │   └── script.sh
  ├── ci-lightweight.yml
  ├── ml-validation.yml
  └── deploy-supabase.yml

  4. Code Conventions

  - Python:
    - Uses Black formatter with line-length 100.
    - Imports are sorted using isort.
    - Async/await for I/O operations.
    - Guard clauses for early returns.
  - TypeScript/Deno:
    - Each function in its own index.ts file within the Supabase functions
  directory.
    - Shared utilities in _shared/.
    - Cache-first reads (return cached data if stale).
  - SwiftUI:
    - Modern concurrency with async/await and actors.
    - Uses Combine for reactive programming.
    - MARK: comments for organization.
    - os_log for logging.

  5. Environment Variables

  From .env.example:

  SUPABASE_URL=
  SUPABASE_SERVICE_KEY=
  ALPACA_API_KEY=
  ALPACA_API_SECRET=
  FINNHUB_API_KEY=
  REDIS_FEATURE_CACHE=true
  USE_UNIFIED_FORECAST=true
  USE_SEPARATE_EVALUATIONS=true
  STRICT_LOOKAHEAD_CHECK=0|1

  6. Known Issues from TODO/FIXME Comments

  - TODO:
    - Refine sentiment features (zero-variance fix pending).
  - FIXME:
    - Validate sentiment variance before re-enabling.

  7. Workflow Conventions (compound-engineering plugin)

  When using /workflows:plan, /workflows:work, or related commands:
  - Check if the target .md file exists BEFORE attempting to read it
  - If the file is missing at docs/workflows/*.md or docs/brainstorms/*.md:
    1. Create the parent directory if needed (mkdir -p docs/workflows/)
    2. Copy from docs/workflows/TEMPLATE_PLAN.md as the starting point
    3. Inform the user the file was created and ask them to edit it
  - Never loop indefinitely searching for files - create what's needed
  - Use these standard paths:
    - Plans: docs/workflows/YYYY-MM-DD-descriptive-name-plan.md
    - Brainstorms: docs/brainstorms/YYYY-MM-DD-topic-brainstorm.md

  By documenting these details in a CLAUDE.md file, you provide a
  comprehensive overview of the project for future reference and
  collaboration.