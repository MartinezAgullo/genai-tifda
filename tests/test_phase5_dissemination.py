"""
TIFDA Phase 5 Comprehensive Test Suite
=======================================

Tests all dissemination scenarios:
1. Rule-based threat assessment (fast, no LLM)
2. LLM-based threat assessment (ambiguous cases)
3. Distance-based need-to-know (must_notify, never_notify, ambiguous)
4. Classification filtering and downgrading
5. Operational role matching
6. Emergency override
7. MQTT dissemination

Usage:
    # Terminal 1: Start MQTT broker (if needed)
    docker compose -f mqtt/docker-compose.yml up -d
    
    # Terminal 2: Start UI (optional, for HITL)
    uv run python -m src.ui.gradio_interface
    
    # Terminal 3: Start mapa-puntos-interes (optional, for COP visualization)
    cd /Users/pablo/Desktop/Scripts/mapa-puntos-interes/
    npm run dev
    
    # Terminal 4: Run tests
    uv run python -m tests.test_phase5_dissemination
    
    # Run specific test scenarios:
    uv run python -m tests.test_phase5_dissemination --scenario rule_based
    uv run python -m tests.test_phase5_dissemination --scenario distance
    uv run python -m tests.test_phase5_dissemination --scenario classification
    uv run python -m tests.test_phase5_dissemination --scenario emergency
    uv run python -m tests.test_phase5_dissemination --all

Prerequisites:
    1. Recipients configured in config/recipients.yaml
    2. Thresholds configured in config/threat_thresholds.yaml
    3. MQTT broker running (optional, tests work without)
"""

import logging
import sys
from datetime import datetime, timezone, UTC
from typing import Dict, Any

from src.core.init_config import initialize_config
from src.tifda_app import run_pipeline
from src.models import SensorMessage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== TEST SCENARIOS ====================

def print_section(title: str):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"{title}")
    print("=" * 80 + "\n")


def print_results(result: Dict[str, Any], scenario_name: str):
    """Print test results in a formatted way"""
    print_section(f"RESULTS: {scenario_name}")
    
    print(f"📊 Pipeline Execution:")
    print(f"   COP Entities: {len(result.get('cop_entities', {}))}")
    print(f"   Threats Detected: {len(result.get('current_threats', []))}")
    print(f"   Approved Threats: {len(result.get('approved_threats', []))}")
    print(f"   Rejected Threats: {len(result.get('rejected_threats', []))}")
    
    # Dissemination stats
    outgoing = result.get('outgoing_messages', [])
    print(f"\n📡 Dissemination:")
    print(f"   Messages Created: {len(outgoing)}")
    
    if outgoing:
        recipients = set(msg.recipient_id for msg in outgoing)
        print(f"   Unique Recipients: {len(recipients)}")
        print(f"   Recipients: {', '.join(sorted(recipients))}")
    
    # Show threat details
    if result.get('current_threats'):
        print(f"\n🎯 Threat Details:")
        for threat in result['current_threats']:
            print(f"   - {threat.threat_source_id}:")
            print(f"     Level: {threat.threat_level.upper()}")
            print(f"     Confidence: {threat.confidence:.1%}")
            print(f"     Affected: {len(threat.affected_entities)} entities")
            print(f"     Reasoning: {threat.reasoning[:100]}...")
    
    # Show dissemination decisions
    if outgoing:
        print(f"\n📤 Dissemination Decisions:")
        for msg in outgoing[:5]:  # Show first 5
            content = msg.content
            print(f"   → {msg.recipient_id}:")
            print(f"     Format: {msg.format_type}")
            print(f"     Priority: {content.get('priority', 'N/A')}")
            if len(outgoing) > 5:
                print(f"   ... and {len(outgoing) - 5} more")
                break
    
    print("\n" + "=" * 80)


