"""
Dissemination Rules
===================

Deterministic rules for need-to-know dissemination decisions.
Handles distance-based routing, operational role matching, and recipient loading.
"""

import math
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Literal, Any
from dataclasses import dataclass

from src.models import EntityCOP, ThreatAssessment


# ==================== DATA STRUCTURES ====================

@dataclass
class RecipientInfo:
    """Recipient configuration information"""
    recipient_id: str
    recipient_name: str
    recipient_type: str
    access_level: str
    location: Optional[Dict[str, float]]  # {lat, lon, alt}
    is_mobile: bool
    elemento_identificado: Optional[str]
    operational_role: str
    priority_entity_types: List[str]
    mqtt_topics: Dict[str, Optional[str]]
    supported_formats: List[str]
    auto_disseminate: bool
    requires_human_approval: bool
    coalition_agreement: Optional[str] = None
    sharing_restrictions: Optional[List[str]] = None
    receive_threat_levels: Optional[List[str]] = None


@dataclass
class DistanceThreshold:
    """Distance thresholds for an entity type/classification"""
    must_notify_km: float
    never_notify_km: float
    reasoning: str


@dataclass
class NotificationDecision:
    """Result of need-to-know decision"""
    should_notify: bool
    reasoning: str
    decision_type: Literal["must_notify", "never_notify", "llm_needed"]
    distance_km: Optional[float] = None
    threshold_used: Optional[DistanceThreshold] = None


# ==================== CONFIGURATION LOADING ====================

_recipients_cache: Optional[List[RecipientInfo]] = None
_thresholds_cache: Optional[Dict] = None


