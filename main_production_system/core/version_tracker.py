"""
Version Tracking and Change History System

Provides comprehensive version tracking for logging and debugging:
- Component identification
- Source code version (git commit hash)
- Timestamp tracking
- Change history management

Author: ML Analysis Platform Team
Date: 2025-01-27
"""

import os
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any, List
import json
import sys


class VersionTracker:
    """
    Tracks code version, component, and source information for logging and debugging.
    """
    
    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize version tracker.
        
        Args:
            repo_path: Path to git repository root. Defaults to current working directory.
        """
        self.repo_path = repo_path or Path.cwd()
        self._git_hash: Optional[str] = None
        self._git_branch: Optional[str] = None
        self._version_cache: Dict[str, Any] = {}
        
    def get_git_hash(self) -> Optional[str]:
        """Get current git commit hash."""
        if self._git_hash is not None:
            return self._git_hash
            
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self._git_hash = result.stdout.strip()
                return self._git_hash
        except (subprocess.SubprocessError, FileNotFoundError, TimeoutError):
            pass
        
        return None
    
    def get_git_branch(self) -> Optional[str]:
        """Get current git branch name."""
        if self._git_branch is not None:
            return self._git_branch
            
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self._git_branch = result.stdout.strip()
                return self._git_branch
        except (subprocess.SubprocessError, FileNotFoundError, TimeoutError):
            pass
        
        return None
    
    def get_version_info(self, component: str = "system") -> Dict[str, Any]:
        """
        Get comprehensive version information for a component.
        
        Args:
            component: Component name (e.g., "data_provider", "arima_garch", "xgboost")
        
        Returns:
            Dictionary with version information
        """
        cache_key = f"{component}_{self.repo_path}"
        if cache_key in self._version_cache:
            return self._version_cache[cache_key]
        
        info = {
            "component": component,
            "timestamp": datetime.now().isoformat(),
            "git_hash": self.get_git_hash(),
            "git_branch": self.get_git_branch(),
            "python_version": sys.version.split()[0],
            "source_path": str(self.repo_path),
        }
        
        # Try to get component-specific version
        try:
            if component == "main_system":
                import main_production_system
                info["package_version"] = getattr(main_production_system, "__version__", None)
        except ImportError:
            pass
        
        self._version_cache[cache_key] = info
        return info
    
    def format_version_tag(self, component: str = "system") -> str:
        """
        Format a version tag string for logging.
        
        Args:
            component: Component name
        
        Returns:
            Formatted tag string like "[component:system|hash:abc123|branch:main]"
        """
        info = self.get_version_info(component)
        parts = [f"component:{component}"]
        
        if info.get("git_hash"):
            parts.append(f"hash:{info['git_hash'][:8]}")
        
        if info.get("git_branch"):
            parts.append(f"branch:{info['git_branch']}")
        
        return "|".join(parts)


class ChangeHistoryTracker:
    """
    Tracks change history for user visibility and debugging.
    """
    
    def __init__(self, history_dir: Path = None):
        """
        Initialize change history tracker.
        
        Args:
            history_dir: Directory to store change history files. Defaults to 'logs/changes/'
        """
        if history_dir is None:
            history_dir = Path(__file__).parent.parent.parent / "logs" / "changes"
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        self.version_tracker = VersionTracker()
        self.logger = logging.getLogger(__name__)
    
    def record_change(
        self,
        component: str,
        action: str,
        details: Dict[str, Any],
        source: str = "unknown",
        result: str = "unknown"
    ) -> str:
        """
        Record a change in history.
        
        Args:
            component: Component that changed (e.g., "data_provider", "model")
            action: Action performed (e.g., "test_executed", "model_trained", "config_updated")
            details: Additional details about the change
            source: Source of the change (e.g., "test_suite", "dashboard", "scheduler")
            result: Result of the change (e.g., "success", "failure", "warning")
        
        Returns:
            Path to the history file entry
        """
        version_info = self.version_tracker.get_version_info(component)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "action": action,
            "source": source,
            "result": result,
            "details": details,
            "version": version_info
        }
        
        # Save to daily history file
        today = datetime.now().strftime("%Y%m%d")
        history_file = self.history_dir / f"changes_{today}.jsonl"
        
        try:
            with open(history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write change history: {e}")
        
        # Also save to component-specific history
        component_file = self.history_dir / f"{component}_history.jsonl"
        try:
            with open(component_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            self.logger.warning(f"Failed to write component history: {e}")
        
        return str(history_file)
    
    def get_recent_changes(
        self,
        component: Optional[str] = None,
        limit: int = 50,
        result_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent change history.
        
        Args:
            component: Filter by component name (optional)
            limit: Maximum number of entries to return
            result_filter: Filter by result (e.g., "success", "failure")
        
        Returns:
            List of change entries
        """
        changes = []
        
        # Read from daily files (most recent first)
        if component:
            history_file = self.history_dir / f"{component}_history.jsonl"
            files_to_check = [history_file] if history_file.exists() else []
        else:
            # Check last 7 days of daily files
            files_to_check = []
            for days_ago in range(7):
                date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                date = date - timedelta(days=days_ago)
                daily_file = self.history_dir / f"changes_{date.strftime('%Y%m%d')}.jsonl"
                if daily_file.exists():
                    files_to_check.append(daily_file)
        
        for history_file in files_to_check:
            try:
                with open(history_file, "r") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        entry = json.loads(line)
                        
                        if result_filter and entry.get("result") != result_filter:
                            continue
                        
                        changes.append(entry)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
        
        # Sort by timestamp (newest first)
        changes.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return changes[:limit]
    
    def generate_change_report(self, component: Optional[str] = None) -> str:
        """
        Generate a human-readable change history report.
        
        Args:
            component: Filter by component (optional)
        
        Returns:
            Formatted report string
        """
        changes = self.get_recent_changes(component=component, limit=100)
        
        if not changes:
            return f"No change history found for component: {component or 'all'}"
        
        report = []
        report.append("=" * 80)
        report.append(f"CHANGE HISTORY REPORT - {component or 'ALL COMPONENTS'}")
        report.append("=" * 80)
        report.append(f"Total Entries: {len(changes)}")
        report.append("")
        
        # Group by component
        by_component = {}
        for entry in changes:
            comp = entry.get("component", "unknown")
            if comp not in by_component:
                by_component[comp] = []
            by_component[comp].append(entry)
        
        for comp, entries in by_component.items():
            report.append(f"\nComponent: {comp}")
            report.append("-" * 80)
            
            for entry in entries[:20]:  # Limit to 20 per component
                timestamp = entry.get("timestamp", "unknown")
                action = entry.get("action", "unknown")
                source = entry.get("source", "unknown")
                result = entry.get("result", "unknown")
                
                # Format result with emoji
                result_icon = {
                    "success": "✅",
                    "failure": "❌",
                    "warning": "⚠️",
                    "unknown": "❓"
                }.get(result, "❓")
                
                report.append(
                    f"  {result_icon} [{timestamp}] {action} | Source: {source} | Result: {result}"
                )
                
                # Show version info if available
                version = entry.get("version", {})
                if version.get("git_hash"):
                    report.append(
                        f"      Version: {version['git_hash'][:8]} | Branch: {version.get('git_branch', 'N/A')}"
                    )
        
        report.append("\n" + "=" * 80)
        return "\n".join(report)


# Global instance
_version_tracker = VersionTracker()
_change_tracker = ChangeHistoryTracker()


def get_version_tracker() -> VersionTracker:
    """Get global version tracker instance."""
    return _version_tracker


def get_change_tracker() -> ChangeHistoryTracker:
    """Get global change history tracker instance."""
    return _change_tracker


# Custom logging formatter that includes version tags
class VersionedLogFormatter(logging.Formatter):
    """
    Custom log formatter that includes component, source, and version information.
    """
    
    def __init__(self, component: str = "system", source: str = "unknown"):
        """
        Initialize formatter.
        
        Args:
            component: Component name
            source: Source identifier (e.g., "test_suite", "dashboard")
        """
        self.component = component
        self.source = source
        self.version_tracker = VersionTracker()
        
        # Base format with version tags
        base_format = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '[component:%(component)s|source:%(source)s|hash:%(git_hash)s] - %(message)s'
        )
        super().__init__(base_format)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with version information."""
        version_info = self.version_tracker.get_version_info(self.component)
        
        # Add version info to record
        record.component = self.component
        record.source = self.source
        record.git_hash = version_info.get("git_hash", "unknown")[:8] if version_info.get("git_hash") else "unknown"
        
        return super().format(record)

