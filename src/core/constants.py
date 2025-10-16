"""
TIFDA Constants
===============

System-wide constants and enumerations following NATO Joint Military Symbology (APP-6).

This module defines the controlled vocabularies used throughout TIFDA for:
- Entity classification (friendly/hostile/neutral/unknown)
- Dimensional categorization (air/ground/sea/space/cyber)
- Platform types (aircraft, vehicles, vessels, infrastructure)
- Threat assessment levels
- Security classifications and access control
- Operational parameters

References:
- NATO APP-6E (Joint Military Symbology)
- MIL-STD-2525D (US equivalent)
- NATO Security Classification Policy
"""

from typing import Literal

# ==================== APP-6 CORE: AFFILIATION ====================

CLASSIFICATIONS = ["friendly", "hostile", "neutral", "unknown"]
"""
Entity affiliation following APP-6 standard identity:
- friendly: Friend (blue in symbology)
- hostile: Hostile or adversary (red in symbology)
- neutral: Neutral (green in symbology)
- unknown: Unknown or pending (yellow in symbology)
"""

# ==================== APP-6 CORE: DIMENSION (BATTLE SPACE) ====================

DIMENSIONS = [
    "air",          # Air domain - aircraft, helicopters, UAVs, missiles
    "ground",       # Ground domain - vehicles, infantry, installations
    "sea_surface",  # Sea surface domain - ships, boats
    "sea_subsurface",  # Subsurface domain - submarines, UUVs
    "space",        # Space domain - satellites, orbital assets
    "cyber",        # Cyber domain - network entities, cyber events
    "other"         # Environmental, abstract, or unclassified
]
"""
Dimensional categorization of entities (APP-6 'Battle Dimension').
Determines the operational domain where entity operates.
"""

# Dimension to NATO symbol code mapping
DIMENSION_SYMBOL_CODES = {
    "air": "A",
    "ground": "G",
    "sea_surface": "S",
    "sea_subsurface": "U",
    "space": "P",
    "cyber": "C",
    "other": "X"
}

# ==================== ENTITY TYPES (Detailed Platform Classification) ====================

# Organized by dimension for clarity
AIR_ENTITY_TYPES = [
    "aircraft",           # Fixed-wing aircraft (general)
    "fighter",            # Fighter aircraft
    "bomber",             # Bomber aircraft
    "transport",          # Transport/cargo aircraft
    "helicopter",         # Rotary-wing aircraft
    "uav",                # Unmanned Aerial Vehicle (drone)
    "missile",            # Missile (air-launched or surface-to-air)
    "air_unknown"         # Unidentified air contact
]

GROUND_ENTITY_TYPES = [
    "ground_vehicle",     # General ground vehicle
    "tank",               # Main battle tank
    "apc",                # Armored Personnel Carrier
    "ifv",                # Infantry Fighting Vehicle
    "artillery",          # Artillery system
    "infantry",           # Dismounted personnel unit
    "command_post",       # Command & Control facility
    "radar_site",         # Radar/sensor installation
    "infrastructure",     # General infrastructure
    "building",           # Building/structure
    "bridge",             # Bridge
    "base",               # Military base/installation
    "ground_unknown"      # Unidentified ground entity
]

SEA_ENTITY_TYPES = [
    "ship",               # General surface vessel
    "carrier",            # Aircraft carrier
    "destroyer",          # Destroyer
    "frigate",            # Frigate
    "corvette",           # Corvette
    "patrol_boat",        # Patrol craft
    "submarine",          # Submarine
    "boat",               # Small boat (RHIB, etc.)
    "sea_unknown"         # Unidentified maritime contact
]

OTHER_ENTITY_TYPES = [
    "satellite",          # Space-based asset
    "cyber_node",         # Cyber entity
    "person",             # Individual person
    "event",              # Abstract event (area of interest, etc.)
    "unknown"             # Completely unknown
]

# Combined list for validation
ENTITY_TYPES = (
    AIR_ENTITY_TYPES +
    GROUND_ENTITY_TYPES +
    SEA_ENTITY_TYPES +
    OTHER_ENTITY_TYPES
)
"""
Detailed entity type classification for all domains.
Maps to APP-6 'Entity' and 'Entity Type' fields.
"""

# ==================== APP-6: ECHELON (COMMAND LEVEL) ====================

