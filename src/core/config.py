"""
TIFDA Configuration Management
===============================

Simple configuration with sensible defaults.
Can be overridden programmatically if needed.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Literal
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
    trusted: bool = Field(False, description="Whether sensor is fully trusted")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional config")


class RecipientConfigModel(BaseModel):
    """Configuration for a downstream recipient"""
    recipient_id: str = Field(..., description="Unique identifier")
    recipient_type: str = Field(..., description="Type: bms, radio, etc.")
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
    deception_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Deception configuration if access_level is enemy_access"
    )


class LLMConfig(BaseModel):
    """LLM configuration"""
    provider: str = Field("openai", description="LLM provider: openai, anthropic, ollama")
    model: str = Field("gpt-4o", description="Model name")
    temperature: float = Field(0.0, description="Temperature for generation")
    max_tokens: Optional[int] = Field(4000, description="Max tokens in response")


class MQTTConfig(BaseModel):
    """MQTT broker configuration"""
    host: str = Field("localhost", description="MQTT broker host")
    port: int = Field(1883, description="MQTT broker port")
    username: Optional[str] = Field(None, description="Username")
    password: Optional[str] = Field(None, description="Password")
    client_id: str = Field("tifda-consumer", description="MQTT client ID")


class IntegrationConfig(BaseModel):
    """Integration configurations"""
    mapa_base_url: str = Field(
        "http://localhost:3000",
        description="Base URL for mapa-puntos-interes"
    )
    mapa_timeout: int = Field(5, description="HTTP timeout in seconds")
    mapa_max_retries: int = Field(3, description="Max retry attempts")
    mapa_auto_sync: bool = Field(True, description="Auto-sync entities to mapa")


class TIFDAConfig(BaseModel):
    """Main TIFDA configuration"""
    # System
    environment: str = Field("development", description="Environment")
    log_level: str = Field("INFO", description="Logging level")
    
    # LLM
    llm: LLMConfig = Field(default_factory=LLMConfig)
    
    # MQTT
    mqtt: MQTTConfig = Field(default_factory=MQTTConfig)
    
    # Integrations
    integrations: IntegrationConfig = Field(default_factory=IntegrationConfig)
    
    # Sensors (can be registered at runtime)
    sensors: Dict[str, SensorConfig] = Field(default_factory=dict)
    
    # Recipients (can be registered at runtime)
    recipients: Dict[str, RecipientConfigModel] = Field(default_factory=dict)
    
    # Paths
    data_dir: Path = Field(Path("data"), description="Data directory")
    checkpoint_dir: Path = Field(Path("data/checkpoints"), description="Checkpoints")
    audit_log_dir: Path = Field(Path("data/audit_logs"), description="Audit logs")
    
    # Feature Flags
    enable_human_review: bool = Field(True, description="Enable HITL review")
    enable_auto_dissemination: bool = Field(False, description="Auto-disseminate without review")
    enable_mqtt: bool = Field(True, description="Enable MQTT integration")
    
    @field_validator("data_dir", "checkpoint_dir", "audit_log_dir")
    @classmethod
    def ensure_path_exists(cls, v: Path) -> Path:
        """Create directory if it doesn't exist"""
        v.mkdir(parents=True, exist_ok=True)
        return v


# ==================== CONFIGURATION INSTANCE ====================

_config: Optional[TIFDAConfig] = None


def get_config() -> TIFDAConfig:
    """
    Get global configuration instance (singleton pattern).
    
    Uses sensible defaults. Can be overridden programmatically:
    
    Example:
        config = get_config()
        config.llm.model = "gpt-4o-mini"
        config.integrations.mapa_base_url = "http://remote-server:3000"
    
    Returns:
        TIFDAConfig instance
    """
    global _config
    
    if _config is None:
        _config = TIFDAConfig()
        print("✅ Configuration initialized with defaults")
    
    return _config


def set_config(config: TIFDAConfig):
    """
    Set global configuration instance.
    
    Args:
        config: TIFDAConfig instance to use
    """
    global _config
    _config = config
    print("✅ Configuration updated")


def register_sensor(sensor_config: SensorConfig):
    """
    Register a sensor at runtime.
    
    Args:
        sensor_config: SensorConfig to register
    """
    config = get_config()
    config.sensors[sensor_config.sensor_id] = sensor_config
    print(f"✅ Sensor registered: {sensor_config.sensor_id}")


def register_recipient(recipient_config: RecipientConfigModel):
    """
    Register a recipient at runtime.
    
    Args:
        recipient_config: RecipientConfigModel to register
    """
    config = get_config()
    config.recipients[recipient_config.recipient_id] = recipient_config
    print(f"✅ Recipient registered: {recipient_config.recipient_id}")


# ==================== EJEMPLO DE USO ====================

if __name__ == "__main__":
    # Get default config
    config = get_config()
    
    print(f"\n📋 Default Configuration:")
    print(f"  Environment: {config.environment}")
    print(f"  LLM Model: {config.llm.model}")
    print(f"  MQTT Host: {config.mqtt.host}:{config.mqtt.port}")
    print(f"  Mapa URL: {config.integrations.mapa_base_url}")
    print(f"  Data Dir: {config.data_dir}")
    
    # Register a sensor
    sensor = SensorConfig(
        sensor_id="radar_01",
        sensor_type="radar",
        enabled=True,
        trusted=True
    )
    register_sensor(sensor)
    
    # Register a recipient
    recipient = RecipientConfigModel(
        recipient_id="allied_bms_uk",
        recipient_type="bms",
        access_level="secret_access",
        supported_formats=["link16", "json"],
        connection_type="mqtt"
    )
    register_recipient(recipient)
    
    print(f"\n📊 Registered Components:")
    print(f"  Sensors: {list(config.sensors.keys())}")
    print(f"  Recipients: {list(config.recipients.keys())}")