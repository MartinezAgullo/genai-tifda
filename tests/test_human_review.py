"""
Test Human Review Node with Gradio UI
======================================

This test sends threats through the pipeline and waits for human review.
Make sure the Gradio UI is running before executing this test.
"""

import logging
from datetime import datetime
from src.tifda_app import run_pipeline
from src.core.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_human_review_integration():
    """Test the complete pipeline with human review"""
    
    print("\n" + "=" * 70)
    print("HUMAN REVIEW INTEGRATION TEST")
    print("=" * 70 + "\n")
    
    # Get config and ensure HITL is enabled
    config = get_config()
    print(f"Config: enable_human_review = {config.enable_human_review}")
    print(f"Config: auto_approve_timeout_seconds = {config.auto_approve_timeout_seconds}")
    print(f"Config: reviewer_id = {config.reviewer_id}")
    print("")
    
    if not config.enable_human_review:
        print("⚠️  WARNING: Human review is DISABLED")
        print("   Set config.enable_human_review = True to test UI")
        print("")
    
    # Test data: Critical threat that should trigger review
    test_cases = [
        {
            "name": "Critical Threat - Hostile Aircraft",
            "sensor_id": "radar_valencia",
            "sensor_type": "radar",
            "data": """
            Unknown military aircraft detected at 39.5N, 0.4W
            Altitude: 5000 meters
            Speed: 850 km/h (fast, military speed)
            Heading: 270 degrees (towards our base)
            Classification: Unknown (no transponder, military profile)
            Distance to base_alpha: 15 km
            """,
            "metadata": {
                "priority": "critical",
                "test": True
            }
        },
        {
            "name": "High Threat - Unknown Vessel",
            "sensor_id": "coastal_radar_01",
            "sensor_type": "radar",
            "data": """
            Unknown naval vessel at 39.2N, 0.1W
            Speed: 30 knots
            Course: 180 degrees
            No AIS transponder
            Large radar signature
            """,
            "metadata": {
                "priority": "high",
                "test": True
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"TEST CASE {i}/{len(test_cases)}: {test_case['name']}")
        print(f"{'=' * 70}\n")
        
        sensor_input = {
            "sensor_id": test_case["sensor_id"],
            "sensor_type": test_case["sensor_type"],
            "data": test_case["data"],
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": test_case["metadata"]
        }
        
        print(f"📡 Sending sensor data to pipeline...")
        print(f"   Sensor: {sensor_input['sensor_id']}")
        print(f"   Type: {sensor_input['sensor_type']}")
        print("")
        
        if config.enable_human_review:
            print("⏳ Pipeline will wait for human review in Gradio UI")
            print(f"   Visit: http://localhost:{config.ui_port}")
            print(f"   Timeout: {config.auto_approve_timeout_seconds}s")
            print("")
        
        # Run pipeline
        result = run_pipeline(sensor_input)
        
        # Print results
        print(f"\n{'=' * 70}")
        print(f"RESULTS - Test Case {i}")
        print(f"{'=' * 70}")
        print(f"✅ COP Entities: {len(result.get('cop_entities', {}))}")
        print(f"🎯 Threats Detected: {len(result.get('current_threats', []))}")
        print(f"✅ Approved Threats: {len(result.get('approved_threats', []))}")
        print(f"❌ Rejected Threats: {len(result.get('rejected_threats', []))}")
        print(f"📡 Transmissions: {len(result.get('transmission_log', []))}")
        
        # Show approved threats
        if result.get('approved_threats'):
            print(f"\nApproved Threats:")
            for threat in result['approved_threats']:
                print(f"  - {threat.threat_source_id} ({threat.threat_level})")
        
        # Show rejected threats
        if result.get('rejected_threats'):
            print(f"\nRejected Threats:")
            for threat in result['rejected_threats']:
                print(f"  - {threat.threat_source_id} ({threat.threat_level})")
        
        print(f"{'=' * 70}\n")
    
    print("\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_human_review_integration()