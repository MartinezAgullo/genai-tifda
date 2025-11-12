"""
COP Update Node
===============

Sixth node in the TIFDA core pipeline - updates COP and syncs to mapa.

This node performs the final COP update operations:
1. Ensures recipients are loaded as friendly entities in COP (one-time initialization)
2. Takes merged entities from cop_merge_node
3. Updates the cop_entities dict in state (add new, update existing)
4. Auto-syncs to mapa-puntos-interes for visualization
5. Updates timestamps and UI triggers
6. Logs all COP changes for audit
7. Completes the core sensor-to-COP pipeline

Recipients Loading:
- Recipients from recipients.yaml are automatically loaded as friendly entities
- Loading occurs once per session (deduplication prevents re-adding)
- Recipients are then available for distance calculations in threat_evaluator_node
- No separate recipient loading node required

Node Signature:
    Input: TIFDAState with parsed_entities (merged) and cop_entities (existing COP)
    Output: Updated TIFDAState with refreshed COP and mapa sync confirmation
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.integrations.cop_sync import get_cop_sync, COPSyncError
from src.models import EntityCOP, Location

# Configure logging
logger = logging.getLogger(__name__)


# ==================== RECIPIENTS LOADING ====================

def _load_recipients_into_cop(cop_entities: Dict[str, EntityCOP]) -> Dict[str, Any]:
    """
    Load recipients from configuration and add as friendly entities to COP.
    
    This function:
    1. Checks if recipients already loaded (prevents duplicates)
    2. Loads from recipients.yaml
    3. Converts to EntityCOP with classification="friendly"
    4. Adds to COP (uses same logic as sensor entities)
    
    Recipients are loaded ONCE and persist in COP for the entire session.
    Deduplication is automatic (checks entity_id before adding).
    
    Args:
        cop_entities: Current COP dictionary
        
    Returns:
        Statistics dictionary:
            - loaded: Number of recipients loaded
            - skipped: Number skipped (no location or already in COP)
            - entity_ids: List of loaded entity IDs
    """
    from src.rules.dissemination_rules import load_recipients_config
    
    # Check if recipients already loaded
    # Recipients have source_sensors=["recipients_config"]
    already_loaded = any(
        "recipients_config" in entity.source_sensors
        for entity in cop_entities.values()
    )
    
    if already_loaded:
        logger.debug("Recipients already in COP, skipping load")
        return {
            "loaded": 0,
            "skipped": 0,
            "entity_ids": [],
            "already_present": True
        }
    
    logger.info("\n🏗️  Loading recipients as friendly assets into COP...")
    
    try:
        # Load recipients from configuration
        recipients = load_recipients_config()
        logger.info(f"   📡 Loaded {len(recipients)} recipients from configuration")
        
        stats = {
            "loaded": 0,
            "skipped": 0,
            "entity_ids": [],
            "already_present": False
        }
        
        recipient_entities = []
        
        for recipient in recipients:
            # Skip if no location
            if recipient.location is None:
                logger.debug(f"   ⏭️  Skipping {recipient.recipient_id} (no static location)")
                stats["skipped"] += 1
                continue
            
            # Use elemento_identificado as entity_id, or fall back to recipient_id
            entity_id = recipient.elemento_identificado or recipient.recipient_id
            
            # Check if already in COP (deduplication)
            if entity_id in cop_entities:
                logger.debug(f"   ✓ {entity_id} already in COP")
                stats["skipped"] += 1
                continue
            
            # Map recipient_type to entity_type
            entity_type_mapping = {
                "friendly_unit": "base",
                "allied_cms": "base",
                "allied_unit": "base",
                "headquarters": "base",
                "naval_unit": "ship",
                "test": "base"
            }
            entity_type = entity_type_mapping.get(recipient.recipient_type, "base")
            
            # Create EntityCOP for this recipient
            recipient_entity = EntityCOP(
                entity_id=entity_id,
                entity_type=entity_type,
                location=Location(
                    lat=recipient.location.lat,
                    lon=recipient.location.lon,
                    alt=recipient.location.alt
                ),
                timestamp=datetime.now(timezone.utc),
                classification="friendly",  # KEY: Recipients are friendly
                information_classification="SECRET",  # Recipients are SECRET assets
                confidence=1.0,  # Known friendly asset
                source_sensors=["recipients_config"],  # Special marker
                metadata={
                    "recipient_id": recipient.recipient_id,
                    "recipient_name": recipient.recipient_name,
                    "operational_role": recipient.operational_role,
                    "access_level": recipient.access_level,
                    "is_mobile": recipient.is_mobile,
                    "loaded_from_config": True,
                    "load_timestamp": datetime.now(timezone.utc).isoformat()
                },
                comments=f"{recipient.recipient_name} - {recipient.operational_role}"
            )
            
            recipient_entities.append(recipient_entity)
            stats["loaded"] += 1
            stats["entity_ids"].append(entity_id)
            
            logger.info(f"   ➕ {recipient.recipient_name} ({entity_id})")
            logger.debug(f"      Type: {entity_type}, Location: {recipient.location.lat:.4f}, {recipient.location.lon:.4f}")
        
        # Add recipients to COP using same logic as sensor entities
        for entity in recipient_entities:
            cop_entities[entity.entity_id] = entity
        
        logger.info(f"   ✅ Loaded {stats['loaded']} recipients into COP")
        logger.info(f"   ⏭️  Skipped {stats['skipped']} (no location or already present)")

        # # Sync recipients to mapa so they appear on the map
        if recipient_entities:
            try:
                from src.integrations.cop_sync import get_cop_sync
                cop_sync = get_cop_sync()
                sync_result = cop_sync.sync_batch(recipient_entities)
                
                if sync_result['success']:
                    logger.info(f"   🗺️  Synced {stats['loaded']} recipients to mapa")
                else:
                    logger.warning(f"   ⚠️  Mapa sync had errors for recipients")
            except Exception as e:
                logger.warning(f"   ⚠️  Failed to sync recipients to mapa: {e}")
        
        return stats
        
    except Exception as e:
        logger.error(f"   ❌ Failed to load recipients: {e}")
        logger.warning("   ⚠️  Continuing without recipient assets in COP")
        return {
            "loaded": 0,
            "skipped": 0,
            "entity_ids": [],
            "error": str(e)
        }


# ==================== COP UPDATE ====================

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
            logger.info(f"      ➕ Adding: {entity_id}")
        
        # Add or update in COP
        cop_entities[entity_id] = entity
    
    stats["total_cop_size"] = len(cop_entities)
    
    return stats


@traceable(name="cop_update_node")
def cop_update_node(state: TIFDAState) -> Dict[str, Any]:
    """
    COP update and synchronization node with recipients loading.
    
    Updates the in-memory COP
    with merged entities and syncs changes to mapa-puntos-interes for
    visualization.
    
    Also ensures recipients are loaded into COP as friendly entities
    on first run. Recipients persist in COP and are available for distance
    calculations in threat_evaluator_node.
    
    Operations:
    1. Load recipients into COP (one-time, deduplicated)
    2. Update cop_entities dict (add new, update existing)
    3. Sync to mapa-puntos-interes (async, non-blocking)
    4. Update cop_last_global_update timestamp
    5. Increment map_update_trigger for UI refresh
    6. Log all changes for audit
    
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
    
    logger.info(f"📊 Current COP size: {len(cop_entities)} entities")
    
    # ============ LOAD RECIPIENTS ============
    
    # Ensure recipients are in COP (one-time load, deduplicated)
    recipient_stats = _load_recipients_into_cop(cop_entities)
    
    if recipient_stats["loaded"] > 0:
        logger.info(f"   ✅ Recipients loaded: {recipient_stats['loaded']} friendly assets added to COP")
        add_notification(
            state,
            f"🏗️  Loaded {recipient_stats['loaded']} friendly assets (recipients) into COP"
        )
    
    # ============ UPDATE COP WITH SENSOR DATA ============
    
    if not parsed_entities:
        logger.warning("⚠️  No sensor entities to update COP with (recipients may have been loaded)")
        
        # Still return updated COP (may include newly loaded recipients)
        reasoning = f"""## COP Update

**Recipients loaded**: {recipient_stats['loaded']}
**Sensor entities**: 0 (none to add)
**Total COP size**: {len(cop_entities)} entities

No sensor entities to process in this update.
"""
        
        return {
            "cop_entities": cop_entities,
            "decision_reasoning": reasoning
        }
    
    logger.info(f"   📡 Updating COP with {len(parsed_entities)} entities from sensor: {sensor_id}")
    
    # ============ UPDATE COP ============
    
    # Make a copy of COP for this update (already includes recipients)
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
    
    now = datetime.now(timezone.utc)
    current_trigger = state.get("map_update_trigger", 0)
    new_trigger = current_trigger + 1
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 🎯 COP Update Complete

