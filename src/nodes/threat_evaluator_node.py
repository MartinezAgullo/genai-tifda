"""
Threat Evaluator Node
=====================

Seventh node in the TIFDA pipeline - LLM-based threat assessment.

This node:
1. Analyzes entities in COP for potential threats
2. Uses LLM (gpt-4o-mini) for tactical intelligence assessment
3. Considers multimodal data (audio transcriptions, image analysis)
4. Evaluates proximity to friendly assets
5. Generates ThreatAssessment objects with reasoning
6. Assigns threat levels: CRITICAL, HIGH, MEDIUM, LOW, NONE

This is where AI adds tactical intelligence - going beyond sensor data
to assess actual threats based on behavior, classification, and context.

Node Signature:
    Input: TIFDAState with cop_entities and parsed_entities (current event)
    Output: Updated TIFDAState with current_threats and threat_matrix
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import math

from langsmith import traceable
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.core.state import TIFDAState, log_decision, add_notification
from src.models import EntityCOP, ThreatAssessment

# Configure logging
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

# Threat assessment configuration
THREAT_ASSESSMENT_MODEL = "gpt-4o-mini"  # Fast and cost-effective
THREAT_ASSESSMENT_TEMPERATURE = 0.1  # Low temperature for consistent assessments
THREAT_PROXIMITY_RADIUS_KM = 50  # Consider threats within 50km of friendlies

# Entities that trigger threat assessment
THREAT_TRIGGER_CLASSIFICATIONS = ["hostile", "unknown"]


# ==================== GEOSPATIAL UTILITIES ====================

def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
    return distance


def _find_nearby_friendlies(
    entity: EntityCOP,
    cop_entities: Dict[str, EntityCOP],
    radius_km: float = THREAT_PROXIMITY_RADIUS_KM
) -> List[EntityCOP]:
    """
    Find friendly entities near a potential threat.
    
    Args:
        entity: Entity to check (potential threat)
        cop_entities: All entities in COP
        radius_km: Search radius in kilometers
        
    Returns:
        List of friendly entities within radius
    """
    nearby_friendlies = []
    
    for other_id, other_entity in cop_entities.items():
        # Skip if not friendly
        if other_entity.classification != "friendly":
            continue
        
        # Skip if same entity
        if other_id == entity.entity_id:
            continue
        
        # Calculate distance
        distance_km = _haversine_distance(
            entity.location.lat, entity.location.lon,
            other_entity.location.lat, other_entity.location.lon
        )
        
        if distance_km <= radius_km:
            nearby_friendlies.append(other_entity)
    
    return nearby_friendlies


# ==================== THREAT ASSESSMENT PROMPTS ====================

THREAT_ASSESSMENT_SYSTEM_PROMPT = """You are a tactical intelligence analyst for a military command center.

Your role is to assess threats based on sensor intelligence and the current operational picture.

THREAT LEVELS:
- CRITICAL: Immediate danger, requires urgent response (e.g., incoming missile, attack in progress)
- HIGH: Significant threat, high probability of hostile action (e.g., hostile forces approaching friendly positions)
- MEDIUM: Potential threat, requires monitoring (e.g., unknown aircraft in restricted airspace)
- LOW: Minor concern, unlikely to be threatening (e.g., neutral vehicle far from operations)
- NONE: No threat detected (e.g., friendly asset, neutral far away)

ASSESSMENT CRITERIA:
1. Classification (hostile > unknown > neutral)
2. Entity type (aircraft/missiles more threatening than ground vehicles)
3. Proximity to friendly assets
4. Speed and heading (approaching vs. moving away)
5. Multimodal intelligence (intercepts, visual confirmation)
6. Confidence level of data

Provide clear, actionable reasoning. Be conservative - when in doubt, assess as higher threat.
"""


def _build_threat_assessment_prompt(
    entity: EntityCOP,
    nearby_friendlies: List[EntityCOP],
    multimodal_available: bool
) -> str:
    """
    Build the threat assessment prompt for LLM.
    
    Args:
        entity: Entity to assess
        nearby_friendlies: Friendly entities nearby
        multimodal_available: Whether multimodal data is available
        
    Returns:
        Formatted prompt string
    """
    prompt = f"""Assess the threat level of the following entity:

