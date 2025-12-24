#!/bin/bash
# SwiftBolt ML Dashboard Launcher
# Usage: ./run_dashboard.sh

cd "$(dirname "$0")"

echo "Starting SwiftBolt ML Dashboard..."
echo "Open http://localhost:8501 in your browser"
echo ""

streamlit run src/dashboard/forecast_dashboard.py \
    --server.port 8501 \
    --server.headless true \
    --browser.gatherUsageStats false