**Sensor**: `{sensor_id}`
**Processing Time**: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}

"""
    
    # Add recipients info if loaded
    if recipient_stats["loaded"] > 0:
        reasoning += f"""### 🏗️  Recipients Loaded:
- ✅ **Friendly assets added**: {recipient_stats['loaded']}
- 📍 **Recipients in COP**: {', '.join(recipient_stats['entity_ids'][:5])}
{'  - ... and ' + str(len(recipient_stats['entity_ids']) - 5) + ' more' if len(recipient_stats['entity_ids']) > 5 else ''}

"""
    
    reasoning += f"""### COP Update:
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
    reasoning += f"""### 🗺️  Mapa Sync:
- Status: {'✅ Success' if sync_success else '⚠️  Partial/Failed'}
- Created: {sync_stats.get('created', 0)}
- Updated: {sync_stats.get('updated', 0)}
- Failed: {sync_stats.get('failed', 0)}

"""
    
    if not sync_success and sync_stats.get('errors'):
        reasoning += "#### Sync Errors:\n"
        for error in sync_stats['errors'][:3]:
            reasoning += f"- {error}\n"
        if len(sync_stats['errors']) > 3:
            reasoning += f"- ... and {len(sync_stats['errors']) - 3} more\n"
        reasoning += "\n"
    
    reasoning += f"""
---

**Next Steps:**
- Threat Evaluator will assess threats using distances to ALL friendly entities (including recipients)
- Recipients are now available for dissemination routing decisions

**🎉 Pipeline complete!** The COP now reflects the latest battlefield intelligence.
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="cop_update_node",
        decision_type="cop_update",
        reasoning=f"Updated COP: {cop_stats['added']} added, {cop_stats['updated']} updated. Recipients: {recipient_stats['loaded']} loaded. Mapa: {sync_message}",
        data={
            "sensor_id": sensor_id,
            "added": cop_stats['added'],
            "updated": cop_stats['updated'],
            "total_cop_size": cop_stats['total_cop_size'],
            "recipients_loaded": recipient_stats['loaded'],
            "recipients_skipped": recipient_stats['skipped'],
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
    logger.info(f"   Recipients: {recipient_stats['loaded']} loaded, {recipient_stats['skipped']} skipped")
    logger.info(f"   Mapa sync: {'Success' if sync_success else 'Partial/Failed'}")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "cop_entities": updated_cop,  # Updated COP dictionary (includes recipients)
        "cop_last_global_update": now,
        "map_update_trigger": new_trigger,  # Trigger UI refresh
        "decision_reasoning": reasoning,
        "error": None if sync_success else sync_message  # Non-fatal mapa errors
    }