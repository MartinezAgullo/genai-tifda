"""
TIFDA Configuration Management
===============================

Handles loading and validation of configuration from YAML files.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from pydantic import BaseModel, Field, field_validator
from src.core.constants import SENSOR_TYPES, OUTPUT_FORMATS, ACCESS_LEVELS


# ==================== CONFIGURATION MODELS ====================

class SensorConfig(BaseModel):
    """Configuration for a sensor"""
    sensor_id: str = Field(..., description="Unique sensor identifier")
    sensor_type: str = Field(..., description="Type of sensor")

    @field_validator("sensor_type")
    @classmethod
    def validate_sensor_type(cls, v: str) -> str:
        """Validate sensor type against known types"""
        if v not in SENSOR_TYPES:
            raise ValueError(
                f"Invalid sensor_type '{v}'. Must be one of: {SENSOR_TYPES}"
            )
        return v

    enabled: bool = Field(True, description="Whether sensor is active")
    trusted: bool = Field(False, description="Whether sensor is fully trusted (skip some validation)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional config")


class RecipientConfigModel(BaseModel):
    """Configuration for a downstream recipient"""
    recipient_id: str = Field(..., description="Unique identifier")
    recipient_type: str = Field(..., description="Type: bms, radio, etc.")
    
    # Access level instead of classification_clearance
    access_level: str = Field(..., description="Recipient's access level")
    
    @field_validator("access_level")
    @classmethod
    def validate_access_level(cls, v: str) -> str:
        """Validate access level against known levels"""
        if v not in ACCESS_LEVELS:
            raise ValueError(
                f"Invalid access_level '{v}'. Must be one of: {ACCESS_LEVELS}"
            )
        return v
    
    supported_formats: List[str] = Field(..., description="Supported output formats")
    
    @field_validator("supported_formats")
    @classmethod
    def validate_formats(cls, v: List[str]) -> List[str]:
        """Validate all formats are supported"""
        invalid = [fmt for fmt in v if fmt not in OUTPUT_FORMATS]
        if invalid:
            raise ValueError(
                f"Invalid formats: {invalid}. Must be from: {OUTPUT_FORMATS}"
            )
        return v
    
    connection_type: str = Field(..., description="mqtt, api, etc.")
    connection_config: Dict[str, Any] = Field(default_factory=dict)
    auto_disseminate: bool = Field(False, description="Auto-send without review")
    
    # Deception config for enemy_access
    deception_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Deception configuration if access_level is enemy_access"
    )


class LLMConfig(BaseModel):
    """LLM configuration (model-agnostic)"""
    provider: str = Field("openai", description="LLM provider: openai, anthropic, ollama")
    model: str = Field("gpt-4o", description="Model name")
    temperature: float = Field(0.0, description="Temperature for generation")
    max_tokens: Optional[int] = Field(None, description="Max tokens in response")
    api_key_env: str = Field("OPENAI_API_KEY", description="Env var for API key")
    base_url: Optional[str] = Field(None, description="Base URL (for Ollama, etc.)")


class MQTTConfig(BaseModel):
    """MQTT broker configuration"""
    host: str = Field("localhost", description="MQTT broker host")
    port: int = Field(1883, description="MQTT broker port")
    username: Optional[str] = Field(None, description="Username (if auth required)")
    password_env: Optional[str] = Field(None, description="Env var for password")
    client_id: str = Field("tifda-consumer", description="MQTT client ID")


class TIFDAConfig(BaseModel):
    """Main TIFDA configuration"""
    # System
    environment: str = Field("development", description="Environment: development, production")
    log_level: str = Field("INFO", description="Logging level")
    
    # LLM
    llm: LLMConfig = Field(default_factory=LLMConfig)
    
    # MQTT
    mqtt: MQTTConfig = Field(default_factory=MQTTConfig)
    
    # Sensors (loaded from sensors.yaml)
    sensors: Dict[str, SensorConfig] = Field(default_factory=dict)
    
    # Recipients (loaded from recipients.yaml)
    recipients: Dict[str, RecipientConfigModel] = Field(default_factory=dict)
    
    # Paths
    data_dir: Path = Field(Path("data"), description="Data directory")
    checkpoint_dir: Path = Field(Path("data/checkpoints"), description="Checkpoints")
    audit_log_dir: Path = Field(Path("data/audit_logs"), description="Audit logs")
    
    # Features
    enable_human_review: bool = Field(True, description="Enable HITL review")
    enable_auto_dissemination: bool = Field(False, description="Auto-disseminate without review")
    enable_mqtt: bool = Field(True, description="Enable MQTT integration")
    
    @field_validator("data_dir", "checkpoint_dir", "audit_log_dir")
    @classmethod
    def ensure_path_exists(cls, v: Path) -> Path:
        """Create directory if it doesn't exist"""
        v.mkdir(parents=True, exist_ok=True)
        return v


