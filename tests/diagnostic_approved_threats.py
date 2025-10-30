"""
Diagnostic script to trace state through TIFDA pipeline
Specifically tracking approved_threats issue
"""

from src.core.config import get_config, register_recipient, RecipientConfigModel
from src.core.state import create_initial_state
from src.nodes.threat_evaluator_node import threat_evaluator_node
from src.nodes.human_review_node import human_review_node
from datetime import datetime

print("=" * 70)
print("🔍 DIAGNOSTIC: Tracking approved_threats through pipeline")
print("=" * 70)

# Configure
config = get_config()
config.mqtt.host = "localhost"
config.mqtt.port = 1883
config.enable_human_review = False  # BYPASS MODE

print(f"\n✅ Config set:")
print(f"   enable_human_review = {config.enable_human_review}")

# Register test recipient
TEST_RECIPIENT_ID = "command_post_001"
register_recipient(RecipientConfigModel(
    recipient_id=TEST_RECIPIENT_ID,
    recipient_type="command",
    access_level="secret_access",
    supported_formats=["json"],
    connection_type="mqtt",
    connection_config={
        "mqtt_topic": "tifda/output/dissemination_reports/command_post_001",
        "qos": 1
    }
))
print(f"✅ Recipient registered: {TEST_RECIPIENT_ID}")

# Create a minimal state with a threat
state = create_initial_state()
state["sensor_metadata"] = {"sensor_id": "test_radar"}

# Manually create a threat assessment (simulating threat_evaluator output)
from src.models import ThreatAssessment

test_threat = ThreatAssessment(
    assessment_id="test_threat_001",
    threat_level="high",
    affected_entities=["base_alpha"],
    threat_source_id="hostile_aircraft_001",
    reasoning="Test hostile aircraft approaching base",
    confidence=0.92,
    timestamp=datetime.utcnow()
)

state["current_threats"] = [test_threat]

print(f"\n📊 Initial state prepared:")
print(f"   current_threats: {len(state['current_threats'])}")
print(f"   First threat: {state['current_threats'][0].threat_source_id}")
print(f"   Threat level: {state['current_threats'][0].threat_level}")

# Now run human_review_node
print(f"\n" + "=" * 70)
print("🎯 Running human_review_node...")
print("=" * 70)

result = human_review_node(state)

print(f"\n" + "=" * 70)
print("📊 RESULT from human_review_node:")
print("=" * 70)
print(f"   Keys returned: {result.keys()}")
print(f"   approved_threats: {len(result.get('approved_threats', []))}")
print(f"   rejected_threats: {len(result.get('rejected_threats', []))}")

if result.get('approved_threats'):
    print(f"\n   ✅ Approved threats:")
    for threat in result['approved_threats']:
        print(f"      - {threat.threat_source_id} ({threat.threat_level})")
else:
    print(f"\n   ❌ NO APPROVED THREATS!")
    print(f"   This is the bug - should have 1 approved threat")

# Check if state was updated
print(f"\n" + "=" * 70)
print("🔍 Checking state update:")
print("=" * 70)

# In LangGraph, the return dict should update the state
# Let's manually update it to simulate what LangGraph does
for key, value in result.items():
    state[key] = value

print(f"   After manual state update:")
print(f"   state['approved_threats']: {len(state.get('approved_threats', []))}")
print(f"   state['current_threats']: {len(state.get('current_threats', []))}")

if state.get('approved_threats'):
    print(f"\n   ✅ State HAS approved_threats after update")
    print(f"      Count: {len(state['approved_threats'])}")
else:
    print(f"\n   ❌ State STILL MISSING approved_threats")
    print(f"      This means the return value is wrong")

print("\n" + "=" * 70)
print("🎯 DIAGNOSIS COMPLETE")
print("=" * 70)