"""
Dissemination Router Node
==========================

Ninth node in the TIFDA pipeline - access control and routing for intelligence.

This node:
1. Takes approved threats from human_review_node
2. Checks recipient access levels and clearances
3. Applies need-to-know policy
4. Routes threats to appropriate recipients
5. Filters classified information based on clearance
6. Creates OutgoingMessage objects for transmission

This is where intelligence is controlled and distributed - ensuring that
classified information only reaches authorized recipients.

Access Control Principles:
- Information Classification Hierarchy: TOP_SECRET > SECRET > CONFIDENTIAL > RESTRICTED > UNCLASSIFIED
- Need-to-Know: Recipients only get intelligence relevant to their mission
- Clearance Matching: Recipients must have appropriate clearance level

Node Signature:
    Input: TIFDAState with approved_threats
    Output: Updated TIFDAState with outgoing_messages (ready for transmission)
"""

import logging
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, timezone

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.models import ThreatAssessment, OutgoingMessage

# Configure logging
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

# Information classification levels (highest to lowest)
CLASSIFICATION_HIERARCHY = [
    "TOP_SECRET",
    "SECRET",
    "CONFIDENTIAL",
    "RESTRICTED",
    "UNCLASSIFIED"
]

# Default recipients (mock - in production would come from database/config)
DEFAULT_RECIPIENTS = {
    "command_post_001": {
        "recipient_id": "command_post_001",
        "recipient_type": "command",
        "clearance_level": "SECRET",
        "need_to_know": ["all"],
        "receive_threat_levels": ["critical", "high", "medium", "low"]
    },
    "command_center": {
        "recipient_id": "command_center",
        "recipient_type": "command",
        "clearance_level": "TOP_SECRET",
        "need_to_know": ["all"],  # Receives all intelligence
        "receive_threat_levels": ["critical", "high", "medium", "low"]
    },
    "tactical_ops": {
        "recipient_id": "tactical_ops",
        "recipient_type": "unit",
        "clearance_level": "SECRET",
        "need_to_know": ["tactical", "operational"],
        "receive_threat_levels": ["critical", "high", "medium"]
    },
    "air_defense": {
        "recipient_id": "air_defense",
        "recipient_type": "unit",
        "clearance_level": "SECRET",
        "need_to_know": ["air_defense", "aircraft"],
        "receive_threat_levels": ["critical", "high"]
    },
    "ground_forces": {
        "recipient_id": "ground_forces",
        "recipient_type": "unit",
        "clearance_level": "CONFIDENTIAL",
        "need_to_know": ["ground", "tactical"],
        "receive_threat_levels": ["critical", "high", "medium"]
    },
    "allied_liaison": {
        "recipient_id": "allied_liaison",
        "recipient_type": "allied",
        "clearance_level": "CONFIDENTIAL",
        "need_to_know": ["operational"],
        "receive_threat_levels": ["critical", "high"]
    }
}


# ==================== ACCESS CONTROL UTILITIES ====================

def _get_classification_level_index(classification: str) -> int:
    """
    Get numeric index for classification level (higher = more classified).
    
    Args:
        classification: Classification level string
        
    Returns:
        Index in hierarchy (0 = TOP_SECRET, 4 = UNCLASSIFIED)
    """
    try:
        return CLASSIFICATION_HIERARCHY.index(classification)
    except ValueError:
        # Unknown classification - default to most restrictive
        logger.warning(f"⚠️  Unknown classification: {classification}, defaulting to TOP_SECRET")
        return 0


def _has_clearance(recipient_clearance: str, required_clearance: str) -> bool:
    """
    Check if recipient has sufficient clearance for information.
    
    Args:
        recipient_clearance: Recipient's clearance level
        required_clearance: Required clearance level for information
        
    Returns:
        True if recipient has sufficient clearance
    """
    recipient_level = _get_classification_level_index(recipient_clearance)
    required_level = _get_classification_level_index(required_clearance)
    
    # Lower index = higher clearance
    return recipient_level <= required_level


