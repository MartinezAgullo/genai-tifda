"""
Parser Node
===========

Second node in the TIFDA pipeline - parses validated sensor messages.

This node:
1. Takes validated sensor messages (firewall_passed=True)
2. Uses ParserFactory to select the appropriate parser
3. Parses sensor data into EntityCOP objects
4. Checks if multimodal processing is needed (audio/image/document files)
5. Updates state with parsed entities

Node Signature:
    Input: TIFDAState with current_sensor_event and firewall_passed=True
    Output: Updated TIFDAState with parsed_entities populated
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.parsers.parser_factory import get_parser_factory
from src.models import SensorMessage

# Configure logging
logger = logging.getLogger(__name__)


@traceable(name="parser_node")
def parser_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Parser selection and execution node.
    
    Selects the appropriate parser based on sensor type and format,
    then parses the sensor message into EntityCOP objects.
    
    This node handles:
    - Parser selection via ParserFactory
    - Format validation (delegated to specific parser)
    - Parsing sensor data → List[EntityCOP]
    - Detection of multimodal content (files requiring processing)
    
    Args:
        state: Current TIFDA state containing current_sensor_event
        
    Returns:
        Dictionary with updated state fields:
            - parsed_entities: List[EntityCOP] (entities extracted from sensor data)
            - sensor_metadata: Dict (updated with parsing info)
            - decision_reasoning: str (markdown-formatted reasoning)
            - notification_queue: List[str] (UI notifications)
            - decision_log: List[Dict] (audit trail entry)
            - error: str (if parsing fails)
            
    Raises:
        ValueError: If current_sensor_event is None or firewall validation not done
    """
    logger.info("=" * 70)
    logger.info("PARSER NODE - Format Detection & Parsing")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    sensor_event = state.get("current_sensor_event")
    
    if sensor_event is None:
        error_msg = "No sensor event to parse (current_sensor_event is None)"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    # Check firewall passed
    firewall_passed = state.get("firewall_passed", False)
    if not firewall_passed:
        error_msg = "Cannot parse sensor event that failed firewall validation"
        logger.error(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    # Extract sensor info
    sensor_id = sensor_event.sensor_id
    sensor_type = sensor_event.sensor_type
    timestamp = sensor_event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    has_file_refs = sensor_event.has_file_references()
    
    logger.info(f"📡 Parsing sensor event:")
    logger.info(f"   Sensor ID: {sensor_id}")
    logger.info(f"   Sensor Type: {sensor_type}")
    logger.info(f"   Timestamp: {timestamp}")
    logger.info(f"   Has file references: {has_file_refs}")
    
    if has_file_refs:
        file_refs = sensor_event.get_file_references()
        logger.info(f"   File references detected: {list(file_refs.keys())}")
    
    # ============ PARSER SELECTION ============
    
    try:
        # Get parser factory
        factory = get_parser_factory()
        
        # Find appropriate parser
        parser = factory.get_parser(sensor_event)
        
        if parser is None:
            error_msg = f"No parser found for sensor type '{sensor_type}'"
            logger.error(f"❌ {error_msg}")
            
            # Log failure
            log_decision(
                state=state,
                node_name="parser_node",
                decision_type="parser_selection_failed",
                reasoning=error_msg,
                data={
                    "sensor_id": sensor_id,
                    "sensor_type": sensor_type
                }
            )
            
            add_notification(state, f"❌ {sensor_id}: No parser available for {sensor_type}")
            
            return {
                "parsed_entities": [],
                "error": error_msg,
                "decision_reasoning": f"## ❌ Parser Selection Failed\n\n{error_msg}"
            }
        
        parser_name = parser.__class__.__name__
        logger.info(f"✅ Selected parser: {parser_name}")
        
        # ============ PARSING ============
        
        logger.info(f"\n🔧 Parsing with {parser_name}...")
        
        # Parse using factory (includes validation)
        success, error_message, entities = factory.parse(sensor_event)
        
        if not success:
            error_msg = f"Parsing failed: {error_message}"
            logger.error(f"❌ {error_msg}")
            
            # Log parsing failure
            log_decision(
                state=state,
                node_name="parser_node",
                decision_type="parsing_failed",
                reasoning=error_msg,
                data={
                    "sensor_id": sensor_id,
                    "sensor_type": sensor_type,
                    "parser": parser_name,
                    "error": error_message
                }
            )
            
            add_notification(state, f"❌ {sensor_id}: Parsing failed - {error_message[:50]}...")
            
            reasoning = f"""## ❌ Parsing Failed

**Sensor**: `{sensor_id}` (type: `{sensor_type}`)
**Parser**: {parser_name}

### Error:
{error_message}

**Action**: Event cannot be processed. Check sensor data format.
"""
            
            return {
                "parsed_entities": [],
                "error": error_msg,
                "decision_reasoning": reasoning
            }
        
        # ============ SUCCESS ============
        
        entity_count = len(entities)
        logger.info(f"✅ Parsing successful: {entity_count} entities extracted")
        
        # Log entity details
        if entity_count > 0:
            logger.info(f"\n📦 Extracted entities:")
            for i, entity in enumerate(entities, 1):
                logger.info(f"   {i}. {entity.entity_id} ({entity.entity_type}) - {entity.classification}")
        else:
            logger.warning(f"⚠️  No entities extracted (valid but empty result)")
        
        # Check for multimodal processing needs
        needs_multimodal = has_file_refs
        if needs_multimodal:
            file_refs = sensor_event.get_file_references()
            logger.info(f"\n🎬 Multimodal processing required:")
            for file_type, file_path in file_refs.items():
                logger.info(f"   - {file_type}: {file_path}")
        
        # ============ BUILD REASONING ============
        
        reasoning = f"""## ✅ Parsing Complete

**Sensor**: `{sensor_id}` (type: `{sensor_type}`)
**Parser**: {parser_name}
**Timestamp**: {timestamp}

### Parsing Results:
- ✅ Entities extracted: **{entity_count}**
"""
        
        if entity_count > 0:
            reasoning += "\n### Extracted Entities:\n"
            for entity in entities:
                reasoning += f"- `{entity.entity_id}` - {entity.entity_type} ({entity.classification})\n"
                reasoning += f"  - Location: {entity.location.lat:.4f}, {entity.location.lon:.4f}\n"
                reasoning += f"  - Confidence: {entity.confidence:.2f}\n"
        
        if needs_multimodal:
            reasoning += "\n### 🎬 Multimodal Processing Needed:\n"
            file_refs = sensor_event.get_file_references()
            for file_type, file_path in file_refs.items():
                reasoning += f"- **{file_type}**: `{file_path}`\n"
            reasoning += "\n**Next**: Route to `multimodal_parser_node` for file processing\n"
        else:
            reasoning += "\n**Next**: Route to `cop_normalizer_node` for entity normalization\n"
        
        # ============ UPDATE STATE ============
        
        # Log successful parsing
        log_decision(
            state=state,
            node_name="parser_node",
            decision_type="parsing_success",
            reasoning=f"Parsed {entity_count} entities using {parser_name}",
            data={
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "parser": parser_name,
                "entity_count": entity_count,
                "needs_multimodal": needs_multimodal,
                "entity_ids": [e.entity_id for e in entities]
            }
        )
        
        # Update sensor metadata
        sensor_metadata = state.get("sensor_metadata", {})
        sensor_metadata.update({
            "parser_used": parser_name,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
            "entity_count": entity_count,
            "needs_multimodal": needs_multimodal
        })
        
        if needs_multimodal:
            sensor_metadata["file_references"] = sensor_event.get_file_references()
        
        # Add notification
        if entity_count > 0:
            add_notification(
                state,
                f"✅ {sensor_id}: Parsed {entity_count} entit{'y' if entity_count == 1 else 'ies'}"
            )
        else:
            add_notification(
                state,
                f"⚠️  {sensor_id}: Parsed successfully but no entities found"
            )
        
        logger.info("\n" + "=" * 70)
        logger.info(f"Parsing complete: {entity_count} entities extracted")
        logger.info("=" * 70 + "\n")
        
        # Return state updates
        return {
            "parsed_entities": entities,
            "sensor_metadata": sensor_metadata,
            "decision_reasoning": reasoning
        }
        
    except Exception as e:
        # Unexpected error during parsing
        error_msg = f"Parser node failed with exception: {str(e)}"
        logger.exception(f"❌ {error_msg}")
        
        # Log the exception
        log_decision(
            state=state,
            node_name="parser_node",
            decision_type="parser_exception",
            reasoning=error_msg,
            data={
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "exception": str(e),
                "exception_type": type(e).__name__
            }
        )
        
        # Add error notification
        add_notification(
            state,
            f"❌ {sensor_id}: Parser exception - {str(e)[:50]}..."
        )
        
        # Return failure state
        return {
            "parsed_entities": [],
            "error": error_msg,
            "decision_reasoning": f"## ❌ Parser Error\n\nException during parsing: {str(e)}"
        }


# ==================== ROUTING FUNCTION ====================

def should_route_to_multimodal(state: TIFDAState) -> str:
    """
    Routing function for conditional edges.
    
    Determines if message needs multimodal processing based on file references.
    
    Args:
        state: Current TIFDA state
        
    Returns:
        "multimodal" if file processing needed, "normalizer" otherwise
    """
    sensor_metadata = state.get("sensor_metadata", {})
    needs_multimodal = sensor_metadata.get("needs_multimodal", False)
    
    if needs_multimodal:
        logger.info("🎬 Routing to multimodal_parser_node (files detected)")
        return "multimodal"
    else:
        logger.info("➡️  Routing to cop_normalizer_node (no files)")
        return "normalizer"


# ==================== TESTING ====================

def test_parser_node():
    """Test the parser node with various sensor messages"""
    from src.core.state import create_state_from_sensor_event
    from src.models import SensorMessage
    
    print("\n" + "=" * 70)
    print("PARSER NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Radar message (inline data, no files)
    print("Test 1: Radar message with inline data")
    print("-" * 70)
    
    radar_msg = SensorMessage(
        sensor_id="radar_01",
        sensor_type="radar",
        timestamp=datetime.now(timezone.utc),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_101",
            "is_simulated": False,
            "tracks": [
                {
                    "track_id": "T001",
                    "location": {"lat": 39.5, "lon": -0.4},
                    "altitude_m": 5000,
                    "speed_kmh": 450,
                    "heading": 270,
                    "classification": "unknown"
                }
            ]
        }
    )
    
    state = create_state_from_sensor_event(radar_msg)
    state["firewall_passed"] = True  # Simulate firewall pass
    
    result = parser_node(state)
    
    print(f"Parsed entities: {len(result['parsed_entities'])}")
    if result['parsed_entities']:
        for entity in result['parsed_entities']:
            print(f"  - {entity.entity_id} ({entity.entity_type})")
    print(f"\nReasoning:\n{result['decision_reasoning']}")
    
    # Test 2: Drone message with image file reference
    print("\n" + "=" * 70)
    print("Test 2: Drone message with image file")
    print("-" * 70)
    
    drone_msg = SensorMessage(
        sensor_id="drone_alpha",
        sensor_type="drone",
        timestamp=datetime.now(timezone.utc),
        data={
            "drone_id": "DRONE_ALPHA_01",
            "flight_mode": "auto",
            "latitude": 39.4762,
            "longitude": -0.3747,
            "altitude_m_agl": 120,
            "heading": 90,
            "ground_speed_kmh": 45,
            "battery_percent": 78,
            "image_link": "data/sensor_data/drone_alpha/IMG_20251027_143100.jpg"
        }
    )
    
    state = create_state_from_sensor_event(drone_msg)
    state["firewall_passed"] = True
    
    result = parser_node(state)
    
    print(f"Parsed entities: {len(result['parsed_entities'])}")
    print(f"Needs multimodal: {result['sensor_metadata'].get('needs_multimodal', False)}")
    
    # Test routing
    route = should_route_to_multimodal(state | result)
    print(f"Route decision: {route}")
    
    # Test 3: Manual report (text-based)
    print("\n" + "=" * 70)
    print("Test 3: Manual report (text-based)")
    print("-" * 70)
    
    manual_msg = SensorMessage(
        sensor_id="operator_charlie",
        sensor_type="manual",
        timestamp=datetime.now(timezone.utc),
        data={
            "report_id": "SPOTREP_001",
            "report_type": "SPOTREP",
            "priority": "high",
            "operator_name": "Cpt. Smith",
            "content": "Visual confirmation: Single military aircraft, no IFF response",
            "latitude": 39.50,
            "longitude": -0.35
        }
    )
    
    state = create_state_from_sensor_event(manual_msg)
    state["firewall_passed"] = True
    
    result = parser_node(state)
    
    print(f"Parsed entities: {len(result['parsed_entities'])}")
    if result['parsed_entities']:
        for entity in result['parsed_entities']:
            print(f"  - {entity.entity_id}: {entity.comments[:50]}...")
    
    print("\n" + "=" * 70)
    print("PARSER NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_parser_node()