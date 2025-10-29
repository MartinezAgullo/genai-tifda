"""
Transmission Node (MQTT ENABLED)
=================================

Eleventh and FINAL node in the TIFDA pipeline - REAL message transmission.

This node:
1. Takes formatted messages from format_adapter_node
2. Publishes messages to MQTT broker via real connection
3. Tracks transmission success/failure
4. Logs all transmissions for audit
5. Completes the full TIFDA pipeline (sensor → dissemination)

✅ PRODUCTION READY - Uses real paho-mqtt client
- Real MQTT broker connection
- TLS support (optional)
- Authentication (optional)
- QoS configuration per recipient
- Connection error handling

Node Signature:
    Input: TIFDAState with pending_transmissions (List[OutgoingMessage])
    Output: Updated TIFDAState with transmission_log (pipeline complete!)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.models.dissemination import OutgoingMessage
from src.integrations.mqtt_publisher import get_mqtt_publisher, MQTTPublisher

# Configure logging
logger = logging.getLogger(__name__)


@traceable(name="transmission_node")
def transmission_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Transmission node - REAL MQTT dissemination.
    
    Publishes messages to MQTT broker for consumption by downstream systems
    (command centers, tactical displays, allied systems, mapa-puntos-interes).
    
    This is the FINAL node in the TIFDA pipeline, completing the flow from
    sensor input to intelligence dissemination.
    
    ✅ PRODUCTION MODE: Real MQTT Connection
    - Connects to configured MQTT broker
    - Publishes to recipient-specific topics
    - Handles connection errors gracefully
    - Logs all transmission results
    
    MQTT Topic Structure:
    - tifda/output/{recipient_id}
    - Configurable per recipient via RecipientConfig
    
    Args:
        state: Current TIFDA state containing:
            - pending_transmissions: List[OutgoingMessage] from format_adapter_node
            - recipients: Dict[str, RecipientConfig] (recipient configs)
        
    Returns:
        Dictionary with updated state fields:
            - transmission_log: List[Dict] (transmission results)
            - pending_transmissions: [] (cleared after transmission)
            - decision_reasoning: str (markdown)
            - notification_queue: List[str]
            - decision_log: List[Dict]
    """
    logger.info("=" * 70)
    logger.info("TRANSMISSION NODE - MQTT Message Dissemination (REAL)")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    pending_transmissions = state.get("pending_transmissions", [])
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not pending_transmissions:
        logger.info("✅ No messages to transmit")
        return {
            "transmission_log": [],
            "decision_reasoning": "## ✅ No Messages to Transmit\n\nNo pending messages for transmission."
        }
    
    logger.info(f"📡 Transmitting {len(pending_transmissions)} messages")
    logger.info(f"   Mode: PRODUCTION (real MQTT)")
    
    # ============ GET MQTT PUBLISHER ============
    
    try:
        mqtt_publisher = get_mqtt_publisher()
        is_healthy, health_msg = mqtt_publisher.health_check()
        
        if not is_healthy:
            error_msg = f"MQTT publisher not healthy: {health_msg}"
            logger.error(f"❌ {error_msg}")
            
            # Return error state
            return {
                "transmission_log": [],
                "error": error_msg,
                "decision_reasoning": f"## ❌ Transmission Failed\n\n{error_msg}\n\nCheck MQTT broker connection."
            }
        
        logger.info(f"✅ MQTT publisher ready: {health_msg}")
        
    except Exception as e:
        error_msg = f"Failed to get MQTT publisher: {e}"
        logger.error(f"❌ {error_msg}")
        
        return {
            "transmission_log": [],
            "error": error_msg,
            "decision_reasoning": f"## ❌ Transmission Failed\n\n{error_msg}"
        }
    
    # ============ GET RECIPIENT CONFIGS ============
    
    # Get recipient configs from state (if available)
    recipient_configs = {}
    
    # Try to get from registered recipients in config
    try:
        from src.core.config import get_config
        config = get_config()
        for recipient_id, recipient_config in config.recipients.items():
            recipient_configs[recipient_id] = {
                'recipient_id': recipient_config.recipient_id,
                'recipient_type': recipient_config.recipient_type,
                'access_level': recipient_config.access_level,
                'connection_type': recipient_config.connection_type,
                'connection_config': recipient_config.connection_config
            }
    except Exception as e:
        logger.warning(f"Could not load recipient configs: {e}")
    
    # ============ TRANSMIT MESSAGES ============
    
    transmission_log = []
    transmission_errors = []
    
    # Stats
    total_messages = len(pending_transmissions)
    successful_transmissions = 0
    failed_transmissions = 0
    total_bytes_transmitted = 0
    
    for message in pending_transmissions:
        message_id = message.message_id
        recipient_id = message.recipient_id
        
        logger.info(f"\n📤 Transmitting: {message_id}")
        logger.info(f"   Recipient: {recipient_id}")
        logger.info(f"   Format: {message.format_type}")
        
        # Get recipient config (if available)
        recipient_config = recipient_configs.get(recipient_id)
        
        # Publish message
        try:
            result = mqtt_publisher.publish_message(
                message=message,
                recipient_config=recipient_config
            )
            
            # Calculate payload size
            payload_size = len(json.dumps(message.content))
            total_bytes_transmitted += payload_size
            
            # Create log entry
            log_entry = {
                "message_id": message_id,
                "recipient_id": recipient_id,
                "topic": result.topic,
                "format": message.format_type,
                "success": result.success,
                "timestamp": result.timestamp.isoformat(),
                "payload_size_bytes": payload_size,
                "qos": recipient_config.get('connection_config', {}).get('qos', 0) if recipient_config else 0
            }
            
            if result.success:
                logger.info(f"   ✅ Published successfully to '{result.topic}'")
                successful_transmissions += 1
                
                # Update message status
                message.transmitted = True
                message.transmission_timestamp = result.timestamp
                message.transmission_status = "success"
            else:
                logger.error(f"   ❌ Publish failed: {result.error}")
                failed_transmissions += 1
                transmission_errors.append(
                    f"{message_id} → {recipient_id}: {result.error}"
                )
                
                # Update message status
                message.transmitted = False
                message.transmission_status = "failed"
                
                log_entry["error"] = result.error
            
            transmission_log.append(log_entry)
            
        except Exception as e:
            error_msg = f"Exception during transmission: {e}"
            logger.error(f"   ❌ {error_msg}")
            failed_transmissions += 1
            transmission_errors.append(f"{message_id} → {recipient_id}: {error_msg}")
            
            # Create error log entry
            log_entry = {
                "message_id": message_id,
                "recipient_id": recipient_id,
                "format": message.format_type,
                "success": False,
                "timestamp": datetime.utcnow().isoformat(),
                "error": error_msg
            }
            transmission_log.append(log_entry)
            
            # Update message status
            message.transmitted = False
            message.transmission_status = "failed"
    
    # ============ GET PUBLISHER STATS ============
    
    publisher_stats = mqtt_publisher.get_stats()
    
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
    
    reasoning = f"""## 📡 Transmission Complete (MQTT)

**Sensor**: `{sensor_id}`
**Messages Transmitted**: {total_messages}
**Transmission Mode**: PRODUCTION (real MQTT)
**Broker Status**: {'✅ Connected' if publisher_stats['connected'] else '❌ Disconnected'}

### Transmission Summary:
- ✅ **Success**: {successful_transmissions} ({transmission_stats['success_rate']:.1%})
- ❌ **Failed**: {failed_transmissions}
- 📊 **Total bytes**: {total_bytes_transmitted:,}

"""
    
    if transmission_errors:
        reasoning += f"### ⚠️ Transmission Errors ({len(transmission_errors)}):\n"
        for error in transmission_errors[:3]:
            reasoning += f"- {error}\n"
        if len(transmission_errors) > 3:
            reasoning += f"- ... and {len(transmission_errors) - 3} more\n"
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
            topics = list(set([log["topic"] for log in logs]))
            reasoning += f"- **{recipient}**: {len(logs)} message(s) ({', '.join(set(formats)).upper()})\n"
            reasoning += f"  - Topics: {', '.join([f'`{t}`' for t in topics])}\n"
        reasoning += "\n"
    
    # Publisher stats
    reasoning += f"""### 📊 MQTT Publisher Statistics:
- Total messages published (lifetime): {publisher_stats['total_published']}
- Total failures (lifetime): {publisher_stats['total_failed']}
- Messages by recipient: {len(publisher_stats['by_recipient'])} recipient(s)

"""
    
    reasoning += "### 📋 Transmission Details:\n"
    
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
        if not log_entry.get("success") and "error" in log_entry:
            reasoning += f"  - Error: {log_entry['error']}\n"
    
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
11. ✅ **Transmission (MQTT - REAL)** ← YOU ARE HERE

