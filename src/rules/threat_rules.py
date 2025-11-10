"""
Threat Assessment Rules
=======================

Deterministic rules for quick threat evaluation.
These rules handle obvious cases without LLM calls.
"""

from typing import Optional, Literal, Dict, Any
from datetime import datetime, timezone, UTC
from pathlib import Path
import yaml

from src.models import EntityCOP


# ==================== THREAT TRIGGERS ====================

THREAT_TRIGGER_CLASSIFICATIONS = ["hostile", "unknown"]
"""Classifications that trigger threat assessment"""

NON_THREAT_CLASSIFICATIONS = ["friendly", "neutral"]
"""Classifications that generally don't pose threats"""


# ==================== LOAD THREAT MULTIPLIERS FROM CONFIG ====================

_threat_multipliers_cache: Optional[Dict[str, float]] = None


def _load_threat_multipliers() -> Dict[str, float]:
    """
    Load threat multipliers from threat_thresholds.yaml.
    
    Returns:
        Dictionary mapping entity_type -> threat_multiplier
    """
    global _threat_multipliers_cache
    
    if _threat_multipliers_cache is not None:
        return _threat_multipliers_cache
    
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
        # Fall back to default multipliers if config not found
        print("⚠️  threat_thresholds.yaml not found, using default multipliers")
        _threat_multipliers_cache = {
            "missile": 3.0,
            "fighter": 2.5,
            "bomber": 2.5,
            "aircraft": 2.0,
            "helicopter": 1.8,
            "uav": 1.5,
            "tank": 1.5,
            "artillery": 1.5,
            "ship": 1.3,
            "destroyer": 1.4,
            "submarine": 1.6,
            "ground_vehicle": 1.0,
            "apc": 1.0,
            "infantry": 0.8,
            "person": 0.5,
            "base": 0.3,
            "building": 0.2,
            "infrastructure": 0.2,
            "default": 1.0
        }
        return _threat_multipliers_cache
    
    # Load from YAML
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Extract threat_multiplier for each entity type
    multipliers = {}
    thresholds = config.get('thresholds', {})
    
    for entity_type, classifications in thresholds.items():
        # Get multiplier from any classification (they should all be the same)
        for classification_data in classifications.values():
            if isinstance(classification_data, dict) and 'threat_multiplier' in classification_data:
                multipliers[entity_type] = classification_data['threat_multiplier']
                break
    
    # Add default if not present
    if 'default' not in multipliers:
        multipliers['default'] = 1.0
    
    _threat_multipliers_cache = multipliers
    return multipliers


def get_threat_multiplier(entity_type: str) -> float:
    """
    Get threat multiplier for entity type.
    
    Args:
        entity_type: Type of entity
        
    Returns:
        Threat multiplier (higher = more threatening)
    """
    multipliers = _load_threat_multipliers()
    return multipliers.get(entity_type, multipliers.get('default', 1.0))


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
    
    if entity.classification == "neutral" and distance_to_nearest_friendly_km and distance_to_nearest_friendly_km > 100:
        return "none"  # Neutral far away = no threat
    
    # ============ OBVIOUS CRITICAL THREATS ============
    
    # Hostile missile = CRITICAL (always)
    if entity.classification == "hostile" and entity.entity_type == "missile":
        return "critical"
    
    # Hostile aircraft very close = CRITICAL
    if (entity.classification == "hostile" and 
        entity.entity_type in ["aircraft", "fighter", "bomber"] and
        distance_to_nearest_friendly_km and distance_to_nearest_friendly_km < 10):
        return "critical"
    
    # High-speed unknown approaching = HIGH (could be hostile)
    if (entity.classification == "unknown" and
        entity.speed_kmh and entity.speed_kmh > 700 and
        distance_to_nearest_friendly_km and distance_to_nearest_friendly_km < 50):
        return "high"
    
    # ============ OBVIOUS HIGH THREATS ============
    
    # Hostile forces close to friendlies
    if (entity.classification == "hostile" and
        distance_to_nearest_friendly_km and distance_to_nearest_friendly_km < 30):
        return "high"
    
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
    
    # ============ ENTITY TYPE MULTIPLIER ============
    type_multiplier = get_threat_multiplier(entity.entity_type)
    score *= type_multiplier
    
    # ============ DISTANCE PENALTY ============
    # Closer = higher threat
    if distance_to_nearest_friendly_km < 10:
        distance_multiplier = 2.0  # Very close
    elif distance_to_nearest_friendly_km < 50:
        distance_multiplier = 1.5  # Close
    elif distance_to_nearest_friendly_km < 100:
        distance_multiplier = 1.2  # Moderate
    elif distance_to_nearest_friendly_km < 200:
        distance_multiplier = 1.0  # Far
    else:
        distance_multiplier = 0.5  # Very far
    
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


# ==================== TESTING ====================

if __name__ == "__main__":
    from datetime import datetime, timezone
    from src.models import Location
    
    print("\n" + "=" * 70)
    print("THREAT RULES TESTING")
    print("=" * 70 + "\n")
    
    # Test 1: Hostile missile (should be CRITICAL)
    print("Test 1: Hostile missile")
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
    
    threat_level = get_obvious_threat_level(aircraft, distance_to_nearest_friendly_km=300)
    threat_score = calculate_threat_score(aircraft, distance_to_nearest_friendly_km=300)
    
    print(f"  Should assess: {should_assess_threat(aircraft)}")
    print(f"  Threat level: {threat_level} (None = LLM should decide)")
    print(f"  Threat score: {threat_score}")
    print(f"  Expected: None (ambiguous), score ~30-50")
    
    # Test 3: Friendly tank
    print("\nTest 3: Friendly tank")
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