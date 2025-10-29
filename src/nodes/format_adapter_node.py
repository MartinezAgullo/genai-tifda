"""
Format Adapter Node
===================

Tenth node in the TIFDA pipeline - format conversion for interoperability.

This node:
1. Takes OutgoingMessage objects from dissemination_router_node
2. Converts to recipient-specific formats:
   - Link16 (NATO tactical data link)
   - JSON (modern APIs)
   - XML (legacy systems)
   - Custom formats per recipient
3. Serializes threat assessment data
4. Adds message headers and metadata
5. Prepares formatted messages for transmission

This enables interoperability with diverse downstream systems - from modern
JSON APIs to legacy military data links.

Supported Formats:
- link16: NATO tactical data link (J-series messages)
- json: Modern REST API format
- xml: Legacy system format
- csv: Simple tabular format

Node Signature:
    Input: TIFDAState with outgoing_messages
    Output: Updated TIFDAState with formatted_messages (ready for transmission)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import xml.etree.ElementTree as ET

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.models import OutgoingMessage, ThreatAssessment

# Configure logging
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

# Format mappings (recipient_id -> preferred format)
# In production, this would come from recipient configuration
DEFAULT_FORMAT_PREFERENCES = {
    "command_center": "json",
    "tactical_ops": "link16",
    "air_defense": "link16",
    "ground_forces": "link16",
    "allied_liaison": "json",
    "analyst_workstation": "json",
    "legacy_system": "xml"
}


# ==================== FORMAT ADAPTERS ====================

def _format_as_link16(message: OutgoingMessage) -> Dict[str, Any]:
    """
    Format message as Link16 J-series message.
    
    Link16 is NATO's primary tactical data link. This is a simplified
    representation of the actual Link16 format.
    
    J-Series Messages:
    - J3.0: Reference Point
    - J3.2: Air Track
    - J3.3: Land Point/Track
    - J12.0: Mission Assignment
    
    Args:
        message: OutgoingMessage to format
        
    Returns:
        Dictionary representing Link16 message
    """
    threat = message.threat_assessment
    
    # Determine J-series message type based on entity
    # (In real implementation, would query COP for entity details)
    message_type = "J3.2"  # Default to air track
    
    # Map threat level to priority
    priority_map = {
        "critical": "FLASH",
        "high": "IMMEDIATE",
        "medium": "PRIORITY",
        "low": "ROUTINE"
    }
    
    link16_message = {
        "format": "link16",
        "message_type": message_type,
        "header": {
            "transmission_id": message.message_id,
            "originator": "TIFDA",
            "timestamp": message.timestamp.strftime("%Y%m%d%H%M%S"),
            "priority": priority_map.get(message.priority, "ROUTINE"),
            "classification": "SECRET",  # Would come from message
            "requires_ack": message.requires_acknowledgment
        },
        "body": {
            "track_id": threat.threat_source_id,
            "threat_level": threat.threat_level.upper(),
            "assessment_confidence": threat.confidence,
            "affected_units": threat.affected_entities,
            "reasoning": threat.reasoning[:100],  # Truncate for Link16
            "timestamp": threat.timestamp.strftime("%Y%m%d%H%M%S")
        }
    }
    
    # Add distance information if available
    if threat.distances_to_affected_km:
        link16_message["body"]["distances_km"] = threat.distances_to_affected_km
    
    return link16_message


def _format_as_json(message: OutgoingMessage) -> Dict[str, Any]:
    """
    Format message as JSON for modern APIs.
    
    This is a clean, structured JSON format suitable for REST APIs,
    web applications, and modern integrations.
    
    Args:
        message: OutgoingMessage to format
        
    Returns:
        Dictionary for JSON serialization
    """
    threat = message.threat_assessment
    
    json_message = {
        "format": "json",
        "api_version": "1.0",
        "message": {
            "message_id": message.message_id,
            "message_type": message.message_type,
            "recipient_id": message.recipient_id,
            "timestamp": message.timestamp.isoformat(),
            "priority": message.priority,
            "requires_acknowledgment": message.requires_acknowledgment
        },
        "threat_assessment": {
            "assessment_id": threat.assessment_id,
            "threat_level": threat.threat_level,
            "threat_source_id": threat.threat_source_id,
            "confidence": threat.confidence,
            "reasoning": threat.reasoning,
            "affected_entities": threat.affected_entities,
            "timestamp": threat.timestamp.isoformat()
        }
    }
    
    # Add optional distance information
    if threat.distances_to_affected_km:
        json_message["threat_assessment"]["distances_to_affected_km"] = threat.distances_to_affected_km
    
    return json_message


def _format_as_xml(message: OutgoingMessage) -> str:
    """
    Format message as XML for legacy systems.
    
    XML format for integration with older military systems
    that expect structured XML documents.
    
    Args:
        message: OutgoingMessage to format
        
    Returns:
        XML string
    """
    threat = message.threat_assessment
    
    # Create root element
    root = ET.Element("ThreatMessage")
    root.set("version", "1.0")
    root.set("format", "xml")
    
    # Message metadata
    metadata = ET.SubElement(root, "Metadata")
    ET.SubElement(metadata, "MessageId").text = message.message_id
    ET.SubElement(metadata, "MessageType").text = message.message_type
    ET.SubElement(metadata, "RecipientId").text = message.recipient_id
    ET.SubElement(metadata, "Timestamp").text = message.timestamp.isoformat()
    ET.SubElement(metadata, "Priority").text = message.priority.upper()
    ET.SubElement(metadata, "RequiresAcknowledgment").text = str(message.requires_acknowledgment)
    
    # Threat assessment
    assessment = ET.SubElement(root, "ThreatAssessment")
    ET.SubElement(assessment, "AssessmentId").text = threat.assessment_id
    ET.SubElement(assessment, "ThreatLevel").text = threat.threat_level.upper()
    ET.SubElement(assessment, "ThreatSourceId").text = threat.threat_source_id
    ET.SubElement(assessment, "Confidence").text = str(threat.confidence)
    ET.SubElement(assessment, "Reasoning").text = threat.reasoning
    ET.SubElement(assessment, "Timestamp").text = threat.timestamp.isoformat()
    
    # Affected entities
    affected = ET.SubElement(assessment, "AffectedEntities")
    for entity_id in threat.affected_entities:
        ET.SubElement(affected, "Entity").text = entity_id
    
    # Distances (if available)
    if threat.distances_to_affected_km:
        distances = ET.SubElement(assessment, "Distances")
        for entity_id, distance_km in threat.distances_to_affected_km.items():
            dist_elem = ET.SubElement(distances, "Distance")
            dist_elem.set("entity", entity_id)
            dist_elem.set("km", str(distance_km))
    
    # Convert to string
    xml_string = ET.tostring(root, encoding="unicode", method="xml")
    
    return {
        "format": "xml",
        "content": xml_string
    }


def _format_as_csv(message: OutgoingMessage) -> Dict[str, Any]:
    """
    Format message as CSV for simple tabular systems.
    
    Simple comma-separated format for spreadsheets and
    basic data processing systems.
    
    Args:
        message: OutgoingMessage to format
        
    Returns:
        Dictionary with CSV content
    """
    threat = message.threat_assessment
    
    # Create CSV header and row
    header = "message_id,recipient_id,timestamp,priority,threat_level,threat_source_id,confidence,reasoning,affected_entities"
    
    # Escape commas in reasoning
    reasoning_escaped = threat.reasoning.replace(",", ";")
    affected_str = "|".join(threat.affected_entities)
    
    row = f"{message.message_id},{message.recipient_id},{message.timestamp.isoformat()},{message.priority},{threat.threat_level},{threat.threat_source_id},{threat.confidence},{reasoning_escaped},{affected_str}"
    
    return {
        "format": "csv",
        "header": header,
        "row": row,
        "content": f"{header}\n{row}"
    }


def _adapt_message_format(message: OutgoingMessage, target_format: str) -> Dict[str, Any]:
    """
    Adapt message to target format.
    
    Args:
        message: OutgoingMessage to adapt
        target_format: Target format (link16, json, xml, csv)
        
    Returns:
        Formatted message dictionary
        
    Raises:
        ValueError: If format is not supported
    """
    if target_format == "link16":
        return _format_as_link16(message)
    elif target_format == "json":
        return _format_as_json(message)
    elif target_format == "xml":
        return _format_as_xml(message)
    elif target_format == "csv":
        return _format_as_csv(message)
    else:
        raise ValueError(f"Unsupported format: {target_format}")


@traceable(name="format_adapter_node")
def format_adapter_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Format adaptation node for message interoperability.
    
    Converts OutgoingMessage objects to recipient-specific formats,
    enabling communication with diverse downstream systems (NATO data links,
    modern APIs, legacy XML systems, etc.).
    
    Format Selection:
    - Uses recipient's preferred format (from configuration)
    - Falls back to message.format if no preference
    - Default to JSON if neither specified
    
    Supported Formats:
    - link16: NATO tactical data link (simplified J-series)
    - json: Modern REST API format
    - xml: Legacy system format
    - csv: Simple tabular format
    
    Args:
        state: Current TIFDA state containing:
            - outgoing_messages: List[OutgoingMessage] from dissemination_router
        
    Returns:
        Dictionary with updated state fields:
            - formatted_messages: List[Dict] (ready for transmission)
            - format_log: List[Dict] (format conversion decisions)
            - decision_reasoning: str (markdown)
            - notification_queue: List[str]
            - decision_log: List[Dict]
    """
    logger.info("=" * 70)
    logger.info("FORMAT ADAPTER NODE - Message Format Conversion")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    outgoing_messages = state.get("outgoing_messages", [])
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not outgoing_messages:
        logger.info("✅ No messages to format")
        return {
            "formatted_messages": [],
            "format_log": [],
            "decision_reasoning": "## ✅ No Messages to Format\n\nNo outgoing messages from previous node."
        }
    
    logger.info(f"📡 Formatting {len(outgoing_messages)} messages")
    
    # ============ FORMAT MESSAGES ============
    
    formatted_messages = []
    format_log = []
    format_errors = []
    
    # Count by format
    format_counts = {
        "link16": 0,
        "json": 0,
        "xml": 0,
        "csv": 0
    }
    
    for message in outgoing_messages:
        logger.info(f"\n📝 Formatting message: {message.message_id}")
        logger.info(f"   Recipient: {message.recipient_id}")
        logger.info(f"   Priority: {message.priority}")
        
        try:
            # Determine target format
            # Priority: 1) Recipient preference, 2) Message format, 3) Default to JSON
            target_format = DEFAULT_FORMAT_PREFERENCES.get(
                message.recipient_id,
                message.format if message.format else "json"
            )
            
            logger.info(f"   Target format: {target_format.upper()}")
            
            # Adapt to format
            formatted_content = _adapt_message_format(message, target_format)
            
            # Create formatted message
            formatted_message = {
                "message_id": message.message_id,
                "recipient_id": message.recipient_id,
                "recipient_type": message.recipient_type,
                "format": target_format,
                "priority": message.priority,
                "requires_acknowledgment": message.requires_acknowledgment,
                "timestamp": datetime.utcnow(),
                "content": formatted_content
            }
            
            formatted_messages.append(formatted_message)
            format_counts[target_format] += 1
            
            logger.info(f"   ✅ Formatted successfully")
            
            # Log format decision
            format_log.append({
                "message_id": message.message_id,
                "recipient_id": message.recipient_id,
                "target_format": target_format,
                "content_size_bytes": len(str(formatted_content)),
                "timestamp": datetime.utcnow()
            })
            
        except Exception as e:
            logger.exception(f"   ❌ Format error: {e}")
            format_errors.append(f"{message.message_id}: {str(e)}")
    
    # ============ RESULTS ============
    
    logger.info(f"\n📊 Formatting complete:")
    logger.info(f"   Messages formatted: {len(formatted_messages)}")
    logger.info(f"   Errors: {len(format_errors)}")
    logger.info(f"   Link16: {format_counts['link16']}")
    logger.info(f"   JSON: {format_counts['json']}")
    logger.info(f"   XML: {format_counts['xml']}")
    logger.info(f"   CSV: {format_counts['csv']}")
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 📝 Format Adaptation Complete

