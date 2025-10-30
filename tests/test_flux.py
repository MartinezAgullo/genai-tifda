"""Test TIFDA flux end-to-end"""

# Imports needed for assertions
import unittest
# Add assertion on the base model type if needed, but dict checking is sufficient here
from src.models import ThreatAssessment, DisseminationDecision, OutgoingMessage

from src.tifda_app import run_pipeline
from src.core.config import get_config, register_recipient, RecipientConfigModel

# Configure MQTT (Ensuring the test environment setup is included)
config = get_config()
config.mqtt.host = "localhost"
config.mqtt.port = 1883

# Disable human review for CLI testing
config.enable_human_review = False

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
                "speed_kmh": 450,
                "heading": 270,
                "classification": "hostile"
            }
        ]
    }
}

print("🚀 Running TIFDA pipeline...\n")
# --- CAPTURE THE FINAL STATE ---
final_state = run_pipeline(sensor_input)
print("\n✅ Pipeline complete!")






# ===================================================================
# NODE EXECUTION ASSERTIONS (Verifying state transitions)
# ===================================================================

# 1. Firewall Node Check (firewall_node)
# Must pass for pipeline to continue.
assert final_state.get("firewall_passed") is True, \
    "FAIL: Firewall node blocked the message (firewall_passed is False)."

# 2. Parser/Normalizer Check (parser_node, normalizer_node)
# Checks that the parsed_entities list was populated.
assert "parsed_entities" in final_state and len(final_state["parsed_entities"]) == 1, \
    "FAIL: Parser/Normalizer did not produce exactly one entity."
# The parsed entity will be an EntityCOP object from src.models

# 3. Merge/COP Update Check (merge_node, cop_update_node)
# Assumes the parser creates an entity with an ID that the merger adds to the COP.
first_entity_id = final_state["parsed_entities"][0].entity_id
assert first_entity_id in final_state["cop_entities"], \
    "FAIL: Merge/COP Update node failed to add the entity to the COP."

# 4. Threat Evaluator Node Check (threat_evaluator_node)
# Asserts that the LLM-based evaluator ran and produced at least one assessment.
assert len(final_state.get("current_threats", [])) > 0, \
    "FAIL: Threat Evaluator node failed to generate a 'current_threats' assessment."

# --- DEBUG INSERTION START ---
print("\n--- DEBUG: Router Input Check ---")
print(f"Entities in COP: {len(final_state.get('cop_entities', {}))}")
print(f"Current Threats: {len(final_state.get('current_threats', []))}")

# **CRITICAL KEY**: The Human Review node's output:
approved_threats = final_state.get("approved_threats", [])
print(f"Approved Threats (Router Input): {len(approved_threats)}")

if len(approved_threats) > 0:
    print(f"  First Approved Threat Level: {approved_threats[0].threat_level}")
# --- DEBUG INSERTION END ---

# NOTE: Human Review is implicitly passed if the graph continues to Dissemination.
# Its output (approved_threats) is used as input for the next node.

# 5. Dissemination Router Check (dissemination_router_node)
# Asserts the router selected targets and created outgoing messages.
# The key for outgoing messages in the state is 'outgoing_messages'
assert len(final_state.get("outgoing_messages", [])) > 0, \
    "FAIL: Dissemination Router node failed to create 'outgoing_messages'."
# Check the log for an audit trail
assert len(final_state.get("dissemination_log", [])) > 0, \
    "FAIL: Dissemination Router did not populate the 'dissemination_log'."

# 6. Format Adapter Check (format_adapter_node)
# The output of this node is 'formatted_messages'
# This list contains the final data ready for the wire.
assert len(final_state.get("formatted_messages", [])) > 0, \
    "FAIL: Format Adapter node failed to create 'formatted_messages'."
# Ensure the format adapter used the registered recipient's format ('json' in this case)
assert any(msg.get("format") == "json" for msg in final_state.get("formatted_messages", [])), \
    "FAIL: Format Adapter did not create a message in the expected format (json)."

# 7. Transmission Node Check (transmission_node)
# The final log of the send attempt.
assert len(final_state.get("transmission_log", [])) > 0, \
    "FAIL: Transmission node failed to log the send attempt in 'transmission_log'."
# Check for success
successful_transmissions = sum(1 for log in final_state["transmission_log"] if log.get("success") is True)
assert successful_transmissions > 0, \
    "FAIL: Transmission node ran but reported no successful transmissions."


print("\n\n✨ ALL NODES VALIDATED: The TIFDA data flux completed successfully and verified all state changes.")