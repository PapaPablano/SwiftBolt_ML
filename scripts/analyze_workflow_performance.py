#!/usr/bin/env python3
"""
GitHub Actions Workflow Performance Analyzer

Analyzes workflow run performance using GitHub API to identify:
- Execution times and trends
- Job duration patterns
- Failure rates
- Performance bottlenecks
- Cost implications
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

def run_gh_api(endpoint: str, jq_filter: Optional[str] = None) -> Dict:
    """Run GitHub CLI API command and return JSON."""
    try:
        cmd = ["gh", "api", endpoint]
        if jq_filter:
            cmd.extend(["--jq", jq_filter])
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if jq_filter:
            return json.loads(result.stdout)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ GitHub API error: {e.stderr}", file=sys.stderr)
        return {}
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}", file=sys.stderr)
        return {}
    except FileNotFoundError:
        print("❌ GitHub CLI (gh) not installed. Install from: https://cli.github.com/", file=sys.stderr)
        return {}


def get_workflow_runs(workflow_name: Optional[str] = None, per_page: int = 30) -> List[Dict]:
    """Get recent workflow runs."""
    endpoint = f"repos/PapaPablano/SwiftBolt_ML/actions/runs?per_page={per_page}"
    if workflow_name:
        # Get workflow ID first
        workflows = run_gh_api("repos/PapaPablano/SwiftBolt_ML/actions/workflows")
        workflow_id = None
        for wf in workflows.get("workflows", []):
            if wf.get("name") == workflow_name or workflow_name in wf.get("path", ""):
                workflow_id = wf.get("id")
                break
        
        if workflow_id:
            endpoint = f"repos/PapaPablano/SwiftBolt_ML/actions/workflows/{workflow_id}/runs?per_page={per_page}"
    
    runs = run_gh_api(endpoint)
    return runs.get("workflow_runs", [])


def get_workflow_run_jobs(run_id: int) -> List[Dict]:
    """Get jobs for a specific workflow run."""
    endpoint = f"repos/PapaPablano/SwiftBolt_ML/actions/runs/{run_id}/jobs"
    jobs_data = run_gh_api(endpoint)
    return jobs_data.get("jobs", [])


def parse_duration(started_at: str, completed_at: Optional[str]) -> Optional[float]:
    """Parse duration in seconds from timestamps."""
    if not started_at:
        return None
    
    try:
        start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        if completed_at:
            end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            return (end - start).total_seconds()
        return None
    except Exception:
        return None


def analyze_workflow_performance(workflow_name: str = "ML Orchestration", limit: int = 10):
    """Analyze performance of a specific workflow."""
    print(f"📊 Analyzing {workflow_name} Performance")
    print("=" * 70)
    print()
    
    # Get workflow runs
    runs = get_workflow_runs(workflow_name, per_page=limit)
    
    if not runs:
        print(f"❌ No workflow runs found for '{workflow_name}'")
        return
    
    print(f"Found {len(runs)} recent runs\n")
    
    # Analyze runs
    success_count = 0
    failure_count = 0
    cancelled_count = 0
    total_duration = 0
    durations = []
    job_stats = defaultdict(list)
    
    for run in runs:
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion", "unknown")
        run_id = run.get("id")
        
        if conclusion == "success":
            success_count += 1
        elif conclusion == "failure":
            failure_count += 1
        elif conclusion == "cancelled":
            cancelled_count += 1
        
        # Get job details
        jobs = get_workflow_run_jobs(run_id)
        run_duration = 0
        
        for job in jobs:
            job_name = job.get("name", "unknown")
            started_at = job.get("started_at")
            completed_at = job.get("completed_at")
            job_duration = parse_duration(started_at, completed_at)
            
            if job_duration:
                job_stats[job_name].append(job_duration)
                run_duration += job_duration
        
        if run_duration > 0:
            durations.append(run_duration)
            total_duration += run_duration
    
    # Print summary
    print("## Overall Statistics")
    print("-" * 70)
    print(f"Total Runs Analyzed: {len(runs)}")
    print(f"✅ Successful: {success_count} ({success_count/len(runs)*100:.1f}%)")
    print(f"❌ Failed: {failure_count} ({failure_count/len(runs)*100:.1f}%)")
    print(f"⏸️  Cancelled: {cancelled_count} ({cancelled_count/len(runs)*100:.1f}%)")
    print()
    
    if durations:
        avg_duration = total_duration / len(durations)
        min_duration = min(durations)
        max_duration = max(durations)
        
        print("## Execution Time Statistics")
        print("-" * 70)
        print(f"Average Duration: {avg_duration/60:.1f} minutes ({avg_duration:.0f} seconds)")
        print(f"Min Duration: {min_duration/60:.1f} minutes ({min_duration:.0f} seconds)")
        print(f"Max Duration: {max_duration/60:.1f} minutes ({max_duration:.0f} seconds)")
        print()
    
    # Job-level analysis
    if job_stats:
        print("## Job Performance Breakdown")
        print("-" * 70)
        print(f"{'Job Name':<30} {'Avg (min)':<12} {'Min (min)':<12} {'Max (min)':<12} {'Runs':<8}")
        print("-" * 70)
        
        for job_name, job_durations in sorted(job_stats.items(), key=lambda x: -sum(x[1])):
            if job_durations:
                avg = sum(job_durations) / len(job_durations)
                min_dur = min(job_durations)
                max_dur = max(job_durations)
                print(f"{job_name:<30} {avg/60:>10.1f} {min_dur/60:>10.1f} {max_dur/60:>10.1f} {len(job_durations):>6}")
        print()
    
    # Cost estimation (GitHub Actions minutes)
    if durations:
        total_minutes = sum(durations) / 60
        print("## Cost Estimation")
        print("-" * 70)
        print(f"Total Minutes Used: {total_minutes:.1f}")
        print(f"Estimated Cost (if over free tier): ${total_minutes * 0.008:.2f}")
        print("(Free tier: 2,000 minutes/month for private repos)")
        print()
    
    # Recent run details
    print("## Recent Runs")
    print("-" * 70)
    print(f"{'Run #':<8} {'Status':<12} {'Duration (min)':<15} {'Created':<20}")
    print("-" * 70)
    
    for run in runs[:10]:
        run_number = run.get("run_number", "?")
        conclusion = run.get("conclusion", "unknown")
        created_at = run.get("created_at", "")[:19].replace("T", " ")
        
        jobs = get_workflow_run_jobs(run.get("id"))
        run_duration = 0
        for job in jobs:
            job_dur = parse_duration(job.get("started_at"), job.get("completed_at"))
            if job_dur:
                run_duration += job_dur
        
        duration_str = f"{run_duration/60:.1f}" if run_duration > 0 else "N/A"
        status_emoji = "✅" if conclusion == "success" else "❌" if conclusion == "failure" else "⏸️"
        
        print(f"#{run_number:<7} {status_emoji} {conclusion:<9} {duration_str:<15} {created_at}")
    
    print()


def compare_workflows():
    """Compare performance across multiple workflows."""
    workflows = [
        "ML Orchestration",
        "Daily Data Refresh",
        "Intraday Ingestion",
        "Intraday Forecast"
    ]
    
    print("📊 Workflow Performance Comparison")
    print("=" * 70)
    print()
    
    for workflow in workflows:
        runs = get_workflow_runs(workflow, per_page=5)
        if runs:
            success = sum(1 for r in runs if r.get("conclusion") == "success")
            print(f"{workflow:<30} {success}/{len(runs)} successful ({success/len(runs)*100:.0f}%)")
        else:
            print(f"{workflow:<30} No recent runs")
    print()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze GitHub Actions workflow performance")
    parser.add_argument("--workflow", "-w", help="Workflow name to analyze", default="ML Orchestration")
    parser.add_argument("--limit", "-l", type=int, help="Number of runs to analyze", default=10)
    parser.add_argument("--compare", "-c", action="store_true", help="Compare all workflows")
    
    args = parser.parse_args()
    
    if args.compare:
        compare_workflows()
    else:
        analyze_workflow_performance(args.workflow, args.limit)


if __name__ == "__main__":
    main()