# ==================== CONFIGURATION LOADER ====================

class ConfigLoader:
    """Loads and manages TIFDA configuration"""
    
    def __init__(self, config_file: str = "configs/development.yaml"):
        """
        Initialize configuration loader
        
        Args:
            config_file: Path to main config file
        """
        self.config_file = Path(config_file)
        self.config: Optional[TIFDAConfig] = None
        
    def load(self) -> TIFDAConfig:
        """
        Load configuration from YAML files
        
        Returns:
            TIFDAConfig instance
        """
        # Load main config
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}
        else:
            print(f"⚠️  Config file not found: {self.config_file}, using defaults")
            config_data = {}
        
        # Create config object
        self.config = TIFDAConfig(**config_data)
        
        # Load sensors
        sensors_file = self.config_file.parent / "sensors.yaml"
        if sensors_file.exists():
            with open(sensors_file, 'r') as f:
                sensors_data = yaml.safe_load(f) or {}
                for sensor_id, sensor_config in sensors_data.get("sensors", {}).items():
                    self.config.sensors[sensor_id] = SensorConfig(
                        sensor_id=sensor_id,
                        **sensor_config
                    )
        
        # Load recipients
        recipients_file = self.config_file.parent / "recipients.yaml"
        if recipients_file.exists():
            with open(recipients_file, 'r') as f:
                recipients_data = yaml.safe_load(f) or {}
                for recipient_id, recipient_config in recipients_data.get("recipients", {}).items():
                    self.config.recipients[recipient_id] = RecipientConfigModel(
                        recipient_id=recipient_id,
                        **recipient_config
                    )
        
        print(f"✅ Configuration loaded from {self.config_file}")
        print(f"   Sensors: {len(self.config.sensors)}")
        print(f"   Recipients: {len(self.config.recipients)}")
        
        return self.config
    
    def get_sensor_config(self, sensor_id: str) -> Optional[SensorConfig]:
        """Get configuration for specific sensor"""
        if not self.config:
            self.load()
        return self.config.sensors.get(sensor_id)
    
    def get_recipient_config(self, recipient_id: str) -> Optional[RecipientConfigModel]:
        """Get configuration for specific recipient"""
        if not self.config:
            self.load()
        return self.config.recipients.get(recipient_id)
    
    def is_sensor_authorized(self, sensor_id: str) -> bool:
        """Check if sensor is authorized and enabled"""
        sensor_config = self.get_sensor_config(sensor_id)
        return sensor_config is not None and sensor_config.enabled


# ==================== GLOBAL CONFIG INSTANCE ====================

_config_loader: Optional[ConfigLoader] = None


def get_config(config_file: str = "configs/development.yaml") -> TIFDAConfig:
    """
    Get global configuration instance (singleton pattern)
    
    Args:
        config_file: Path to config file (only used on first call)
        
    Returns:
        TIFDAConfig instance
    """
    global _config_loader
    
    if _config_loader is None:
        _config_loader = ConfigLoader(config_file)
        _config_loader.load()
    
    return _config_loader.config


def reload_config(config_file: str = "configs/development.yaml") -> TIFDAConfig:
    """
    Force reload of configuration
    
    Args:
        config_file: Path to config file
        
    Returns:
        Reloaded TIFDAConfig instance
    """
    global _config_loader
    _config_loader = ConfigLoader(config_file)
    return _config_loader.load()