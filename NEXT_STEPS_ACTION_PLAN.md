# Next Steps Action Plan
## Implementation Verified - Ready for Enhancement

**Date:** January 24, 2026  
**Status:** ✅ Core Framework Verified - Ready for Optional Enhancements  
**Estimated Timeline:** 5-6 hours for all suggested improvements

---

## QUICK START (Pick One)

### Option A: Deploy As-Is (15 minutes)
✅ **All forecasting improvements are working**
✅ TP1/TP2/TP3/SL are stored in database
✅ Quality scoring is active
✅ Charts show TP1 targets

**Action:**
```bash
cd /Users/ericpeterson/SwiftBolt_ML
git add -A
git commit -m "Forecasting framework verified - production ready"
git push origin master
```

**Result:** Live system with full forecasting suite

---

### Option B: Add Polish First (5-6 hours)
Suggest this option - adds trader-facing improvements

---

## DETAILED ENHANCEMENT ROADMAP

## Task 1: Chart Overlays (TP2, TP3, Stop Loss)
**Priority:** MEDIUM  
**Effort:** 2 hours  
**Impact:** HIGH (traders see full target ladder)

### What It Does
- Renders TP2 line (secondary target, green dashed)
- Renders TP3 line (tertiary target, green dotted)
- Renders Stop Loss line (red line)
- Adds legend showing all price levels

### File to Edit
```
client-macos/SwiftBoltML/Views/AdvancedChartView.swift
```

### Code to Add (After TP1 line)

```swift
// TP2 Line (Secondary Target)
if let tp2 = forecast?.synthesis_data?["tp2"] as? NSNumber {
    let tp2Line = ChartLimitLine(limit: CGFloat(tp2.floatValue))
    tp2Line.label = String(format: "TP2: $%.2f", tp2.floatValue)
    tp2Line.lineColor = .systemGreen.withAlphaComponent(0.6)
    tp2Line.lineWidth = 1.5
    tp2Line.lineDashPhase = 3
    tp2Line.lineDashLengths = [5, 3]
    chartView.rightAxis.addLimitLine(tp2Line)
}

// TP3 Line (Tertiary Target)
if let tp3 = forecast?.synthesis_data?["tp3"] as? NSNumber {
    let tp3Line = ChartLimitLine(limit: CGFloat(tp3.floatValue))
    tp3Line.label = String(format: "TP3: $%.2f", tp3.floatValue)
    tp3Line.lineColor = .systemGreen.withAlphaComponent(0.3)
    tp3Line.lineWidth = 1.0
    tp3Line.lineDashPhase = 5
    tp3Line.lineDashLengths = [3, 2]
    chartView.rightAxis.addLimitLine(tp3Line)
}

// Stop Loss Line
if let sl = forecast?.synthesis_data?["stop_loss"] as? NSNumber {
    let slLine = ChartLimitLine(limit: CGFloat(sl.floatValue))
    slLine.label = String(format: "SL: $%.2f", sl.floatValue)
    slLine.lineColor = .systemRed.withAlphaComponent(0.8)
    slLine.lineWidth = 2.0
    chartView.rightAxis.addLimitLine(slLine)
}
```

### Testing
1. Open app
2. Select AAPL
3. Scroll chart right edge
4. Verify 4 lines visible: TP1 (blue), TP2 (green), TP3 (faint green), SL (red)

### Commit
```bash
git add client-macos/SwiftBoltML/Views/AdvancedChartView.swift
git commit -m "Add TP2/TP3/SL chart overlays"
```

---

## Task 2: Quality Badge on Chart
**Priority:** MEDIUM  
**Effort:** 1 hour  
**Impact:** MEDIUM (shows forecast reliability at a glance)

### What It Does
- Adds colored badge showing quality score (0-1)
- 0.8+ = 🟢 GREEN (high quality)
- 0.6-0.8 = 🟡 YELLOW (medium quality)
- <0.6 = 🟠 RED (low quality)

### File to Edit
```
client-macos/SwiftBoltML/Views/ForecastHeaderView.swift
```

### Code to Add