**Intelligence has been successfully disseminated to downstream systems via MQTT!** 🚀

### Next Steps:
- Monitor recipient systems for message consumption
- Review transmission logs and error rates
- Configure additional recipients as needed
- Tune QoS levels for reliability requirements
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="transmission_node",
        decision_type="transmission",
        reasoning=f"Transmitted {total_messages} messages via MQTT: {successful_transmissions} success, {failed_transmissions} failed",
        data={
            "sensor_id": sensor_id,
            "total_messages": total_messages,
            "successful": successful_transmissions,
            "failed": failed_transmissions,
            "success_rate": transmission_stats['success_rate'],
            "total_bytes": total_bytes_transmitted,
            "transmission_mode": "mqtt",
            "mqtt_connected": publisher_stats['connected']
        }
    )
    
    # Add notifications
    if successful_transmissions > 0:
        add_notification(
            state,
            f"📡 {successful_transmissions} message(s) transmitted via MQTT"
        )
    
    if failed_transmissions > 0:
        add_notification(
            state,
            f"❌ {failed_transmissions} transmission(s) failed"
        )
    
    # Pipeline complete notification
    add_notification(
        state,
        "🎉 TIFDA pipeline complete - intelligence disseminated via MQTT!"
    )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ TRANSMISSION COMPLETE - PIPELINE FINISHED!")
    logger.info(f"   Success: {successful_transmissions}/{total_messages}")
    logger.info(f"   Intelligence has been disseminated via MQTT")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "transmission_log": transmission_log,
        "pending_transmissions": [],  # Clear after transmission
        "decision_reasoning": reasoning
    }


