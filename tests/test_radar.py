"""Test TIFDA with a simple radar event."""
import os
from dotenv import load_dotenv

from datetime import datetime
from src.tifda_app import tifda_app
from src.core.state import create_state_from_sensor_event
from src.models import SensorMessage

# Load environment variables from .env file
load_dotenv()

# Create a simple radar message
sensor_msg = SensorMessage(
    sensor_id="radar_01",
    sensor_type="radar",
    timestamp=datetime.utcnow(),
    data={
        "format": "asterix",
        "tracks": [
            {
                "track_id": "T001",
                "location": {"lat": 39.5, "lon": -0.4},
                "altitude_m": 5000,
                "speed_kmh": 450,
                "heading": 270,
                "classification": "unknown"
            }
        ]
    }
)

# Create initial state
print("🚀 Starting TIFDA pipeline...")
initial_state = create_state_from_sensor_event(sensor_msg)

# Run pipeline
result = tifda_app.invoke(initial_state)

# Check results
print("\n" + "="*70)
print("✅ PIPELINE COMPLETE!")
print("="*70)
print(f"📊 COP Size: {len(result['cop_entities'])} entities")
print(f"⚠️  Threats Detected: {len(result.get('current_threats', []))}")
print(f"👤 Threats Approved: {len(result.get('approved_threats', []))}")
print(f"📡 Messages Transmitted: {result.get('transmission_stats', {}).get('success', 0)}")
print("\n🎉 Intelligence successfully disseminated!")