```swift
// Quality Badge
if let qualityScore = forecast?.synthesis_data?["quality_score"] as? NSNumber {
    let score = CGFloat(qualityScore.doubleValue)
    
    let badgeColor: UIColor
    let scoreLabel: String
    
    switch score {
    case 0.8...: 
        badgeColor = .systemGreen
        scoreLabel = "High Quality"
    case 0.6..<0.8:
        badgeColor = .systemYellow
        scoreLabel = "Medium Quality"
    default:
        badgeColor = .systemRed
        scoreLabel = "Low Quality"
    }
    
    // Create badge
    let badge = UIView()
    badge.backgroundColor = badgeColor.withAlphaComponent(0.2)
    badge.layer.borderColor = badgeColor.cgColor
    badge.layer.borderWidth = 1.5
    badge.layer.cornerRadius = 12
    
    let label = UILabel()
    label.text = String(format: "%@: %.0f%%", scoreLabel, score * 100)
    label.font = .systemFont(ofSize: 12, weight: .semibold)
    label.textColor = badgeColor
    
    badge.addSubview(label)
    label.snp.makeConstraints { $0.edges.equalToSuperview().inset(8) }
    
    // Add to header
    headerView.addSubview(badge)
    badge.snp.makeConstraints { make in
        make.trailing.equalToSuperview().inset(16)
        make.top.equalToSuperview().inset(8)
        make.height.equalTo(28)
    }
}
```

### Testing
1. Open app
2. Check header - badge shows quality score with color
3. Try different symbols (scores vary)

### Commit
```bash
git add client-macos/SwiftBoltML/Views/ForecastHeaderView.swift
git commit -m "Add quality score badge to forecast header"
```

---

## Task 3: Min-Confidence Gating
**Priority:** LOW  
**Effort:** 1 hour  
**Impact:** MEDIUM (prevents low-quality signals)

### What It Does
- Skips writing forecasts with confidence < 0.50 to database
- Logs why they're skipped
- Keeps metrics clean

### File to Edit
```
ml/src/unified_forecast_job.py
```

### Code to Add (In `process_symbol()` method)

```python
def process_symbol(self, symbol: str, horizon: str):
    """
    Process single symbol forecast.
    """
    try:
        # ... existing code to generate forecast ...
        forecast_result = self.synthesizer.generate_forecast(...)
        
        # NEW: Min-confidence gating
        if forecast_result.confidence < 0.50:
            logger.info(
                f"Skipping {symbol} {horizon}: "
                f"confidence {forecast_result.confidence:.1%} < 50% threshold"
            )
            self.metrics['low_confidence_skipped'] = \
                self.metrics.get('low_confidence_skipped', 0) + 1
            return None
        
        # ... rest of processing ...
        self.persist_to_db(forecast_result)
        
    except Exception as e:
        logger.error(f"Error processing {symbol}: {e}")
        self.metrics['errors'].append(str(e))
```

### Testing
```bash
# Run forecast with test symbol
python3 ml/src/unified_forecast_job.py --symbol=AAPL --horizon=1D --test-mode

# Check logs:
# INFO: Skipping TSLA 1D: confidence 45.0% < 50% threshold
```

### Commit
```bash
git add ml/src/unified_forecast_job.py
git commit -m "Add min-confidence gating (skip <50%)"
```

---

## Task 4: Daily Quality Report
**Priority:** LOW  
**Effort:** 2 hours  
**Impact:** HIGH (automated monitoring)

### What It Does
- Runs every day at 4:00 PM PT
- Emails summary of today's forecasts
- Shows accuracy, issues, best/worst predictions
- Suggests actions

### File to Create
```
ml/scripts/daily_quality_report.py
```

### Code Template

