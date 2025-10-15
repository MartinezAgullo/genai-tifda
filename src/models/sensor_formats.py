# Input formats (ASTERIX, etc.)
"""
Sensor Input Format Models
===========================

Data structures for different sensor input formats.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class SensorMessage(BaseModel):
    """
    Base structure for all MQTT sensor messages
    
    All sensors publish messages in this format.
    """
    sensor_id: str = Field(..., description="Unique sensor identifier")
    sensor_type: Literal["radar", "drone", "radio", "manual"] = Field(
        ...,
        description="Type of sensor"
    )
    timestamp: datetime = Field(..., description="When this data was captured")
    message_type: Literal["inline_data", "file_reference"] = Field(
        ...,
        description="Whether data is inline or references a file"
    )
    
    # One of these will be populated
    inline_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Inline JSON data for small messages"
    )
    file_reference: Optional["FileReference"] = Field(
        None,
        description="Reference to external file for large data"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "sensor_id": "radar_01",
                "sensor_type": "radar",
                "timestamp": "2025-10-15T14:30:00Z",
                "message_type": "inline_data",
                "inline_data": {
                    "format": "asterix",
                    "tracks": [{"track_id": "T001", "location": {"lat": 39.5, "lon": -0.4}}]
                },
                "file_reference": None
            }
        }


class FileReference(BaseModel):
    """Reference to an external file for processing"""
    file_type: Literal["audio", "image", "document", "video"] = Field(
        ...,
        description="Type of file"
    )
    file_path: str = Field(..., description="Path to file (absolute or relative)")
    file_size_mb: float = Field(..., description="File size in megabytes")
    mime_type: str = Field(..., description="MIME type of the file")
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_type": "audio",
                "file_path": "data/sensor_data/radio_bravo/transmission_143200.mp3",
                "file_size_mb": 1.1,
                "mime_type": "audio/mpeg"
            }
        }


class ASTERIXTrack(BaseModel):
    """Single radar track in ASTERIX format"""
    track_id: str = Field(..., description="Track identifier")
    location: Dict[str, float] = Field(..., description="Lat/lon coordinates")
    altitude_m: float = Field(..., description="Altitude in meters")
    speed_kmh: float = Field(..., description="Speed in km/h")
    heading: Optional[float] = Field(None, description="Heading in degrees")
    classification: Optional[str] = Field(None, description="Target classification")


class ASTERIXMessage(BaseModel):
    """ASTERIX radar message format (simplified JSON representation)"""
    format: Literal["asterix"] = "asterix"
    tracks: list[ASTERIXTrack] = Field(default_factory=list, description="List of tracks")
    
    class Config:
        json_schema_extra = {
            "example": {
                "format": "asterix",
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
        }


class DroneData(BaseModel):
    """Drone telemetry and image data"""
    location: Dict[str, float] = Field(..., description="Drone location")
    altitude_m: float = Field(..., description="Altitude")
    camera_heading: Optional[float] = Field(None, description="Camera heading")
    image_path: Optional[str] = Field(None, description="Path to captured image")
    
    class Config:
        json_schema_extra = {
            "example": {
                "location": {"lat": 39.4762, "lon": -0.3747},
                "altitude_m": 120,
                "camera_heading": 90,
                "image_path": "data/sensor_data/drone_alpha/IMG_20251015.jpg"
            }
        }


class RadioData(BaseModel):
    """Radio communication metadata"""
    channel: str = Field(..., description="Radio channel")
    duration_sec: float = Field(..., description="Transmission duration")
    signal_strength: Optional[float] = Field(None, description="Signal strength in dBm")
    audio_path: Optional[str] = Field(None, description="Path to audio file")
    
    class Config:
        json_schema_extra = {
            "example": {
                "channel": "tactical_01",
                "duration_sec": 45,
                "signal_strength": -72,
                "audio_path": "data/sensor_data/radio_bravo/transmission.mp3"
            }
        }


class ManualReport(BaseModel):
    """Human-generated situation report"""
    operator_name: str = Field(..., description="Name or ID of operator")
    report_type: str = Field(..., description="Type of report (sitrep, spot_report, etc.)")
    priority: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Report priority"
    )
    content: str = Field(..., description="Report text content")
    location: Optional[Dict[str, float]] = Field(None, description="Location if applicable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "operator_name": "Cpt. Smith",
                "report_type": "spot_report",
                "priority": "high",
                "content": "Visual confirmation: Single military aircraft, no IFF response",
                "location": {"lat": 39.50, "lon": -0.35}
            }
        }