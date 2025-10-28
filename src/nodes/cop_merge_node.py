"""
COP Merge Node
==============

Fifth node in the TIFDA pipeline - merges duplicate entities (sensor fusion).

This node:
1. Takes normalized entities from current sensor event
2. Compares with existing COP entities
3. Detects duplicates (same entity reported by multiple sensors)
4. Merges duplicates intelligently:
   - Combines source_sensors lists
   - Increases confidence based on multiple observations
   - Updates location/heading with newest/most accurate data
   - Merges metadata
5. Adds new entities that don't match existing ones

This is the core of SENSOR FUSION - combining observations from multiple
sensors to create a more accurate, confident picture of the battlefield.

Node Signature:
    Input: TIFDAState with parsed_entities (normalized) and cop_entities (existing COP)
    Output: Updated TIFDAState with merged entities ready for COP update
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
import math

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.models import EntityCOP, Location

# Configure logging
logger = logging.getLogger(__name__)

# ==================== MERGE CONFIGURATION ====================

# Distance threshold for considering entities as "same" (in meters)
MERGE_DISTANCE_THRESHOLD_M = 500  # 500m default

# Time window for merging (seconds)
MERGE_TIME_WINDOW_SEC = 300  # 5 minutes

# Confidence boost for multi-sensor confirmation
CONFIDENCE_BOOST_PER_SENSOR = 0.1  # +10% per additional sensor


# ==================== GEOSPATIAL UTILITIES ====================

def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    
    Args:
        lat1, lon1: First point (degrees)
        lat2, lon2: Second point (degrees)
        
    Returns:
        Distance in meters
    """
    # Earth radius in meters
    R = 6371000
    
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    
    distance = R * c
    return distance


def _entities_are_duplicate(
    entity1: EntityCOP,
    entity2: EntityCOP,
    distance_threshold_m: float = MERGE_DISTANCE_THRESHOLD_M,
    time_window_sec: float = MERGE_TIME_WINDOW_SEC
) -> bool:
    """
    Determine if two entities represent the same real-world object.
    
    Criteria for duplicate detection:
    1. Same entity_type (both aircraft, both tanks, etc.)
    2. Geographic proximity (within distance_threshold_m)
    3. Temporal proximity (within time_window_sec)
    4. Similar classification (if both are classified)
    
    Args:
        entity1: First entity
        entity2: Second entity
        distance_threshold_m: Max distance to consider entities as same
        time_window_sec: Max time difference to consider entities as same
        
    Returns:
        True if entities are likely duplicates
    """
    # 1. Must be same type
    if entity1.entity_type != entity2.entity_type:
        return False
    
    # 2. Check geographic proximity
    distance_m = _haversine_distance(
        entity1.location.lat, entity1.location.lon,
        entity2.location.lat, entity2.location.lon
    )
    
    if distance_m > distance_threshold_m:
        return False
    
    # 3. Check temporal proximity
    time_diff_sec = abs((entity1.timestamp - entity2.timestamp).total_seconds())
    
    if time_diff_sec > time_window_sec:
        return False
    
    # 4. Check classification compatibility (if both are classified)
    # If both entities have non-"unknown" classifications, they should match
    if (entity1.classification != "unknown" and 
        entity2.classification != "unknown" and
        entity1.classification != entity2.classification):
        # Different classifications - probably not the same entity
        return False
    
    # All criteria met - likely a duplicate
    return True