def load_recipients_config(config_path: Optional[Path] = None) -> List[RecipientInfo]:
    """
    Load recipients from YAML configuration.
    
    Args:
        config_path: Path to recipients.yaml (None = use default)
        
    Returns:
        List of RecipientInfo objects
    """
    global _recipients_cache
    
    if _recipients_cache is not None:
        return _recipients_cache
    
    if config_path is None:
        # Try multiple possible locations
        possible_paths = [
            Path("src/config/recipients.yaml"),
            Path("config/recipients.yaml"),
            Path(__file__).parent.parent / "config" / "recipients.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
        
        if config_path is None:
            raise FileNotFoundError(
                "Could not find recipients.yaml. Tried: " + 
                ", ".join(str(p) for p in possible_paths)
            )
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    recipients = []
    for recipient_data in config['recipients']:
        recipient = RecipientInfo(
            recipient_id=recipient_data['recipient_id'],
            recipient_name=recipient_data['recipient_name'],
            recipient_type=recipient_data['recipient_type'],
            access_level=recipient_data['access_level'],
            location=recipient_data.get('location'),
            is_mobile=recipient_data['is_mobile'],
            elemento_identificado=recipient_data.get('elemento_identificado'),
            operational_role=recipient_data['operational_role'],
            priority_entity_types=recipient_data['priority_entity_types'],
            mqtt_topics=recipient_data['mqtt_topics'],
            supported_formats=recipient_data['supported_formats'],
            auto_disseminate=recipient_data['auto_disseminate'],
            requires_human_approval=recipient_data['requires_human_approval'],
            coalition_agreement=recipient_data.get('coalition_agreement'),
            sharing_restrictions=recipient_data.get('sharing_restrictions'),
            receive_threat_levels=recipient_data.get('receive_threat_levels')
        )
        recipients.append(recipient)
    
    _recipients_cache = recipients
    print(f"✅ Loaded {len(recipients)} recipients from {config_path}")
    
    return recipients


def load_threat_thresholds(config_path: Optional[Path] = None) -> Dict:
    """
    Load distance thresholds from YAML configuration.
    
    Args:
        config_path: Path to threat_thresholds.yaml (None = use default)
        
    Returns:
        Dictionary with thresholds and role modifiers
    """
    global _thresholds_cache
    
    if _thresholds_cache is not None:
        return _thresholds_cache
    
    if config_path is None:
        # Try multiple possible locations
        possible_paths = [
            Path("src/config/threat_thresholds.yaml"),
            Path("config/threat_thresholds.yaml"),
            Path(__file__).parent.parent / "config" / "threat_thresholds.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
        
        if config_path is None:
            raise FileNotFoundError(
                "Could not find threat_thresholds.yaml. Tried: " +
                ", ".join(str(p) for p in possible_paths)
            )
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    _thresholds_cache = config
    print(f"✅ Loaded threat thresholds from {config_path}")
    
    return config


# ==================== DISTANCE CALCULATION ====================

def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    
    Args:
        lat1, lon1: First point (degrees)
        lat2, lon2: Second point (degrees)
        
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    
    distance = R * c
    return round(distance, 2)


# ==================== THRESHOLD RETRIEVAL ====================

def get_distance_threshold(
    entity_type: str,
    classification: str,
    operational_role: Optional[str] = None
) -> DistanceThreshold:
    """
    Get distance thresholds for entity type and classification.
    
    Applies operational role modifiers if applicable.
    
    Args:
        entity_type: Type of entity (aircraft, tank, etc.)
        classification: friendly, hostile, unknown, neutral
        operational_role: Recipient's operational role (for modifiers)
        
    Returns:
        DistanceThreshold with must_notify_km and never_notify_km
    """
    thresholds_config = load_threat_thresholds()
    
    # Get base thresholds
    thresholds_data = thresholds_config['thresholds']
    
    # Try exact entity type match
    if entity_type in thresholds_data:
        entity_thresholds = thresholds_data[entity_type]
    else:
        # Fall back to default
        entity_thresholds = thresholds_data['default']
    
    # Get classification-specific threshold
    if classification in entity_thresholds:
        threshold_data = entity_thresholds[classification]
    else:
        # Fall back to 'unknown' classification
        threshold_data = entity_thresholds.get('unknown', entity_thresholds.get('hostile'))
    
    must_notify_km = threshold_data['must_notify_km']
    never_notify_km = threshold_data['never_notify_km']
    reasoning = threshold_data['reasoning']
    
    # Apply operational role modifier
    if operational_role:
        role_modifiers = thresholds_config.get('role_modifiers', {})
        
        if operational_role in role_modifiers:
            modifier_config = role_modifiers[operational_role]
            
            # Check if this entity type is in the role's priority list
            entity_types = modifier_config['entity_types']
            if entity_types == ["all"] or entity_type in entity_types:
                multiplier = modifier_config['multiplier']
                
                must_notify_km *= multiplier
                never_notify_km *= multiplier
                
                reasoning += f" (Role modifier: {operational_role} ×{multiplier})"
    
    return DistanceThreshold(
        must_notify_km=round(must_notify_km, 2),
        never_notify_km=round(never_notify_km, 2),
        reasoning=reasoning
    )


# ==================== NOTIFICATION DECISION ====================

def should_notify_recipient(
    threat_entity: EntityCOP,
    recipient: RecipientInfo,
    distance_km: float
) -> NotificationDecision:
    """
    Determine if recipient should be notified about this threat.
    
    Uses distance-based rules:
    - distance < must_notify_km → MUST NOTIFY (mandatory)
    - distance > never_notify_km → DON'T NOTIFY (too far)
    - In between → LLM NEEDED (ambiguous)
    
    Args:
        threat_entity: The threat entity
        recipient: Recipient information
        distance_km: Distance from threat to recipient
        
    Returns:
        NotificationDecision with should_notify and reasoning
    """
    # Get distance thresholds
    threshold = get_distance_threshold(
        entity_type=threat_entity.entity_type,
        classification=threat_entity.classification,
        operational_role=recipient.operational_role
    )
    
    # ============ RULE-BASED DECISIONS ============
    
    # Must notify (very close)
    if distance_km < threshold.must_notify_km:
        return NotificationDecision(
            should_notify=True,
            reasoning=f"Distance {distance_km}km < threshold {threshold.must_notify_km}km - MANDATORY notification",
            decision_type="must_notify",
            distance_km=distance_km,
            threshold_used=threshold
        )
    
    # Never notify (too far)
    if distance_km > threshold.never_notify_km:
        return NotificationDecision(
            should_notify=False,
            reasoning=f"Distance {distance_km}km > threshold {threshold.never_notify_km}km - TOO FAR to notify",
            decision_type="never_notify",
            distance_km=distance_km,
            threshold_used=threshold
        )
    
    # ============ AMBIGUOUS (LLM NEEDED) ============
    
    return NotificationDecision(
        should_notify=True,  # Default to yes, let LLM refine
        reasoning=f"Distance {distance_km}km in ambiguous range [{threshold.must_notify_km}, {threshold.never_notify_km}]km - LLM reasoning needed",
        decision_type="llm_needed",
        distance_km=distance_km,
        threshold_used=threshold
    )


def get_notification_decision(
    threat_assessment: ThreatAssessment,
    threat_entity: EntityCOP,
    recipient: RecipientInfo,
    recipient_location: Dict[str, float],
    emergency_override: bool = False
) -> NotificationDecision:
    """
    High-level notification decision combining multiple factors.
    
    Args:
        threat_assessment: Threat assessment object
        threat_entity: The threat source entity
        recipient: Recipient information
        recipient_location: Recipient's current location {lat, lon}
        emergency_override: If True, bypass all rules and notify
        
    Returns:
        NotificationDecision
    """
    # ============ EMERGENCY OVERRIDE ============
    if emergency_override:
        return NotificationDecision(
            should_notify=True,
            reasoning="EMERGENCY OVERRIDE ACTIVE - bypassing all rules",
            decision_type="must_notify",
            distance_km=None
        )
    
    # ============ COMMAND POSTS GET EVERYTHING ============
    if recipient.operational_role in ["command_control", "strategic_command"]:
        return NotificationDecision(
            should_notify=True,
            reasoning=f"Recipient is {recipient.operational_role} - receives all threats",
            decision_type="must_notify",
            distance_km=None
        )
    
    # ============ THREAT LEVEL FILTER ============
    if recipient.receive_threat_levels:
        if threat_assessment.threat_level not in recipient.receive_threat_levels:
            return NotificationDecision(
                should_notify=False,
                reasoning=f"Threat level '{threat_assessment.threat_level}' not in recipient's filter {recipient.receive_threat_levels}",
                decision_type="never_notify",
                distance_km=None
            )
    
    # ============ OPERATIONAL ROLE MATCHING ============
    # Check if entity type matches recipient's priority types
    if recipient.priority_entity_types != ["all"]:
        entity_matches = False
        for priority_type in recipient.priority_entity_types:
            if threat_entity.entity_type == priority_type:
                entity_matches = True
                break
            # Also check category matching (e.g., "fighter" matches "aircraft")
            if priority_type in ["aircraft", "ground_vehicle", "ship"]:
                if threat_entity.entity_type.startswith(priority_type):
                    entity_matches = True
                    break
        
        if not entity_matches:
            return NotificationDecision(
                should_notify=False,
                reasoning=f"Entity type '{threat_entity.entity_type}' not in recipient's priority types {recipient.priority_entity_types}",
                decision_type="never_notify",
                distance_km=None
            )
    
    # ============ DISTANCE-BASED DECISION ============
    distance_km = calculate_distance_km(
        threat_entity.location.lat,
        threat_entity.location.lon,
        recipient_location['lat'],
        recipient_location['lon']
    )
    
    return should_notify_recipient(
        threat_entity=threat_entity,
        recipient=recipient,
        distance_km=distance_km
    )


# ==================== BATCH OPERATIONS ====================

def filter_recipients_by_distance(
    threat_entity: EntityCOP,
    recipients: List[RecipientInfo],
    cop_entities: Dict[str, EntityCOP]
) -> Tuple[List[RecipientInfo], List[RecipientInfo], List[RecipientInfo]]:
    """
    Filter recipients into must-notify, never-notify, and ambiguous groups.
    
    Args:
        threat_entity: Threat source entity
        recipients: List of all recipients
        cop_entities: Full COP for querying mobile unit positions
        
    Returns:
        (must_notify, never_notify, ambiguous) lists
    """
    must_notify = []
    never_notify = []
    ambiguous = []
    
    for recipient in recipients:
        # Skip if no location available
        if recipient.location is None and not recipient.is_mobile:
            ambiguous.append(recipient)
            continue
        
        # Get recipient location
        if recipient.location:
            recipient_location = recipient.location
        elif recipient.is_mobile and recipient.elemento_identificado:
            # Query from COP
            recipient_entity = cop_entities.get(recipient.elemento_identificado)
            if recipient_entity:
                recipient_location = {
                    'lat': recipient_entity.location.lat,
                    'lon': recipient_entity.location.lon
                }
            else:
                # Can't find mobile unit - mark as ambiguous
                ambiguous.append(recipient)
                continue
        else:
            ambiguous.append(recipient)
            continue
        
        # Get notification decision
        decision = should_notify_recipient(
            threat_entity=threat_entity,
            recipient=recipient,
            distance_km=calculate_distance_km(
                threat_entity.location.lat,
                threat_entity.location.lon,
                recipient_location['lat'],
                recipient_location['lon']
            )
        )
        
        if decision.decision_type == "must_notify":
            must_notify.append(recipient)
        elif decision.decision_type == "never_notify":
            never_notify.append(recipient)
        else:  # llm_needed
            ambiguous.append(recipient)
    
    return must_notify, never_notify, ambiguous


# ==================== TESTING ====================

if __name__ == "__main__":
    from datetime import datetime
    from src.models import Location
    
    print("\n" + "=" * 70)
    print("DISSEMINATION RULES TESTING")
    print("=" * 70 + "\n")
    
    # Test 1: Load configurations
    print("Test 1: Load configurations")
    print("-" * 70)
    
    try:
        recipients = load_recipients_config()
        print(f"✅ Loaded {len(recipients)} recipients")
        
        thresholds = load_threat_thresholds()
        print(f"✅ Loaded {len(thresholds['thresholds'])} entity type thresholds")
        print(f"✅ Loaded {len(thresholds['role_modifiers'])} role modifiers")
    except Exception as e:
        print(f"❌ Failed to load configs: {e}")
        exit(1)
    
    # Test 2: Distance calculation
    print("\nTest 2: Distance calculation")
    print("-" * 70)
    
    distance = calculate_distance_km(39.5, 0.4, 39.4, 0.3)
    print(f"Distance from (39.5, 0.4) to (39.4, 0.3): {distance}km")
    print(f"Expected: ~15km")
    
    # Test 3: Threshold retrieval
    print("\nTest 3: Get thresholds with role modifier")
    print("-" * 70)
    
    threshold = get_distance_threshold(
        entity_type="aircraft",
        classification="hostile",
        operational_role="air_defense"
    )
    print(f"Hostile aircraft for air_defense unit:")
    print(f"  Must notify: {threshold.must_notify_km}km")
    print(f"  Never notify: {threshold.never_notify_km}km")
    print(f"  Reasoning: {threshold.reasoning}")
    
    # Test 4: Notification decision
    print("\nTest 4: Notification decision")
    print("-" * 70)
    
    hostile_aircraft = EntityCOP(
        entity_id="hostile_001",
        entity_type="aircraft",
        location=Location(lat=39.5, lon=0.4),
        timestamp=datetime.utcnow(),
        classification="hostile",
        information_classification="SECRET",
        confidence=0.9,
        source_sensors=["radar_01"],
        speed_kmh=850
    )
    
    # Recipient very close (should be must_notify)
    recipient_close = RecipientInfo(
        recipient_id="base_alpha",
        recipient_name="Base Alpha",
        recipient_type="friendly_unit",
        access_level="secret_access",
        location={"lat": 39.52, "lon": 0.42, "alt": 50},  # ~3km away
        is_mobile=False,
        elemento_identificado=None,
        operational_role="air_defense",
        priority_entity_types=["aircraft"],
        mqtt_topics={},
        supported_formats=["json"],
        auto_disseminate=True,
        requires_human_approval=False
    )
    
    decision = should_notify_recipient(
        threat_entity=hostile_aircraft,
        recipient=recipient_close,
        distance_km=3.0
    )
    
    print(f"Decision for recipient 3km away:")
    print(f"  Should notify: {decision.should_notify}")
    print(f"  Decision type: {decision.decision_type}")
    print(f"  Reasoning: {decision.reasoning}")
    print(f"  Expected: MUST_NOTIFY")
    
    print("\n" + "=" * 70)
    print("DISSEMINATION RULES TEST COMPLETE")
    print("=" * 70 + "\n")