```python
#!/usr/bin/env python3
"""
Daily forecast quality report - runs at 4pm PT.
Emails summary of today's forecasts + metrics.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.data.supabase_db import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DailyQualityReporter:
    def __init__(self):
        self.email_to = os.getenv('REPORT_EMAIL', 'eric@swiftbolt.local')
        self.email_from = 'noreply@swiftbolt.local'
    
    def generate_report(self) -> str:
        """
        Generate HTML report of today's forecasts.
        """
        today = datetime.now().date()
        
        # Fetch today's forecasts
        forecasts = db.query(
            """SELECT 
                symbol, horizon, confidence, direction,
                synthesis_data, actual_return, directional_correct
            FROM ml_forecasts
            WHERE DATE(created_at) = %s
            ORDER BY symbol, horizon""",
            (today,)
        )
        
        if not forecasts:
            return "<p>No forecasts generated today.</p>"
        
        df = pd.DataFrame(forecasts)
        
        # Calculate metrics
        total = len(df)
        high_conf = len(df[df['confidence'] >= 0.70])
        med_conf = len(df[(df['confidence'] >= 0.60) & (df['confidence'] < 0.70)])
        low_conf = len(df[df['confidence'] < 0.60])
        
        # Accuracy
        correct = df['directional_correct'].sum() if 'directional_correct' in df else 0
        accuracy = correct / total * 100 if total > 0 else 0
        
        # HTML report
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>SwiftBolt Forecast Quality Report</h2>
            <p><strong>Date:</strong> {today}</p>
            
            <h3>Summary</h3>
            <table border="1">
                <tr>
                    <td>Total Forecasts</td>
                    <td><strong>{total}</strong></td>
                </tr>
                <tr>
                    <td>High Confidence (≥70%)</td>
                    <td><strong>{high_conf}</strong></td>
                </tr>
                <tr>
                    <td>Medium Confidence (60-70%)</td>
                    <td><strong>{med_conf}</strong></td>
                </tr>
                <tr>
                    <td>Low Confidence (<60%)</td>
                    <td><strong style="color: red;">{low_conf}</strong></td>
                </tr>
                <tr>
                    <td>Accuracy (Y-day predictions)</td>
                    <td><strong>{accuracy:.1f}%</strong></td>
                </tr>
            </table>
            
            <h3>Top 5 Forecasts</h3>
            <table border="1">
                <tr>
                    <th>Symbol</th>
                    <th>Horizon</th>
                    <th>Direction</th>
                    <th>Confidence</th>
                    <th>Target (TP1)</th>
                </tr>
        """
        
        for _, row in df.nlargest(5, 'confidence').iterrows():
            synthesis = row['synthesis_data']
            tp1 = synthesis.get('tp1', 'N/A') if isinstance(synthesis, dict) else 'N/A'
            html += f"""
                <tr>
                    <td>{row['symbol']}</td>
                    <td>{row['horizon']}</td>
                    <td>{row['direction']}</td>
                    <td>{row['confidence']:.0%}</td>
                    <td>${tp1:.2f}</td>
                </tr>
            """
        
        html += """</table>
        
            <h3>Issues Found</h3>
        """
        
        if low_conf > 0:
            html += f"<p style='color: orange;'>⚠️ {low_conf} forecasts below 60% confidence</p>"
        
        if accuracy < 50:
            html += f"<p style='color: red;'>✗ Accuracy {accuracy:.1f}% < 50% - review recommended</p>"
        else:
            html += f"<p style='color: green;'>✓ Accuracy {accuracy:.1f}% on target</p>"
        
        html += """</body></html>"""
        
        return html
    
    def send_email(self, html: str):
        """
        Send email with report.
        """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"SwiftBolt Daily Report - {datetime.now().date()}"
        msg['From'] = self.email_from
        msg['To'] = self.email_to
        
        part = MIMEText(html, 'html')
        msg.attach(part)
        
        # Send
        try:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
            server.quit()
            logger.info(f"Email sent to {self.email_to}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    def run(self):
        """
        Generate and send report.
        """
        logger.info("Generating daily quality report...")
        html = self.generate_report()
        self.send_email(html)
        logger.info("Done.")


if __name__ == '__main__':
    reporter = DailyQualityReporter()
    reporter.run()
```

### Setup Cron Job

```bash
# Edit crontab
crontab -e

# Add line (runs daily at 4pm PT = 23:00 UTC)
0 23 * * * cd /Users/ericpeterson/SwiftBolt_ML && python3 ml/scripts/daily_quality_report.py
```

