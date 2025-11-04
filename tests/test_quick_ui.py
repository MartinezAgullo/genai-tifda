"""
Quick Test - Send Threat to UI
===============================

This sends a single critical threat to test the UI integration.
The 'data' structure has been adapted to a dictionary 
to match the Pydantic SensorMessage model.

Usage:
    # Terminal 1: Start UI
    uv run python -m src.ui.gradio_interface
    
    # Terminal 2: Run this test
    uv run python -m tests.test_quick_ui
"""

import logging
from datetime import datetime
from src.core.init_config import initialize_config
from src.tifda_app import run_pipeline
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def quick_ui_test():
    """Send a single threat to UI for testing"""
    
    print("\n" + "=" * 80)
    print("QUICK UI TEST - Sending Critical Threat")
    print("=" * 80 + "\n")
    
    # Initialize config
    config = initialize_config()
    
    print(f"✅ Config initialized")
    print(f"   HITL Enabled: {config.enable_human_review}")
    print(f"   Timeout: {config.auto_approve_timeout_seconds}s")
    print(f"   UI: http://localhost:{config.ui_port}")
    print()
    
    # Create a critical threat scenario
    # *** ADAPTATION START: 'data' is now a dictionary (Dict[str, Any]) ***
    sensor_data: Dict[str, Any] = {
        # Using a simplified ASTERIX-like structure for the radar data
        "format": "structured_threat_report", # A custom format identifier
        "system_id": "ES_RAD_101",
        "raw_alert": "CRITICAL ALERT: Hostile military aircraft detected",
        "tracks": [
            {
                "track_id": "T001",
                "location": {"lat": 39.5, "lon": -0.4},
                "altitude_m": 5000,
                "speed_kmh": 850,
                "heading": 270,
                "classification": "HOSTILE",
                "quality": {
                    "accuracy_m": 50,
                    "plot_count": 5,
                    "ssr_code": "NO_IFF"
                },
                # Additional threat-specific details
                "assessment": {
                    "distance_to_base_km": 15,
                    "time_to_threat_range_min": 2,
                    "recommended_action": "IMMEDIATE ALERT"
                }
            }
        ],
        "summary": "Hostile aircraft on direct intercept course towards base_alpha."
    }
    
    sensor_input = {
        "sensor_id": "radar_valencia_01",
        "sensor_type": "radar",
        "data": sensor_data, # Pass the structured dictionary
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": {
            "priority": "critical",
            "test": True,
            "scenario": "hostile_aircraft_intercept"
        }
    }
    # *** ADAPTATION END ***
    
    print("📡 Sending CRITICAL threat to pipeline...")
    print(f"   Sensor: {sensor_input['sensor_id']}")
    print(f"   Scenario: Hostile aircraft on intercept course")
    print()
    
    if config.enable_human_review:
        print("⏳ Pipeline will WAIT for your review in the UI")
        print(f"   Check: http://localhost:{config.ui_port}")
        print(f"   Timeout: {config.auto_approve_timeout_seconds}s")
        print()
        print("👉 Go review the threat in your browser now!")
        print()
    
    # Run pipeline
    print("🚀 Running pipeline...")
    # The run_pipeline function should now successfully create a SensorMessage 
    # as the 'data' field is a dictionary.
    result = run_pipeline(sensor_input) 
    
    # Show results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"✅ COP Entities: {len(result.get('cop_entities', {}))}")
    print(f"🎯 Threats Detected: {len(result.get('current_threats', []))}")
    print(f"✅ Approved: {len(result.get('approved_threats', []))}")
    print(f"❌ Rejected: {len(result.get('rejected_threats', []))}")
    
    if result.get('approved_threats'):
        print(f"\n✅ Approved Threats:")
        for threat in result['approved_threats']:
            print(f"   - {threat.threat_source_id}")
            print(f"     Level: {threat.threat_level}")
            print(f"     Confidence: {threat.confidence:.1%}")
    
    if result.get('rejected_threats'):
        print(f"\n❌ Rejected Threats:")
        for threat in result['rejected_threats']:
            print(f"   - {threat.threat_source_id}")
            print(f"     Level: {threat.threat_level}")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80 + "\n")
    
    print("Check the Review History tab in the UI to see your decision!")


if __name__ == "__main__":
    try:
        quick_ui_test()
    except KeyboardInterrupt:
        print("\n\n❌ Test interrupted")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()