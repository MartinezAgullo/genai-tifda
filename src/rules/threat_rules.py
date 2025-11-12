"""
Threat Assessment Rules
===================================

Deterministic rules for quick threat evaluation.
These rules handle obvious cases without LLM calls.

ENHANCED: Now uses complete threat_thresholds.yaml data including:
- threat_multiplier for scoring
- must_notify_km for critical distance decisions  
- never_notify_km for far-away filtering
- classification-specific thresholds
"""

from typing import Optional, Literal, Dict, Any, Tuple
from datetime import datetime, timezone, UTC
from pathlib import Path
import yaml

from src.models import EntityCOP


# ==================== THREAT TRIGGERS ====================

THREAT_TRIGGER_CLASSIFICATIONS = ["hostile", "unknown"]
"""Classifications that trigger threat assessment"""

NON_THREAT_CLASSIFICATIONS = ["friendly", "neutral"]
"""Classifications that generally don't pose threats"""


# ==================== LOAD THRESHOLDS FROM CONFIG ====================

_threat_thresholds_cache: Optional[Dict] = None


def _load_threat_thresholds() -> Dict:
    """
    Load complete threat thresholds from threat_thresholds.yaml.
    
    Returns:
        Dictionary with thresholds and role modifiers:
        {
            'thresholds': {
                'aircraft': {
                    'hostile': {'must_notify_km': 300, 'never_notify_km': 600, 'threat_multiplier': 2.0, ...},
                    'friendly': {...},
                    ...
                },
                ...
            },
            'role_modifiers': {...}
        }
    """
    global _threat_thresholds_cache
    
    if _threat_thresholds_cache is not None:
        return _threat_thresholds_cache
    
    # Try multiple possible locations
    possible_paths = [
        Path("config/threat_thresholds.yaml"),
        Path("src/config/threat_thresholds.yaml"),
        Path(__file__).parent.parent / "config" / "threat_thresholds.yaml",
    ]
    
    config_path = None
    for path in possible_paths:
        if path.exists():
            config_path = path
            break
    
    if config_path is None:
        # Fall back to minimal default if config not found
        print("⚠️  threat_thresholds.yaml not found, using minimal defaults")
        _threat_thresholds_cache = {
            'thresholds': {
                'default': {
                    'hostile': {'must_notify_km': 100, 'never_notify_km': 300, 'threat_multiplier': 1.0},
                    'unknown': {'must_notify_km': 75, 'never_notify_km': 250, 'threat_multiplier': 1.0},
                    'friendly': {'must_notify_km': 75, 'never_notify_km': 250, 'threat_multiplier': 1.0},
                    'neutral': {'must_notify_km': 25, 'never_notify_km': 100, 'threat_multiplier': 1.0},
                }
            },
            'role_modifiers': {}
        }
        return _threat_thresholds_cache
    
    # Load from YAML
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    _threat_thresholds_cache = config
    return config


def get_distance_thresholds(
    entity_type: str,
    classification: str
) -> Tuple[float, float, float]:
    """
    Get distance thresholds for entity type and classification from YAML.
    
    Args:
        entity_type: Type of entity (e.g., 'aircraft', 'tank')
        classification: Classification (e.g., 'hostile', 'friendly')
        
    Returns:
        Tuple of (must_notify_km, never_notify_km, threat_multiplier)
    """
    config = _load_threat_thresholds()
    thresholds = config.get('thresholds', {})
    
    # Try exact entity type first
    entity_thresholds = thresholds.get(entity_type, {})
    classification_data = entity_thresholds.get(classification, None)
    
    # Fallback to default if not found
    if not classification_data:
        default_thresholds = thresholds.get('default', {})
        classification_data = default_thresholds.get(classification, {
            'must_notify_km': 100,
            'never_notify_km': 300,
            'threat_multiplier': 1.0
        })
    
    return (
        classification_data.get('must_notify_km', 100),
        classification_data.get('never_notify_km', 300),
        classification_data.get('threat_multiplier', 1.0)
    )


def get_threat_multiplier(entity_type: str, classification: str = 'hostile') -> float:
    """
    Get threat multiplier for entity type and classification from YAML.
    
    Args:
        entity_type: Type of entity
        classification: Classification (default: 'hostile')
        
    Returns:
        Threat multiplier (higher = more threatening)
    """
    _, _, multiplier = get_distance_thresholds(entity_type, classification)
    return multiplier


# ==================== SPEED-BASED THREAT ASSESSMENT ====================

