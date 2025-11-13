"""
COP Entity Models
=================

Core data structures for the Common Operational Picture (COP).
These models represent entities (assets, dangers, infrastructure) 
tracked in the tactical environment.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from typing import Any


class Location(BaseModel):
    """Geographic location with optional altitude"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    alt: Optional[float] = Field(None, description="Altitude in meters (optional)")
    
    @field_validator('lat', 'lon')
    @classmethod
    def round_coordinates(cls, v: float) -> float:
        """Round to 6 decimal places (~0.1m precision)"""
        return round(v, 6)


class EntityCOP(BaseModel):
    """
    Common Operational Picture Entity
    
    Represents any tracked entity in the battlefield: aircraft, vehicles,
    infrastructure, persons, etc.
    """
    entity_id: str = Field(..., description="Unique identifier for this entity")
    entity_type: str = Field(..., description="Type: aircraft, ground_vehicle, ship, infrastructure, person, etc.")
    location: Location = Field(..., description="Current geographic location")
    timestamp: datetime = Field(..., description="When this information was recorded")
    
    # Classification (IFF - Identification Friend or Foe)
    classification: Literal["friendly", "hostile", "neutral", "unknown"] = Field(
        "unknown",
        description="IFF classification (affiliation) - determines symbology color"
    )
    
    # Information Classification (Security level)
    information_classification: Literal["TOP_SECRET", "SECRET", "CONFIDENTIAL", "RESTRICTED", "UNCLASSIFIED"] = Field(
        "UNCLASSIFIED",
        description="Security classification level of this entity's information (determines who can see it)"
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in this information (0.0-1.0)"
    )
    
    # Source tracking
    source_sensors: List[str] = Field(
        default_factory=list,
        description="List of sensor IDs that reported this entity"
    )
    
    # Additional metadata (sensor-specific data)
    metadata: Dict = Field(
        default_factory=dict,
        description="Additional sensor-specific metadata"
    )
    
    # Optional fields
    speed_kmh: Optional[float] = Field(None, description="Speed in km/h")
    heading: Optional[float] = Field(None, ge=0, le=360, description="Heading in degrees")
    comments: Optional[str] = Field(None, description="Human-readable comments")

    def to_mapa_punto_interes(self) -> Dict[str, Any]:
        """
        Convert EntityCOP to mapa-puntos-interes format (NEW API v2)
        
        Returns:
            Dict ready for POST /api/puntos
            
        Note:
            Uses new lowercase enum categories and alliance field.
            Removed deprecated fields: ciudad, provincia, direccion, telefono, email, website
        """
        # Map TIFDA entity_type to NEW mapa lowercase categoria enum
        # Valid categories: missile, fighter, bomber, aircraft, helicopter, uav,
        #                  tank, artillery, ship, destroyer, submarine, ground_vehicle,
        #                  apc, infantry, person, base, building, infrastructure, default
        entity_type_to_categoria = {
            # Air entities
            "aircraft": "aircraft",
            "fighter": "fighter",
            "bomber": "bomber",
            "transport": "aircraft",
            "helicopter": "helicopter",
            "uav": "uav",
            "missile": "missile",
            "air_unknown": "aircraft",
            
            # Ground entities
            "tank": "tank",
            "apc": "apc",
            "ifv": "apc",
            "artillery": "artillery",
            "infantry": "infantry",
            "ground_vehicle": "ground_vehicle",
            "ground_unknown": "ground_vehicle",
            
            # Sea entities
            "ship": "ship",
            "carrier": "ship",
            "destroyer": "destroyer",
            "frigate": "destroyer",
            "corvette": "destroyer",
            "patrol_boat": "ship",
            "submarine": "submarine",
            "boat": "ship",
            "sea_unknown": "ship",
            
            # Infrastructure
            "command_post": "base",
            "radar_site": "base",
            "infrastructure": "infrastructure",
            "building": "building",
            "bridge": "infrastructure",
            "base": "base",
            
            # Other
            "satellite": "default",
            "cyber_node": "default",
            "person": "person",
            "event": "default",
            "unknown": "default"
        }
        
        # Get categoria with fallback to "default"
        categoria = entity_type_to_categoria.get(self.entity_type, "default")
        
        # Map TIFDA classification to mapa alliance
        # TIFDA: friendly, hostile, neutral, unknown
        # Mapa:  friendly, hostile, neutral, unknown (same!)
        alliance = self.classification  # Direct mapping
        
        # Determine country from metadata or use Unknown
        country = self.metadata.get("country", "Unknown")
        
        # Build punto data with NEW schema
        punto_data = {
            "nombre": self.entity_id,
            "descripcion": self.comments or f"{self.entity_type} - {self.classification}",
            "categoria": categoria,
            "country": country,
            "alliance": alliance,
            "elemento_identificado": self.entity_id,
            "activo": True,
            "tipo_elemento": self.entity_type,
            "prioridad": self._calculate_priority(),
            "observaciones": self._build_observations(),
            "longitud": self.location.lon,
            "latitud": self.location.lat
        }

        # Add optional altitude
        if self.location.alt is not None:
            punto_data['altitud'] = self.location.alt
            
        return punto_data
    
    def _calculate_priority(self) -> int:
        """Calculate priority 0-10 based on threat level and classification"""
        priority_map = {
            "hostile": 9,
            "unknown": 6,
            "neutral": 3,
            "friendly": 2
        }
        return priority_map.get(self.classification, 5)
    
    def _build_observations(self) -> str:
        """Build observation text from metadata"""
        obs = []
        obs.append(f"Classification: {self.classification}")
        obs.append(f"Info Level: {self.information_classification}")
        obs.append(f"Confidence: {self.confidence:.2f}")
        obs.append(f"Sensors: {', '.join(self.source_sensors)}")
        if self.speed_kmh:
            obs.append(f"Speed: {self.speed_kmh} km/h")
        if self.heading:
            obs.append(f"Heading: {self.heading}°")
        return " | ".join(obs)
    
    
    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "radar_01_T001",
                "entity_type": "aircraft",
                "location": {"lat": 39.5, "lon": -0.4, "alt": 5000},
                "timestamp": "2025-10-15T14:30:00Z",
                "classification": "unknown",
                "information_classification": "SECRET",
                "confidence": 0.9,
                "source_sensors": ["radar_01"],
                "metadata": {
                    "track_id": "T001",
                    "altitude_m": 5000,
                    "speed_kmh": 450
                },
                "speed_kmh": 450,
                "heading": 270
            }
        }


