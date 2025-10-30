"""Test TIFDA flux end-to-end"""

from src.tifda_app import run_pipeline
from src.core.config import get_config, register_recipient, RecipientConfigModel

# Configure MQTT
config = get_config()
config.mqtt.host = "localhost"
config.mqtt.port = 1883

# Register test recipient
register_recipient(RecipientConfigModel(
    recipient_id="command_post_001",
    recipient_type="command",
    access_level="secret_access",
    supported_formats=["json"],
    connection_type="mqtt",
    connection_config={
        "mqtt_topic": "tifda/output/dissemination_reports/command_post_001",
        "qos": 1
    }
))

# Test sensor input (dummy radar data)
sensor_input = {
    "sensor_id": "test_radar_01",
    "sensor_type": "radar",
    "data": {
        "format": "asterix",
        "system_id": "radar_system_01",
        "classification_level": "SECRET",
        "tracks": [
            {
                "track_id": "T001",
                "location": {"lat": 39.5, "lon": -0.4, "alt": 5000},
                "speed_kmh": 450,            # Speed of tracked object
                "heading": 270,              # Direction in degrees with respect to North of tracked object
                "classification": "unknown"
            }
        ]
    }
}

print("🚀 Running TIFDA pipeline...\n")
result = run_pipeline(sensor_input)
print("\n✅ Pipeline complete!")