def scenario_1_rule_based_obvious_threats():
    """
    Test 1: Rule-Based Threat Assessment (No LLM Needed)
    
    Tests:
    - Hostile missile → CRITICAL (obvious)
    - Friendly aircraft → NONE (obvious)
    - Should NOT call LLM for these cases
    """
    print_section("TEST 1: Rule-Based Obvious Threats")
    
    print("📋 Scenario:")
    print("   - Hostile missile detected (CRITICAL threat, no LLM needed)")
    print("   - Friendly aircraft detected (no threat, no LLM needed)")
    print("   - Expected: Fast rule-based assessment, no expensive LLM calls")
    print()
    
    sensor_msg = SensorMessage(
        sensor_id="radar_test_01",
        sensor_type="radar",
        timestamp=datetime.now(UTC),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_TEST",
            "tracks": [
                {
                    "track_id": "MISSILE_001",
                    "location": {"lat": 39.5, "lon": -0.4},
                    "altitude_m": 10000,
                    "speed_kmh": 2000,  # Very fast (missile)
                    "heading": 270,
                    "classification": "hostile"  # Hostile missile = CRITICAL
                },
                {
                    "track_id": "FRIENDLY_FIGHTER_001",
                    "location": {"lat": 39.6, "lon": -0.5},
                    "altitude_m": 8000,
                    "speed_kmh": 850,
                    "heading": 90,
                    "classification": "friendly"  # Friendly = NONE
                }
            ]
        }
    )
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat()
    })
    
    print_results(result, "Rule-Based Obvious Threats")
    
    # Validate
    threats = result.get('current_threats', [])
    print("\n✅ Validation:")
    print(f"   Expected 1 threat (missile), got {len(threats)}")
    
    if threats:
        missile_threat = [t for t in threats if 'MISSILE' in t.threat_source_id]
        if missile_threat:
            print(f"   ✅ Missile threat level: {missile_threat[0].threat_level}")
            print(f"   ✅ Expected: CRITICAL (rule-based, fast)")
    
    return result


def scenario_2_distance_based_must_notify():
    """
    Test 2: Distance-Based Must Notify
    
    Tests:
    - Hostile aircraft very close to base (<300km for hostile aircraft)
    - Should trigger MUST_NOTIFY (rule-based, no LLM)
    - Multiple recipients at different distances
    """
    print_section("TEST 2: Distance-Based Must Notify")
    
    print("📋 Scenario:")
    print("   - Hostile aircraft at 39.5, -0.4")
    print("   - Base Alpha at 39.4, 0.3 (~15km away)")
    print("   - Expected: MUST_NOTIFY base_alpha (distance < must_notify_km)")
    print()
    
    sensor_msg = SensorMessage(
        sensor_id="radar_valencia_02",
        sensor_type="radar",
        timestamp=datetime.now(UTC),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_VALENCIA",
            "tracks": [
                {
                    "track_id": "HOSTILE_FIGHTER_001",
                    "location": {"lat": 39.5, "lon": -0.4},  # ~15km from base
                    "altitude_m": 5000,
                    "speed_kmh": 850,
                    "heading": 270,  # Approaching
                    "classification": "hostile"
                }
            ]
        }
    )
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat()
    })
    
    print_results(result, "Distance-Based Must Notify")
    
    # Validate
    outgoing = result.get('outgoing_messages', [])
    print("\n✅ Validation:")
    print(f"   Messages sent: {len(outgoing)}")
    
    base_alpha_msgs = [m for m in outgoing if 'base_alpha' in m.recipient_id]
    if base_alpha_msgs:
        print(f"   ✅ base_alpha received {len(base_alpha_msgs)} message(s)")
        print(f"   ✅ Expected: MUST_NOTIFY (distance < 300km)")
    else:
        print(f"   ⚠️  base_alpha not in recipients (check recipients.yaml)")
    
    return result


def scenario_3_distance_based_never_notify():
    """
    Test 3: Distance-Based Never Notify
    
    Tests:
    - Hostile aircraft very far away (>600km)
    - Should trigger NEVER_NOTIFY (too far, rule-based)
    - Recipients far away should NOT receive message
    """
    print_section("TEST 3: Distance-Based Never Notify")
    
    print("📋 Scenario:")
    print("   - Hostile aircraft at 45.0, 5.0 (France, ~700km away)")
    print("   - All Spanish bases >600km away")
    print("   - Expected: NEVER_NOTIFY distant units (too far)")
    print()
    
    sensor_msg = SensorMessage(
        sensor_id="radar_distant_01",
        sensor_type="radar",
        timestamp=datetime.now(UTC),
        data={
            "format": "asterix",
            "system_id": "FR_RAD_PARIS",
            "tracks": [
                {
                    "track_id": "HOSTILE_FAR_001",
                    "location": {"lat": 45.0, "lon": 5.0},  # France (~700km from Valencia)
                    "altitude_m": 8000,
                    "speed_kmh": 800,
                    "heading": 180,
                    "classification": "hostile"
                }
            ]
        }
    )
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat()
    })
    
    print_results(result, "Distance-Based Never Notify")
    
    # Validate
    outgoing = result.get('outgoing_messages', [])
    print("\n✅ Validation:")
    print(f"   Messages sent: {len(outgoing)}")
    print(f"   Expected: Few or none to distant units")
    
    if outgoing:
        recipients = [m.recipient_id for m in outgoing]
        print(f"   Recipients: {', '.join(recipients)}")
        print(f"   Note: Command posts may still receive (they get everything)")
    
    return result