ECHELONS = [
    "individual",    # Single person/platform
    "team",          # Team/Crew (2-4)
    "squad",         # Squad (8-13)
    "section",       # Section (~20)
    "platoon",       # Platoon (30-50)
    "company",       # Company (100-200)
    "battalion",     # Battalion (400-1000)
    "regiment",      # Regiment/Group
    "brigade",       # Brigade (3000-5000)
    "division",      # Division (10000-20000)
    "corps",         # Corps (20000-50000)
    "army",          # Army (50000+)
    "army_group",    # Army Group/Theater
    "none"           # Not applicable (e.g., infrastructure)
]
"""
Military organizational echelon (size/command level).
Maps to APP-6 'Echelon' modifier field.
Only applicable to military units, not individual platforms or infrastructure.
"""

# Echelon symbol codes (APP-6 amplifiers)
ECHELON_SYMBOL_CODES = {
    "individual": "A",
    "team": "B",
    "squad": "C",
    "section": "D",
    "platoon": "E",
    "company": "F",
    "battalion": "G",
    "regiment": "H",
    "brigade": "I",
    "division": "J",
    "corps": "K",
    "army": "L",
    "army_group": "M",
    "none": ""
}

# ==================== THREAT LEVELS ====================

THREAT_LEVELS = ["critical", "high", "medium", "low", "none"]
"""
Threat severity assessment levels.
Determines priority and response urgency.
"""

# Threat level priorities (for sorting)
THREAT_LEVEL_PRIORITY = {
    "critical": 5,  # Imminent danger, immediate action required
    "high": 4,      # Significant threat, urgent response needed
    "medium": 3,    # Moderate threat, monitor closely
    "low": 2,       # Minor threat, routine monitoring
    "none": 1       # No identified threat
}

# ==================== CLASSIFICATION LEVELS (Information Sensitivity) ====================

CLASSIFICATION_LEVELS = [
    "TOP_SECRET",      # Exceptionally grave damage to national security if disclosed
    "SECRET",          # Serious damage to national security if disclosed
    "CONFIDENTIAL",    # Damage to national security if disclosed
    "RESTRICTED",      # Undesirable effects if disclosed (NATO/EU standard)
    "UNCLASSIFIED"     # No classification required (publicly releasable)
]
"""
Information security classification levels (NATO/National standard).
Determines data sensitivity, handling requirements, and dissemination controls.

NATO Standard:
- TOP SECRET: Exceptionally grave damage
- SECRET: Serious damage
- CONFIDENTIAL: Damage to national security
- RESTRICTED: Undesirable effects (NATO specific, between CONFIDENTIAL and UNCLASSIFIED)
- UNCLASSIFIED: Publicly releasable

Note: US uses same levels except RESTRICTED (uses CONFIDENTIAL → UNCLASSIFIED directly).
"""

# Classification hierarchy (for determining max level and access control)
CLASSIFICATION_HIERARCHY = {
    "TOP_SECRET": 5,
    "SECRET": 4,
    "CONFIDENTIAL": 3,
    "RESTRICTED": 2,
    "UNCLASSIFIED": 1
}

# ==================== ACCESS LEVELS (Who can view information) ====================

ACCESS_LEVELS = [
    "top_secret_access",    # Can view TOP_SECRET and all below
    "secret_access",        # Can view SECRET and all below
    "confidential_access",  # Can view CONFIDENTIAL and all below
    "restricted_access",    # Can view RESTRICTED and all below
    "unclassified_access",  # Can view UNCLASSIFIED only (public access)
    "enemy_access"          # Special: Receives controlled disinformation (honeypot)
]
"""
Access levels for recipients (users, systems, allied forces).
Determines what classification levels a recipient can view.

Access control follows "read down" principle:
- top_secret_access can read: TOP_SECRET, SECRET, CONFIDENTIAL, RESTRICTED, UNCLASSIFIED
- secret_access can read: SECRET, CONFIDENTIAL, RESTRICTED, UNCLASSIFIED
- confidential_access can read: CONFIDENTIAL, RESTRICTED, UNCLASSIFIED
- restricted_access can read: RESTRICTED, UNCLASSIFIED
- unclassified_access can read: UNCLASSIFIED only

Special case: "enemy_access" is for deception operations (honeypot).
Recipients with enemy_access receive mix of UNCLASSIFIED (real but low-value) 
and fabricated information to mislead adversaries.
"""