def _assess_speed_threat(speed_kmh: Optional[float], entity_type: str) -> float:
    """
    Assess threat based on speed (fast-moving entities are more threatening).
    
    Args:
        speed_kmh: Speed in km/h
        entity_type: Type of entity
        
    Returns:
        Threat multiplier (0.5 to 2.0)
    """
    if speed_kmh is None:
        return 1.0  # Unknown speed, neutral
    
    # Aircraft speed ranges
    if entity_type in ["aircraft", "fighter", "bomber", "helicopter", "missile"]:
        if speed_kmh > 800:  # Supersonic
            return 2.0  # Very high threat (military fast jet)
        elif speed_kmh > 500:
            return 1.8  # High threat (military aircraft)
        elif speed_kmh > 300:
            return 1.3  # Moderate threat (transport or slow fighter)
        elif speed_kmh > 100:
            return 1.0  # Low threat (helicopter, slow aircraft)
        else:
            return 0.7  # Very slow (maybe hovering helicopter)
    
    # Ground vehicle speed ranges
    elif entity_type in ["ground_vehicle", "tank", "apc"]:
        if speed_kmh > 60:
            return 1.5  # Fast-moving ground unit (maneuvering)
        elif speed_kmh > 30:
            return 1.2  # Normal movement
        elif speed_kmh > 10:
            return 1.0  # Slow movement
        else:
            return 0.8  # Stationary or very slow
    
    # Ships
    elif entity_type in ["ship", "destroyer", "submarine"]:
        if speed_kmh > 50:
            return 1.5  # High-speed approach
        elif speed_kmh > 20:
            return 1.2  # Normal cruising
        else:
            return 1.0  # Slow or stationary
    
    return 1.0


# ==================== RULE-BASED THREAT ASSESSMENT ====================

def should_assess_threat(entity: EntityCOP) -> bool:
    """
    Quick check: Does this entity need threat assessment?
    
    Args:
        entity: Entity to check
        
    Returns:
        True if threat assessment is needed
    """
    # Always assess hostile and unknown
    if entity.classification in THREAT_TRIGGER_CLASSIFICATIONS:
        return True
    
    # Don't assess friendly (unless speed is suspicious)
    if entity.classification == "friendly":
        # Exception: Very fast friendly aircraft might be interceptor responding to threat
        if entity.speed_kmh and entity.speed_kmh > 800:
            return True  # Assess to understand situation
        return False
    
    # Neutral entities only assessed if close or fast-moving
    if entity.classification == "neutral":
        # This is a quick filter - actual distance check happens later
        return False
    
    return True


def get_obvious_threat_level(
    entity: EntityCOP,
    distance_to_nearest_friendly_km: Optional[float] = None
) -> Optional[Literal["critical", "high", "medium", "low", "none"]]:
    """
    Deterministic threat level for obvious cases (no LLM needed).
    
    Uses thresholds from threat_thresholds.yaml for intelligent decisions.
    Returns None if ambiguous (LLM should decide).
    
    Args:
        entity: Entity to assess
        distance_to_nearest_friendly_km: Distance to closest friendly (if known)
        
    Returns:
        Threat level if obvious, None if ambiguous
    """
    # ============ OBVIOUS NON-THREATS ============
    
    if entity.classification == "friendly":
        return "none"  # Friendly = no threat
    
    # Use YAML thresholds for neutral entities
    if entity.classification == "neutral" and distance_to_nearest_friendly_km:
        _, never_notify_km, _ = get_distance_thresholds(entity.entity_type, "neutral")
        if distance_to_nearest_friendly_km > never_notify_km:
            return "none"  # Neutral far away (beyond never_notify threshold) = no threat
    
    # ============ OBVIOUS CRITICAL THREATS ============
    
    # Hostile missile = CRITICAL (always)
    if entity.classification == "hostile" and entity.entity_type == "missile":
        return "critical"
    
    # Use YAML thresholds for hostile aircraft proximity decisions
    if entity.classification == "hostile" and entity.entity_type in ["aircraft", "fighter", "bomber"]:
        if distance_to_nearest_friendly_km:
            must_notify_km, _, _ = get_distance_thresholds(entity.entity_type, "hostile")
            
            # Very close (< 10km) = CRITICAL
            if distance_to_nearest_friendly_km < 10:
                return "critical"
            
            # Within must_notify range = HIGH
            if distance_to_nearest_friendly_km < must_notify_km * 0.5:  # Within half of must_notify
                return "high"
    
    # High-speed unknown approaching = HIGH (could be hostile)
    if (entity.classification == "unknown" and
        entity.speed_kmh and entity.speed_kmh > 700 and
        distance_to_nearest_friendly_km):
        
        must_notify_km, _, _ = get_distance_thresholds(entity.entity_type, "unknown")
        if distance_to_nearest_friendly_km < must_notify_km:
            return "high"
    
    # ============ OBVIOUS HIGH THREATS ============
    
    # Hostile forces close to friendlies - use YAML thresholds
    if entity.classification == "hostile" and distance_to_nearest_friendly_km:
        must_notify_km, _, _ = get_distance_thresholds(entity.entity_type, "hostile")
        
        # Within must_notify threshold = HIGH threat
        if distance_to_nearest_friendly_km < must_notify_km * 0.3:  # Within 30% of must_notify
            return "high"
    
    # ============ OBVIOUS FAR-AWAY (LOW or NONE) ============
    
    # Use YAML never_notify threshold
    if distance_to_nearest_friendly_km:
        _, never_notify_km, _ = get_distance_thresholds(entity.entity_type, entity.classification)
        
        # Beyond never_notify threshold = no significant threat
        if distance_to_nearest_friendly_km > never_notify_km:
            if entity.classification == "hostile":
                return "low"  # Hostile but very far
            else:
                return "none"  # Unknown/neutral and far away
    
    # ============ AMBIGUOUS CASES ============
    
    # Everything else needs LLM reasoning
    return None