def scenario_4_classification_downgrading():
    """
    Test 4: Classification Filtering and Downgrading
    
    Tests:
    - TOP_SECRET entity
    - Recipient with SECRET clearance
    - Should downgrade entity (remove sensitive details)
    - Recipient with CONFIDENTIAL clearance should be blocked
    """
    print_section("TEST 4: Classification Downgrading")
    
    print("📋 Scenario:")
    print("   - TOP_SECRET hostile aircraft")
    print("   - Recipients with different clearances (TOP_SECRET, SECRET, CONFIDENTIAL)")
    print("   - Expected: Downgrade for SECRET, block for CONFIDENTIAL")
    print()
    
    sensor_msg = SensorMessage(
        sensor_id="radar_classified_01",
        sensor_type="radar",
        timestamp=datetime.now(UTC),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_CLASSIFIED",
            "tracks": [
                {
                    "track_id": "TOP_SECRET_TARGET",
                    "location": {"lat": 39.5, "lon": -0.4},
                    "altitude_m": 5000,
                    "speed_kmh": 900,
                    "heading": 270,
                    "classification": "hostile",
                    # This would be marked as TOP_SECRET in your normalizer
                }
            ]
        },
        metadata={
            "information_classification": "TOP_SECRET",
            "source": "classified_radar"
        }
    )
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat(),
        "metadata": sensor_msg.metadata
    })
    
    print_results(result, "Classification Downgrading")
    
    # Validate
    outgoing = result.get('outgoing_messages', [])
    print("\n✅ Validation:")
    
    if outgoing:
        print(f"   Messages sent: {len(outgoing)}")
        for msg in outgoing:
            print(f"   → {msg.recipient_id}: format={msg.format_type}")
    else:
        print(f"   ⚠️  No messages (all recipients may lack clearance)")
    
    return result


def scenario_5_operational_role_matching():
    """
    Test 5: Operational Role Matching
    
    Tests:
    - Aircraft threat
    - Air defense unit should receive (priority_entity_types match)
    - Ground unit should NOT receive (not their role)
    - Naval unit should NOT receive (not their role)
    """
    print_section("TEST 5: Operational Role Matching")
    
    print("📋 Scenario:")
    print("   - Unknown aircraft detected")
    print("   - Air defense units: SHOULD receive (operational role match)")
    print("   - Ground/naval units: Should NOT receive (irrelevant)")
    print()
    
    sensor_msg = SensorMessage(
        sensor_id="radar_coastal_03",
        sensor_type="radar",
        timestamp=datetime.now(UTC),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_COASTAL",
            "tracks": [
                {
                    "track_id": "UNKNOWN_AIRCRAFT_001",
                    "location": {"lat": 39.3, "lon": -0.2},
                    "altitude_m": 6000,
                    "speed_kmh": 700,
                    "heading": 45,
                    "classification": "unknown"
                }
            ]
        }
    )
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat()
    })
    
    print_results(result, "Operational Role Matching")
    
    # Validate
    outgoing = result.get('outgoing_messages', [])
    print("\n✅ Validation:")
    
    if outgoing:
        recipients = [m.recipient_id for m in outgoing]
        print(f"   Recipients: {', '.join(recipients)}")
        
        air_defense = [r for r in recipients if 'air' in r.lower() or 'defense' in r.lower()]
        if air_defense:
            print(f"   ✅ Air defense units received: {', '.join(air_defense)}")
    
    return result


