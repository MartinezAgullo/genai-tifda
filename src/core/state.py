"""
TIFDA State Schema
==================

LangGraph state definition for the TIFDA pipeline.
This is the main data structure that flows through all graph nodes.
"""

from datetime import datetime
from typing import Annotated, Dict, List, Optional, Any
from typing_extensions import TypedDict
import operator
from src.core.constants import CLASSIFICATIONS
from src.core.constants import ENTITY_TYPES


from src.models import (
    EntityCOP,
    SensorMessage,
    ThreatAssessment,
    DisseminationDecision,
    OutgoingMessage,
    HumanFeedback,
    ReviewDecision
)


class TIFDAState(TypedDict):
    """
    Main LangGraph state for TIFDA pipeline
    
    This state flows through all nodes in the graph, getting updated
    at each step. Uses Annotated types with operator.add for lists
    to enable incremental updates.
    """
    
    # ============ PERSISTENT COP (The heart of the system) ============
    cop_entities: Dict[str, EntityCOP]
    """
    The Common Operational Picture - all tracked entities
    Key: entity_id, Value: EntityCOP
    """
    
    cop_last_global_update: datetime
    """When the COP was last modified"""
    
    # ============ INCOMING SENSOR EVENT ============
    current_sensor_event: Optional[SensorMessage]
    """The NEW sensor data being processed in this graph invocation"""
    
    sensor_metadata: Dict[str, Any]
    """Metadata about the current sensor (id, type, timestamp, etc.)"""
    
    # ============ PROCESSING PIPELINE STATE ============
    raw_input: Any
    """Raw input data before parsing (can be JSON, file path, etc.)"""
    
    parsed_entities: List[EntityCOP]
    """Entities extracted from current sensor event"""
    
    firewall_passed: bool
    """Whether input passed security validation"""
    
    firewall_issues: Annotated[List[str], operator.add]
    """List of security issues detected (appended across nodes)"""
    
    # ============ THREAT ASSESSMENT ============
    current_threats: List[ThreatAssessment]
    """Threat assessments for current situation"""
    
    threat_history: Annotated[List[ThreatAssessment], operator.add]
    """Historical threat assessments (accumulated over time)"""
    
    threat_matrix: Dict[str, List[str]]
    """
    Quick lookup: asset_id -> list of threat_ids affecting it
    Used for fast threat queries
    """
    
    # ============ DISSEMINATION ============
    dissemination_decisions: List[DisseminationDecision]
    """Current dissemination decisions (who gets what)"""
    
    pending_transmissions: List[OutgoingMessage]
    """Messages ready to be sent"""
    
    transmission_log: Annotated[List[Dict], operator.add]
    """Log of all transmissions (accumulated over time)"""
    
    # ============ HUMAN-IN-THE-LOOP ============
    requires_human_review: bool
    """Whether current processing requires human approval"""
    
    human_feedback: Optional[HumanFeedback]
    """Feedback from human reviewer (if provided)"""
    
    review_reason: Optional[str]
    """Why human review was triggered"""
    
    pending_review_items: List[Dict[str, Any]]
    """Queue of items awaiting human review"""
    
    # ============ AUDIT & REASONING ============
    decision_reasoning: str
    """Markdown-formatted reasoning for current decisions"""
    
    decision_log: Annotated[List[Dict], operator.add]
    """
    Audit trail of all decisions made
    Each entry: {timestamp, node, decision_type, reasoning, data}
    """
    
    processing_metadata: Dict[str, Any]
    """
    Metadata about processing (timing, model versions, etc.)
    Example: {"start_time": ..., "llm_model": "gpt-4o", "total_nodes": 8}
    """
    
    # ============ ERROR HANDLING ============
    error: Optional[str]
    """Error message if processing failed"""
    
    retry_count: int
    """Number of retries attempted for current event"""
    
    # ============ UI STATE ============
    map_update_trigger: int
    """
    Increment this to force Gradio map refresh
    UI polls this value to detect changes
    """
    
    notification_queue: Annotated[List[str], operator.add]
    """Queue of notifications for Gradio UI"""


# ==================== STATE INITIALIZATION ====================

def create_initial_state() -> TIFDAState:
    """
    Create initial empty state for TIFDA system
    
    Used when starting a new processing session or after reset.
    
    Returns:
        Empty TIFDAState with default values
    """
    return TIFDAState(
        # COP
        cop_entities={},
        cop_last_global_update=datetime.utcnow(),
        
        # Current event
        current_sensor_event=None,
        sensor_metadata={},
        
        # Processing
        raw_input=None,
        parsed_entities=[],
        firewall_passed=False,
        firewall_issues=[],
        
        # Threats
        current_threats=[],
        threat_history=[],
        threat_matrix={},
        
        # Dissemination
        dissemination_decisions=[],
        pending_transmissions=[],
        transmission_log=[],
        
        # HITL
        requires_human_review=False,
        human_feedback=None,
        review_reason=None,
        pending_review_items=[],
        
        # Audit
        decision_reasoning="",
        decision_log=[],
        processing_metadata={
            "created_at": datetime.utcnow().isoformat(),
            "version": "0.1.0"
        },
        
        # Error handling
        error=None,
        retry_count=0,
        
        # UI
        map_update_trigger=0,
        notification_queue=[]
    )