def calculate_threat_score(
    entity: EntityCOP,
    distance_to_nearest_friendly_km: float,
    confidence_weight: float = 0.8
) -> float:
    """
    Calculate numeric threat score (0-100) for prioritization.
    
    Uses threat_multiplier from YAML config.
    Higher score = more threatening.
    
    Args:
        entity: Entity to score
        distance_to_nearest_friendly_km: Distance to closest friendly
        confidence_weight: How much to weight entity confidence (0-1)
        
    Returns:
        Threat score (0-100)
    """
    score = 0.0
    
    # ============ BASE SCORE BY CLASSIFICATION ============
    classification_scores = {
        "hostile": 80,
        "unknown": 50,
        "neutral": 20,
        "friendly": 0
    }
    score += classification_scores.get(entity.classification, 30)
    
    # ============ ENTITY TYPE MULTIPLIER FROM YAML ============
    type_multiplier = get_threat_multiplier(entity.entity_type, entity.classification)
    score *= type_multiplier
    
    # ============ DISTANCE PENALTY USING YAML THRESHOLDS ============
    # Use must_notify_km and never_notify_km for intelligent distance scaling
    must_notify_km, never_notify_km, _ = get_distance_thresholds(
        entity.entity_type,
        entity.classification
    )
    
    if distance_to_nearest_friendly_km < must_notify_km * 0.5:
        distance_multiplier = 2.0  # Very close (within half of must_notify)
    elif distance_to_nearest_friendly_km < must_notify_km:
        distance_multiplier = 1.5  # Close (within must_notify range)
    elif distance_to_nearest_friendly_km < never_notify_km:
        distance_multiplier = 1.0  # Moderate (between thresholds)
    elif distance_to_nearest_friendly_km < never_notify_km * 1.5:
        distance_multiplier = 0.7  # Far (beyond never_notify)
    else:
        distance_multiplier = 0.3  # Very far
    
    score *= distance_multiplier
    
    # ============ SPEED ASSESSMENT ============
    speed_multiplier = _assess_speed_threat(entity.speed_kmh, entity.entity_type)
    score *= speed_multiplier
    
    # ============ CONFIDENCE ADJUSTMENT ============
    # Lower confidence = slightly lower threat score (but not too much)
    confidence_factor = confidence_weight * entity.confidence + (1 - confidence_weight)
    score *= confidence_factor
    
    # ============ NORMALIZE TO 0-100 ============
    score = min(100, max(0, score))
    
    return round(score, 2)


# ==================== UTILITY FUNCTIONS ====================

def is_high_priority_entity_type(entity_type: str) -> bool:
    """
    Check if entity type is high-priority (requires immediate attention).
    
    Args:
        entity_type: Entity type string
        
    Returns:
        True if high-priority
    """
    high_priority_types = [
        "missile",
        "fighter",
        "bomber",
        "submarine",
        "artillery"
    ]
    return entity_type in high_priority_types


def get_entity_threat_category(entity_type: str) -> str:
    """
    Get threat category for entity type.
    
    Args:
        entity_type: Entity type string
        
    Returns:
        Category: "air", "ground", "naval", "infrastructure", "other"
    """
    air_types = ["aircraft", "fighter", "bomber", "helicopter", "uav", "missile"]
    ground_types = ["tank", "apc", "ground_vehicle", "infantry", "artillery", "person"]
    naval_types = ["ship", "destroyer", "submarine", "carrier", "patrol_boat"]
    infrastructure_types = ["base", "building", "infrastructure", "radar_site"]
    
    if entity_type in air_types:
        return "air"
    elif entity_type in ground_types:
        return "ground"
    elif entity_type in naval_types:
        return "naval"
    elif entity_type in infrastructure_types:
        return "infrastructure"
    else:
        return "other"