def _merge_two_entities(
    existing: EntityCOP,
    new: EntityCOP,
    boost_confidence: bool = True
) -> EntityCOP:
    """
    Merge two duplicate entities into one.
    
    Merge strategy:
    - Use newest timestamp
    - Use location from most recent observation
    - Combine source_sensors lists
    - Boost confidence (multiple sensors confirm = higher confidence)
    - Use best available classification (prefer non-"unknown")
    - Merge metadata
    - Use highest information classification
    
    Args:
        existing: Existing entity in COP
        new: New entity from current sensor event
        boost_confidence: Whether to boost confidence for multi-sensor confirmation
        
    Returns:
        Merged EntityCOP
    """
    # Determine which is newer
    is_new_newer = new.timestamp >= existing.timestamp
    newer_entity = new if is_new_newer else existing
    older_entity = existing if is_new_newer else new
    
    # Combine source sensors (unique)
    combined_sources = list(set(existing.source_sensors + new.source_sensors))
    
    # Calculate merged confidence
    if boost_confidence:
        # Base confidence: take max of the two
        base_confidence = max(existing.confidence, new.confidence)
        
        # Boost for multi-sensor confirmation
        num_sensors = len(combined_sources)
        confidence_boost = (num_sensors - 1) * CONFIDENCE_BOOST_PER_SENSOR
        
        merged_confidence = min(base_confidence + confidence_boost, 1.0)
    else:
        merged_confidence = max(existing.confidence, new.confidence)
    
    # Choose best classification (prefer non-"unknown")
    if existing.classification != "unknown":
        merged_classification = existing.classification
    elif new.classification != "unknown":
        merged_classification = new.classification
    else:
        merged_classification = "unknown"
    
    # Use highest information classification level
    info_class_levels = {
        "UNCLASSIFIED": 0,
        "RESTRICTED": 1,
        "CONFIDENTIAL": 2,
        "SECRET": 3,
        "TOP_SECRET": 4
    }
    
    existing_level = info_class_levels.get(existing.information_classification, 0)
    new_level = info_class_levels.get(new.information_classification, 0)
    
    merged_info_class = (
        existing.information_classification if existing_level >= new_level
        else new.information_classification
    )
    
    # Merge metadata
    merged_metadata = {**older_entity.metadata, **newer_entity.metadata}
    merged_metadata["merged_from_sensors"] = combined_sources
    merged_metadata["merge_count"] = merged_metadata.get("merge_count", 1) + 1
    
    # Merge comments
    merged_comments = None
    if newer_entity.comments:
        merged_comments = newer_entity.comments
        if older_entity.comments and older_entity.comments not in newer_entity.comments:
            merged_comments += f"\n[Previous: {older_entity.comments}]"
    elif older_entity.comments:
        merged_comments = older_entity.comments
    
    # Create merged entity
    merged_entity = EntityCOP(
        entity_id=existing.entity_id,  # Keep existing ID
        entity_type=newer_entity.entity_type,
        location=newer_entity.location,  # Use newest location
        timestamp=newer_entity.timestamp,  # Use newest timestamp
        classification=merged_classification,
        information_classification=merged_info_class,
        confidence=merged_confidence,
        source_sensors=combined_sources,
        metadata=merged_metadata,
        speed_kmh=newer_entity.speed_kmh or older_entity.speed_kmh,
        heading=newer_entity.heading if newer_entity.heading is not None else older_entity.heading,
        comments=merged_comments
    )
    
    return merged_entity


@traceable(name="cop_merge_node")
def cop_merge_node(state: TIFDAState) -> Dict[str, Any]:
    """
    COP merge and sensor fusion node.
    
    Implements sensor fusion by detecting and merging duplicate entities
    reported by multiple sensors. This creates a more accurate and confident
    Common Operational Picture.
    
    Merge algorithm:
    1. For each new entity from current sensor:
       a. Search existing COP for duplicates (same type, nearby, recent)
       b. If duplicate found → merge entities (combine sources, boost confidence)
       c. If no duplicate → add as new entity
    2. Track merge statistics for audit
    
    Args:
        state: Current TIFDA state containing:
            - parsed_entities: Normalized entities from current sensor
            - cop_entities: Existing COP entities
        
    Returns:
        Dictionary with updated state fields:
            - parsed_entities: List[EntityCOP] (merged entities to add/update)
            - decision_reasoning: str (markdown-formatted report)
            - notification_queue: List[str] (UI notifications)
            - decision_log: List[Dict] (audit trail entry)
    """
    logger.info("=" * 70)
    logger.info("COP MERGE NODE - Sensor Fusion & Deduplication")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    parsed_entities = state.get("parsed_entities", [])
    cop_entities = state.get("cop_entities", {})
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not parsed_entities:
        logger.warning("⚠️  No entities to merge")
        return {
            "parsed_entities": [],
            "decision_reasoning": "## ⚠️  No Entities to Merge\n\nNo entities found in parsed_entities."
        }
    
    logger.info(f"📡 Merging {len(parsed_entities)} new entities from sensor: {sensor_id}")
    logger.info(f"📊 Existing COP contains: {len(cop_entities)} entities")
    
    # ============ MERGE ENTITIES ============
    
    merged_entities = []
    merge_stats = {
        "new_entities": 0,
        "merged_entities": 0,
        "updated_entities": 0
    }
    
    merge_details = []
    
    for new_entity in parsed_entities:
        logger.info(f"\n🔍 Processing: {new_entity.entity_id}")
        
        # Search for duplicates in existing COP
        duplicate_found = False
        
        for existing_id, existing_entity in cop_entities.items():
            is_duplicate = _entities_are_duplicate(
                existing_entity,
                new_entity,
                distance_threshold_m=MERGE_DISTANCE_THRESHOLD_M,
                time_window_sec=MERGE_TIME_WINDOW_SEC
            )
            
            if is_duplicate:
                # Calculate distance for logging
                distance_m = _haversine_distance(
                    existing_entity.location.lat, existing_entity.location.lon,
                    new_entity.location.lat, new_entity.location.lon
                )
                
                logger.info(f"   🔗 Duplicate found: {existing_id}")
                logger.info(f"      Distance: {distance_m:.1f}m")
                logger.info(f"      Time diff: {abs((new_entity.timestamp - existing_entity.timestamp).total_seconds()):.1f}s")
                
                # Merge entities
                merged_entity = _merge_two_entities(existing_entity, new_entity)
                
                logger.info(f"   ✅ Merged: {len(merged_entity.source_sensors)} sensors, confidence: {merged_entity.confidence:.2f}")
                
                merged_entities.append(merged_entity)
                merge_stats["merged_entities"] += 1
                
                merge_details.append({
                    "action": "merge",
                    "entity_id": merged_entity.entity_id,
                    "sensors": merged_entity.source_sensors,
                    "confidence": merged_entity.confidence,
                    "distance_m": distance_m
                })
                
                duplicate_found = True
                break  # Only merge with first duplicate found
        
        if not duplicate_found:
            # No duplicate - this is a new entity
            logger.info(f"   ➕ New entity: {new_entity.entity_id}")
            
            merged_entities.append(new_entity)
            merge_stats["new_entities"] += 1
            
            merge_details.append({
                "action": "new",
                "entity_id": new_entity.entity_id,
                "type": new_entity.entity_type,
                "classification": new_entity.classification
            })
    
    # ============ RESULTS ============
    
    logger.info(f"\n📊 Merge complete:")
    logger.info(f"   ➕ New entities: {merge_stats['new_entities']}")
    logger.info(f"   🔗 Merged entities: {merge_stats['merged_entities']}")
    logger.info(f"   📦 Total output: {len(merged_entities)}")
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 🔗 COP Merge Complete (Sensor Fusion)

