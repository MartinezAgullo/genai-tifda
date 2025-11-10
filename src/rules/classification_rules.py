"""
Classification Rules
====================

Rules for handling classified information:
- Access control (who can see what)
- Classification downgrading (removing sensitive details)
- Entity filtering by clearance level
"""

from typing import List, Dict, Literal, Optional
from copy import deepcopy

from src.models import EntityCOP


# ==================== CLASSIFICATION HIERARCHY ====================

CLASSIFICATION_HIERARCHY = [
    "TOP_SECRET",
    "SECRET",
    "CONFIDENTIAL",
    "RESTRICTED",
    "UNCLASSIFIED"
]
"""Information classification levels (highest to lowest)"""

ACCESS_LEVEL_TO_CLASSIFICATION = {
    "top_secret_access": "TOP_SECRET",
    "secret_access": "SECRET",
    "confidential_access": "CONFIDENTIAL",
    "restricted_access": "RESTRICTED",
    "unclassified_access": "UNCLASSIFIED",
}
"""Map access levels to maximum classification they can view"""


# ==================== ACCESS CONTROL ====================

def _get_classification_index(classification: str) -> int:
    """
    Get numeric index for classification (lower = more classified).
    
    Args:
        classification: Classification string
        
    Returns:
        Index (0 = TOP_SECRET, 4 = UNCLASSIFIED)
    """
    try:
        return CLASSIFICATION_HIERARCHY.index(classification)
    except ValueError:
        # Unknown classification - treat as most restrictive
        return 0


def can_recipient_access(
    recipient_access_level: str,
    information_classification: str
) -> bool:
    """
    Check if recipient can access information at given classification.
    
    Args:
        recipient_access_level: e.g., "secret_access"
        information_classification: e.g., "TOP_SECRET"
        
    Returns:
        True if recipient has sufficient clearance
    """
    # Get max classification recipient can see
    max_classification = ACCESS_LEVEL_TO_CLASSIFICATION.get(
        recipient_access_level,
        "UNCLASSIFIED"
    )
    
    # Get indices (lower = more classified)
    recipient_index = _get_classification_index(max_classification)
    required_index = _get_classification_index(information_classification)
    
    # Can access if recipient clearance >= required clearance
    return recipient_index <= required_index


def get_highest_accessible_classification(recipient_access_level: str) -> str:
    """
    Get the highest classification level a recipient can access.
    
    Args:
        recipient_access_level: Access level string
        
    Returns:
        Highest classification (e.g., "SECRET")
    """
    return ACCESS_LEVEL_TO_CLASSIFICATION.get(
        recipient_access_level,
        "UNCLASSIFIED"
    )


# ==================== CLASSIFICATION DOWNGRADING ====================

def downgrade_entity_classification(
    entity: EntityCOP,
    target_classification: str
) -> EntityCOP:
    """
    Downgrade entity to target classification by removing sensitive details.
    
    Downgrading rules:
    - TOP_SECRET → SECRET: Remove exact sensor sources, precise speed/heading
    - SECRET → CONFIDENTIAL: Remove precise location (round to 0.01°), confidence
    - CONFIDENTIAL → RESTRICTED: Remove metadata, keep only basic info
    - RESTRICTED → UNCLASSIFIED: Keep only entity type and general area
    
    Args:
        entity: Original entity
        target_classification: Target classification level
        
    Returns:
        Downgraded copy of entity
    """
    # Work with a copy
    downgraded = deepcopy(entity)
    
    # Get classification indices
    original_index = _get_classification_index(entity.information_classification)
    target_index = _get_classification_index(target_classification)
    
    # No downgrading needed if target is same or more classified
    if target_index <= original_index:
        return downgraded
    
    # Update classification field
    downgraded.information_classification = target_classification
    
    # ============ DOWNGRADE FROM TOP_SECRET ============
    if original_index == 0:  # Was TOP_SECRET
        # Remove exact sensor sources (keep count only)
        if len(downgraded.source_sensors) > 0:
            downgraded.source_sensors = [f"{len(downgraded.source_sensors)} sources"]
        
        # Round speed and heading
        if downgraded.speed_kmh:
            downgraded.speed_kmh = round(downgraded.speed_kmh / 50) * 50  # Round to nearest 50
        
        if downgraded.heading is not None:
            downgraded.heading = round(downgraded.heading / 10) * 10  # Round to nearest 10°
        
        # Remove sensitive metadata
        if "multimodal_results" in downgraded.metadata:
            del downgraded.metadata["multimodal_results"]
        
        if "raw_sensor_data" in downgraded.metadata:
            del downgraded.metadata["raw_sensor_data"]
    
    # ============ DOWNGRADE FROM SECRET ============
    if original_index <= 1 and target_index >= 2:  # To CONFIDENTIAL or below
        # Round location to 0.01° (~1km precision)
        downgraded.location.lat = round(downgraded.location.lat, 2)
        downgraded.location.lon = round(downgraded.location.lon, 2)
        
        # Remove altitude
        if downgraded.location.alt is not None:
            downgraded.location.alt = None
        
        # Reduce confidence precision
        downgraded.confidence = round(downgraded.confidence, 1)
        
        # Remove detailed metadata
        downgraded.metadata = {
            k: v for k, v in downgraded.metadata.items()
            if k in ["detection_time", "last_update"]
        }
    
    # ============ DOWNGRADE FROM CONFIDENTIAL ============
    if original_index <= 2 and target_index >= 3:  # To RESTRICTED or below
        # Remove all metadata
        downgraded.metadata = {}
        
        # Remove source sensors
        downgraded.source_sensors = []
        
        # Remove speed/heading
        downgraded.speed_kmh = None
        downgraded.heading = None
        
        # Remove comments
        downgraded.comments = None
    
    # ============ DOWNGRADE TO UNCLASSIFIED ============
    if target_index == 4:  # UNCLASSIFIED
        # Keep only: entity_id, entity_type, approximate location, classification
        downgraded.location.lat = round(downgraded.location.lat, 1)  # ~10km precision
        downgraded.location.lon = round(downgraded.location.lon, 1)
        downgraded.location.alt = None
        
        downgraded.confidence = 0.5  # Generic "moderate" confidence
        downgraded.source_sensors = []
        downgraded.metadata = {}
        downgraded.speed_kmh = None
        downgraded.heading = None
        downgraded.comments = "Location approximate"
    
    return downgraded


