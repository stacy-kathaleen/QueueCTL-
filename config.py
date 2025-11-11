"""
Configuration Manager - Handles persistent configuration
"""

import json
from pathlib import Path


class Config:
    """Manages configuration with JSON persistence"""
    
    DEFAULT_CONFIG = {
        'max_retries': 3,
        'backoff_base': 2,
        'worker_timeout': 300
    }
    
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self):
        """Load configuration from file or create defaults"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                # Merge with defaults for any missing keys
                return {**self.DEFAULT_CONFIG, **config}
        else:
            self._save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self, config):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def get(self, key, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set configuration value"""
        self.config[key] = value
        self._save_config(self.config)
    
    def get_all(self):
        """Get all configuration values"""
        return self.config.copy()