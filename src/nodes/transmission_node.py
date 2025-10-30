"""
Transmission Node (MQTT ENABLED)
=================================

Eleventh and FINAL node in TIFDA pipeline - REAL message transmission.

✅ PRODUCTION READY - Uses real paho-mqtt client
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
import json

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.integrations.mqtt_publisher import get_mqtt_publisher

logger = logging.getLogger(__name__)

@traceable(name="transmission_node")
def transmission_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Transmission node - REAL MQTT dissemination.
    
    Publishes to: tifda/output/dissemination_reports/{recipient_id}
    """
    logger.info("=" * 70)
    logger.info("TRANSMISSION NODE - MQTT (REAL)")
    logger.info("=" * 70)
    
    formatted_messages = state.get("formatted_messages", [])
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not formatted_messages:
        logger.info("✅ No messages to transmit")
        return {
            "transmission_log": [],
            "decision_reasoning": "## ✅ No Messages to Transmit\n\nNo formatted messages."
        }
    
    logger.info(f"📡 Transmitting {len(formatted_messages)} messages")
    
    # Get MQTT publisher
    try:
        mqtt_publisher = get_mqtt_publisher()
        is_healthy, health_msg = mqtt_publisher.health_check()
        
        if not is_healthy:
            error_msg = f"MQTT publisher not healthy: {health_msg}"
            logger.error(f"❌ {error_msg}")
            return {
                "transmission_log": [],
                "error": error_msg,
                "decision_reasoning": f"## ❌ Transmission Failed\n\n{error_msg}"
            }
        
        logger.info(f"✅ MQTT ready: {health_msg}")
        
    except Exception as e:
        error_msg = f"Failed to get MQTT publisher: {e}"
        logger.error(f"❌ {error_msg}")
        return {
            "transmission_log": [],
            "error": error_msg,
            "decision_reasoning": f"## ❌ Transmission Failed\n\n{error_msg}"
        }
    
    # Get recipient configs
    recipient_configs = {}
    try:
        from src.core.config import get_config
        config = get_config()
        for rid, rc in config.recipients.items():
            recipient_configs[rid] = {
                'recipient_id': rc.recipient_id,
                'recipient_type': rc.recipient_type,
                'connection_config': rc.connection_config
            }
    except Exception as e:
        logger.warning(f"Could not load recipient configs: {e}")
    
    # Transmit messages
    transmission_log = []
    transmission_errors = []
    total_messages = len(formatted_messages)
    successful_transmissions = 0
    failed_transmissions = 0
    total_bytes_transmitted = 0
    
    for formatted_message in formatted_messages:
        message_id = formatted_message["message_id"]
        recipient_id = formatted_message["recipient_id"]
        priority = formatted_message["priority"]
        
        logger.info(f"\n📤 Transmitting: {message_id}")
        logger.info(f"   Recipient: {recipient_id}")
        logger.info(f"   Priority: {priority}")
        
        recipient_config = recipient_configs.get(recipient_id)
        
        # Determine topic
        if recipient_config and 'connection_config' in recipient_config:
            topic = recipient_config['connection_config'].get(
                'mqtt_topic',
                f"tifda/output/dissemination_reports/{recipient_id}"
            )
            qos = recipient_config['connection_config'].get('qos', 1)
        else:
            topic = f"tifda/output/dissemination_reports/{recipient_id}"
            qos_map = {"critical": 2, "high": 1, "medium": 1, "low": 0}
            qos = qos_map.get(priority, 1)
        
        try:
            # Create OutgoingMessage
            from src.models.dissemination import OutgoingMessage
            
            msg = OutgoingMessage(
                message_id=message_id,
                decision_id=formatted_message.get("decision_id", "unknown"),
                recipient_id=recipient_id,
                format_type=formatted_message["format"],
                content=formatted_message["content"],
                timestamp=datetime.utcnow()
            )
            
            # Publish
            result = mqtt_publisher.publish_message(msg, recipient_config)
            
            payload_size = len(json.dumps(formatted_message["content"]))
            total_bytes_transmitted += payload_size
            
            log_entry = {
                "message_id": message_id,
                "recipient_id": recipient_id,
                "topic": result.topic,
                "format": formatted_message["format"],
                "priority": priority,
                "qos": qos,
                "payload_size_bytes": payload_size,
                "success": result.success,
                "timestamp": result.timestamp.isoformat()
            }
            
            if result.success:
                logger.info(f"   ✅ Published to '{result.topic}'")
                successful_transmissions += 1
            else:
                logger.error(f"   ❌ Failed: {result.error}")
                failed_transmissions += 1
                transmission_errors.append(f"{message_id}: {result.error}")
                log_entry["error"] = result.error
            
            transmission_log.append(log_entry)
            
        except Exception as e:
            logger.error(f"   ❌ Exception: {e}")
            failed_transmissions += 1
            transmission_errors.append(f"{message_id}: {e}")
            
            transmission_log.append({
                "message_id": message_id,
                "recipient_id": recipient_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
    
    # Stats
    publisher_stats = mqtt_publisher.get_stats()
    
    # Results
    transmission_stats = {
        "total": total_messages,
        "success": successful_transmissions,
        "failed": failed_transmissions,
        "success_rate": successful_transmissions / total_messages if total_messages > 0 else 0,
        "total_bytes": total_bytes_transmitted
    }
    
    logger.info(f"\n📊 Transmission complete:")
    logger.info(f"   ✅ Success: {successful_transmissions}/{total_messages}")
    logger.info(f"   ❌ Failed: {failed_transmissions}")
    
    # Build reasoning
    reasoning = f"""## 📡 Transmission Complete (MQTT)

**Sensor**: `{sensor_id}`
**Messages**: {total_messages}
**Mode**: PRODUCTION (real MQTT)

### Summary:
- ✅ Success: {successful_transmissions} ({transmission_stats['success_rate']:.1%})
- ❌ Failed: {failed_transmissions}
- 📊 Bytes: {total_bytes_transmitted:,}

"""
    
    if transmission_errors:
        reasoning += f"### Errors ({len(transmission_errors)}):\n"
        for error in transmission_errors[:3]:
            reasoning += f"- {error}\n"
        reasoning += "\n"
    
    messages_by_recipient = {}
    for log_entry in transmission_log:
        if log_entry.get("success"):
            recipient = log_entry["recipient_id"]
            if recipient not in messages_by_recipient:
                messages_by_recipient[recipient] = []
            messages_by_recipient[recipient].append(log_entry)
    
    if messages_by_recipient:
        reasoning += "### Transmitted To:\n"
        for recipient, logs in messages_by_recipient.items():
            topics = list(set([log["topic"] for log in logs]))
            reasoning += f"- **{recipient}**: {len(logs)} message(s)\n"
            reasoning += f"  - Topics: {', '.join([f'`{t}`' for t in topics])}\n"
        reasoning += "\n"
    
    reasoning += f"""### MQTT Stats:
- Total published (lifetime): {publisher_stats['total_published']}
- Total failed (lifetime): {publisher_stats['total_failed']}

### Details:
"""
    
    for log_entry in transmission_log[:5]:
        icon = "✅" if log_entry.get("success") else "❌"
        reasoning += f"{icon} `{log_entry['message_id']}` → `{log_entry.get('topic', 'N/A')}`\n"
    
    if len(transmission_log) > 5:
        reasoning += f"\n... and {len(transmission_log) - 5} more\n"
    
    reasoning += "\n---\n\n## 🎉 TIFDA PIPELINE COMPLETE!\n\nIntelligence disseminated via MQTT! 🚀\n"
    
    # Update state
    log_decision(
        state=state,
        node_name="transmission_node",
        decision_type="transmission",
        reasoning=f"Transmitted {total_messages} via MQTT: {successful_transmissions} success, {failed_transmissions} failed",
        data={
            "sensor_id": sensor_id,
            "total_messages": total_messages,
            "successful": successful_transmissions,
            "failed": failed_transmissions,
            "success_rate": transmission_stats['success_rate'],
            "total_bytes": total_bytes_transmitted,
            "transmission_mode": "mqtt"
        }
    )
    
    if successful_transmissions > 0:
        add_notification(state, f"📡 {successful_transmissions} message(s) transmitted via MQTT")
    
    if failed_transmissions > 0:
        add_notification(state, f"❌ {failed_transmissions} transmission(s) failed")
    
    add_notification(state, "🎉 TIFDA pipeline complete!")
    
    logger.info(f"\n✅ TRANSMISSION COMPLETE - Success: {successful_transmissions}/{total_messages}\n")
    
    return {
        "transmission_log": transmission_log,
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