### Testing
```bash
# Manual test
python3 ml/scripts/daily_quality_report.py

# Check email inbox
```

### Commit
```bash
git add ml/scripts/daily_quality_report.py
git commit -m "Add automated daily quality report"
```

---

## FULL EXECUTION CHECKLIST

### Before Starting
- [ ] Backup current code (git branch)
- [ ] Ensure all tests pass
- [ ] Verify API endpoints responding

### Task 1: Chart Overlays (2h)
- [ ] Edit `AdvancedChartView.swift`
- [ ] Add TP2 line code
- [ ] Add TP3 line code
- [ ] Add Stop Loss line code
- [ ] Test on simulator (AAPL)
- [ ] Commit with message

### Task 2: Quality Badge (1h)
- [ ] Edit `ForecastHeaderView.swift`
- [ ] Add quality score badge
- [ ] Test color changes (high/med/low)
- [ ] Commit with message

### Task 3: Min-Confidence Gating (1h)
- [ ] Edit `unified_forecast_job.py`
- [ ] Add confidence check
- [ ] Add logging
- [ ] Test with low-confidence symbol
- [ ] Commit with message

### Task 4: Daily Report (2h)
- [ ] Create `daily_quality_report.py`
- [ ] Configure email settings
- [ ] Test report generation
- [ ] Setup cron job
- [ ] Commit with message

### After Completion
- [ ] All tests pass
- [ ] Commit history clean
- [ ] Ready for deployment

---

## DEPLOYMENT COMMANDS

### Option 1: Deploy Everything
```bash
cd /Users/ericpeterson/SwiftBolt_ML

# Create feature branch
git checkout -b feature/forecasting-enhancements

# Make changes (Tasks 1-4)
# ... edit files ...

# Test
pytest ml/tests/  # Verify Python tests pass
# Test Swift app manually

# Commit
git add -A
git commit -m "Add forecasting UI enhancements + quality monitoring"

# Push and create PR
git push origin feature/forecasting-enhancements
```

### Option 2: Deploy Incrementally
```bash
# Task 1
git checkout -b feature/chart-overlays
# ... make changes ...
git commit -m "Add TP2/TP3/SL overlays"
git push
# Create PR, merge

# Task 2
git checkout -b feature/quality-badge
# ... make changes ...
git commit -m "Add quality score badge"
git push
# ... and so on
```

---

## SUCCESS METRICS

After implementation, verify:

### Chart Overlays Working
- [ ] Open app, select AAPL
- [ ] Scroll right on chart
- [ ] See 4 lines: TP1 (blue), TP2 (green dashed), TP3 (green dotted), SL (red)

### Quality Badge Working
- [ ] Badge shows score (0-100%)
- [ ] Color changes: green (80%+), yellow (60-80%), red (<60%)

### Min-Confidence Gating Working
- [ ] Run: `python3 ml/src/unified_forecast_job.py --test-mode`
- [ ] Check logs: "Skipping X symbols with confidence <50%"
- [ ] Database only has high-quality forecasts

### Daily Report Working
- [ ] Check email inbox at 4pm PT
- [ ] Report shows summary + top 5 predictions + issues
- [ ] Links to dashboard if applicable

---

## ESTIMATED TIMELINE

| Task | Effort | Status |
|------|--------|--------|
| Chart Overlays | 2h | Ready to start |
| Quality Badge | 1h | Ready to start |
| Min-Confidence Gating | 1h | Ready to start |
| Daily Report | 2h | Ready to start |
| Testing & QA | 1h | After all tasks |
| **TOTAL** | **7h** | Can complete today |

---

## QUESTIONS? 

Refer to:
- `IMPLEMENTATION_VERIFICATION_REPORT.md` - Confirms what's working
- `STOCK_FORECASTING_FRAMEWORK.md` - Theory & background
- `SWIFT_BOLT_IMPLEMENTATION.md` - Architecture details
- `FORECASTING_QUICK_REFERENCE.md` - Daily operations

**All your forecasting improvements are correctly implemented. These enhancements are purely optional polish. 🚀**