ENTITY DETAILS:
- ID: {entity.entity_id}
- Type: {entity.entity_type}
- Classification: {entity.classification}
- Location: {entity.location.lat:.4f}°N, {entity.location.lon:.4f}°E
"""
    
    if entity.location.alt:
        prompt += f"- Altitude: {entity.location.alt:.0f}m\n"
    
    if entity.speed_kmh:
        prompt += f"- Speed: {entity.speed_kmh:.0f} km/h\n"
    
    if entity.heading is not None:
        prompt += f"- Heading: {entity.heading:.0f}°\n"
    
    prompt += f"- Confidence: {entity.confidence:.2f}\n"
    prompt += f"- Source sensors: {', '.join(entity.source_sensors)}\n"
    
    # Comments (may include multimodal flags)
    if entity.comments:
        prompt += f"- Additional info: {entity.comments}\n"
    
    # Multimodal data
    if multimodal_available and "multimodal_results" in entity.metadata:
        prompt += "\nMULTIMODAL INTELLIGENCE:\n"
        
        multimodal = entity.metadata["multimodal_results"]
        
        if "audio" in multimodal and multimodal["audio"].get("success"):
            prompt += "- Audio transcription available (radio intercept)\n"
            # Include snippet of transcription
            report = multimodal["audio"]["report"]
            snippet = report[:300] + "..." if len(report) > 300 else report
            prompt += f"  Preview: {snippet}\n"
        
        if "image" in multimodal and multimodal["image"].get("success"):
            prompt += "- Visual analysis available (imagery)\n"
            report = multimodal["image"]["report"]
            snippet = report[:300] + "..." if len(report) > 300 else report
            prompt += f"  Preview: {snippet}\n"
        
        if "document" in multimodal and multimodal["document"].get("success"):
            prompt += "- Document intelligence available\n"
            report = multimodal["document"]["report"]
            snippet = report[:300] + "..." if len(report) > 300 else report
            prompt += f"  Preview: {snippet}\n"
    
    # Nearby friendlies
    if nearby_friendlies:
        prompt += f"\nNEARBY FRIENDLY ASSETS ({len(nearby_friendlies)}):\n"
        for friendly in nearby_friendlies[:5]:  # Show first 5
            distance_km = _haversine_distance(
                entity.location.lat, entity.location.lon,
                friendly.location.lat, friendly.location.lon
            )
            prompt += f"- {friendly.entity_id} ({friendly.entity_type}) at {distance_km:.1f}km\n"
        
        if len(nearby_friendlies) > 5:
            prompt += f"- ... and {len(nearby_friendlies) - 5} more\n"
    else:
        prompt += "\nNEARBY FRIENDLY ASSETS: None within 50km\n"
    
    prompt += """
TASK:
Provide a threat assessment in the following format:

THREAT_LEVEL: [CRITICAL/HIGH/MEDIUM/LOW/NONE]
REASONING: [2-3 sentences explaining your assessment]
CONFIDENCE: [0.0-1.0]

