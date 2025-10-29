"""
COP Update Node
===============

Sixth and FINAL node in the TIFDA Phase 1 pipeline - updates COP and syncs to mapa.

This node:
1. Takes merged entities from cop_merge_node
2. Updates the cop_entities dict in state (add new, update existing)
3. Auto-syncs to mapa-puntos-interes for visualization
4. Updates timestamps and UI triggers
5. Logs all COP changes for audit
6. Completes the core sensor-to-COP pipeline

This is the culmination of the entire pipeline - where sensor data becomes
actionable intelligence in the Common Operational Picture.

Node Signature:
    Input: TIFDAState with parsed_entities (merged) and cop_entities (existing COP)
    Output: Updated TIFDAState with refreshed COP and mapa sync confirmation
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.integrations.cop_sync import get_cop_sync, COPSyncError
from src.models import EntityCOP

# Configure logging
logger = logging.getLogger(__name__)


def _update_cop_with_entities(
    cop_entities: Dict[str, EntityCOP],
    merged_entities: List[EntityCOP]
) -> Dict[str, Any]:
    """
    Update COP dictionary with merged entities.
    
    Strategy:
    - If entity_id exists in COP → UPDATE (replace with newer data)
    - If entity_id is new → ADD (new entity in COP)
    
    Args:
        cop_entities: Current COP dictionary {entity_id: EntityCOP}
        merged_entities: List of entities to add/update
        
    Returns:
        Statistics dictionary:
            - added: Number of new entities
            - updated: Number of updated entities
            - total_cop_size: Total entities in COP after update
    """
    stats = {
        "added": 0,
        "updated": 0,
        "entity_ids_added": [],
        "entity_ids_updated": []
    }
    
    for entity in merged_entities:
        entity_id = entity.entity_id
        
        if entity_id in cop_entities:
            # Entity exists - UPDATE
            stats["updated"] += 1
            stats["entity_ids_updated"].append(entity_id)
            logger.info(f"   📝 Updating: {entity_id}")
        else:
            # New entity - ADD
            stats["added"] += 1
            stats["entity_ids_added"].append(entity_id)
            logger.info(f"   ➕ Adding: {entity_id}")
        
        # Add or update in COP
        cop_entities[entity_id] = entity
    
    stats["total_cop_size"] = len(cop_entities)
    
    return stats


@traceable(name="cop_update_node")
def cop_update_node(state: TIFDAState) -> Dict[str, Any]:
    """
    COP update and synchronization node.
    
    Final node in the Phase 1 core pipeline. Updates the in-memory COP
    with merged entities and syncs changes to mapa-puntos-interes for
    visualization.
    
    Operations:
    1. Update cop_entities dict (add new, update existing)
    2. Sync to mapa-puntos-interes (async, non-blocking)
    3. Update cop_last_global_update timestamp
    4. Increment map_update_trigger for UI refresh
    5. Log all changes for audit
    
    Args:
        state: Current TIFDA state containing:
            - parsed_entities: Merged entities from cop_merge_node
            - cop_entities: Existing COP dictionary
        
    Returns:
        Dictionary with updated state fields:
            - cop_entities: Dict[str, EntityCOP] (updated COP)
            - cop_last_global_update: datetime (last update timestamp)
            - map_update_trigger: int (incremented for UI refresh)
            - decision_reasoning: str (markdown-formatted report)
            - notification_queue: List[str] (UI notifications)
            - decision_log: List[Dict] (audit trail entry)
            - error: str (if sync fails, non-fatal)
    """
    logger.info("=" * 70)
    logger.info("COP UPDATE NODE - Final COP Update & Mapa Sync")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    parsed_entities = state.get("parsed_entities", [])
    cop_entities = state.get("cop_entities", {})
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not parsed_entities:
        logger.warning("⚠️  No entities to update COP with")
        return {
            "decision_reasoning": "## ⚠️  No COP Update Needed\n\nNo entities to add/update."
        }
    
    logger.info(f"📡 Updating COP with {len(parsed_entities)} entities from sensor: {sensor_id}")
    logger.info(f"📊 Current COP size: {len(cop_entities)} entities")
    
    # ============ UPDATE COP ============
    
    # Make a copy of COP for this update
    updated_cop = cop_entities.copy()
    
    # Update COP with merged entities
    cop_stats = _update_cop_with_entities(updated_cop, parsed_entities)
    
    logger.info(f"\n📊 COP update complete:")
    logger.info(f"   ➕ Added: {cop_stats['added']}")
    logger.info(f"   📝 Updated: {cop_stats['updated']}")
    logger.info(f"   📦 Total COP size: {cop_stats['total_cop_size']}")
    
    # ============ SYNC TO MAPA ============
    
    sync_success = False
    sync_message = ""
    sync_stats = {}
    
    try:
        logger.info(f"\n🗺️  Syncing to mapa-puntos-interes...")
        
        # Get COP sync instance
        cop_sync = get_cop_sync()
        
        # Sync only the entities that were added/updated
        sync_result = cop_sync.sync_batch(parsed_entities)
        
        sync_success = sync_result['success']
        sync_stats = sync_result
        
        if sync_success:
            logger.info(f"   ✅ Mapa sync successful:")
            logger.info(f"      Created: {sync_result['created']}")
            logger.info(f"      Updated: {sync_result['updated']}")
            logger.info(f"      Failed: {sync_result['failed']}")
            
            sync_message = (
                f"Synced {sync_result['created']} created, "
                f"{sync_result['updated']} updated to mapa"
            )
        else:
            logger.warning(f"   ⚠️  Mapa sync completed with errors:")
            logger.warning(f"      Failed: {sync_result['failed']}")
            for error in sync_result.get('errors', [])[:3]:  # Show first 3 errors
                logger.warning(f"      - {error}")
            
            sync_message = f"Mapa sync partial: {sync_result['failed']} entities failed"
            
    except Exception as e:
        logger.error(f"   ❌ Mapa sync failed: {str(e)}")
        sync_success = False
        sync_message = f"Mapa sync error: {str(e)}"
        sync_stats = {
            'created': 0,
            'updated': 0,
            'failed': len(parsed_entities),
            'errors': [str(e)]
        }
    
    # ============ UPDATE TIMESTAMPS & TRIGGERS ============
    
    now = datetime.utcnow()
    current_trigger = state.get("map_update_trigger", 0)
    new_trigger = current_trigger + 1
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 🎯 COP Update Complete

**Sensor**: `{sensor_id}`
**Processing Time**: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}

### COP Update:
- ➕ **New entities added**: {cop_stats['added']}
- 📝 **Existing entities updated**: {cop_stats['updated']}
- 📊 **Total COP size**: {cop_stats['total_cop_size']} entities

"""
    
    if cop_stats['added'] > 0:
        reasoning += "#### New Entities Added:\n"
        for entity_id in cop_stats['entity_ids_added'][:10]:  # Show first 10
            reasoning += f"- `{entity_id}`\n"
        if len(cop_stats['entity_ids_added']) > 10:
            reasoning += f"- ... and {len(cop_stats['entity_ids_added']) - 10} more\n"
        reasoning += "\n"
    
    if cop_stats['updated'] > 0:
        reasoning += "#### Updated Entities:\n"
        for entity_id in cop_stats['entity_ids_updated'][:10]:  # Show first 10
            reasoning += f"- `{entity_id}`\n"
        if len(cop_stats['entity_ids_updated']) > 10:
            reasoning += f"- ... and {len(cop_stats['entity_ids_updated']) - 10} more\n"
        reasoning += "\n"
    
    # Mapa sync status
    reasoning += "### 🗺️  Mapa Sync:\n"
    if sync_success:
        reasoning += f"- ✅ **Status**: Success\n"
        reasoning += f"- 📦 **Created**: {sync_stats.get('created', 0)}\n"
        reasoning += f"- 📝 **Updated**: {sync_stats.get('updated', 0)}\n"
        if sync_stats.get('failed', 0) > 0:
            reasoning += f"- ⚠️  **Failed**: {sync_stats['failed']}\n"
    else:
        reasoning += f"- ⚠️  **Status**: Partial failure or error\n"
        reasoning += f"- ❌ **Failed**: {sync_stats.get('failed', len(parsed_entities))}\n"
        if sync_stats.get('errors'):
            reasoning += f"- **Error**: {sync_stats['errors'][0][:100]}...\n"
    
    reasoning += f"""
### 📊 Pipeline Summary:
This completes the core TIFDA pipeline for this sensor event:
1. ✅ Firewall validation passed
2. ✅ Format parsed successfully
3. ✅ Entities normalized and validated
4. ✅ Duplicates merged (sensor fusion)
5. ✅ COP updated with {cop_stats['added'] + cop_stats['updated']} entities
6. {'✅' if sync_success else '⚠️ '} Mapa visualization {'synced' if sync_success else 'partially synced'}

**🎉 Pipeline complete!** The COP now reflects the latest battlefield intelligence.
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="cop_update_node",
        decision_type="cop_update",
        reasoning=f"Updated COP: {cop_stats['added']} added, {cop_stats['updated']} updated. Mapa: {sync_message}",
        data={
            "sensor_id": sensor_id,
            "added": cop_stats['added'],
            "updated": cop_stats['updated'],
            "total_cop_size": cop_stats['total_cop_size'],
            "mapa_sync_success": sync_success,
            "mapa_sync_stats": sync_stats
        }
    )
    
    # Add notifications
    if cop_stats['added'] > 0:
        add_notification(
            state,
            f"➕ {sensor_id}: {cop_stats['added']} new entit{'y' if cop_stats['added'] == 1 else 'ies'} added to COP"
        )
    
    if cop_stats['updated'] > 0:
        add_notification(
            state,
            f"📝 {sensor_id}: {cop_stats['updated']} entit{'y' if cop_stats['updated'] == 1 else 'ies'} updated in COP"
        )
    
    if sync_success:
        add_notification(
            state,
            f"✅ {sensor_id}: Synced to mapa visualization"
        )
    else:
        add_notification(
            state,
            f"⚠️  {sensor_id}: Mapa sync had errors (COP still updated)"
        )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"✅ COP UPDATE COMPLETE - Pipeline finished!")
    logger.info(f"   COP size: {cop_stats['total_cop_size']} entities")
    logger.info(f"   Mapa sync: {'Success' if sync_success else 'Partial/Failed'}")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "cop_entities": updated_cop,  # Updated COP dictionary
        "cop_last_global_update": now,
        "map_update_trigger": new_trigger,  # Trigger UI refresh
        "decision_reasoning": reasoning,
        "error": None if sync_success else sync_message  # Non-fatal mapa errors
    }


# ==================== TESTING ====================

def test_cop_update_node():
    """Test the COP update node"""
    from src.core.state import create_initial_state
    from src.models import Location
    
    print("\n" + "=" * 70)
    print("COP UPDATE NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Add new entities to empty COP
    print("Test 1: Add new entities to empty COP")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_01"}
    state["cop_entities"] = {}  # Empty COP
    
    # New entities to add
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="radar_01_T001",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4, alt=5000),
            timestamp=datetime.utcnow(),
            classification="unknown",
            information_classification="SECRET",
            confidence=0.8,
            source_sensors=["radar_01"]
        ),
        EntityCOP(
            entity_id="radar_01_T002",
            entity_type="ground_vehicle",
            location=Location(lat=39.6, lon=-0.5),
            timestamp=datetime.utcnow(),
            classification="hostile",
            information_classification="CONFIDENTIAL",
            confidence=0.75,
            source_sensors=["radar_01"]
        )
    ]
    
    result = cop_update_node(state)
    
    print(f"Input entities: {len(state['parsed_entities'])}")
    print(f"Initial COP size: {len(state['cop_entities'])}")
    print(f"Updated COP size: {len(result['cop_entities'])}")
    print(f"New entities added: {result['decision_reasoning'].count('➕')}")
    print(f"Map trigger incremented: {result['map_update_trigger'] > state['map_update_trigger']}")
    
    print(f"\nReasoning preview:\n{result['decision_reasoning'][:400]}...")
    
    # Test 2: Update existing entities
    print("\n" + "=" * 70)
    print("Test 2: Update existing entities in COP")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_02"}
    
    # COP already has entity from radar_01
    state["cop_entities"] = {
        "radar_01_T001": EntityCOP(
            entity_id="radar_01_T001",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4, alt=5000),
            timestamp=datetime(2025, 10, 27, 14, 30, 0),
            classification="unknown",
            information_classification="SECRET",
            confidence=0.7,
            source_sensors=["radar_01"]
        )
    }
    
    # Merged entity with updated data (from merge node)
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="radar_01_T001",  # Same ID - UPDATE
            entity_type="aircraft",
            location=Location(lat=39.501, lon=-0.401, alt=5100),
            timestamp=datetime.utcnow(),
            classification="hostile",  # Updated classification
            information_classification="SECRET",
            confidence=0.85,  # Boosted confidence
            source_sensors=["radar_01", "radar_02"],  # Multi-sensor
            metadata={"merged_from_sensors": ["radar_01", "radar_02"]}
        )
    ]
    
    result = cop_update_node(state)
    
    print(f"Updated entities: {result['decision_reasoning'].count('📝')}")
    print(f"Final COP size: {len(result['cop_entities'])}")
    
    updated_entity = result['cop_entities']['radar_01_T001']
    print(f"\nUpdated entity details:")
    print(f"  Sensors: {updated_entity.source_sensors}")
    print(f"  Confidence: {updated_entity.confidence}")
    print(f"  Classification: {updated_entity.classification}")
    
    # Test 3: Mixed add and update
    print("\n" + "=" * 70)
    print("Test 3: Mixed scenario (add + update)")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "drone_alpha"}
    
    # Existing COP
    state["cop_entities"] = {
        "radar_01_T001": EntityCOP(
            entity_id="radar_01_T001",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4),
            timestamp=datetime.utcnow(),
            classification="unknown",
            information_classification="SECRET",
            confidence=0.8,
            source_sensors=["radar_01"]
        )
    }
    
    # Mix of new and update
    state["parsed_entities"] = [
        # UPDATE existing
        EntityCOP(
            entity_id="radar_01_T001",
            entity_type="aircraft",
            location=Location(lat=39.501, lon=-0.401),
            timestamp=datetime.utcnow(),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.9,
            source_sensors=["radar_01", "drone_alpha"]
        ),
        # ADD new
        EntityCOP(
            entity_id="drone_alpha_vehicle_01",
            entity_type="ground_vehicle",
            location=Location(lat=39.6, lon=-0.5),
            timestamp=datetime.utcnow(),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.85,
            source_sensors=["drone_alpha"]
        )
    ]
    
    result = cop_update_node(state)
    
    print(f"Initial COP: {len(state['cop_entities'])} entities")
    print(f"Updated COP: {len(result['cop_entities'])} entities")
    print(f"Added: {result['decision_reasoning'].count('➕ **New')}")
    print(f"Updated: {result['decision_reasoning'].count('📝 **Existing')}")
    
    print("\n" + "=" * 70)
    print("COP UPDATE NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_cop_update_node()