# ==================== ENTITY FILTERING ====================

def filter_entities_by_clearance(
    entities: List[EntityCOP],
    recipient_access_level: str,
    emergency_override: bool = False
) -> List[EntityCOP]:
    """
    Filter and downgrade entities based on recipient's clearance.
    
    Args:
        entities: List of entities to filter
        recipient_access_level: Recipient's access level
        emergency_override: If True, bypass classification (return all at original level)
        
    Returns:
        List of entities recipient can access (downgraded if necessary)
    """
    if emergency_override:
        # Emergency override: return everything as-is
        return entities
    
    max_classification = get_highest_accessible_classification(recipient_access_level)
    
    accessible_entities = []
    
    for entity in entities:
        # Check if recipient can access this entity
        if can_recipient_access(recipient_access_level, entity.information_classification):
            # Can access - but may need downgrading
            if entity.information_classification == max_classification:
                # No downgrading needed
                accessible_entities.append(entity)
            else:
                # Downgrade to recipient's max level
                downgraded = downgrade_entity_classification(entity, max_classification)
                accessible_entities.append(downgraded)
        # If can't access, skip entity entirely
    
    return accessible_entities


def get_accessible_entity_ids(
    entities: Dict[str, EntityCOP],
    recipient_access_level: str
) -> List[str]:
    """
    Get list of entity IDs that recipient can access.
    
    Args:
        entities: Dictionary of entities {entity_id: EntityCOP}
        recipient_access_level: Recipient's access level
        
    Returns:
        List of accessible entity IDs
    """
    accessible_ids = []
    
    for entity_id, entity in entities.items():
        if can_recipient_access(recipient_access_level, entity.information_classification):
            accessible_ids.append(entity_id)
    
    return accessible_ids


# ==================== CLASSIFICATION SUMMARY ====================

def get_classification_summary(entities: List[EntityCOP]) -> Dict[str, int]:
    """
    Get summary of classification levels in entity list.
    
    Args:
        entities: List of entities
        
    Returns:
        Dictionary with counts per classification level
    """
    summary = {level: 0 for level in CLASSIFICATION_HIERARCHY}
    
    for entity in entities:
        classification = entity.information_classification
        if classification in summary:
            summary[classification] += 1
        else:
            summary["UNCLASSIFIED"] += 1  # Unknown = treat as unclassified
    
    return summary


# ==================== TESTING ====================

