"""
COP Normalizer Node
===================

Fourth node in the TIFDA pipeline - normalizes and validates entities.

This node:
1. Takes parsed_entities (potentially enriched with multimodal data)
2. Normalizes entity IDs for consistency across sensors
3. Validates all EntityCOP fields
4. Sets defaults for optional fields
5. Cleans up data inconsistencies
6. Prepares entities for COP merge/update

Node Signature:
    Input: TIFDAState with parsed_entities
    Output: Updated TIFDAState with normalized, validated entities
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.core.constants import CLASSIFICATIONS, CLASSIFICATION_LEVELS, ENTITY_TYPES
from src.models import EntityCOP, Location

# Configure logging
logger = logging.getLogger(__name__)


def _normalize_entity_id(entity: EntityCOP, sensor_id: str) -> str:
    """
    Normalize entity ID for consistency across sensors.
    
    Strategy:
    - Keep original entity_id from parser
    - Ensure it includes sensor_id prefix if not already present
    - Format: {sensor_id}_{entity_identifier}
    
    Args:
        entity: Entity to normalize
        sensor_id: Source sensor ID
        
    Returns:
        Normalized entity_id
    """
    original_id = entity.entity_id
    
    # If entity_id already contains sensor_id, keep it
    if original_id.startswith(f"{sensor_id}_"):
        return original_id
    
    # Otherwise, prepend sensor_id
    normalized_id = f"{sensor_id}_{original_id}"
    
    return normalized_id


def _validate_classification(classification: str) -> str:
    """
    Validate and normalize classification (IFF).
    
    Args:
        classification: IFF classification
        
    Returns:
        Validated classification (lowercased)
        
    Raises:
        ValueError: If classification is invalid
    """
    classification_lower = classification.lower()
    
    if classification_lower not in CLASSIFICATIONS:
        raise ValueError(
            f"Invalid classification '{classification}'. "
            f"Must be one of: {CLASSIFICATIONS}"
        )
    
    return classification_lower


def _validate_information_classification(info_class: str) -> str:
    """
    Validate information classification level.
    
    Args:
        info_class: Information classification level
        
    Returns:
        Validated classification level (uppercased)
        
    Raises:
        ValueError: If classification level is invalid
    """
    info_class_upper = info_class.upper()
    
    if info_class_upper not in CLASSIFICATION_LEVELS:
        raise ValueError(
            f"Invalid information classification '{info_class}'. "
            f"Must be one of: {CLASSIFICATION_LEVELS}"
        )
    
    return info_class_upper


def _validate_entity_type(entity_type: str) -> str:
    """
    Validate entity type.
    
    Args:
        entity_type: Entity type
        
    Returns:
        Validated entity type (lowercased)
        
    Raises:
        ValueError: If entity type is invalid
    """
    entity_type_lower = entity_type.lower()
    
    if entity_type_lower not in ENTITY_TYPES:
        raise ValueError(
            f"Invalid entity_type '{entity_type}'. "
            f"Must be one of: {ENTITY_TYPES}"
        )
    
    return entity_type_lower


def _validate_confidence(confidence: float) -> float:
    """
    Validate and clamp confidence value.
    
    Args:
        confidence: Confidence value
        
    Returns:
        Validated confidence (clamped to 0.0-1.0)
    """
    if confidence < 0.0:
        logger.warning(f"⚠️  Confidence {confidence} < 0.0, clamping to 0.0")
        return 0.0
    elif confidence > 1.0:
        logger.warning(f"⚠️  Confidence {confidence} > 1.0, clamping to 1.0")
        return 1.0
    else:
        return confidence


def _validate_location(location: Location) -> Location:
    """
    Validate geographic location.
    
    Args:
        location: Location to validate
        
    Returns:
        Validated location
        
    Raises:
        ValueError: If coordinates are invalid
    """
    # Validate latitude
    if not (-90 <= location.lat <= 90):
        raise ValueError(f"Latitude {location.lat} out of valid range [-90, 90]")
    
    # Validate longitude
    if not (-180 <= location.lon <= 180):
        raise ValueError(f"Longitude {location.lon} out of valid range [-180, 180]")
    
    # Validate altitude if present
    if location.alt is not None:
        # Reasonable altitude range: -500m (Dead Sea) to 50,000m (max aircraft altitude)
        if not (-500 <= location.alt <= 50000):
            logger.warning(
                f"⚠️  Altitude {location.alt}m is outside typical range [-500, 50000], "
                f"but keeping it"
            )
    
    return location


def _validate_heading(heading: float) -> float:
    """
    Validate and normalize heading.
    
    Args:
        heading: Heading in degrees
        
    Returns:
        Normalized heading (0-360)
    """
    if heading is None:
        return None
    
    # Normalize to 0-360 range
    normalized = heading % 360
    
    if normalized != heading:
        logger.debug(f"Normalized heading {heading}° to {normalized}°")
    
    return normalized


def _normalize_entity(entity: EntityCOP, sensor_id: str) -> EntityCOP:
    """
    Normalize and validate a single entity.
    
    Args:
        entity: Entity to normalize
        sensor_id: Source sensor ID
        
    Returns:
        Normalized EntityCOP
        
    Raises:
        ValueError: If entity has invalid fields
    """
    # Normalize entity ID
    normalized_id = _normalize_entity_id(entity, sensor_id)
    
    # Validate classification
    validated_classification = _validate_classification(entity.classification)
    
    # Validate information classification
    validated_info_class = _validate_information_classification(
        entity.information_classification
    )
    
    # Validate entity type
    validated_entity_type = _validate_entity_type(entity.entity_type)
    
    # Validate confidence
    validated_confidence = _validate_confidence(entity.confidence)
    
    # Validate location
    validated_location = _validate_location(entity.location)
    
    # Validate heading if present
    validated_heading = _validate_heading(entity.heading) if entity.heading is not None else None
    
    # Ensure source_sensors list contains current sensor
    source_sensors = entity.source_sensors.copy() if entity.source_sensors else []
    if sensor_id not in source_sensors:
        source_sensors.append(sensor_id)
    
    # Create normalized entity
    normalized_entity = EntityCOP(
        entity_id=normalized_id,
        entity_type=validated_entity_type,
        location=validated_location,
        timestamp=entity.timestamp,
        classification=validated_classification,
        information_classification=validated_info_class,
        confidence=validated_confidence,
        source_sensors=source_sensors,
        metadata=entity.metadata or {},
        speed_kmh=entity.speed_kmh,
        heading=validated_heading,
        comments=entity.comments
    )
    
    return normalized_entity


@traceable(name="cop_normalizer_node")
def cop_normalizer_node(state: TIFDAState) -> Dict[str, Any]:
    """
    COP normalization and validation node.
    
    Normalizes and validates all parsed entities before they are merged
    into the Common Operational Picture. Ensures data consistency and
    catches invalid values early.
    
    Normalization steps:
    1. Normalize entity IDs (ensure sensor_id prefix)
    2. Validate classifications (IFF and information level)
    3. Validate entity types
    4. Clamp confidence values to [0.0, 1.0]
    5. Validate geographic coordinates
    6. Normalize headings to [0, 360)
    7. Ensure source_sensors lists are correct
    
    Args:
        state: Current TIFDA state containing parsed_entities
        
    Returns:
        Dictionary with updated state fields:
            - parsed_entities: List[EntityCOP] (normalized and validated)
            - decision_reasoning: str (markdown-formatted report)
            - notification_queue: List[str] (UI notifications)
            - decision_log: List[Dict] (audit trail entry)
            - error: str (if normalization fails)
    """
    logger.info("=" * 70)
    logger.info("COP NORMALIZER NODE - Entity Validation & Normalization")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    parsed_entities = state.get("parsed_entities", [])
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not parsed_entities:
        logger.warning("⚠️  No entities to normalize")
        
        return {
            "parsed_entities": [],
            "decision_reasoning": "## ⚠️  No Entities to Normalize\n\nNo entities found in parsed_entities."
        }
    
    logger.info(f"📡 Normalizing {len(parsed_entities)} entities from sensor: {sensor_id}")
    
    # ============ NORMALIZE ENTITIES ============
    
    normalized_entities = []
    normalization_errors = []
    warnings = []
    
    for i, entity in enumerate(parsed_entities, 1):
        try:
            logger.info(f"\n🔧 Normalizing entity {i}/{len(parsed_entities)}: {entity.entity_id}")
            
            # Track changes
            original_id = entity.entity_id
            original_confidence = entity.confidence
            
            # Normalize entity
            normalized_entity = _normalize_entity(entity, sensor_id)
            
            # Log changes
            if normalized_entity.entity_id != original_id:
                logger.info(f"   ✏️  Entity ID: {original_id} → {normalized_entity.entity_id}")
            
            if normalized_entity.confidence != original_confidence:
                logger.info(f"   ✏️  Confidence: {original_confidence} → {normalized_entity.confidence}")
            
            # Log validation results
            logger.info(f"   ✅ Classification: {normalized_entity.classification}")
            logger.info(f"   ✅ Info Level: {normalized_entity.information_classification}")
            logger.info(f"   ✅ Entity Type: {normalized_entity.entity_type}")
            logger.info(f"   ✅ Location: {normalized_entity.location.lat:.4f}, {normalized_entity.location.lon:.4f}")
            
            normalized_entities.append(normalized_entity)
            
        except ValueError as e:
            error_msg = f"Entity {entity.entity_id}: {str(e)}"
            logger.error(f"   ❌ {error_msg}")
            normalization_errors.append(error_msg)
            
        except Exception as e:
            error_msg = f"Entity {entity.entity_id}: Unexpected error - {str(e)}"
            logger.exception(f"   ❌ {error_msg}")
            normalization_errors.append(error_msg)
    
    # ============ RESULTS ============
    
    success_count = len(normalized_entities)
    error_count = len(normalization_errors)
    
    logger.info(f"\n📊 Normalization complete:")
    logger.info(f"   ✅ Success: {success_count}/{len(parsed_entities)}")
    logger.info(f"   ❌ Errors: {error_count}")
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 🔧 Entity Normalization Complete

**Sensor**: `{sensor_id}`
**Entities Processed**: {len(parsed_entities)}

### Normalization Results:
- ✅ **Successfully normalized**: {success_count}
- ❌ **Validation errors**: {error_count}

"""
    
    if normalized_entities:
        reasoning += "### Normalized Entities:\n"
        for entity in normalized_entities:
            reasoning += f"- `{entity.entity_id}` ({entity.entity_type})\n"
            reasoning += f"  - Classification: {entity.classification} | Info: {entity.information_classification}\n"
            reasoning += f"  - Location: {entity.location.lat:.4f}, {entity.location.lon:.4f}\n"
            reasoning += f"  - Confidence: {entity.confidence:.2f}\n"
    
    if normalization_errors:
        reasoning += "\n### ❌ Validation Errors:\n"
        for error in normalization_errors:
            reasoning += f"- {error}\n"
    
    if error_count == 0:
        reasoning += "\n**Next**: Route to `cop_merge_node` for deduplication\n"
    else:
        reasoning += f"\n**Warning**: {error_count} entities failed validation and were dropped.\n"
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="cop_normalizer_node",
        decision_type="entity_normalization",
        reasoning=f"Normalized {success_count} entities, {error_count} errors",
        data={
            "sensor_id": sensor_id,
            "input_count": len(parsed_entities),
            "success_count": success_count,
            "error_count": error_count,
            "errors": normalization_errors
        }
    )
    
    # Add notifications
    if success_count > 0:
        add_notification(
            state,
            f"✅ {sensor_id}: Normalized {success_count} entit{'y' if success_count == 1 else 'ies'}"
        )
    
    if error_count > 0:
        add_notification(
            state,
            f"⚠️  {sensor_id}: {error_count} entit{'y' if error_count == 1 else 'ies'} failed validation"
        )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Normalization complete: {success_count} normalized, {error_count} errors")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "parsed_entities": normalized_entities,  # Replace with normalized entities
        "decision_reasoning": reasoning,
        "error": "; ".join(normalization_errors) if normalization_errors else None
    }