def get_threshold_info(entity_type: str, classification: str) -> Dict[str, Any]:
    """
    Get complete threshold information for an entity type and classification.
    
    Useful for logging and debugging.
    
    Args:
        entity_type: Type of entity
        classification: Classification
        
    Returns:
        Dictionary with must_notify_km, never_notify_km, threat_multiplier, reasoning
    """
    config = _load_threat_thresholds()
    thresholds = config.get('thresholds', {})
    
    # Try exact entity type first
    entity_thresholds = thresholds.get(entity_type, {})
    classification_data = entity_thresholds.get(classification, None)
    
    # Fallback to default
    if not classification_data:
        default_thresholds = thresholds.get('default', {})
        classification_data = default_thresholds.get(classification, {})
    
    return classification_data


# ==================== TESTING ====================

if __name__ == "__main__":
    from datetime import datetime, timezone
    from src.models import Location
    
    print("\n" + "=" * 70)
    print("THREAT RULES TESTING (Enhanced with YAML)")
    print("=" * 70 + "\n")
    
    # Test 0: Show loaded thresholds
    print("Test 0: YAML Configuration Loading")
    print("-" * 70)
    config = _load_threat_thresholds()
    print(f"Loaded thresholds for {len(config.get('thresholds', {}))} entity types")
    print(f"Loaded {len(config.get('role_modifiers', {}))} role modifiers")
    
    # Show example thresholds
    for entity_type in ['aircraft', 'missile', 'tank']:
        for classification in ['hostile', 'friendly']:
            info = get_threshold_info(entity_type, classification)
            print(f"\n{entity_type} ({classification}):")
            print(f"  must_notify: {info.get('must_notify_km')}km")
            print(f"  never_notify: {info.get('never_notify_km')}km")
            print(f"  multiplier: {info.get('threat_multiplier')}")
    
    # Test 1: Hostile missile (should be CRITICAL)
    print("\n\nTest 1: Hostile missile")
    print("-" * 70)
    missile = EntityCOP(
        entity_id="missile_001",
        entity_type="missile",
        location=Location(lat=39.5, lon=0.4),
        timestamp=datetime.now(UTC),
        classification="hostile",
        information_classification="SECRET",
        confidence=0.95,
        source_sensors=["radar_01"],
        speed_kmh=1200
    )
    
    threat_level = get_obvious_threat_level(missile, distance_to_nearest_friendly_km=50)
    threat_score = calculate_threat_score(missile, distance_to_nearest_friendly_km=50)
    
    print(f"  Should assess: {should_assess_threat(missile)}")
    print(f"  Threat level: {threat_level}")
    print(f"  Threat score: {threat_score}")
    print(f"  Expected: CRITICAL, score ~95+")
    
    # Test 2: Unknown slow aircraft far away
    print("\nTest 2: Unknown slow aircraft far away")
    print("-" * 70)
    aircraft = EntityCOP(
        entity_id="aircraft_002",
        entity_type="aircraft",
        location=Location(lat=39.8, lon=0.8),
        timestamp=datetime.now(UTC),
        classification="unknown",
        information_classification="SECRET",
        confidence=0.75,
        source_sensors=["radar_01"],
        speed_kmh=250
    )
    
    # Test at different distances
    for distance in [50, 200, 400]:
        threat_level = get_obvious_threat_level(aircraft, distance_to_nearest_friendly_km=distance)
        threat_score = calculate_threat_score(aircraft, distance_to_nearest_friendly_km=distance)
        
        must_notify, never_notify, _ = get_distance_thresholds("aircraft", "unknown")
        print(f"\n  Distance: {distance}km (must_notify: {must_notify}km, never_notify: {never_notify}km)")
        print(f"  Threat level: {threat_level}")
        print(f"  Threat score: {threat_score}")
    
    # Test 3: Friendly tank
    print("\n\nTest 3: Friendly tank")
    print("-" * 70)
    tank = EntityCOP(
        entity_id="tank_003",
        entity_type="tank",
        location=Location(lat=39.4, lon=0.3),
        timestamp=datetime.now(UTC),
        classification="friendly",
        information_classification="SECRET",
        confidence=1.0,
        source_sensors=["manual"],
        speed_kmh=30
    )
    
    threat_level = get_obvious_threat_level(tank, distance_to_nearest_friendly_km=0)
    threat_score = calculate_threat_score(tank, distance_to_nearest_friendly_km=0)
    
    print(f"  Should assess: {should_assess_threat(tank)}")
    print(f"  Threat level: {threat_level}")
    print(f"  Threat score: {threat_score}")
    print(f"  Expected: NONE, score ~0")
    
    print("\n" + "=" * 70)
    print("THREAT RULES TEST COMPLETE")
    print("=" * 70 + "\n")