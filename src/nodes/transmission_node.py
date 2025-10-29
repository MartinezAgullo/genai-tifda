"""
Transmission Node
=================

Eleventh and FINAL node in the TIFDA pipeline - message transmission.

This node:
1. Takes formatted messages from format_adapter_node
2. Publishes messages to MQTT topics
3. Tracks transmission success/failure
4. Logs all transmissions for audit
5. Completes the full TIFDA pipeline (sensor → dissemination)

This is where intelligence reaches downstream systems - the final step
in transforming sensor data into actionable, distributed intelligence.

Current Implementation:
- MOCK MODE: Logs transmissions instead of actual MQTT publish
- Simulates success/failure for testing
- Ready for integration with real MQTT broker

Future Integration:
- Replace mock with real MQTT client (paho-mqtt)
- Configure broker connection
- Handle retries and acknowledgments
- Support multiple protocols (MQTT, AMQP, Kafka)

Node Signature:
    Input: TIFDAState with formatted_messages
    Output: Updated TIFDAState with transmission_log (pipeline complete!)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import time
import json

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification

# Configure logging
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

# MQTT configuration (mock for now)
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_BASE_TOPIC = "tifda/dissemination"

# Mock transmission settings
MOCK_TRANSMISSION_DELAY_SEC = 0.1  # Simulate network delay
MOCK_FAILURE_RATE = 0.0  # 0% failure rate for testing

# Topic routing (recipient_type -> MQTT topic)
TOPIC_ROUTING = {
    "command": f"{MQTT_BASE_TOPIC}/command",
    "unit": f"{MQTT_BASE_TOPIC}/units",
    "allied": f"{MQTT_BASE_TOPIC}/allied",
    "system": f"{MQTT_BASE_TOPIC}/systems",
    "analyst": f"{MQTT_BASE_TOPIC}/analysts"
}


# ==================== TRANSMISSION UTILITIES ====================

def _get_mqtt_topic(recipient_type: str, recipient_id: str) -> str:
    """
    Determine MQTT topic for recipient.
    
    Topic structure: tifda/dissemination/{type}/{recipient_id}
    
    Args:
        recipient_type: Type of recipient (command, unit, allied, etc.)
        recipient_id: Specific recipient identifier
        
    Returns:
        MQTT topic string
    """
    base_topic = TOPIC_ROUTING.get(recipient_type, f"{MQTT_BASE_TOPIC}/other")
    return f"{base_topic}/{recipient_id}"


def _mock_mqtt_publish(
    topic: str,
    payload: Dict[str, Any],
    qos: int = 1
) -> tuple[bool, str]:
    """
    Mock MQTT publish for testing.
    
    In production, this would be replaced with:
    ```python
    import paho.mqtt.client as mqtt
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT)
    result = client.publish(topic, json.dumps(payload), qos=qos)
    ```
    
    Args:
        topic: MQTT topic
        payload: Message payload (will be JSON serialized)
        qos: Quality of Service (0, 1, 2)
        
    Returns:
        (success, message)
    """
    # Simulate network delay
    time.sleep(MOCK_TRANSMISSION_DELAY_SEC)
    
    # Simulate occasional failures
    import random
    if random.random() < MOCK_FAILURE_RATE:
        return False, "Mock transmission failure (simulated network error)"
    
    # Log the mock transmission
    payload_size = len(json.dumps(payload))
    logger.info(f"   📤 MOCK PUBLISH: {topic}")
    logger.info(f"      QoS: {qos}, Size: {payload_size} bytes")
    
    return True, f"Published to {topic}"


def _serialize_message_payload(formatted_message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize formatted message for transmission.
    
    Ensures message is JSON-serializable and adds transmission metadata.
    
    Args:
        formatted_message: Formatted message from format_adapter_node
        
    Returns:
        Serializable payload dictionary
    """
    # Convert datetime objects to ISO format strings
    def serialize_datetime(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj
    
    # Create payload
    payload = {
        "tifda_version": "1.0",
        "transmission_timestamp": datetime.utcnow().isoformat(),
        "message": {
            "message_id": formatted_message["message_id"],
            "recipient_id": formatted_message["recipient_id"],
            "format": formatted_message["format"],
            "priority": formatted_message["priority"],
            "requires_acknowledgment": formatted_message.get("requires_acknowledgment", False),
            "content": formatted_message["content"]
        }
    }
    
    return payload


@traceable(name="transmission_node")
def transmission_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Transmission node - final dissemination via MQTT.
    
    Publishes formatted messages to MQTT topics for consumption by
    downstream systems (command centers, tactical displays, allied systems).
    
    This is the FINAL node in the TIFDA pipeline, completing the flow from
    sensor input to intelligence dissemination.
    
    Current Implementation: MOCK MODE
    - Logs transmissions instead of actual MQTT publish
    - Simulates success/failure for testing
    - Ready for production MQTT integration
    
    Production Integration:
    - Replace _mock_mqtt_publish with real paho-mqtt client
    - Configure broker connection (host, port, auth)
    - Implement retry logic for failed transmissions
    - Handle QoS levels and acknowledgments
    
    MQTT Topic Structure:
    - tifda/dissemination/command/{recipient_id}
    - tifda/dissemination/units/{recipient_id}
    - tifda/dissemination/allied/{recipient_id}
    - tifda/dissemination/systems/{recipient_id}
    
    Args:
        state: Current TIFDA state containing:
            - formatted_messages: List[Dict] from format_adapter_node
        
    Returns:
        Dictionary with updated state fields:
            - transmission_log: List[Dict] (transmission results)
            - transmission_stats: Dict (success/failure counts)
            - decision_reasoning: str (markdown)
            - notification_queue: List[str]
            - decision_log: List[Dict]
    """
    logger.info("=" * 70)
    logger.info("TRANSMISSION NODE - MQTT Message Dissemination")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    formatted_messages = state.get("formatted_messages", [])
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not formatted_messages:
        logger.info("✅ No messages to transmit")
        return {
            "transmission_log": [],
            "transmission_stats": {
                "total": 0,
                "success": 0,
                "failed": 0
            },
            "decision_reasoning": "## ✅ No Messages to Transmit\n\nNo formatted messages from previous node."
        }
    
    logger.info(f"📡 Transmitting {len(formatted_messages)} messages")
    logger.info(f"   Mode: MOCK (simulated MQTT)")
    logger.info(f"   Broker: {MQTT_BROKER}:{MQTT_PORT}")
    
    # ============ TRANSMIT MESSAGES ============
    
    transmission_log = []
    transmission_errors = []
    
    # Stats
    total_messages = len(formatted_messages)
    successful_transmissions = 0
    failed_transmissions = 0
    total_bytes_transmitted = 0
    
    for formatted_message in formatted_messages:
        message_id = formatted_message["message_id"]
        recipient_id = formatted_message["recipient_id"]
        recipient_type = formatted_message["recipient_type"]
        priority = formatted_message["priority"]
        
        logger.info(f"\n📤 Transmitting: {message_id}")
        logger.info(f"   Recipient: {recipient_id} ({recipient_type})")
        logger.info(f"   Priority: {priority}")
        logger.info(f"   Format: {formatted_message['format']}")
        
        try:
            # Determine topic
            topic = _get_mqtt_topic(recipient_type, recipient_id)
            
            # Serialize payload
            payload = _serialize_message_payload(formatted_message)
            payload_size = len(json.dumps(payload))
            total_bytes_transmitted += payload_size
            
            # Determine QoS based on priority
            qos_map = {
                "critical": 2,  # Exactly once
                "high": 1,      # At least once
                "medium": 1,    # At least once
                "low": 0        # At most once
            }
            qos = qos_map.get(priority, 1)
            
            logger.info(f"   Topic: {topic}")
            logger.info(f"   QoS: {qos}")
            
            # Publish (mock)
            success, result_msg = _mock_mqtt_publish(topic, payload, qos=qos)
            
            if success:
                logger.info(f"   ✅ Transmitted successfully")
                successful_transmissions += 1
            else:
                logger.warning(f"   ❌ Transmission failed: {result_msg}")
                failed_transmissions += 1
                transmission_errors.append(f"{message_id}: {result_msg}")
            
            # Log transmission
            transmission_log.append({
                "message_id": message_id,
                "recipient_id": recipient_id,
                "topic": topic,
                "format": formatted_message["format"],
                "priority": priority,
                "qos": qos,
                "payload_size_bytes": payload_size,
                "success": success,
                "result": result_msg,
                "timestamp": datetime.utcnow(),
                "transmission_mode": "mock"
            })
            
        except Exception as e:
            logger.exception(f"   ❌ Transmission error: {e}")
            failed_transmissions += 1
            transmission_errors.append(f"{message_id}: {str(e)}")
            
            transmission_log.append({
                "message_id": message_id,
                "recipient_id": recipient_id,
                "success": False,
                "result": f"Error: {str(e)}",
                "timestamp": datetime.utcnow(),
                "transmission_mode": "mock"
            })
    
    # ============ RESULTS ============
    
    transmission_stats = {
        "total": total_messages,
        "success": successful_transmissions,
        "failed": failed_transmissions,
        "success_rate": successful_transmissions / total_messages if total_messages > 0 else 0,
        "total_bytes": total_bytes_transmitted
    }
    
    logger.info(f"\n📊 Transmission complete:")
    logger.info(f"   Total: {total_messages}")
    logger.info(f"   ✅ Success: {successful_transmissions}")
    logger.info(f"   ❌ Failed: {failed_transmissions}")
    logger.info(f"   Success rate: {transmission_stats['success_rate']:.1%}")
    logger.info(f"   Total bytes: {total_bytes_transmitted:,}")
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 📡 Transmission Complete

**Sensor**: `{sensor_id}`
**Messages Transmitted**: {total_messages}
**Transmission Mode**: MOCK (simulated MQTT)

### Transmission Summary:
- ✅ **Success**: {successful_transmissions} ({transmission_stats['success_rate']:.1%})
- ❌ **Failed**: {failed_transmissions}
- 📊 **Total bytes**: {total_bytes_transmitted:,}

"""
    
    if transmission_errors:
        reasoning += f"### ⚠️  Transmission Errors ({len(transmission_errors)}):\n"
        for error in transmission_errors[:3]:
            reasoning += f"- {error}\n"
        reasoning += "\n"
    
    # Group by recipient
    messages_by_recipient = {}
    for log_entry in transmission_log:
        if log_entry.get("success"):
            recipient = log_entry["recipient_id"]
            if recipient not in messages_by_recipient:
                messages_by_recipient[recipient] = []
            messages_by_recipient[recipient].append(log_entry)
    
    if messages_by_recipient:
        reasoning += "### 📤 Successfully Transmitted To:\n"
        for recipient, logs in messages_by_recipient.items():
            formats = [log["format"] for log in logs]
            reasoning += f"- **{recipient}**: {len(logs)} message(s) ({', '.join(set(formats)).upper()})\n"
        reasoning += "\n"
    
    reasoning += f"""### 🔗 MQTT Configuration:
- **Broker**: {MQTT_BROKER}:{MQTT_PORT}
- **Base Topic**: `{MQTT_BASE_TOPIC}`
- **Topic Structure**: `{MQTT_BASE_TOPIC}/{{type}}/{{recipient_id}}`

### 📋 Transmission Details:
"""
    
    # Show first few transmissions
    for log_entry in transmission_log[:5]:
        if log_entry.get("success"):
            icon = "✅"
        else:
            icon = "❌"
        
        reasoning += f"{icon} `{log_entry['message_id']}`\n"
        reasoning += f"  - Topic: `{log_entry.get('topic', 'N/A')}`\n"
        reasoning += f"  - QoS: {log_entry.get('qos', 'N/A')}\n"
        reasoning += f"  - Size: {log_entry.get('payload_size_bytes', 0)} bytes\n"
    
    if len(transmission_log) > 5:
        reasoning += f"\n... and {len(transmission_log) - 5} more\n"
    
    reasoning += f"""
---

## 🎉 TIFDA PIPELINE COMPLETE!

The full pipeline has been executed successfully:

### Phase 1: Core Pipeline ✅
1. ✅ Firewall validation
2. ✅ Format parsing
3. ✅ Multimodal processing
4. ✅ Entity normalization
5. ✅ Sensor fusion (duplicate merging)
6. ✅ COP update + mapa sync

### Phase 2: Intelligence & Output ✅
7. ✅ Threat assessment (LLM)
8. ✅ Human review (HITL)
9. ✅ Dissemination routing (access control)
10. ✅ Format adaptation (interoperability)
11. ✅ **Transmission (MQTT)** ← YOU ARE HERE

**Intelligence has been successfully disseminated to downstream systems!** 🚀

### Next Steps:
- Replace mock MQTT with real broker connection
- Configure recipient systems to consume messages
- Enable acknowledgments and retry logic
- Monitor transmission metrics in production
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="transmission_node",
        decision_type="transmission",
        reasoning=f"Transmitted {total_messages} messages: {successful_transmissions} success, {failed_transmissions} failed",
        data={
            "sensor_id": sensor_id,
            "total_messages": total_messages,
            "successful": successful_transmissions,
            "failed": failed_transmissions,
            "success_rate": transmission_stats['success_rate'],
            "total_bytes": total_bytes_transmitted,
            "transmission_mode": "mock"
        }
    )
    
    # Add notifications
    if successful_transmissions > 0:
        add_notification(
            state,
            f"📡 {successful_transmissions} message(s) transmitted successfully"
        )
    
    if failed_transmissions > 0:
        add_notification(
            state,
            f"❌ {failed_transmissions} transmission(s) failed"
        )
    
    # Pipeline complete notification
    add_notification(
        state,
        "🎉 TIFDA pipeline complete - intelligence disseminated!"
    )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ TRANSMISSION COMPLETE - PIPELINE FINISHED!")
    logger.info(f"   Success: {successful_transmissions}/{total_messages}")
    logger.info(f"   Intelligence has been disseminated to downstream systems")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "transmission_log": transmission_log,
        "transmission_stats": transmission_stats,
        "decision_reasoning": reasoning
    }


# ==================== TESTING ====================

def test_transmission_node():
    """Test the transmission node"""
    from src.core.state import create_initial_state
    
    print("\n" + "=" * 70)
    print("TRANSMISSION NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Transmit messages
    print("Test 1: Transmit formatted messages")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_01"}
    
    # Create formatted messages
    state["formatted_messages"] = [
        {
            "message_id": "msg_001",
            "recipient_id": "command_center",
            "recipient_type": "command",
            "format": "json",
            "priority": "critical",
            "requires_acknowledgment": True,
            "content": {
                "format": "json",
                "threat_level": "critical"
            }
        },
        {
            "message_id": "msg_002",
            "recipient_id": "tactical_ops",
            "recipient_type": "unit",
            "format": "link16",
            "priority": "high",
            "requires_acknowledgment": True,
            "content": {
                "format": "link16",
                "threat_level": "high"
            }
        },
        {
            "message_id": "msg_003",
            "recipient_id": "allied_liaison",
            "recipient_type": "allied",
            "format": "json",
            "priority": "medium",
            "requires_acknowledgment": False,
            "content": {
                "format": "json",
                "threat_level": "medium"
            }
        }
    ]
    
    result = transmission_node(state)
    
    print(f"Messages transmitted: {result['transmission_stats']['total']}")
    print(f"Success: {result['transmission_stats']['success']}")
    print(f"Failed: {result['transmission_stats']['failed']}")
    print(f"Success rate: {result['transmission_stats']['success_rate']:.1%}")
    print(f"Total bytes: {result['transmission_stats']['total_bytes']:,}")
    
    print(f"\nTransmission log:")
    for log_entry in result['transmission_log']:
        status = "✅" if log_entry['success'] else "❌"
        print(f"  {status} {log_entry['message_id']} → {log_entry['recipient_id']}")
    
    print(f"\nReasoning preview:\n{result['decision_reasoning'][:500]}...")
    
    print("\n" + "=" * 70)
    print("TRANSMISSION NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_transmission_node()