ACCESS_LEVEL_HIERARCHY = {
    "top_secret_access": 5,
    "secret_access": 4,
    "confidential_access": 3,
    "restricted_access": 2,
    "unclassified_access": 1,
    "enemy_access": 0  # Below all - controlled information operations
}

# ==================== ACCESS CONTROL HELPERS ====================

def can_access_classification(
    access_level: str,
    data_classification: str
) -> bool:
    """
    Determine if an access level can view data with given classification.
    
    Implements "read down" access control: higher clearance can read lower classifications.
    
    Args:
        access_level: Recipient's access level (e.g., "secret_access")
        data_classification: Data's classification (e.g., "SECRET")
        
    Returns:
        True if access is permitted, False otherwise
        
    Examples:
        >>> can_access_classification("secret_access", "CONFIDENTIAL")
        True  # SECRET clearance can read CONFIDENTIAL data
        
        >>> can_access_classification("confidential_access", "SECRET")
        False  # CONFIDENTIAL clearance CANNOT read SECRET data
        
        >>> can_access_classification("enemy_access", "SECRET")
        False  # Enemy never gets real classified data
        
        >>> can_access_classification("enemy_access", "UNCLASSIFIED")
        True  # Enemy can get UNCLASSIFIED (or controlled leaks)
    """
    # Special case: enemy_access only gets UNCLASSIFIED or controlled disinformation
    if access_level == "enemy_access":
        return data_classification == "UNCLASSIFIED"
    
    # Normal access control: "read down" principle
    access_rank = ACCESS_LEVEL_HIERARCHY.get(access_level, 0)
    data_rank = CLASSIFICATION_HIERARCHY.get(data_classification, 999)
    
    # Can access if your clearance level >= data classification level
    return access_rank >= data_rank


def get_max_classification_for_access(access_level: str) -> str:
    """
    Get the highest classification level a recipient can view.
    
    Args:
        access_level: Recipient's access level
        
    Returns:
        Maximum classification level they can view
        
    Examples:
        >>> get_max_classification_for_access("secret_access")
        "SECRET"
        
        >>> get_max_classification_for_access("restricted_access")
        "RESTRICTED"
        
        >>> get_max_classification_for_access("enemy_access")
        "UNCLASSIFIED"
    """
    if access_level == "enemy_access":
        return "UNCLASSIFIED"
    
    access_rank = ACCESS_LEVEL_HIERARCHY.get(access_level, 0)
    
    # Find classification with matching rank
    for classification, rank in CLASSIFICATION_HIERARCHY.items():
        if rank == access_rank:
            return classification
    
    return "UNCLASSIFIED"  # Fallback to lowest classification


def filter_entities_by_access(
    entities: list,
    access_level: str
) -> list:
    """
    Filter entities based on recipient's access level.
    
    Removes entities that recipient doesn't have clearance to view.
    
    Args:
        entities: List of EntityCOP objects
        access_level: Recipient's access level
        
    Returns:
        Filtered list of entities recipient is authorized to view
        
    Example:
        >>> entities = [entity_ts, entity_secret, entity_unclass]
        >>> filter_entities_by_access(entities, "secret_access")
        [entity_secret, entity_unclass]  # TOP_SECRET entity filtered out
    """
    filtered = []
    
    for entity in entities:
        # Get entity's information classification
        # Default to UNCLASSIFIED if not specified
        entity_classification = getattr(
            entity, 
            'information_classification', 
            entity.metadata.get('information_classification', 'UNCLASSIFIED')
        )
        
        if can_access_classification(access_level, entity_classification):
            filtered.append(entity)
    
    return filtered


def get_highest_classification(classifications: list[str]) -> str:
    """
    Get the highest classification level from a list.
    
    Args:
        classifications: List of classification levels
        
    Returns:
        Highest classification level
        
    Example:
        >>> get_highest_classification(["SECRET", "UNCLASSIFIED", "CONFIDENTIAL"])
        "SECRET"
    """
    if not classifications:
        return "UNCLASSIFIED"
    
    max_rank = 0
    highest = "UNCLASSIFIED"
    
    for classification in classifications:
        rank = CLASSIFICATION_HIERARCHY.get(classification, 0)
        if rank > max_rank:
            max_rank = rank
            highest = classification
    
    return highest

# ==================== SENSOR TYPES ====================

SENSOR_TYPES = ["radar", "drone", "radio", "manual", "other"]
"""
Types of sensors providing input to TIFDA.
Determines parsing and processing strategy.
"""