def scenario_6_emergency_override():
    """
    Test 6: Emergency Override (Red Button)
    
    Tests:
    - Emergency override flag set to True
    - ALL recipients should receive ALL threats
    - Bypasses distance, classification, role matching
    """
    print_section("TEST 6: Emergency Override (Red Button)")
    
    print("📋 Scenario:")
    print("   - 🚨 EMERGENCY OVERRIDE ACTIVE 🚨")
    print("   - Multiple threats of different types")
    print("   - Expected: ALL recipients receive ALL threats")
    print("   - Bypasses: distance, classification, role matching")
    print()
    
    sensor_msg = SensorMessage(
        sensor_id="radar_emergency_01",
        sensor_type="radar",
        timestamp=datetime.now(UTC),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_EMERGENCY",
            "tracks": [
                {
                    "track_id": "THREAT_AIR",
                    "location": {"lat": 39.5, "lon": -0.4},
                    "altitude_m": 5000,
                    "speed_kmh": 850,
                    "heading": 270,
                    "classification": "hostile"
                },
                {
                    "track_id": "THREAT_GROUND",
                    "location": {"lat": 39.2, "lon": -0.6},
                    "altitude_m": 0,
                    "speed_kmh": 60,
                    "heading": 0,
                    "classification": "hostile"
                },
                {
                    "track_id": "THREAT_FAR",
                    "location": {"lat": 42.0, "lon": 2.0},  # Far away
                    "altitude_m": 3000,
                    "speed_kmh": 500,
                    "heading": 180,
                    "classification": "hostile"
                }
            ]
        }
    )
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat(),
        "emergency_override": True  # 🚨 RED BUTTON PRESSED
    })
    
    print_results(result, "Emergency Override")
    
    # Validate
    outgoing = result.get('outgoing_messages', [])
    print("\n✅ Validation:")
    print(f"   Messages sent: {len(outgoing)}")
    print(f"   Expected: MANY more than normal (all recipients)")
    
    if outgoing:
        recipients = set(m.recipient_id for m in outgoing)
        print(f"   Unique recipients: {len(recipients)}")
        print(f"   Recipients: {', '.join(sorted(recipients))}")
        print(f"   🚨 Emergency override bypassed all filters")
    
    return result


def scenario_7_mixed_threats_comprehensive():
    """
    Test 7: Comprehensive Mixed Threats
    
    Tests all logic paths:
    - Multiple entity types (aircraft, ground, ship)
    - Multiple classifications (hostile, unknown, neutral, friendly)
    - Various distances (close, medium, far)
    - Different speeds (fast, medium, slow)
    """
    print_section("TEST 7: Comprehensive Mixed Scenario")
    
    print("📋 Scenario:")
    print("   - Multiple threats of different types")
    print("   - Tests: rule-based, LLM, distance, classification, roles")
    print("   - Most comprehensive test of all Phase 5 logic")
    print()
    
    sensor_msg = SensorMessage(
        sensor_id="radar_comprehensive_01",
        sensor_type="radar",
        timestamp=datetime.now(UTC),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_MULTI",
            "tracks": [
                # Close hostile aircraft (MUST_NOTIFY air defense)
                {
                    "track_id": "CLOSE_HOSTILE",
                    "location": {"lat": 39.45, "lon": -0.35},  # Very close
                    "altitude_m": 5000,
                    "speed_kmh": 850,
                    "heading": 270,
                    "classification": "hostile"
                },
                # Medium distance unknown (LLM decides)
                {
                    "track_id": "MEDIUM_UNKNOWN",
                    "location": {"lat": 39.8, "lon": -0.8},  # ~50km
                    "altitude_m": 3000,
                    "speed_kmh": 400,
                    "heading": 90,
                    "classification": "unknown"
                },
                # Far hostile (NEVER_NOTIFY except command)
                {
                    "track_id": "FAR_HOSTILE",
                    "location": {"lat": 41.0, "lon": 1.0},  # ~300km
                    "altitude_m": 8000,
                    "speed_kmh": 700,
                    "heading": 180,
                    "classification": "hostile"
                },
                # Friendly (NONE threat)
                {
                    "track_id": "FRIENDLY_PATROL",
                    "location": {"lat": 39.5, "lon": -0.5},
                    "altitude_m": 4000,
                    "speed_kmh": 450,
                    "heading": 0,
                    "classification": "friendly"
                },
                # Neutral far (NONE threat)
                {
                    "track_id": "NEUTRAL_CIVILIAN",
                    "location": {"lat": 39.9, "lon": -0.2},
                    "altitude_m": 2000,
                    "speed_kmh": 300,
                    "heading": 45,
                    "classification": "neutral"
                }
            ]
        }
    )
    
    result = run_pipeline({
        "sensor_id": sensor_msg.sensor_id,
        "sensor_type": sensor_msg.sensor_type,
        "data": sensor_msg.data,
        "timestamp": sensor_msg.timestamp.isoformat()
    })
    
    print_results(result, "Comprehensive Mixed Scenario")
    
    # Validate
    threats = result.get('current_threats', [])
    outgoing = result.get('outgoing_messages', [])
    
    print("\n✅ Validation:")
    print(f"   Threats detected: {len(threats)}")
    print(f"   Expected: 2-3 (hostile and maybe unknown)")
    print(f"   Messages sent: {len(outgoing)}")
    print(f"   Expected: Varies based on distance/role matching")
    
    if threats:
        threat_levels = [t.threat_level for t in threats]
        print(f"   Threat levels: {', '.join(threat_levels)}")
    
    return result


