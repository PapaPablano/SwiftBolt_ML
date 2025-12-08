# SwiftBolt ML

A macOS SwiftUI application for stock, futures, and options analysis with ML-powered forecasting.

## Tech Stack

- **Client**: Swift 5.9+, SwiftUI, macOS 14+
- **Backend**: Supabase Edge Functions (TypeScript/Deno)
- **Database**: PostgreSQL (Supabase)
- **ML**: Python 3.11+, scikit-learn, pandas
- **Data Providers**: Finnhub, Massive API

## Project Structure

```
SwiftBolt_ML/
├── backend/          # Supabase Edge Functions
├── client-macos/     # SwiftUI macOS app
├── ml/               # Python ML pipeline
├── infra/            # Docker, deployment configs
├── docs/             # Architecture documentation
├── CLAUDE.md         # Claude Code instructions
└── README.md
```

## Getting Started

### Prerequisites

- macOS 14+
- Xcode 15+
- Node.js 18+
- Python 3.11+
- Supabase CLI

### Environment Setup

1. Copy environment template:
   ```bash
   cp .env.example .env
   ```

2. Fill in your API keys in `.env`

### Backend Development

```bash
cd backend
npm install
npx supabase start
npx supabase functions serve
```

### ML Pipeline

```bash
cd ml
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### macOS Client

Open `client-macos/SwiftBolt.xcodeproj` in Xcode and run.

## Documentation

- [Master Blueprint](docs/master_blueprint.md) - Full architecture
- [Implementation Checklist](docs/blueprint_checklist.md) - Progress tracker

## License

Proprietary - All rights reserved