# ==================== OUTPUT FORMATS ====================

OUTPUT_FORMATS = [
    "link16",      # Link-16 tactical data link (NATO standard)
    "json",        # Generic JSON format
    "asterix",     # ASTERIX radar format (EUROCONTROL)
    "cot",         # Cursor-on-Target (ATAK, WinTAK)
    "voice_text",  # Text for voice synthesis (tactical radio)
    "custom"       # Custom format for specific recipients
]
"""
Supported output formats for dissemination to downstream systems.
"""

# ==================== REPORT TYPES (Military Standard) ====================

REPORT_TYPES = [
    "SITREP",   # Situation Report - general situation update
    "SPOTREP",  # Spot Report - immediate observation of enemy activity
    "SALUTE",   # Size, Activity, Location, Unit, Time, Equipment
    "LOGREP",   # Logistics Report - supply and maintenance status
    "MEDEVAC",  # Medical Evacuation request
    "OTHER"     # Non-standard report type
]
"""
Standard military report types for manual operator reports.
"""

# ==================== REVIEW DECISIONS (HITL) ====================

REVIEW_DECISIONS = ["approve", "reject", "modify"]
"""
Human-in-the-loop review decision options.
"""

# ==================== GEOSPATIAL ====================

# Default map center (Valencia, Spain)
DEFAULT_MAP_CENTER = (39.4699, -0.3763)
"""Default map center for visualization (Valencia, Spain)"""

# Distance thresholds (in kilometers) - for threat proximity assessment
THREAT_DISTANCE_CRITICAL = 10   # < 10km = critical threat
THREAT_DISTANCE_HIGH = 50       # < 50km = high threat
THREAT_DISTANCE_MEDIUM = 150    # < 150km = medium threat
THREAT_DISTANCE_LOW = 500       # < 500km = low threat
"""
Distance-based threat level thresholds.
Used by threat evaluator to assess proximity risk.
"""

# ==================== CONFIDENCE THRESHOLDS ====================

MIN_CONFIDENCE_FOR_ALERT = 0.5              # Minimum to trigger any alert
MIN_CONFIDENCE_FOR_AUTO_DISSEMINATE = 0.7   # Auto-send without review
MIN_CONFIDENCE_FOR_CLASSIFICATION = 0.6     # Minimum to classify as friend/foe
"""
Confidence thresholds for automated decision-making.
Lower confidence triggers human review.
"""

# ==================== HUMAN REVIEW TRIGGERS ====================

HUMAN_REVIEW_TRIGGERS = {
    "critical_threat": True,           # Critical threats always need review
    "top_secret_dissemination": True,  # TOP_SECRET data needs approval
    "low_confidence": 0.6,             # Confidence below this triggers review
    "first_contact": True,             # First time seeing entity/sensor type
    "conflicting_sensors": True,       # Multiple sensors disagree
    "enemy_access_transmission": True  # Deception ops need approval
}
"""
Conditions that trigger mandatory human-in-the-loop review.
"""

# ==================== SYSTEM (LangGraph) ====================

# Graph node names (for consistent referencing across codebase)
NODE_NAMES = {
    "firewall": "firewall_node",
    "parser": "multimodal_parser_node",
    "cop_normalizer": "cop_normalizer_node",
    "cop_merge": "cop_merge_node",
    "cop_update": "cop_update_node",
    "threat_evaluator": "threat_evaluator_node",
    "human_review": "human_review_node",
    "dissemination_router": "dissemination_router_node",
    "format_adapter": "format_adapter_node",
    "transmission": "transmission_node",
    "audit_logger": "audit_logger_node"
}
"""LangGraph node identifiers for pipeline orchestration"""

# LangGraph state keys (for type-safe state access)
STATE_KEYS = {
    "cop_entities": "cop_entities",
    "current_sensor_event": "current_sensor_event",
    "parsed_entities": "parsed_entities",
    "threat_assessments": "threat_assessments",
    "dissemination_decisions": "dissemination_decisions",
    "requires_human_review": "requires_human_review",
    "human_feedback": "human_feedback",
    "error": "error"
}
"""TIFDAState field names for type-safe access"""

# ==================== MQTT ====================