Be specific and actionable. Focus on the most critical factors.
"""
    
    return prompt


def _parse_llm_threat_assessment(
    llm_response: str,
    entity: EntityCOP
) -> Optional[Dict[str, Any]]:
    """
    Parse LLM response into structured threat assessment.
    
    Args:
        llm_response: LLM response text
        entity: Entity being assessed
        
    Returns:
        Dictionary with threat_level, reasoning, confidence
        None if parsing fails
    """
    try:
        lines = llm_response.strip().split('\n')
        
        threat_level = None
        reasoning = None
        confidence = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("THREAT_LEVEL:"):
                level_text = line.split(":", 1)[1].strip().upper()
                # Extract just the level (in case there's extra text)
                for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]:
                    if level in level_text:
                        threat_level = level.lower()
                        break
            
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()
            
            elif line.startswith("CONFIDENCE:"):
                conf_text = line.split(":", 1)[1].strip()
                # Extract float
                try:
                    confidence = float(conf_text)
                except:
                    # Try to extract first number
                    import re
                    match = re.search(r'(\d+\.?\d*)', conf_text)
                    if match:
                        confidence = float(match.group(1))
        
        # Validate we got all required fields
        if not threat_level or not reasoning:
            logger.warning(f"⚠️  LLM response missing required fields")
            logger.warning(f"   Response: {llm_response[:200]}...")
            return None
        
        # Default confidence if not provided
        if confidence is None:
            confidence = 0.7
        
        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))
        
        return {
            "threat_level": threat_level,
            "reasoning": reasoning,
            "confidence": confidence
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to parse LLM response: {e}")
        logger.error(f"   Response: {llm_response[:200]}...")
        return None


@traceable(name="threat_evaluator_node")
def threat_evaluator_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Threat evaluation node using LLM intelligence.
    
    Analyzes entities in COP to identify potential threats. Uses LLM
    to provide tactical intelligence assessment considering:
    - Entity classification and type
    - Proximity to friendly assets
    - Multimodal intelligence (audio/image/document)
    - Speed, heading, and behavior patterns
    
    Threat assessment triggers:
    - New hostile entities in COP
    - New unknown entities in COP
    - Entities approaching friendly assets
    
    Args:
        state: Current TIFDA state containing:
            - parsed_entities: Entities from current sensor event
            - cop_entities: Full COP
        
    Returns:
        Dictionary with updated state fields:
            - current_threats: List[ThreatAssessment] (new threats)
            - threat_history: List[ThreatAssessment] (append to history)
            - threat_matrix: Dict (entity_id -> list of threat_ids)
            - decision_reasoning: str (markdown)
            - notification_queue: List[str]
            - decision_log: List[Dict]
    """
    logger.info("=" * 70)
    logger.info("THREAT EVALUATOR NODE - LLM Intelligence Assessment")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    parsed_entities = state.get("parsed_entities", [])
    cop_entities = state.get("cop_entities", {})
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not parsed_entities:
        logger.warning("⚠️  No new entities to assess")
        return {
            "current_threats": [],
            "decision_reasoning": "## ⚠️  No Threat Assessment Needed\n\nNo new entities to evaluate."
        }
    
    logger.info(f"📡 Evaluating threats from sensor: {sensor_id}")
    logger.info(f"   New entities: {len(parsed_entities)}")
    logger.info(f"   Total COP size: {len(cop_entities)}")
    
    # ============ FILTER ENTITIES FOR ASSESSMENT ============
    
    # Only assess hostile and unknown entities
    entities_to_assess = [
        entity for entity in parsed_entities
        if entity.classification in THREAT_TRIGGER_CLASSIFICATIONS
    ]
    
    if not entities_to_assess:
        logger.info("✅ No hostile/unknown entities - no threats detected")
        
        return {
            "current_threats": [],
            "decision_reasoning": f"""## ✅ No Threats Detected

All {len(parsed_entities)} new entities are friendly or neutral.
No threat assessment required.
"""
        }
    
    logger.info(f"🎯 Assessing {len(entities_to_assess)} potentially threatening entities")
    
    # ============ INITIALIZE LLM ============
    
    try:
        llm = ChatOpenAI(
            model=THREAT_ASSESSMENT_MODEL,
            temperature=THREAT_ASSESSMENT_TEMPERATURE
        )
    except Exception as e:
        error_msg = f"Failed to initialize LLM: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return {
            "current_threats": [],
            "error": error_msg,
            "decision_reasoning": f"## ❌ Threat Assessment Failed\n\n{error_msg}"
        }
    
    # ============ ASSESS EACH ENTITY ============
    
    threat_assessments = []
    assessment_errors = []
    
    for entity in entities_to_assess:
        logger.info(f"\n🔍 Assessing: {entity.entity_id} ({entity.entity_type}, {entity.classification})")
        
        try:
            # Find nearby friendlies
            nearby_friendlies = _find_nearby_friendlies(entity, cop_entities)
            
            logger.info(f"   Nearby friendlies: {len(nearby_friendlies)}")
            
            # Check if multimodal data available
            has_multimodal = (
                "multimodal_results" in entity.metadata and
                entity.metadata.get("multimodal_processed", False)
            )
            
            if has_multimodal:
                logger.info(f"   Multimodal data: Available")
            
            # Build prompt
            prompt = _build_threat_assessment_prompt(
                entity,
                nearby_friendlies,
                has_multimodal
            )
            
            # Call LLM
            logger.info(f"   🤖 Calling LLM for threat assessment...")
            
            messages = [
                SystemMessage(content=THREAT_ASSESSMENT_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]
            
            response = llm.invoke(messages)
            llm_response_text = response.content
            
            logger.info(f"   ✅ LLM response received ({len(llm_response_text)} chars)")
            
            # Parse response
            parsed = _parse_llm_threat_assessment(llm_response_text, entity)
            
            if not parsed:
                logger.warning(f"   ⚠️  Failed to parse LLM response, skipping")
                assessment_errors.append(f"{entity.entity_id}: Failed to parse LLM response")
                continue
            
            # Create ThreatAssessment
            assessment_id = f"threat_{entity.entity_id}_{int(datetime.utcnow().timestamp())}"
            
            # Calculate distances to affected entities (nearby friendlies)
            distances_to_affected = {}
            for friendly in nearby_friendlies:
                distance_km = _haversine_distance(
                    entity.location.lat, entity.location.lon,
                    friendly.location.lat, friendly.location.lon
                )
                distances_to_affected[friendly.entity_id] = distance_km
            
            threat_assessment = ThreatAssessment(
                assessment_id=assessment_id,
                threat_level=parsed["threat_level"],
                affected_entities=[f.entity_id for f in nearby_friendlies],
                threat_source_id=entity.entity_id,
                reasoning=parsed["reasoning"],
                confidence=parsed["confidence"],
                timestamp=datetime.utcnow(),
                distances_to_affected_km=distances_to_affected if distances_to_affected else None
            )
            
            threat_assessments.append(threat_assessment)
            
            logger.info(f"   ✅ Threat level: {threat_assessment.threat_level.upper()}")
            logger.info(f"   ✅ Confidence: {threat_assessment.confidence:.2f}")
            logger.info(f"   ✅ Affected: {len(threat_assessment.affected_entities)} assets")
            
        except Exception as e:
            logger.exception(f"   ❌ Error assessing {entity.entity_id}: {e}")
            assessment_errors.append(f"{entity.entity_id}: {str(e)}")
    
    # ============ BUILD THREAT MATRIX ============
    
    threat_matrix = {}
    
    for assessment in threat_assessments:
        # Map affected entities to this threat
        for entity_id in assessment.affected_entities:
            if entity_id not in threat_matrix:
                threat_matrix[entity_id] = []
            threat_matrix[entity_id].append(assessment.assessment_id)
    
    # ============ RESULTS ============
    
    logger.info(f"\n📊 Threat evaluation complete:")
    logger.info(f"   Assessments: {len(threat_assessments)}")
    logger.info(f"   Errors: {len(assessment_errors)}")
    
    # Count by threat level
    threat_counts = {
        "critical": sum(1 for t in threat_assessments if t.threat_level == "critical"),
        "high": sum(1 for t in threat_assessments if t.threat_level == "high"),
        "medium": sum(1 for t in threat_assessments if t.threat_level == "medium"),
        "low": sum(1 for t in threat_assessments if t.threat_level == "low"),
        "none": sum(1 for t in threat_assessments if t.threat_level == "none")
    }
    
    logger.info(f"   🔴 CRITICAL: {threat_counts['critical']}")
    logger.info(f"   🟠 HIGH: {threat_counts['high']}")
    logger.info(f"   🟡 MEDIUM: {threat_counts['medium']}")
    logger.info(f"   🟢 LOW: {threat_counts['low']}")
    logger.info(f"   ⚪ NONE: {threat_counts['none']}")
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 🎯 Threat Assessment Complete

**Sensor**: `{sensor_id}`
**Entities Evaluated**: {len(entities_to_assess)}

### Threat Summary:
"""
    
    if threat_counts["critical"] > 0:
        reasoning += f"- 🔴 **CRITICAL**: {threat_counts['critical']} (IMMEDIATE ACTION REQUIRED)\n"
    if threat_counts["high"] > 0:
        reasoning += f"- 🟠 **HIGH**: {threat_counts['high']}\n"
    if threat_counts["medium"] > 0:
        reasoning += f"- 🟡 **MEDIUM**: {threat_counts['medium']}\n"
    if threat_counts["low"] > 0:
        reasoning += f"- 🟢 **LOW**: {threat_counts['low']}\n"
    if threat_counts["none"] > 0:
        reasoning += f"- ⚪ **NONE**: {threat_counts['none']}\n"
    
    if not threat_assessments:
        reasoning += "\n✅ No threats detected.\n"
    else:
        reasoning += "\n### Threat Details:\n\n"
        
        # Show critical and high threats first
        priority_threats = [t for t in threat_assessments if t.threat_level in ["critical", "high"]]
        
        for assessment in priority_threats:
            icon = "🔴" if assessment.threat_level == "critical" else "🟠"
            reasoning += f"{icon} **{assessment.threat_source_id}** - {assessment.threat_level.upper()}\n"
            reasoning += f"  - Confidence: {assessment.confidence:.2f}\n"
            reasoning += f"  - Reasoning: {assessment.reasoning}\n"
            reasoning += f"  - Affected assets: {len(assessment.affected_entities)}\n"
            reasoning += "\n"
    
    if assessment_errors:
        reasoning += f"\n### ⚠️  Assessment Errors ({len(assessment_errors)}):\n"
        for error in assessment_errors[:3]:
            reasoning += f"- {error}\n"
    
    reasoning += f"""
**Next**: Route to `human_review_node` for operator approval
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="threat_evaluator_node",
        decision_type="threat_assessment",
        reasoning=f"Assessed {len(entities_to_assess)} entities: {threat_counts['critical']} critical, {threat_counts['high']} high",
        data={
            "sensor_id": sensor_id,
            "entities_assessed": len(entities_to_assess),
            "assessments_created": len(threat_assessments),
            "threat_counts": threat_counts,
            "errors": assessment_errors
        }
    )
    
    # Add notifications
    if threat_counts["critical"] > 0:
        add_notification(
            state,
            f"🔴 CRITICAL: {threat_counts['critical']} critical threat(s) detected!"
        )
    
    if threat_counts["high"] > 0:
        add_notification(
            state,
            f"🟠 HIGH: {threat_counts['high']} high-priority threat(s) detected"
        )
    
    if len(threat_assessments) == 0:
        add_notification(
            state,
            f"✅ {sensor_id}: No threats detected"
        )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Threat evaluation complete: {len(threat_assessments)} assessments")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "current_threats": threat_assessments,
        "threat_matrix": threat_matrix,
        "decision_reasoning": reasoning
    }


