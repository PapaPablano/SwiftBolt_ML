#!/bin/bash
# Get detailed analysis of a specific workflow run

RUN_ID=${1:-""}
WORKFLOW_NAME=${2:-"ML Orchestration"}

if [ -z "$RUN_ID" ]; then
    echo "Getting latest run for $WORKFLOW_NAME..."
    RUN_ID=$(gh api repos/PapaPablano/SwiftBolt_ML/actions/runs \
        --jq ".workflow_runs[] | select(.name == \"$WORKFLOW_NAME\") | .id" | head -1)
fi

if [ -z "$RUN_ID" ]; then
    echo "❌ No run found"
    exit 1
fi

echo "📊 Analyzing Run #$RUN_ID"
echo "=================================="
echo ""

# Get run details
echo "## Run Information"
gh api repos/PapaPablano/SwiftBolt_ML/actions/runs/$RUN_ID \
    --jq '{status, conclusion, created_at, updated_at, run_number, head_branch}' | jq '.'

echo ""
echo "## Job Performance"
echo ""

# Get jobs with timing
gh api repos/PapaPablano/SwiftBolt_ML/actions/runs/$RUN_ID/jobs \
    --jq '.jobs[] | {
        name,
        status,
        conclusion,
        duration: (
            if .completed_at and .started_at then
                ((.completed_at | fromdateiso8601) - (.started_at | fromdateiso8601))
            else null
            end
        ),
        steps: [.steps[] | {name, number, conclusion, duration: (
            if .completed_at and .started_at then
                ((.completed_at | fromdateiso8601) - (.started_at | fromdateiso8601))
            else null
            end
        )}]
    }' | jq -s 'sort_by(-.duration)'