if __name__ == "__main__":
    from datetime import datetime, timezone
    from src.models import Location
    
    print("\n" + "=" * 70)
    print("CLASSIFICATION RULES TESTING")
    print("=" * 70 + "\n")
    
    # Test 1: Access control
    print("Test 1: Access control checks")
    print("-" * 70)
    
    tests = [
        ("secret_access", "SECRET", True),
        ("secret_access", "TOP_SECRET", False),
        ("secret_access", "CONFIDENTIAL", True),
        ("confidential_access", "SECRET", False),
        ("top_secret_access", "TOP_SECRET", True),
    ]
    
    for access_level, classification, expected in tests:
        result = can_recipient_access(access_level, classification)
        status = "✅" if result == expected else "❌"
        print(f"{status} {access_level} accessing {classification}: {result} (expected {expected})")
    
    # Test 2: Downgrading
    print("\nTest 2: Classification downgrading")
    print("-" * 70)
    
    top_secret_entity = EntityCOP(
        entity_id="radar_001_T001",
        entity_type="aircraft",
        location=Location(lat=39.123456, lon=0.456789, alt=5000),
        timestamp=datetime.now(timezone.utc),
        classification="hostile",
        information_classification="TOP_SECRET",
        confidence=0.95,
        source_sensors=["radar_001", "radar_002", "elint_003"],
        metadata={
            "multimodal_results": {"audio": "classified"},
            "raw_sensor_data": "classified",
            "detection_time": "14:30:00"
        },
        speed_kmh=876,
        heading=127,
        comments="High confidence hostile fighter"
    )
    
    print(f"Original (TOP_SECRET):")
    print(f"  Location: {top_secret_entity.location.lat}, {top_secret_entity.location.lon}, {top_secret_entity.location.alt}m")
    print(f"  Speed: {top_secret_entity.speed_kmh} km/h, Heading: {top_secret_entity.heading}°")
    print(f"  Sensors: {top_secret_entity.source_sensors}")
    print(f"  Metadata keys: {list(top_secret_entity.metadata.keys())}")
    
    # Downgrade to SECRET
    secret_entity = downgrade_entity_classification(top_secret_entity, "SECRET")
    print(f"\nDowngraded to SECRET:")
    print(f"  Location: {secret_entity.location.lat}, {secret_entity.location.lon}, {secret_entity.location.alt}")
    print(f"  Speed: {secret_entity.speed_kmh} km/h, Heading: {secret_entity.heading}°")
    print(f"  Sensors: {secret_entity.source_sensors}")
    print(f"  Metadata keys: {list(secret_entity.metadata.keys())}")
    
    # Downgrade to CONFIDENTIAL
    confidential_entity = downgrade_entity_classification(top_secret_entity, "CONFIDENTIAL")
    print(f"\nDowngraded to CONFIDENTIAL:")
    print(f"  Location: {confidential_entity.location.lat}, {confidential_entity.location.lon}, {confidential_entity.location.alt}")
    print(f"  Speed: {confidential_entity.speed_kmh}, Heading: {confidential_entity.heading}")
    print(f"  Sensors: {confidential_entity.source_sensors}")
    print(f"  Metadata keys: {list(confidential_entity.metadata.keys())}")
    
    # Downgrade to UNCLASSIFIED
    unclassified_entity = downgrade_entity_classification(top_secret_entity, "UNCLASSIFIED")
    print(f"\nDowngraded to UNCLASSIFIED:")
    print(f"  Location: {unclassified_entity.location.lat}, {unclassified_entity.location.lon}, {unclassified_entity.location.alt}")
    print(f"  Speed: {unclassified_entity.speed_kmh}, Heading: {unclassified_entity.heading}")
    print(f"  Sensors: {unclassified_entity.source_sensors}")
    print(f"  Metadata: {unclassified_entity.metadata}")
    print(f"  Comments: {unclassified_entity.comments}")
    
    # Test 3: Entity filtering
    print("\nTest 3: Entity filtering by clearance")
    print("-" * 70)
    
    entities = [
        top_secret_entity,
        EntityCOP(
            entity_id="friendly_001",
            entity_type="tank",
            location=Location(lat=39.4, lon=0.3),
            timestamp=datetime.now(timezone.utc),
            classification="friendly",
            information_classification="CONFIDENTIAL",
            confidence=1.0,
            source_sensors=["manual"]
        )
    ]
    
    filtered = filter_entities_by_clearance(entities, "secret_access")
    print(f"Original entities: {len(entities)}")
    print(f"Filtered for secret_access: {len(filtered)}")
    print(f"Expected: 1 (TOP_SECRET filtered out, CONFIDENTIAL downgraded to SECRET)")
    
    if filtered:
        print(f"  Entity 1: {filtered[0].entity_id}, classification={filtered[0].information_classification}")
    
    print("\n" + "=" * 70)
    print("CLASSIFICATION RULES TEST COMPLETE")
    print("=" * 70 + "\n")