def _check_need_to_know(
    recipient_needs: List[str],
    threat: ThreatAssessment,
    cop_entities: Dict
) -> bool:
    """
    Check if recipient has need-to-know for this threat.
    
    Need-to-know is based on:
    - Recipient's areas of responsibility
    - Threat source entity type
    - Affected entity types
    
    Args:
        recipient_needs: List of recipient's need-to-know areas
        threat: ThreatAssessment to check
        cop_entities: Full COP dictionary
        
    Returns:
        True if recipient has need-to-know
    """
    # "all" means receives everything
    if "all" in recipient_needs:
        return True
    
    # Get threat source entity
    threat_entity = cop_entities.get(threat.threat_source_id)
    
    if not threat_entity:
        # Can't determine need-to-know without entity data
        # Default to yes (err on side of dissemination)
        return True
    
    # Check if entity type matches recipient's need-to-know
    entity_type = threat_entity.entity_type
    
    # Map entity types to need-to-know areas
    type_to_area = {
        "aircraft": "aircraft",
        "helicopter": "aircraft",
        "uav": "aircraft",
        "ground_vehicle": "ground",
        "tank": "ground",
        "apc": "ground",
        "infantry": "ground",
        "ship": "naval",
        "submarine": "naval",
        "missile": "air_defense",
        "artillery": "ground"
    }
    
    need_area = type_to_area.get(entity_type, "tactical")
    
    # Check if recipient needs this area
    if need_area in recipient_needs:
        return True
    
    # Check for tactical/operational catch-all
    if "tactical" in recipient_needs or "operational" in recipient_needs:
        return True
    
    return False


def _should_disseminate_to_recipient(
    recipient: Dict[str, Any],
    threat: ThreatAssessment,
    cop_entities: Dict
) -> tuple[bool, str]:
    """
    Determine if threat should be disseminated to recipient.
    
    Args:
        recipient: Recipient configuration dictionary
        threat: ThreatAssessment to route
        cop_entities: Full COP dictionary
        
    Returns:
        (should_send, reason)
    """
    # 1. Check threat level
    if threat.threat_level not in recipient["receive_threat_levels"]:
        return False, f"Threat level {threat.threat_level} not in recipient's filter"
    
    # 2. Check clearance
    # Get highest classification from threat and source entity
    threat_entity = cop_entities.get(threat.threat_source_id)
    
    if threat_entity:
        required_clearance = threat_entity.information_classification
    else:
        # Default to SECRET if we can't determine
        required_clearance = "SECRET"
    
    if not _has_clearance(recipient["clearance_level"], required_clearance):
        return False, f"Insufficient clearance (requires {required_clearance}, has {recipient['clearance_level']})"
    
    # 3. Check need-to-know
    if not _check_need_to_know(recipient["need_to_know"], threat, cop_entities):
        return False, "No need-to-know for this threat"
    
    # All checks passed
    return True, "Authorized"


def _filter_threat_for_clearance(
    threat: ThreatAssessment,
    recipient_clearance: str,
    cop_entities: Dict
) -> ThreatAssessment:
    """
    Filter threat information based on recipient clearance.
    
    Lower clearance recipients get sanitized versions:
    - Generic location (lat/lon rounded)
    - Reduced metadata
    - Generic reasoning
    
    Args:
        threat: Original ThreatAssessment
        recipient_clearance: Recipient's clearance level
        cop_entities: Full COP dictionary
        
    Returns:
        Filtered ThreatAssessment
    """
    # Get required clearance
    threat_entity = cop_entities.get(threat.threat_source_id)
    
    if not threat_entity:
        # Can't filter without entity - return as-is
        return threat
    
    required_clearance = threat_entity.information_classification
    
    # If recipient has full clearance, no filtering needed
    if _has_clearance(recipient_clearance, required_clearance):
        return threat
    
    # Recipient has lower clearance - sanitize
    # (In practice, this shouldn't happen due to routing checks,
    # but including as defense-in-depth)
    
    logger.warning(f"⚠️  Filtering threat for lower clearance: {recipient_clearance} < {required_clearance}")
    
    # Create sanitized version
    filtered_reasoning = f"Threat detected in operational area. Classification: {threat.threat_level}."
    
    return ThreatAssessment(
        assessment_id=threat.assessment_id,
        threat_level=threat.threat_level,
        affected_entities=threat.affected_entities,
        threat_source_id=threat.threat_source_id,
        reasoning=filtered_reasoning,  # Generic reasoning
        confidence=threat.confidence,
        timestamp=threat.timestamp,
        distances_to_affected_km=None  # Remove precise distances
    )


