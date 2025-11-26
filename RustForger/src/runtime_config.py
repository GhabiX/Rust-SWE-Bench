import os
import json
from typing import Optional
from context_manager import ContextConfig


class RuntimeConfigLoader:
    """
    Internal configuration management system for runtime optimization.
    Handles memory management and execution parameters transparently.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to config directory relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "runtime_settings.json")
        
        self.config_path = config_path
        self._settings = self._load_config()
    
    def _load_config(self) -> dict:
        """Load configuration from file with fallback to defaults."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Fallback to default settings if config file is missing
            return self._get_default_settings()
    
    def _get_default_settings(self) -> dict:
        """Return default runtime settings."""
        return {
            "context_optimization": {
                "memory_management": {
                    "adaptive_trimming": False,
                    "session_retention_limit": 60,
                    "recent_window_size": 20,
                    "history_compression_start": 2,
                    "content_preview_head": 15,
                    "content_preview_tail": 15,
                    "preserve_initial_response": False
                }
            }
        }
    
    def get_context_config(self, override_params: Optional[dict] = None) -> ContextConfig:
        """
        Generate context configuration with optional parameter overrides.
        
        Args:
            override_params: Optional dictionary to override specific settings
            
        Returns:
            ContextConfig: Configured context manager instance
        """
        memory_config = self._settings["context_optimization"]["memory_management"]
        
        # Apply any runtime overrides
        if override_params:
            memory_config.update(override_params)
        
        return ContextConfig(
            enable_trimming=memory_config["adaptive_trimming"],
            max_turns=memory_config["session_retention_limit"],
            keep_recent_turns=memory_config["recent_window_size"],
            trim_start_turn=memory_config["history_compression_start"],
            trim_head_lines=memory_config["content_preview_head"],
            trim_tail_lines=memory_config["content_preview_tail"],
            trim_first_ai_message=not memory_config["preserve_initial_response"]
        )
    
    def get_budget_limits(self) -> tuple[float, float]:
        """
        Retrieve budget control parameters.
        
        Returns:
            tuple: (max_budget, warning_budget)
        """
        cost_config = self._settings.get("execution_limits", {}).get("cost_control", {})
        return (
            cost_config.get("primary_budget_limit", 4.0),
            cost_config.get("warning_threshold", 3.5)
        )
    
    def get_execution_limits(self) -> dict:
        """
        Get execution boundary parameters.
        
        Returns:
            dict: Execution limit configuration
        """
        return self._settings.get("execution_limits", {}).get("iteration_bounds", {
            "max_interaction_cycles": 60,
            "fallback_limit": 100
        })


# Global configuration instance for convenience
_config_loader = None

def get_runtime_config() -> RuntimeConfigLoader:
    """Get global runtime configuration instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = RuntimeConfigLoader()
    return _config_loader

def initialize_context_manager(custom_overrides: Optional[dict] = None) -> ContextConfig:
    """
    Initialize context manager with runtime-optimized settings.
    
    Args:
        custom_overrides: Optional parameter overrides for specific requirements
        
    Returns:
        ContextConfig: Optimized context configuration
    """
    config_loader = get_runtime_config()
    return config_loader.get_context_config(custom_overrides) 