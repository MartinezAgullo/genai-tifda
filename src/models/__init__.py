"""
TIFDA Data Models
=================

Pydantic models for all TIFDA data structures.
"""

# COP entities
from src.models.cop_entities import (
    Location,
    EntityCOP,
    ThreatAssessment,
    COPSnapshot
)

# Dissemination
from src.models.dissemination import (
    DisseminationDecision,
    OutgoingMessage,
    RecipientConfig
)

# Human feedback
from src.models.human_feedback import (
    HumanFeedback,
    ReviewDecision
)

# Sensor formats
from src.models.sensor_formats import (
    SensorMessage,
    FileReference,
    TrackQuality,
    ASTERIXTrack,
    ASTERIXMessage,
    DroneData,
    RadioData,
    ManualReport
)

__all__ = [
    # COP
    "Location",
    "EntityCOP",
    "ThreatAssessment",
    "COPSnapshot",
    
    # Dissemination
    "DisseminationDecision",
    "OutgoingMessage",
    "RecipientConfig",
    
    # Human feedback
    "HumanFeedback",
    "ReviewDecision",
    
    # Sensor formats
    "SensorMessage",
    "FileReference",
    "TrackQuality",
    "ASTERIXTrack",
    "ASTERIXMessage",
    "DroneData",
    "RadioData",
    "ManualReport",
]