@traceable(name="dissemination_router_node")
def dissemination_router_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Dissemination routing and access control node.
    
    Routes approved threat assessments to authorized recipients based on:
    - Information classification and recipient clearance
    - Need-to-know (mission relevance)
    - Threat level filters
    
    Access control ensures:
    - Classified information only reaches authorized recipients
    - Recipients only get mission-relevant intelligence
    - Audit trail of dissemination decisions
    
    Args:
        state: Current TIFDA state containing:
            - approved_threats: List[ThreatAssessment] from human_review_node
            - cop_entities: Full COP dictionary
        
    Returns:
        Dictionary with updated state fields:
            - outgoing_messages: List[OutgoingMessage] (ready for transmission)
            - dissemination_log: List[Dict] (routing decisions)
            - decision_reasoning: str (markdown)
            - notification_queue: List[str]
            - decision_log: List[Dict]
    """
    logger.info("=" * 70)
    logger.info("DISSEMINATION ROUTER NODE - Access Control & Routing")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    approved_threats = state.get("approved_threats", [])
    cop_entities = state.get("cop_entities", {})
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not approved_threats:
        logger.info("✅ No approved threats to disseminate")
        return {
            "outgoing_messages": [],
            "dissemination_log": [],
            "decision_reasoning": "## ✅ No Threats to Disseminate\n\nNo approved threats from previous node."
        }
    
    logger.info(f"📡 Routing {len(approved_threats)} approved threats")
    logger.info(f"   Recipients: {len(DEFAULT_RECIPIENTS)}")
    
    # ============ ROUTE THREATS TO RECIPIENTS ============
    
    outgoing_messages = []
    dissemination_log = []
    
    # Stats
    total_messages = 0
    blocked_by_clearance = 0
    blocked_by_need_to_know = 0
    blocked_by_threat_level = 0
    
    for threat in approved_threats:
        logger.info(f"\n🔍 Routing threat: {threat.threat_source_id} ({threat.threat_level})")
        
        threat_recipients = []
        
        for recipient_id, recipient_config in DEFAULT_RECIPIENTS.items():
            # Check if should disseminate
            should_send, reason = _should_disseminate_to_recipient(
                recipient_config,
                threat,
                cop_entities
            )
            
            if should_send:
                logger.info(f"   ✅ {recipient_id}: {reason}")
                
                # Filter threat based on clearance
                filtered_threat = _filter_threat_for_clearance(
                    threat,
                    recipient_config["clearance_level"],
                    cop_entities
                )
                
                # Generate a decision_id for this message
                decision_id = f"decision_{threat.assessment_id}_{recipient_id}"

                # Build content dictionary with threat information
                content = {
                    "threat_assessment": {
                        "assessment_id": filtered_threat.assessment_id,
                        "threat_level": filtered_threat.threat_level,
                        "threat_source_id": filtered_threat.threat_source_id,
                        "affected_entities": filtered_threat.affected_entities,
                        "reasoning": filtered_threat.reasoning,
                        "confidence": filtered_threat.confidence,
                        "timestamp": filtered_threat.timestamp.isoformat(),
                        "distances_to_affected_km": filtered_threat.distances_to_affected_km
                    },
                    "message_type": "threat_alert",
                    "priority": threat.threat_level,
                    "requires_acknowledgment": threat.threat_level in ["critical", "high"],
                    "recipient_type": recipient_config["recipient_type"],
                    "sensor_id": sensor_id
                }

                # Create outgoing message
                # Create outgoing message with correct schema
                message = OutgoingMessage(
                    message_id=f"msg_{threat.assessment_id}_{recipient_id}_{int(datetime.now(timezone.utc).timestamp())}",
                    decision_id=decision_id,
                    recipient_id=recipient_id,
                    format_type="json",  # Default to json, will be adapted in format_adapter_node
                    content=content,
                    timestamp=datetime.now(timezone.utc)
                )
                
                outgoing_messages.append(message)
                threat_recipients.append(recipient_id)
                total_messages += 1
                
            else:
                logger.info(f"   ❌ {recipient_id}: {reason}")
                
                # Track blocking reasons
                if "clearance" in reason.lower():
                    blocked_by_clearance += 1
                elif "need-to-know" in reason.lower():
                    blocked_by_need_to_know += 1
                elif "threat level" in reason.lower():
                    blocked_by_threat_level += 1
        
        # Log dissemination decision
        dissemination_log.append({
            "threat_id": threat.assessment_id,
            "threat_source_id": threat.threat_source_id,
            "threat_level": threat.threat_level,
            "recipients": threat_recipients,
            "recipient_count": len(threat_recipients),
            "timestamp": datetime.now(timezone.utc)
        })
        
        logger.info(f"   📤 Disseminated to {len(threat_recipients)} recipient(s)")
    
    
    
    # ============ RESULTS ============
    # 🔍 DEBUG OUTPUT
    # print(f"\n🔍 DEBUG dissemination_router_node:")
    # print(f"   Approved threats processed: {len(approved_threats)}")
    # print(f"   Outgoing messages created: {len(outgoing_messages)}")
    # print(f"   Total messages counter: {total_messages}")
    # if approved_threats:
    #     print(f"   First threat ID: {approved_threats[0].threat_source_id}")
    #     print(f"   First threat level: {approved_threats[0].threat_level}")
    # print(f"   Recipients configured: {list(DEFAULT_RECIPIENTS.keys())}")
    # print(f"   Blocked by clearance: {blocked_by_clearance}")
    # print(f"   Blocked by need-to-know: {blocked_by_need_to_know}")
    # print(f"   Blocked by threat level: {blocked_by_threat_level}")
    # print()    
    # 🔍 DEBUG OUTPUT

    
    logger.info(f"\n📊 Routing complete:")
    logger.info(f"   Messages created: {total_messages}")
    logger.info(f"   Unique recipients: {len(set(msg.recipient_id for msg in outgoing_messages))}")
    logger.info(f"   Blocked by clearance: {blocked_by_clearance}")
    logger.info(f"   Blocked by need-to-know: {blocked_by_need_to_know}")
    logger.info(f"   Blocked by threat level: {blocked_by_threat_level}")
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 📡 Dissemination Routing Complete

**Sensor**: `{sensor_id}`
**Approved Threats**: {len(approved_threats)}
**Recipients Configured**: {len(DEFAULT_RECIPIENTS)}

### Dissemination Summary:
- 📤 **Messages created**: {total_messages}
- 👥 **Unique recipients**: {len(set(msg.recipient_id for msg in outgoing_messages))}

### Access Control Statistics:
- ❌ Blocked by clearance: {blocked_by_clearance}
- ❌ Blocked by need-to-know: {blocked_by_need_to_know}
- ❌ Blocked by threat level filter: {blocked_by_threat_level}

"""
    
    if outgoing_messages:
        reasoning += "### 📤 Outgoing Messages:\n\n"
        
        # Group by recipient
        messages_by_recipient = {}
        for msg in outgoing_messages:
            if msg.recipient_id not in messages_by_recipient:
                messages_by_recipient[msg.recipient_id] = []
            messages_by_recipient[msg.recipient_id].append(msg)
        
        for recipient_id, messages in messages_by_recipient.items():
            recipient_config = DEFAULT_RECIPIENTS[recipient_id]
            reasoning += f"**{recipient_id}** ({recipient_config['recipient_type']}, clearance: {recipient_config['clearance_level']})\n"
            
            for msg in messages:
                threat_source_id = msg.content.get("threat_assessment", {}).get("threat_source_id", "unknown")
                priority = msg.content.get("priority", "unknown")
                
                icon = "🔴" if msg.content.get("priority") == "critical" else "🟠" if msg.content.get("priority") == "high" else "🟡"
                reasoning += f"  {icon} {threat_source_id} ({priority})\n"
            
            reasoning += "\n"
    else:
        reasoning += "⚠️  **No messages generated** (all threats blocked by access control)\n\n"
    
    # Show dissemination log
    if dissemination_log:
        reasoning += "### 📋 Dissemination Log:\n"
        for log_entry in dissemination_log:
            reasoning += f"- `{log_entry['threat_source_id']}` → {log_entry['recipient_count']} recipient(s)\n"
        reasoning += "\n"
    
    reasoning += """
### Access Control Principles Applied:
1. **Classification Matching**: Recipients must have appropriate clearance
2. **Need-to-Know**: Recipients only get mission-relevant intelligence
3. **Threat Level Filters**: Recipients configured for specific threat levels

**Next**: Route to `format_adapter_node` for message formatting
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="dissemination_router_node",
        decision_type="dissemination_routing",
        reasoning=f"Routed {len(approved_threats)} threats to {total_messages} messages for {len(set(msg.recipient_id for msg in outgoing_messages))} recipients",
        data={
            "sensor_id": sensor_id,
            "threats_routed": len(approved_threats),
            "messages_created": total_messages,
            "unique_recipients": len(set(msg.recipient_id for msg in outgoing_messages)),
            "blocked_by_clearance": blocked_by_clearance,
            "blocked_by_need_to_know": blocked_by_need_to_know,
            "blocked_by_threat_level": blocked_by_threat_level
        }
    )
    
    # Add notifications
    if total_messages > 0:
        critical_high = sum(1 for msg in outgoing_messages if msg.content.get("priority") in ["critical", "high"])

        
        if critical_high > 0:
            add_notification(
                state,
                f"📤 {critical_high} critical/high threat alert(s) disseminated"
            )
        
        if total_messages > critical_high:
            add_notification(
                state,
                f"📤 {total_messages - critical_high} medium/low threat alert(s) disseminated"
            )
    
    if blocked_by_clearance + blocked_by_need_to_know + blocked_by_threat_level > 0:
        total_blocked = blocked_by_clearance + blocked_by_need_to_know + blocked_by_threat_level
        add_notification(
            state,
            f"🔒 {total_blocked} dissemination(s) blocked by access control"
        )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Routing complete: {total_messages} messages to {len(set(msg.recipient_id for msg in outgoing_messages))} recipients")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "outgoing_messages": outgoing_messages,
        "dissemination_log": dissemination_log,
        "decision_reasoning": reasoning
    }


# ==================== TESTING ====================

def test_dissemination_router_node():
    """Test the dissemination router node"""
    from src.core.state import create_initial_state
    from src.models import Location, EntityCOP
    
    print("\n" + "=" * 70)
    print("DISSEMINATION ROUTER NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Route threats to recipients
    print("Test 1: Route threats with access control")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_01"}
    
    # COP with threat source entity
    state["cop_entities"] = {
        "hostile_aircraft_001": EntityCOP(
            entity_id="hostile_aircraft_001",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4, alt=5000),
            timestamp=datetime.now(timezone.utc),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.9,
            source_sensors=["radar_01"]
        )
    }
    
    # Approved threats
    state["approved_threats"] = [
        ThreatAssessment(
            assessment_id="threat_001",
            threat_level="critical",
            affected_entities=["base_alpha"],
            threat_source_id="hostile_aircraft_001",
            reasoning="Hostile aircraft on intercept course",
            confidence=0.95,
            timestamp=datetime.now(timezone.utc)
        ),
        ThreatAssessment(
            assessment_id="threat_002",
            threat_level="medium",
            affected_entities=["patrol_bravo"],
            threat_source_id="hostile_aircraft_001",
            reasoning="Medium priority threat",
            confidence=0.75,
            timestamp=datetime.now(timezone.utc)
        )
    ]
    
    result = dissemination_router_node(state)
    
    print(f"Threats routed: {len(state['approved_threats'])}")
    print(f"Messages created: {len(result['outgoing_messages'])}")
    print(f"Unique recipients: {len(set(msg.recipient_id for msg in result['outgoing_messages']))}")
    
    print(f"\nMessages by recipient:")
    messages_by_recipient = {}
    for msg in result['outgoing_messages']:
        if msg.recipient_id not in messages_by_recipient:
            messages_by_recipient[msg.recipient_id] = []
        messages_by_recipient[msg.recipient_id].append(msg)
    
    for recipient_id, messages in messages_by_recipient.items():
        print(f"  {recipient_id}: {len(messages)} message(s)")
        for msg in messages:
            print(f"    - {msg.content.get('priority')} priority")

    
    print(f"\nReasoning preview:\n{result['decision_reasoning'][:500]}...")
    
    print("\n" + "=" * 70)
    print("DISSEMINATION ROUTER NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_dissemination_router_node()