# ==================== TESTING ====================

def test_threat_evaluator_node():
    """Test the threat evaluator node"""
    from src.core.state import create_initial_state
    from src.models import Location
    
    print("\n" + "=" * 70)
    print("THREAT EVALUATOR NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Hostile entity near friendly assets
    print("Test 1: Hostile entity approaching friendlies")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_01"}
    
    # COP with friendly assets
    state["cop_entities"] = {
        "base_alpha": EntityCOP(
            entity_id="base_alpha",
            entity_type="base",
            location=Location(lat=39.500, lon=-0.400),
            timestamp=datetime.utcnow(),
            classification="friendly",
            information_classification="SECRET",
            confidence=1.0,
            source_sensors=["manual"]
        )
    }
    
    # New hostile entity nearby
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="radar_01_T001",
            entity_type="aircraft",
            location=Location(lat=39.520, lon=-0.420, alt=5000),  # ~3km from base
            timestamp=datetime.utcnow(),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.85,
            source_sensors=["radar_01"],
            speed_kmh=450,
            heading=180  # Heading toward base
        )
    ]
    
    # Note: This will call actual LLM
    print("⚠️  This test calls real LLM (gpt-4o-mini)")
    print("    Make sure OPENAI_API_KEY is set in .env")
    print()
    
    try:
        result = threat_evaluator_node(state)
        
        print(f"Threats detected: {len(result['current_threats'])}")
        
        if result['current_threats']:
            for threat in result['current_threats']:
                print(f"\nThreat Assessment:")
                print(f"  Source: {threat.threat_source_id}")
                print(f"  Level: {threat.threat_level.upper()}")
                print(f"  Confidence: {threat.confidence:.2f}")
                print(f"  Reasoning: {threat.reasoning}")
                print(f"  Affected: {len(threat.affected_entities)} assets")
        
        print(f"\nReasoning preview:\n{result['decision_reasoning'][:400]}...")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("   Check that OPENAI_API_KEY is set")
    
    print("\n" + "=" * 70)
    print("THREAT EVALUATOR NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_threat_evaluator_node()