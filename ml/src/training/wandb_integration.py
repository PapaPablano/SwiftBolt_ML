"""Weights & Biases integration for ML experiment tracking.

Tracks experiments, logs metrics, saves artifacts, and enables
hyperparameter optimization with W&B sweeps.

Usage:
    from src.training.wandb_integration import WandBTracker
    
    # Initialize
    tracker = WandBTracker(
        project="swiftbolt-ml",
        entity="your-team"
    )
    
    # Start run
    run = tracker.start_run(
        name="forecast-experiment-1",
        config={"learning_rate": 0.001, "epochs": 100}
    )
    
    # Log metrics
    tracker.log_metrics({"train_loss": 0.5, "val_accuracy": 0.85}, step=1)
    
    # Save model
    tracker.save_model(model, "best_model.pkl")
    
    # Finish
    tracker.finish_run()

References:
    - W&B Documentation: https://docs.wandb.ai/
    - ML Experiment Tracking Best Practices
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import wandb, but make it optional
try:
    import wandb
    WANDB_AVAILABLE = True
except ImportError:
    WANDB_AVAILABLE = False
    logger.warning(
        "Weights & Biases not available. Install with: pip install wandb"
    )


class WandBTracker:
    """Weights & Biases experiment tracker."""
    
    def __init__(
        self,
        project: str = "swiftbolt-ml",
        entity: Optional[str] = None,
        enabled: bool = True
    ):
        """Initialize W&B tracker.
        
        Args:
            project: W&B project name
            entity: W&B team/user name (optional)
            enabled: Enable/disable tracking (for testing)
        """
        self.project = project
        self.entity = entity
        self.enabled = enabled and WANDB_AVAILABLE
        self.current_run = None
        
        if not WANDB_AVAILABLE and enabled:
            logger.warning("W&B tracking disabled (wandb not installed)")
        
        if self.enabled:
            logger.info(f"W&B tracker initialized: project={project}")
    
    def start_run(
        self,
        name: Optional[str] = None,
        config: Optional[Dict] = None,
        tags: Optional[list] = None,
        notes: Optional[str] = None,
        resume: Optional[str] = None
    ):
        """Start a W&B run.
        
        Args:
            name: Run name
            config: Configuration dictionary
            tags: List of tags
            notes: Run notes/description
            resume: Resume mode ('allow', 'must', 'never')
        
        Returns:
            W&B run object or None if disabled
        """
        if not self.enabled:
            logger.debug("W&B tracking disabled, skipping run start")
            return None
        
        self.current_run = wandb.init(
            project=self.project,
            entity=self.entity,
            name=name,
            config=config,
            tags=tags,
            notes=notes,
            resume=resume
        )
        
        logger.info(f"Started W&B run: {self.current_run.name}")
        return self.current_run
    
    def log_metrics(
        self,
        metrics: Dict[str, Any],
        step: Optional[int] = None,
        commit: bool = True
    ):
        """Log metrics to W&B.
        
        Args:
            metrics: Dictionary of metrics
            step: Global step number
            commit: Whether to commit (save) metrics immediately
        """
        if not self.enabled or self.current_run is None:
            return
        
        wandb.log(metrics, step=step, commit=commit)
        logger.debug(f"Logged metrics: {list(metrics.keys())}")
    
    def log_artifact(
        self,
        file_path: str,
        name: str,
        type: str = "model",
        description: Optional[str] = None,
        metadata: Optional[Dict] = None
    ):
        """Log an artifact (model, dataset, etc.) to W&B.
        
        Args:
            file_path: Path to file
            name: Artifact name
            type: Artifact type ('model', 'dataset', 'result')
            description: Artifact description
            metadata: Additional metadata
        """
        if not self.enabled or self.current_run is None:
            return
        
        artifact = wandb.Artifact(
            name=name,
            type=type,
            description=description,
            metadata=metadata
        )
        
        artifact.add_file(file_path)
        wandb.log_artifact(artifact)
        
        logger.info(f"Logged artifact: {name} ({type})")
    
    def save_model(
        self,
        model: Any,
        filename: str,
        metadata: Optional[Dict] = None
    ):
        """Save model as W&B artifact.
        
        Args:
            model: Model object (will be pickled)
            filename: Filename for saved model
            metadata: Model metadata
        """
        if not self.enabled or self.current_run is None:
            return
        
        import pickle
        
        # Save model locally first
        model_path = Path(wandb.run.dir) / filename
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        
        # Log as artifact
        self.log_artifact(
            str(model_path),
            name=f"model-{wandb.run.id}",
            type="model",
            metadata=metadata
        )
        
        logger.info(f"Saved model: {filename}")
    
    def finish_run(self):
        """Finish current W&B run."""
        if not self.enabled or self.current_run is None:
            return
        
        wandb.finish()
        logger.info("Finished W&B run")
        self.current_run = None
    
    def watch_model(
        self,
        model: Any,
        log: str = "all",
        log_freq: int = 100
    ):
        """Watch model for gradient and parameter tracking.
        
        Args:
            model: PyTorch or Keras model
            log: What to log ('gradients', 'parameters', 'all')
            log_freq: Logging frequency
        """
        if not self.enabled or self.current_run is None:
            return
        
        wandb.watch(model, log=log, log_freq=log_freq)
        logger.info(f"Watching model: log={log}, freq={log_freq}")


class WandBSweepManager:
    """Manage W&B hyperparameter sweeps."""
    
    def __init__(
        self,
        project: str = "swiftbolt-ml",
        entity: Optional[str] = None
    ):
        """Initialize sweep manager.
        
        Args:
            project: W&B project name
            entity: W&B team/user name
        """
        self.project = project
        self.entity = entity
        
        if not WANDB_AVAILABLE:
            raise ImportError("wandb required for sweeps. Install with: pip install wandb")
    
    def create_sweep(
        self,
        sweep_config: Dict,
        sweep_name: Optional[str] = None
    ) -> str:
        """Create a hyperparameter sweep.
        
        Args:
            sweep_config: Sweep configuration dictionary
            sweep_name: Name for the sweep
        
        Returns:
            Sweep ID
        """
        sweep_id = wandb.sweep(
            sweep_config,
            project=self.project,
            entity=self.entity
        )
        
        logger.info(f"Created sweep: {sweep_id}")
        return sweep_id
    
    def run_sweep_agent(
        self,
        sweep_id: str,
        train_function: callable,
        count: Optional[int] = None
    ):
        """Run sweep agent.
        
        Args:
            sweep_id: Sweep ID
            train_function: Training function to call for each run
            count: Number of runs to execute
        """
        wandb.agent(
            sweep_id,
            function=train_function,
            count=count,
            project=self.project,
            entity=self.entity
        )
        
        logger.info(f"Sweep agent completed: {sweep_id}")


# Predefined sweep configurations
SWEEP_CONFIGS = {
    "grid_search": {
        "method": "grid",
        "metric": {
            "name": "val_accuracy",
            "goal": "maximize"
        },
        "parameters": {
            "learning_rate": {"values": [0.001, 0.01, 0.1]},
            "batch_size": {"values": [32, 64, 128]},
            "epochs": {"value": 100}
        }
    },
    "random_search": {
        "method": "random",
        "metric": {
            "name": "val_loss",
            "goal": "minimize"
        },
        "parameters": {
            "learning_rate": {"distribution": "log_uniform_values", "min": 0.0001, "max": 0.1},
            "batch_size": {"values": [32, 64, 128, 256]},
            "dropout": {"distribution": "uniform", "min": 0.1, "max": 0.5}
        }
    },
    "bayesian_search": {
        "method": "bayes",
        "metric": {
            "name": "val_accuracy",
            "goal": "maximize"
        },
        "parameters": {
            "learning_rate": {"distribution": "log_uniform_values", "min": 0.0001, "max": 0.1},
            "num_layers": {"values": [2, 3, 4, 5]},
            "hidden_size": {"values": [64, 128, 256, 512]}
        }
    }
}


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 70)
    print("W&B Integration - Self Test")
    print("=" * 70)
    
    if not WANDB_AVAILABLE:
        print("\n⚠️ Weights & Biases not installed")
        print("Install with: pip install wandb")
        print("\nExample usage:")
        print("""
        from src.training.wandb_integration import WandBTracker
        
        # Initialize
        tracker = WandBTracker(project="swiftbolt-ml")
        
        # Start run
        run = tracker.start_run(
            name="experiment-1",
            config={"lr": 0.001, "epochs": 100}
        )
        
        # Training loop
        for epoch in range(100):
            # ... train model ...
            tracker.log_metrics({
                "train_loss": train_loss,
                "val_accuracy": val_acc
            }, step=epoch)
        
        # Save model
        tracker.save_model(model, "best_model.pkl")
        
        # Finish
        tracker.finish_run()
        """)
    else:
        print("\n✅ Weights & Biases available")
        print("\nExample tracker usage shown above")
        
        print("\n📊 Sweep Configuration Examples:")
        for name, config in SWEEP_CONFIGS.items():
            print(f"\n{name}:")
            print(f"  Method: {config['method']}")
            print(f"  Metric: {config['metric']['name']} ({config['metric']['goal']})")
            print(f"  Parameters: {list(config['parameters'].keys())}")
    
    print("\n" + "=" * 70)
    print("✅ W&B integration ready!")
    print("=" * 70)
