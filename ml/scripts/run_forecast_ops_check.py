"""
Daily/weekly forecast ops check for 1D/1W/1M horizons.

Example:
  python ml/scripts/run_forecast_ops_check.py --symbols AAPL,NVDA --horizons 1D,1W,1M
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure local imports work
ml_dir = Path(__file__).parent.parent
sys.path.insert(0, str(ml_dir))
sys.path.insert(0, str(Path(__file__).parent))

from run_forecast_quality import get_forecast_quality  # noqa: E402


def parse_list(value: str, fallback: list[str]) -> list[str]:
    if not value:
        return fallback
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_quality_score(score: float | int | None) -> float:
    if score is None:
        return 0.0
    score = float(score)
    return score * 100 if score <= 1 else score


def main() -> int:
    parser = argparse.ArgumentParser(description="Forecast ops check (quality + confidence).")
    parser.add_argument("--symbols", default="AAPL", help="Comma-separated tickers")
    parser.add_argument("--horizons", default="1D,1W,1M", help="Comma-separated horizons")
    parser.add_argument("--timeframe", default="d1", help="Forecast timeframe (default: d1)")
    parser.add_argument("--min-quality", type=float, default=60.0, help="Min quality score (0-100)")
    parser.add_argument("--fail-on-issues", action="store_true", help="Exit non-zero on warnings")
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output JSON")
    args = parser.parse_args()

    symbols = parse_list(args.symbols, ["AAPL"])
    horizons = parse_list(args.horizons, ["1D", "1W", "1M"])

    results = []
    has_warnings = False

    for symbol in symbols:
        for horizon in horizons:
            result = get_forecast_quality(symbol=symbol, horizon=horizon, timeframe=args.timeframe)
            quality = normalize_quality_score(result.get("qualityScore"))
            result["qualityScore"] = quality

            issues = result.get("issues") or []
            if quality < args.min_quality:
                issues.append(
                    {
                        "level": "warning",
                        "type": "low_quality",
                        "message": f"Quality {quality:.1f} below threshold {args.min_quality:.1f}",
                        "action": "review",
                    }
                )
                result["issues"] = issues

            if any(issue.get("level") == "warning" for issue in issues):
                has_warnings = True

            results.append(result)

    if args.json_output:
        print(json.dumps({"results": results}, indent=2))
    else:
        for result in results:
            issues = result.get("issues") or []
            issue_summary = "; ".join(issue.get("type", "issue") for issue in issues) if issues else "ok"
            print(
                f"{result.get('symbol')} {result.get('horizon')} "
                f"quality={result.get('qualityScore'):.1f} "
                f"conf={float(result.get('confidence', 0)) * 100:.0f}% "
                f"issues={issue_summary}"
            )

    if args.fail_on_issues and has_warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