**Sensor**: `{sensor_id}`
**Messages Formatted**: {len(formatted_messages)}
**Errors**: {len(format_errors)}

### Format Distribution:
"""
    
    if format_counts["link16"] > 0:
        reasoning += f"- 🔗 **Link16**: {format_counts['link16']} (NATO tactical data link)\n"
    if format_counts["json"] > 0:
        reasoning += f"- 📄 **JSON**: {format_counts['json']} (modern APIs)\n"
    if format_counts["xml"] > 0:
        reasoning += f"- 📋 **XML**: {format_counts['xml']} (legacy systems)\n"
    if format_counts["csv"] > 0:
        reasoning += f"- 📊 **CSV**: {format_counts['csv']} (tabular format)\n"
    
    reasoning += "\n"
    
    if formatted_messages:
        reasoning += "### 📤 Formatted Messages:\n\n"
        
        # Group by recipient
        messages_by_recipient = {}
        for msg in formatted_messages:
            if msg["recipient_id"] not in messages_by_recipient:
                messages_by_recipient[msg["recipient_id"]] = []
            messages_by_recipient[msg["recipient_id"]].append(msg)
        
        for recipient_id, messages in messages_by_recipient.items():
            formats = [msg["format"] for msg in messages]
            reasoning += f"**{recipient_id}**: {len(messages)} message(s) in {', '.join(set(formats)).upper()}\n"
        
        reasoning += "\n"
    
    if format_errors:
        reasoning += f"### ⚠️  Format Errors ({len(format_errors)}):\n"
        for error in format_errors[:3]:
            reasoning += f"- {error}\n"
        reasoning += "\n"
    
    # Show format examples (truncated)
    if formatted_messages:
        reasoning += "### 📋 Format Examples:\n\n"
        
        # Show one example per format
        shown_formats = set()
        for msg in formatted_messages[:3]:
            if msg["format"] not in shown_formats:
                shown_formats.add(msg["format"])
                
                content_preview = str(msg["content"])[:200]
                reasoning += f"**{msg['format'].upper()}** (to {msg['recipient_id']}):\n"
                reasoning += f"```\n{content_preview}...\n```\n\n"
    
    reasoning += """