**Sensor**: `{sensor_id}`
**Input Entities**: {len(parsed_entities)}
**Existing COP Size**: {len(cop_entities)}

### Merge Results:
- ➕ **New entities**: {merge_stats['new_entities']}
- 🔗 **Merged with existing**: {merge_stats['merged_entities']}
- 📦 **Total output**: {len(merged_entities)}

"""
    
    if merge_stats["merged_entities"] > 0:
        reasoning += "### 🔗 Merged Entities (Multi-Sensor Confirmation):\n"
        for detail in merge_details:
            if detail["action"] == "merge":
                reasoning += f"- `{detail['entity_id']}`\n"
                reasoning += f"  - Sensors: {', '.join(detail['sensors'])} ({len(detail['sensors'])} total)\n"
                reasoning += f"  - Confidence: {detail['confidence']:.2f}\n"
                reasoning += f"  - Distance: {detail['distance_m']:.1f}m\n"
    
    if merge_stats["new_entities"] > 0:
        reasoning += "\n### ➕ New Entities (First Observation):\n"
        for detail in merge_details:
            if detail["action"] == "new":
                reasoning += f"- `{detail['entity_id']}` ({detail['type']}) - {detail['classification']}\n"
    
    reasoning += f"""
### Merge Configuration:
- Distance threshold: {MERGE_DISTANCE_THRESHOLD_M}m
- Time window: {MERGE_TIME_WINDOW_SEC}s ({MERGE_TIME_WINDOW_SEC/60:.1f} minutes)
- Confidence boost: +{CONFIDENCE_BOOST_PER_SENSOR*100:.0f}% per additional sensor

**Next**: Route to `cop_update_node` to update COP and sync to mapa
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="cop_merge_node",
        decision_type="entity_merge",
        reasoning=f"Merged {len(parsed_entities)} entities: {merge_stats['new_entities']} new, {merge_stats['merged_entities']} merged",
        data={
            "sensor_id": sensor_id,
            "input_count": len(parsed_entities),
            "output_count": len(merged_entities),
            "new_entities": merge_stats["new_entities"],
            "merged_entities": merge_stats["merged_entities"],
            "merge_details": merge_details
        }
    )
    
    # Add notifications
    if merge_stats["merged_entities"] > 0:
        add_notification(
            state,
            f"🔗 {sensor_id}: Multi-sensor confirmation on {merge_stats['merged_entities']} entit{'y' if merge_stats['merged_entities'] == 1 else 'ies'}"
        )
    
    if merge_stats["new_entities"] > 0:
        add_notification(
            state,
            f"➕ {sensor_id}: {merge_stats['new_entities']} new entit{'y' if merge_stats['new_entities'] == 1 else 'ies'} detected"
        )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Merge complete: {merge_stats['new_entities']} new, {merge_stats['merged_entities']} merged")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "parsed_entities": merged_entities,  # Replace with merged entities
        "decision_reasoning": reasoning
    }


