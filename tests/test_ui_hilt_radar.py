"""
HITL Test with Correct ASTERIX Format
======================================

This test uses the correct ASTERIX format that your parsers recognize.
It will properly create threats and send them to the UI for review.

Usage:
    # Terminal 1: Start UI
    uv run python -m src.ui.gradio_interface
    
    # Terminal 2: Run this test
    uv run python -m tests.test_ui_hilt_radar

    # Terminal 3: Check mapa puntos interes
    cd /Users/pablo/Desktop/Scripts/mapa-puntos-interes/
    docker compose up -d
    npm run dev

    To ensure that the mapa puntos intere runs properly it is necessary
    to initialise the PostgreSQL. Follow this steps (only first time):

        # 1. Start Docker Desktop
        open -a Docker
        # Wait ~30 seconds for Docker to start

        # 2. Start PostgreSQL container
        cd /Users/pablo/Desktop/Scripts/mapa-puntos-interes
        docker compose up -d

        # 3. Initialize database
        node scripts/init-db.js

        # 4. Start mapa server
        npm run dev

"""

import logging
from datetime import datetime
from src.core.init_config import initialize_config
from src.tifda_app import run_pipeline
from src.models import SensorMessage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_hitl_critical_threat():
    """Test HITL with a critical hostile aircraft"""
    
    print("\n" + "=" * 80)
    print("HITL TEST - Critical Hostile Aircraft (ASTERIX Format)")
    print("=" * 80 + "\n")
    
    # Initialize config
    config = initialize_config()
    
    print(f"✅ Config initialized")
    print(f"   HITL Enabled: {config.enable_human_review}")
    print(f"   Timeout: {config.auto_approve_timeout_seconds}s")
    print(f"   UI: http://localhost:{config.ui_port}")
    print()
    
    # Create ASTERIX radar message with HOSTILE aircraft
    sensor_msg = SensorMessage(
        sensor_id="radar_valencia_01",
        sensor_type="radar",
        timestamp=datetime.utcnow(),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_VALENCIA",
            "tracks": [
                {
                    "track_id": "T001_HOSTILE",
                    "location": {"lat": 39.5, "lon": -0.4},
                    "altitude_m": 5000,
                    "speed_kmh": 850,  # Fast military speed
                    "heading": 270,  # Towards base
                    "classification": "hostile"  # THIS TRIGGERS THREAT!
                },
                {
                    "track_id": "T002_UNKNOWN",
                    "location": {"lat": 39.52, "lon": -0.38},
                    "altitude_m": 3000,
                    "speed_kmh": 600,
                    "heading": 180,
                    "classification": "unknown"
                }
            ]
        }
    )
    
    print("📡 Sending ASTERIX radar data with HOSTILE aircraft...")
    print(f"   Sensor: {sensor_msg.sensor_id}")
    print(f"   Tracks: 2 (1 hostile, 1 unknown)")
    print()
    
    if config.enable_human_review:
        print("⏳ Pipeline will WAIT for your review in the UI")
        print(f"   Check: http://localhost:{config.ui_port}")
        print(f"   Timeout: {config.auto_approve_timeout_seconds}s")
        print()
        print("👉 REFRESH YOUR BROWSER to see the threats!")
        print()
    
    # Run pipeline
    print("🚀 Running pipeline...")
    print()
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat()
    })
    
    # Show results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"✅ COP Entities: {len(result.get('cop_entities', {}))}")
    print(f"🎯 Threats Detected: {len(result.get('current_threats', []))}")
    print(f"✅ Approved: {len(result.get('approved_threats', []))}")
    print(f"❌ Rejected: {len(result.get('rejected_threats', []))}")
    print(f"📡 Transmissions: {len(result.get('transmission_log', []))}")
    
    if result.get('cop_entities'):
        print(f"\n📋 COP Entities:")
        for entity_id, entity in result['cop_entities'].items():
            print(f"   - {entity_id}")
            print(f"     Type: {entity.entity_type}")
            print(f"     Classification: {entity.classification}")
    
    if result.get('current_threats'):
        print(f"\n🎯 Threats Detected:")
        for threat in result['current_threats']:
            print(f"   - {threat.threat_source_id}")
            print(f"     Level: {threat.threat_level.upper()}")
            print(f"     Confidence: {threat.confidence:.1%}")
            print(f"     Affected: {', '.join(threat.affected_entities)}")
    
    if result.get('approved_threats'):
        print(f"\n✅ Approved Threats:")
        for threat in result['approved_threats']:
            print(f"   - {threat.threat_source_id}")
            print(f"     Level: {threat.threat_level}")
    
    if result.get('rejected_threats'):
        print(f"\n❌ Rejected Threats:")
        for threat in result['rejected_threats']:
            print(f"   - {threat.threat_source_id}")
            print(f"     Level: {threat.threat_level}")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80 + "\n")
    
    print("💡 Check the Review History tab in the UI to see your decisions!")


def test_hitl_multiple_threats():
    """Test HITL with multiple threats"""
    
    print("\n" + "=" * 80)
    print("HITL TEST - Multiple Threats")
    print("=" * 80 + "\n")
    
    config = initialize_config()
    
    # Create message with multiple potential threats
    sensor_msg = SensorMessage(
        sensor_id="radar_coastal_01",
        sensor_type="radar",
        timestamp=datetime.utcnow(),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_COASTAL",
            "tracks": [
                {
                    "track_id": "SHIP_001",
                    "location": {"lat": 39.2, "lon": -0.1},
                    "altitude_m": 0,  # Sea level
                    "speed_kmh": 55,  # Fast for a ship
                    "heading": 180,
                    "classification": "unknown"  # Unknown vessel
                },
                {
                    "track_id": "AIR_001",
                    "location": {"lat": 39.6, "lon": -0.5},
                    "altitude_m": 8000,
                    "speed_kmh": 750,
                    "heading": 90,
                    "classification": "unknown"
                },
                {
                    "track_id": "FRIENDLY_001",
                    "location": {"lat": 39.45, "lon": -0.35},
                    "altitude_m": 3000,
                    "speed_kmh": 400,
                    "heading": 0,
                    "classification": "friendly"
                }
            ]
        }
    )
    
    print("📡 Sending radar data with multiple tracks...")
    print(f"   Tracks: 3 (2 unknown, 1 friendly)")
    print()
    
    if config.enable_human_review:
        print("⏳ Waiting for your review...")
        print()
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat()
    })
    
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"✅ COP Entities: {len(result.get('cop_entities', {}))}")
    print(f"🎯 Threats: {len(result.get('current_threats', []))}")
    print(f"✅ Approved: {len(result.get('approved_threats', []))}")
    print(f"❌ Rejected: {len(result.get('rejected_threats', []))}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    import sys
    
    try:
        # Run first test
        test_hitl_critical_threat()
        
        # Ask if user wants to run second test
        if len(sys.argv) > 1 and sys.argv[1] == "--multiple":
            print("\n\n")
            input("Press ENTER to run second test (multiple threats)...")
            test_hitl_multiple_threats()
            
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()