def create_state_from_sensor_event(
    sensor_event: SensorMessage,
    existing_cop: Optional[Dict[str, EntityCOP]] = None
) -> TIFDAState:
    """
    Create state for processing a new sensor event
    
    Preserves existing COP if provided, otherwise starts fresh.
    
    Args:
        sensor_event: New sensor message to process
        existing_cop: Existing COP entities (if continuing from previous state)
        
    Returns:
        TIFDAState ready for graph processing
    """
    state = create_initial_state()
    
    # Set current event
    state["current_sensor_event"] = sensor_event
    state["sensor_metadata"] = {
        "sensor_id": sensor_event.sensor_id,
        "sensor_type": sensor_event.sensor_type,
        "timestamp": sensor_event.timestamp.isoformat(),
        "has_files": sensor_event.has_file_references()
    }
    
    # Preserve existing COP if provided
    if existing_cop:
        state["cop_entities"] = existing_cop
    
    # Set processing metadata
    state["processing_metadata"]["event_received_at"] = datetime.utcnow().isoformat()
    state["processing_metadata"]["sensor_id"] = sensor_event.sensor_id
    
    return state


# ==================== STATE UTILITIES ====================

def get_entity_by_id(state: TIFDAState, entity_id: str) -> Optional[EntityCOP]:
    """
    Safely retrieve entity from COP by ID
    
    Args:
        state: Current TIFDA state
        entity_id: Entity identifier
        
    Returns:
        EntityCOP if found, None otherwise
    """
    return state["cop_entities"].get(entity_id)


def add_entity_to_cop(state: TIFDAState, entity: EntityCOP) -> None:
    """
    Add or update entity in COP
    
    Args:
        state: Current TIFDA state
        entity: Entity to add/update
    """
    state["cop_entities"][entity.entity_id] = entity
    state["cop_last_global_update"] = datetime.utcnow()
    state["map_update_trigger"] += 1  # Trigger UI refresh


def remove_entity_from_cop(state: TIFDAState, entity_id: str) -> bool:
    """
    Remove entity from COP
    
    Args:
        state: Current TIFDA state
        entity_id: Entity to remove
        
    Returns:
        True if entity was removed, False if not found
    """
    if entity_id in state["cop_entities"]:
        del state["cop_entities"][entity_id]
        state["cop_last_global_update"] = datetime.utcnow()
        state["map_update_trigger"] += 1
        return True
    return False


def get_entities_by_classification(
    state: TIFDAState,
    classification: str
) -> List[EntityCOP]:
    """
    Get all entities with specific classification
    
    Args:
        state: Current TIFDA state
        classification: "friendly", "hostile", "neutral", or "unknown"
        
    Returns:
        List of matching entities
        
    Raises:
        ValueError: If classification is invalid
    """
    if classification not in CLASSIFICATIONS:
        raise ValueError(
            f"Invalid classification '{classification}'. "
            f"Must be one of: {CLASSIFICATIONS}"
        )
    
    return [
        entity for entity in state["cop_entities"].values()
        if entity.classification == classification
    ]


def get_entities_by_type(
    state: TIFDAState,
    entity_type: str
) -> List[EntityCOP]:
    """
    Get all entities of specific type
    
    Args:
        state: Current TIFDA state
        entity_type: e.g., "aircraft", "ground_vehicle", "tank"
        
    Returns:
        List of matching entities
        
    Raises:
        ValueError: If entity_type is invalid
    """
    if entity_type not in ENTITY_TYPES:
        raise ValueError(
            f"Invalid entity_type '{entity_type}'. "
            f"Must be one of: {ENTITY_TYPES}"
        )
    
    return [
        entity for entity in state["cop_entities"].values()
        if entity.entity_type == entity_type
    ]


def add_notification(state: TIFDAState, message: str) -> None:
    """
    Add notification for UI display
    
    Args:
        state: Current TIFDA state
        message: Notification message
    """
    timestamp = datetime.utcnow().strftime("%H:%M:%S")
    state["notification_queue"].append(f"[{timestamp}] {message}")


def log_decision(
    state: TIFDAState,
    node_name: str,
    decision_type: str,
    reasoning: str,
    data: Optional[Dict] = None
) -> None:
    """
    Add entry to decision audit log
    
    Args:
        state: Current TIFDA state
        node_name: Name of node making decision
        decision_type: Type of decision (e.g., "threat_assessment", "dissemination")
        reasoning: Natural language reasoning
        data: Additional data about the decision
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "node": node_name,
        "decision_type": decision_type,
        "reasoning": reasoning,
        "data": data or {}
    }
    state["decision_log"].append(log_entry)