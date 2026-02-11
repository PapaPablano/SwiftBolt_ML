"""
Configuration Loader for ML Analysis Platform

Provides centralized configuration management with YAML support,
environment variable override, and validation.

Author: ML Analysis Platform Team
Date: October 28, 2025
"""

from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml
import os
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Configuration loader with validation and environment variable support.
    """
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize configuration loader.
        
        Args:
            config_path: Path to config file (defaults to standard location)
        """
        if config_path is None:
            # Default to standard config location
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "main_production_system" / "config" / "data_paths.yaml"
        
        self.config_path = Path(config_path)
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """
        Load configuration from YAML file.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        logger.info(f"Loading configuration from: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f)
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        logger.info("Configuration loaded successfully")
    
    def _apply_env_overrides(self):
        """
        Apply environment variable overrides to configuration.
        
        Looks for environment variables matching config keys with prefix ML_
        Example: ML_PROVIDERS_ALPHA_VANTAGE_ENABLED=false
        """
        prefix = "ML_"
        
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert ML_SECTION_SUBSECTION_KEY to nested dict path
                config_path = key[len(prefix):].lower().split('_')
                
                try:
                    self._set_nested_value(config_path, value)
                    logger.debug(f"Applied env override: {key} = {value}")
                except Exception as e:
                    logger.warning(f"Failed to apply env override {key}: {e}")
    
    def _set_nested_value(self, path: list, value: str):
        """
        Set nested dictionary value from path.
        
        Args:
            path: List of keys representing nested path
            value: String value to set (will be converted to appropriate type)
        """
        current = self._config
        
        # Navigate to parent
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set value with type conversion
        final_key = path[-1]
        current[final_key] = self._convert_value(value)
    
    def _convert_value(self, value: str) -> Any:
        """
        Convert string value to appropriate type.
        
        Args:
            value: String value
            
        Returns:
            Converted value
        """
        # Boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # None/null
        if value.lower() in ('none', 'null', ''):
            return None
        
        # Number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # String (default)
        return value
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path.
        
        Args:
            key_path: Dot-separated path (e.g., 'paths.raw')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        keys = key_path.split('.')
        current = self._config
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def get_path(self, key: str, base_path: Optional[Path] = None) -> Path:
        """
        Get path from configuration and convert to Path object.
        
        Args:
            key: Configuration key (e.g., 'paths.raw')
            base_path: Base path to resolve relative paths (defaults to project root)
            
        Returns:
            Path object
        """
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent
        
        path_str = self.get(key)
        if path_str is None:
            raise ValueError(f"Path configuration not found: {key}")
        
        path = Path(path_str)
        
        if not path.is_absolute():
            path = base_path / path
        
        return path
    
    def get_provider_config(self, provider: str) -> dict:
        """
        Get provider-specific configuration.
        
        Args:
            provider: Provider name (e.g., 'alpha_vantage')
            
        Returns:
            Provider configuration dictionary
        """
        config = self.get(f'providers.{provider}', {})
        
        # Add API key from environment if specified
        if 'env_key' in config:
            env_key = config['env_key']
            api_key = os.getenv(env_key)
            if api_key:
                config['api_key'] = api_key
            else:
                logger.warning(f"API key environment variable not set: {env_key}")
        
        return config
    
    def get_all(self) -> dict:
        """
        Get entire configuration as dictionary.
        
        Returns:
            Deep copy of configuration
        """
        return deepcopy(self._config)
    
    def validate(self) -> bool:
        """
        Validate configuration structure and values.
        
        Returns:
            True if valid, raises exception otherwise
        """
        required_sections = ['paths', 'providers', 'processing', 'dashboard', 'models']
        
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"Required configuration section missing: {section}")
        
        # Validate paths section
        required_paths = ['raw', 'engineered', 'forecasts', 'models', 'outputs']
        paths = self._config.get('paths', {})
        
        for path_key in required_paths:
            if path_key not in paths:
                raise ValueError(f"Required path configuration missing: paths.{path_key}")
        
        logger.info("Configuration validation passed")
        return True
    
    def reload(self):
        """
        Reload configuration from file.
        """
        logger.info("Reloading configuration")
        self._load_config()
    
    def __repr__(self) -> str:
        return f"ConfigLoader(config_path={self.config_path})"


# Global configuration instance
_global_config = None


def get_config(config_path: Optional[Union[str, Path]] = None) -> ConfigLoader:
    """
    Get or create global configuration instance.
    
    Args:
        config_path: Optional custom config path
        
    Returns:
        ConfigLoader instance
    """
    global _global_config
    
    if _global_config is None or config_path is not None:
        _global_config = ConfigLoader(config_path=config_path)
    
    return _global_config


def load_data_config(config_path: Optional[Union[str, Path]] = None) -> dict:
    """
    Load data configuration as dictionary (convenience function).
    
    Args:
        config_path: Optional custom config path
        
    Returns:
        Configuration dictionary
    """
    config = get_config(config_path)
    return config.get_all()