### Supported Formats:
- **Link16**: NATO J-series tactical data link
- **JSON**: Modern REST API format
- **XML**: Legacy military system format
- **CSV**: Simple tabular format

**Next**: Route to `transmission_node` for MQTT publishing
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="format_adapter_node",
        decision_type="format_adaptation",
        reasoning=f"Formatted {len(outgoing_messages)} messages: {format_counts['link16']} Link16, {format_counts['json']} JSON, {format_counts['xml']} XML, {format_counts['csv']} CSV",
        data={
            "sensor_id": sensor_id,
            "messages_formatted": len(formatted_messages),
            "format_counts": format_counts,
            "errors": format_errors
        }
    )
    
    # Add notifications
    if len(formatted_messages) > 0:
        add_notification(
            state,
            f"📝 {len(formatted_messages)} message(s) formatted for transmission"
        )
    
    if format_errors:
        add_notification(
            state,
            f"⚠️  {len(format_errors)} format error(s)"
        )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Formatting complete: {len(formatted_messages)} messages ready")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "formatted_messages": formatted_messages,
        "format_log": format_log,
        "decision_reasoning": reasoning
    }


# ==================== TESTING ====================

def test_format_adapter_node():
    """Test the format adapter node"""
    from src.core.state import create_initial_state
    
    print("\n" + "=" * 70)
    print("FORMAT ADAPTER NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Format messages in different formats
    print("Test 1: Format messages for different recipients")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_01"}
    
    # Create outgoing messages
    state["outgoing_messages"] = [
        OutgoingMessage(
            message_id="msg_001",
            recipient_id="command_center",  # JSON format
            recipient_type="command",
            message_type="threat_alert",
            format="json",
            threat_assessment=ThreatAssessment(
                assessment_id="threat_001",
                threat_level="critical",
                affected_entities=["base_alpha"],
                threat_source_id="hostile_aircraft_001",
                reasoning="Hostile aircraft on intercept course",
                confidence=0.95,
                timestamp=datetime.utcnow()
            ),
            timestamp=datetime.utcnow(),
            priority="critical",
            requires_acknowledgment=True
        ),
        OutgoingMessage(
            message_id="msg_002",
            recipient_id="tactical_ops",  # Link16 format
            recipient_type="unit",
            message_type="threat_alert",
            format="link16",
            threat_assessment=ThreatAssessment(
                assessment_id="threat_001",
                threat_level="critical",
                affected_entities=["base_alpha"],
                threat_source_id="hostile_aircraft_001",
                reasoning="Hostile aircraft on intercept course",
                confidence=0.95,
                timestamp=datetime.utcnow()
            ),
            timestamp=datetime.utcnow(),
            priority="critical",
            requires_acknowledgment=True
        ),
        OutgoingMessage(
            message_id="msg_003",
            recipient_id="legacy_system",  # XML format
            recipient_type="system",
            message_type="threat_alert",
            format="xml",
            threat_assessment=ThreatAssessment(
                assessment_id="threat_002",
                threat_level="high",
                affected_entities=["patrol_bravo"],
                threat_source_id="hostile_vehicle_002",
                reasoning="Hostile ground vehicle approaching",
                confidence=0.85,
                timestamp=datetime.utcnow()
            ),
            timestamp=datetime.utcnow(),
            priority="high",
            requires_acknowledgment=True
        )
    ]
    
    result = format_adapter_node(state)
    
    print(f"Messages formatted: {len(result['formatted_messages'])}")
    
    print(f"\nFormats used:")
    format_counts = {}
    for msg in result['formatted_messages']:
        fmt = msg['format']
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
    
    for fmt, count in format_counts.items():
        print(f"  {fmt.upper()}: {count}")
    
    print(f"\nFirst formatted message:")
    first_msg = result['formatted_messages'][0]
    print(f"  Recipient: {first_msg['recipient_id']}")
    print(f"  Format: {first_msg['format']}")
    print(f"  Content preview: {str(first_msg['content'])[:200]}...")
    
    print(f"\nReasoning preview:\n{result['decision_reasoning'][:500]}...")
    
    print("\n" + "=" * 70)
    print("FORMAT ADAPTER NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_format_adapter_node()