# ==================== TEST RUNNER ====================

def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "█" * 80)
    print("█" + " " * 78 + "█")
    print("█" + "  TIFDA PHASE 5 - COMPREHENSIVE TEST SUITE".center(78) + "█")
    print("█" + " " * 78 + "█")
    print("█" * 80 + "\n")
    
    # Initialize config
    print("⚙️  Initializing TIFDA configuration...")
    config = initialize_config()
    print(f"✅ Config loaded")
    print(f"   HITL: {config.enable_human_review}")
    print(f"   MQTT: {config.enable_mqtt}")
    print(f"   Recipients: {len(config.recipients)}")
    print()
    
    # Run tests
    scenarios = [
        ("Rule-Based Threats", scenario_1_rule_based_obvious_threats),
        ("Distance: Must Notify", scenario_2_distance_based_must_notify),
        ("Distance: Never Notify", scenario_3_distance_based_never_notify),
        ("Classification", scenario_4_classification_downgrading),
        ("Operational Roles", scenario_5_operational_role_matching),
        ("Emergency Override", scenario_6_emergency_override),
        ("Comprehensive", scenario_7_mixed_threats_comprehensive),
    ]
    
    results = []
    for i, (name, test_func) in enumerate(scenarios, 1):
        print(f"\n{'▼' * 80}")
        print(f"TEST {i}/{len(scenarios)}: {name}")
        print(f"{'▼' * 80}\n")
        
        try:
            result = test_func()
            results.append((name, True, result))
            print(f"\n✅ TEST {i} PASSED: {name}")
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n❌ TEST {i} FAILED: {name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(scenarios):
            input("\n⏸️  Press ENTER to continue to next test...")
    
    # Summary
    print("\n" + "█" * 80)
    print("█" + "  TEST SUMMARY".center(78) + "█")
    print("█" * 80 + "\n")
    
    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed
    
    print(f"Total Tests: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print()
    
    for name, success, _ in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}  {name}")
    
    print("\n" + "█" * 80 + "\n")


if __name__ == "__main__":
    try:
        # Check command line arguments
        if len(sys.argv) > 1:
            scenario = sys.argv[1]
            
            if scenario == "--all":
                run_all_tests()
            elif scenario == "--rule_based" or scenario == "1":
                scenario_1_rule_based_obvious_threats()
            elif scenario == "--distance_must" or scenario == "2":
                scenario_2_distance_based_must_notify()
            elif scenario == "--distance_never" or scenario == "3":
                scenario_3_distance_based_never_notify()
            elif scenario == "--classification" or scenario == "4":
                scenario_4_classification_downgrading()
            elif scenario == "--roles" or scenario == "5":
                scenario_5_operational_role_matching()
            elif scenario == "--emergency" or scenario == "6":
                scenario_6_emergency_override()
            elif scenario == "--comprehensive" or scenario == "7":
                scenario_7_mixed_threats_comprehensive()
            else:
                print(f"Unknown scenario: {scenario}")
                print("Available scenarios: 1-7, --all, --rule_based, --distance_must, etc.")
        else:
            # No arguments: run all
            run_all_tests()
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()