# ==================== TESTING ====================

def test_cop_merge_node():
    """Test the COP merge node"""
    from src.core.state import create_initial_state
    
    print("\n" + "=" * 70)
    print("COP MERGE NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Merge duplicate entities
    print("Test 1: Merge duplicate entities (multi-sensor confirmation)")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_02"}
    
    # Existing COP has one entity from radar_01
    state["cop_entities"] = {
        "radar_01_T001": EntityCOP(
            entity_id="radar_01_T001",
            entity_type="aircraft",
            location=Location(lat=39.500, lon=-0.400, alt=5000),
            timestamp=datetime(2025, 10, 27, 14, 30, 0),
            classification="unknown",
            information_classification="SECRET",
            confidence=0.7,
            source_sensors=["radar_01"]
        )
    }
    
    # New entity from radar_02 at nearly same location (duplicate!)
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="radar_02_T001",
            entity_type="aircraft",
            location=Location(lat=39.501, lon=-0.401, alt=5100),  # ~150m away
            timestamp=datetime(2025, 10, 27, 14, 31, 0),  # 1 minute later
            classification="hostile",  # New classification info
            information_classification="SECRET",
            confidence=0.8,
            source_sensors=["radar_02"]
        )
    ]
    
    result = cop_merge_node(state)
    
    print(f"Input entities: {len(state['parsed_entities'])}")
    print(f"Existing COP: {len(state['cop_entities'])}")
    print(f"Output entities: {len(result['parsed_entities'])}")
    
    if result['parsed_entities']:
        merged = result['parsed_entities'][0]
        print(f"\nMerged entity:")
        print(f"  ID: {merged.entity_id}")
        print(f"  Sensors: {merged.source_sensors}")
        print(f"  Confidence: {merged.confidence:.2f} (boosted from multi-sensor)")
        print(f"  Classification: {merged.classification}")
    
    print(f"\nReasoning preview:\n{result['decision_reasoning'][:400]}...")
    
    # Test 2: New entity (no duplicate)
    print("\n" + "=" * 70)
    print("Test 2: New entity (no duplicate in COP)")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_02"}
    state["cop_entities"] = {}  # Empty COP
    
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="radar_02_T002",
            entity_type="aircraft",
            location=Location(lat=40.000, lon=-1.000),  # Far away
            timestamp=datetime.utcnow(),
            classification="unknown",
            information_classification="CONFIDENTIAL",
            confidence=0.75,
            source_sensors=["radar_02"]
        )
    ]
    
    result = cop_merge_node(state)
    
    print(f"Output entities: {len(result['parsed_entities'])}")
    print(f"Action: {'New entity' if '➕ New entities: 1' in result['decision_reasoning'] else 'Unknown'}")
    
    # Test 3: Multiple entities, some merge, some new
    print("\n" + "=" * 70)
    print("Test 3: Mixed scenario (some merge, some new)")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "drone_alpha"}
    
    # Existing COP
    state["cop_entities"] = {
        "radar_01_T001": EntityCOP(
            entity_id="radar_01_T001",
            entity_type="ground_vehicle",
            location=Location(lat=39.500, lon=-0.400),
            timestamp=datetime.utcnow(),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.8,
            source_sensors=["radar_01"]
        )
    }
    
    # New entities: one matches existing, one is new
    state["parsed_entities"] = [
        # This one matches radar_01_T001
        EntityCOP(
            entity_id="drone_alpha_vehicle_01",
            entity_type="ground_vehicle",
            location=Location(lat=39.501, lon=-0.401),  # Close to existing
            timestamp=datetime.utcnow(),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.85,
            source_sensors=["drone_alpha"]
        ),
        # This one is new
        EntityCOP(
            entity_id="drone_alpha_vehicle_02",
            entity_type="ground_vehicle",
            location=Location(lat=39.600, lon=-0.500),  # Different location
            timestamp=datetime.utcnow(),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.8,
            source_sensors=["drone_alpha"]
        )
    ]
    
    result = cop_merge_node(state)
    
    print(f"Input: {len(state['parsed_entities'])} entities")
    print(f"Output: {len(result['parsed_entities'])} entities")
    print(f"New: {result['decision_reasoning'].count('➕')}")
    print(f"Merged: {result['decision_reasoning'].count('🔗')}")
    
    print("\n" + "=" * 70)
    print("COP MERGE NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_cop_merge_node()