# MQTT topic structure (templated)
MQTT_TOPICS = {
    "radar": "tifda/sensors/radar/{sensor_id}",
    "drone": "tifda/sensors/drone/{sensor_id}",
    "radio": "tifda/sensors/radio/{sensor_id}",
    "manual": "tifda/sensors/manual/{operator_id}",
    "other": "tifda/sensors/other/{sensor_id}",
    "output": "tifda/output/{recipient_id}"
}
"""MQTT topic templates for sensor inputs and downstream outputs"""

# MQTT Quality of Service levels by message type
MQTT_QOS = {
    "radar": 1,      # At least once delivery
    "drone": 1,      # At least once delivery
    "radio": 0,      # Best effort (audio files are large)
    "manual": 2,     # Exactly once (critical human input)
    "output": 2      # Exactly once (dissemination must be reliable)
}
"""MQTT QoS levels ensuring appropriate delivery guarantees per sensor type"""

# ==================== FILE HANDLING ====================

# Supported file extensions for multimodal processing
SUPPORTED_FILE_TYPES = {
    "audio": [".mp3", ".wav", ".m4a", ".flac", ".ogg"],
    "image": [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif"],
    "document": [".txt", ".pdf", ".doc", ".docx"],
    "video": [".mp4", ".avi", ".mov", ".mkv"]
}
"""File extensions supported by multimodal processing tools"""

# Maximum file sizes (in MB)
MAX_FILE_SIZE = {
    "audio": 50,
    "image": 10,
    "document": 5,
    "video": 100
}
"""Maximum file sizes to prevent memory issues and ensure responsiveness"""

# ==================== TIMING ====================

# Gradio UI polling interval (seconds)
UI_REFRESH_INTERVAL = 2.5
"""Gradio map refresh rate for near-real-time updates"""

# Entity expiration time (seconds) - how long before entity is considered stale
ENTITY_EXPIRATION_TIME = None  # Currently disabled (no auto-expiration)
"""Time before COP entity expires (None = no expiration, future feature)"""

# ==================== NATO SYMBOLOGY (APP-6E Simplified) ====================

# APP-6E standard affiliation colors
NATO_COLORS = {
    "friendly": "#0080FF",  # Blue
    "hostile": "#FF0000",   # Red
    "neutral": "#00FF00",   # Green
    "unknown": "#FFFF00"    # Yellow
}
"""
APP-6E standard colors for entity affiliation.
Used in map visualization for quick threat identification.
"""

# APP-6E Symbol Identity Codes (SIDC components)
NATO_SYMBOL_CODES = {
    # Standard Identity (Affiliation)
    "friendly": "F",
    "hostile": "H",
    "neutral": "N",
    "unknown": "U",
    
    # Battle Dimension
    "air": "A",
    "ground": "G",
    "sea_surface": "S",
    "sea_subsurface": "U",
    "space": "P",
    "cyber": "C"
}
"""
APP-6E Symbol Identification Code (SIDC) components.
Used for generating NATO-compliant military symbols.

SIDC Structure (15 characters):
  Position 1-2: Standard Identity (affiliation)
  Position 3: Battle Dimension
  Position 4-10: Entity/type codes
  Position 11-15: Modifiers (echelon, status, etc.)
"""

# ==================== HELPER FUNCTIONS ====================

def get_dimension_for_entity_type(entity_type: str) -> str:
    """
    Infer battle dimension from entity type
    
    Args:
        entity_type: Entity type string
        
    Returns:
        Dimension string (air, ground, sea_surface, etc.)
    """
    if entity_type in AIR_ENTITY_TYPES:
        return "air"
    elif entity_type in GROUND_ENTITY_TYPES:
        return "ground"
    elif entity_type in SEA_ENTITY_TYPES:
        if entity_type == "submarine":
            return "sea_subsurface"
        return "sea_surface"
    elif entity_type == "satellite":
        return "space"
    elif entity_type == "cyber_node":
        return "cyber"
    else:
        return "other"


def get_threat_level_from_distance(distance_km: float) -> str:
    """
    Determine threat level based on distance
    
    Args:
        distance_km: Distance to threat in kilometers
        
    Returns:
        Threat level string
    """
    if distance_km < THREAT_DISTANCE_CRITICAL:
        return "critical"
    elif distance_km < THREAT_DISTANCE_HIGH:
        return "high"
    elif distance_km < THREAT_DISTANCE_MEDIUM:
        return "medium"
    elif distance_km < THREAT_DISTANCE_LOW:
        return "low"
    else:
        return "none"