class ThreatAssessment(BaseModel):
    """
    Threat evaluation for a specific entity or situation
    
    Generated by the threat evaluator agent to assess risks.
    """
    assessment_id: str = Field(..., description="Unique ID for this assessment")
    threat_level: Literal["critical", "high", "medium", "low", "none"] = Field(
        ...,
        description="Severity of the threat"
    )
    
    # What is threatened
    affected_entities: List[str] = Field(
        ...,
        description="List of entity IDs that are affected by this threat"
    )
    
    # What is threatening
    threat_source_id: Optional[str] = Field(
        None,
        description="Entity ID of the threat source (if applicable)"
    )
    
    # Assessment details
    reasoning: str = Field(..., description="Natural language explanation of the threat")
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in this assessment"
    )
    
    timestamp: datetime = Field(..., description="When this assessment was made")
    
    # Geospatial context
    distances_to_affected_km: Optional[Dict[str, float]] = Field(
        None,
        description="Distance from threat to each affected entity (entity_id -> km)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "assessment_id": "threat_001",
                "threat_level": "high",
                "affected_entities": ["radar_base_01", "command_post_alpha"],
                "threat_source_id": "aircraft_T001",
                "reasoning": "Unknown aircraft approaching restricted airspace at high speed",
                "confidence": 0.85,
                "timestamp": "2025-10-15T14:30:00Z",
                "distances_to_affected_km": {
                    "radar_base_01": 45.2,
                    "command_post_alpha": 52.8
                }
            }
        }


class COPSnapshot(BaseModel):
    """
    Snapshot of the entire Common Operational Picture at a point in time
    
    Used for checkpointing and audit trail.
    """
    snapshot_id: str = Field(..., description="Unique identifier for this snapshot")
    timestamp: datetime = Field(..., description="When this snapshot was taken")
    entities: Dict[str, EntityCOP] = Field(
        default_factory=dict,
        description="All entities in the COP (entity_id -> EntityCOP)"
    )
    threat_assessments: List[ThreatAssessment] = Field(
        default_factory=list,
        description="Active threat assessments"
    )
    metadata: Dict = Field(
        default_factory=dict,
        description="Additional snapshot metadata"
    )