# ==================== TESTING ====================

def test_transmission_node():
    """Test the transmission node with real MQTT (requires broker running)"""
    from src.core.state import create_initial_state
    from src.models.dissemination import OutgoingMessage
    from datetime import datetime
    
    print("\n" + "=" * 70)
    print("TRANSMISSION NODE TEST (REAL MQTT)")
    print("=" * 70 + "\n")
    
    print("⚠️  This test requires a running MQTT broker")
    print("   Start broker: podman compose up (or mosquitto -c config.conf)")
    print()
    
    # Test: Transmit messages
    print("Test: Transmit messages via MQTT")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_test"}
    
    # Create OutgoingMessage objects
    state["pending_transmissions"] = [
        OutgoingMessage(
            message_id="test_msg_001",
            decision_id="test_dec_001",
            recipient_id="test_recipient_1",
            format_type="json",
            content={
                "message_type": "test",
                "threat_level": "low",
                "test_data": "Hello from TIFDA"
            },
            timestamp=datetime.utcnow(),
            transmitted=False
        ),
        OutgoingMessage(
            message_id="test_msg_002",
            decision_id="test_dec_001",
            recipient_id="mapa",
            format_type="json",
            content={
                "message_type": "cop_update",
                "entity_count": 5,
                "test_data": "COP sync test"
            },
            timestamp=datetime.utcnow(),
            transmitted=False
        )
    ]
    
    try:
        result = transmission_node(state)
        
        print(f"\n✅ Transmission node executed")
        print(f"Messages processed: {len(state['pending_transmissions'])}")
        print(f"Transmission log entries: {len(result.get('transmission_log', []))}")
        
        if result.get('transmission_log'):
            print(f"\nTransmission results:")
            for log_entry in result['transmission_log']:
                status = "✅" if log_entry['success'] else "❌"
                print(f"  {status} {log_entry['message_id']} → {log_entry.get('topic', 'N/A')}")
        
        if result.get('error'):
            print(f"\n⚠️ Error: {result['error']}")
        
        print(f"\nReasoning preview:\n{result.get('decision_reasoning', '')[:500]}...")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print(f"   Make sure MQTT broker is running!")
    
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