# ==================== TESTING ====================

def test_cop_normalizer_node():
    """Test the COP normalizer node"""
    from src.core.state import create_initial_state
    
    print("\n" + "=" * 70)
    print("COP NORMALIZER NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Valid entities
    print("Test 1: Valid entities")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_01"}
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="T001",  # Missing sensor prefix
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4, alt=5000),
            timestamp=datetime.utcnow(),
            classification="unknown",
            information_classification="SECRET",
            confidence=0.9,
            source_sensors=[]  # Empty, should be populated
        ),
        EntityCOP(
            entity_id="T002",
            entity_type="ground_vehicle",
            location=Location(lat=39.6, lon=-0.5),
            timestamp=datetime.utcnow(),
            classification="hostile",
            information_classification="CONFIDENTIAL",
            confidence=0.85,
            source_sensors=["radar_01"]
        )
    ]
    
    result = cop_normalizer_node(state)
    
    print(f"Input entities: {len(state['parsed_entities'])}")
    print(f"Normalized entities: {len(result['parsed_entities'])}")
    
    for entity in result['parsed_entities']:
        print(f"  - {entity.entity_id} (sources: {entity.source_sensors})")
    
    print(f"\nReasoning preview:\n{result['decision_reasoning'][:300]}...")
    
    # Test 2: Invalid classification
    print("\n" + "=" * 70)
    print("Test 2: Invalid classification (should fail)")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_02"}
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="T003",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4),
            timestamp=datetime.utcnow(),
            classification="invalid_classification",  # INVALID!
            information_classification="SECRET",
            confidence=0.9,
            source_sensors=["radar_02"]
        )
    ]
    
    result = cop_normalizer_node(state)
    
    print(f"Input entities: {len(state['parsed_entities'])}")
    print(f"Normalized entities: {len(result['parsed_entities'])}")
    print(f"Error present: {result.get('error') is not None}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    
    # Test 3: Confidence clamping
    print("\n" + "=" * 70)
    print("Test 3: Confidence out of range (should clamp)")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_03"}
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="T004",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4),
            timestamp=datetime.utcnow(),
            classification="friendly",
            information_classification="UNCLASSIFIED",
            confidence=1.5,  # > 1.0, should be clamped
            source_sensors=["radar_03"]
        )
    ]
    
    result = cop_normalizer_node(state)
    
    if result['parsed_entities']:
        entity = result['parsed_entities'][0]
        print(f"Original confidence: 1.5")
        print(f"Normalized confidence: {entity.confidence}")
        print(f"Clamped correctly: {entity.confidence == 1.0}")
    
    print("\n" + "=" * 70)
    print("COP NORMALIZER NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_cop_normalizer_node()