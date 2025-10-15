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
    Data can be inline JSON or contain references to external files.
    """
    sensor_id: str = Field(..., description="Unique sensor identifier")
    sensor_type: Literal["radar", "drone", "radio", "manual", "other"] = Field(
        ...,
        description="Type of sensor"
    )
    timestamp: datetime = Field(..., description="When this data was captured")
    
    # Flexible data structure
    data: Dict[str, Any] = Field(
        ...,
        description="Sensor data (can be inline JSON or contain file references)"
    )
    
    # Helper methods
    def has_file_references(self) -> bool:
        """
        Check if data contains file paths/links that need processing
        
        Returns:
            True if any file reference keys are present in data
        """
        file_keys = [
            "file_path",
            "audio_path", 
            "image_path",
            "image_link",
            "document_path",
            "video_path"
        ]
        return any(key in self.data for key in file_keys)
    
    def get_file_references(self) -> Dict[str, str]:
        """
        Extract all file references from data
        
        Returns:
            Dictionary of {file_type: file_path}
        """
        file_keys = {
            "audio_path": "audio",
            "image_path": "image",
            "image_link": "image",
            "document_path": "document",
            "video_path": "video",
            "file_path": "unknown"
        }
        
        references = {}
        for key, file_type in file_keys.items():
            if key in self.data:
                references[file_type] = self.data[key]
        
        return references
    
    class Config:
        json_schema_extra = {
            "examples": [
                # Example 1: Radar with inline data (no files)
                {
                    "sensor_id": "radar_01",
                    "sensor_type": "radar",
                    "timestamp": "2025-10-15T14:30:00Z",
                    "data": {
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
                                "classification": "unknown",
                                "quality": {
                                    "accuracy_m": 50,
                                    "plot_count": 5,
                                    "ssr_code": "7700"
                                }
                            }
                        ]
                    }
                },
                # Example 2: Drone with file reference (image)
                {
                    "sensor_id": "drone_alpha",
                    "sensor_type": "drone",
                    "timestamp": "2025-10-15T14:31:00Z",
                    "data": {
                        "drone_id": "DRONE_ALPHA_01",
                        "flight_mode": "auto",
                        "latitude": 39.4762,
                        "longitude": -0.3747,
                        "altitude_m_agl": 120,
                        "altitude_m_msl": 145,
                        "heading": 90,
                        "ground_speed_kmh": 45,
                        "battery_percent": 78,
                        "camera_heading": 90,
                        "image_link": "data/sensor_data/drone_alpha/IMG_20251015_143100.jpg"
                    }
                },
                # Example 3: Radio with audio file reference
                {
                    "sensor_id": "radio_bravo",
                    "sensor_type": "radio",
                    "timestamp": "2025-10-15T14:32:00Z",
                    "data": {
                        "station_id": "INTERCEPT_BRAVO_01",
                        "frequency_mhz": 145.500,
                        "bandwidth_khz": 12.5,
                        "modulation_type": "FM",
                        "channel": "tactical_01",
                        "duration_sec": 45,
                        "signal_strength": -72,
                        "audio_path": "data/sensor_data/radio_bravo/transmission_143200.mp3"
                    }
                },
                # Example 4: Manual report with inline text
                {
                    "sensor_id": "operator_charlie",
                    "sensor_type": "manual",
                    "timestamp": "2025-10-15T14:33:00Z",
                    "data": {
                        "report_id": "SPOTREP_001",
                        "report_type": "SPOTREP",
                        "priority": "high",
                        "operator_name": "Cpt. Smith",
                        "content": "Visual confirmation: Single military aircraft, no IFF response",
                        "latitude": 39.50,
                        "longitude": -0.35,
                        "altitude_m": None
                    }
                },
                # Example 5: Other sensor type with mixed data
                {
                    "sensor_id": "acoustic_sensor_01",
                    "sensor_type": "other",
                    "timestamp": "2025-10-15T14:34:00Z",
                    "data": {
                        "detection_type": "acoustic",
                        "bearing": 135,
                        "estimated_range_m": 2500,
                        "confidence": 0.75,
                        "audio_path": "data/sensor_data/acoustic/detection_143400.wav"
                    }
                }
            ]
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


class TrackQuality(BaseModel):
    """Quality metrics for radar tracks"""
    accuracy_m: Optional[float] = Field(None, description="Estimated position accuracy in meters")
    plot_count: Optional[int] = Field(None, description="Number of plots used to generate this track")
    ssr_code: Optional[str] = Field(None, description="SSR transponder code (if available)")

class ASTERIXTrack(BaseModel):
    """Single radar track in ASTERIX format"""
    track_id: str = Field(..., description="Track identifier")
    location: Dict[str, float] = Field(..., description="Lat/lon coordinates")
    altitude_m: Optional[float] = Field(None, description="Altitude in meters (optional)")
    speed_kmh: float = Field(..., description="Speed in km/h")
    heading: Optional[float] = Field(None, description="Heading in degrees")
    classification: Optional[str] = Field(None, description="Target classification")
    quality: Optional["TrackQuality"] = Field(None, description="Track quality metrics")

class ASTERIXMessage(BaseModel):
    """ASTERIX radar message format (simplified JSON representation)"""
    format: Literal["asterix"] = "asterix"

    system_id: str = Field(..., description="Radar system identifier (e.g., 'ES_RAD_101')")
    timestamp: datetime = Field(..., description="Message generation timestamp")
    is_simulated: bool = Field(False, description="Whether this is simulated data")
    
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
    
    # 1. Identification and System Status
    drone_id: str = Field(..., description="Unique identifier for the drone unit")
    timestamp: datetime = Field(..., description="Timestamp of telemetry reading")
    flight_mode: Literal["manual", "auto", "loiter", "rtl", "mission"] = Field(
        ...,
        description="Current flight mode"
    )
    
    # 2. Position and Navigation
    latitude: float = Field(..., ge=-90, le=90, description="Latitude (degrees)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude (degrees)")
    altitude_m_agl: float = Field(..., description="Altitude Above Ground Level (meters)")
    altitude_m_msl: Optional[float] = Field(None, description="Altitude Above Mean Sea Level (meters)")
    
    heading: Optional[float] = Field(None, ge=0, le=360, description="Heading in degrees")
    ground_speed_kmh: Optional[float] = Field(None, description="Ground speed in km/h")
    
    # 3. Battery and System Health
    battery_percent: Optional[float] = Field(None, ge=0, le=100, description="Battery level")
    
    # 4. Payload (Camera)
    camera_heading: Optional[float] = Field(None, description="Camera gimbal heading")
    image_link: Optional[str] = Field(None, description="Path/URL to captured image")
    
    class Config:
        json_schema_extra = {
            "example": {
                "drone_id": "DRONE_ALPHA_01",
                "timestamp": "2025-10-15T14:30:00Z",
                "flight_mode": "auto",
                "latitude": 39.4762,
                "longitude": -0.3747,
                "altitude_m_agl": 120,
                "altitude_m_msl": 145,
                "heading": 90,
                "ground_speed_kmh": 45,
                "battery_percent": 78,
                "camera_heading": 90,
                "image_link": "data/sensor_data/drone_alpha/IMG_20251015_143000.jpg"
            }
        }


class RadioData(BaseModel):
    """Radio communication interception metadata"""
    
    # Station and timing
    station_id: str = Field(..., description="Unique ID of the intercept station")
    timestamp: datetime = Field(..., description="Start of transmission timestamp")
    
    # Signal characteristics
    frequency_mhz: float = Field(..., description="Carrier frequency (MHz)")
    bandwidth_khz: float = Field(..., description="Signal bandwidth (kHz)")
    modulation_type: Literal["AM", "FM", "SSB", "FSK", "DMR", "other"] = Field(
        ...,
        description="Detected modulation type"
    )
    
    # Original fields
    channel: str = Field(..., description="Radio channel identifier")
    duration_sec: float = Field(..., description="Transmission duration in seconds")
    signal_strength: Optional[float] = Field(None, description="Signal strength in dBm")
    
    # Audio file reference
    audio_path: Optional[str] = Field(None, description="Path to recorded audio file")
    
    class Config:
        json_schema_extra = {
            "example": {
                "station_id": "INTERCEPT_BRAVO_01",
                "timestamp": "2025-10-15T14:32:00Z",
                "frequency_mhz": 145.500,
                "bandwidth_khz": 12.5,
                "modulation_type": "FM",
                "channel": "tactical_01",
                "duration_sec": 45,
                "signal_strength": -72,
                "audio_path": "data/sensor_data/radio_bravo/transmission_143200.mp3"
            }
        }


class ManualReport(BaseModel):
    """Human-generated situation report"""
    
    # Identification
    report_id: Optional[str] = Field(None, description="Unique report identifier")
    timestamp: datetime = Field(..., description="When report was created (MANDATORY)")
    
    # Report classification
    report_type: Literal["SITREP", "SPOTREP", "SALUTE", "LOGREP", "MEDEVAC", "OTHER"] = Field(
        "OTHER",
        description="Military report type"
    )
    priority: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Report priority"
    )
    
    # Content
    operator_name: str = Field(..., description="Name or ID of reporting operator")
    content: str = Field(..., description="Report text content")
    
    # Geographic information (optional but explicit)
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude of event")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude of event")
    altitude_m: Optional[float] = Field(None, description="Altitude of event in meters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_id": "SPOTREP_001",
                "timestamp": "2025-10-15T14:33:00Z",
                "report_type": "SPOTREP",
                "priority": "high",
                "operator_name": "Cpt. Smith",
                "content": "Visual confirmation: Single military aircraft, no IFF response, continuing westward",
                "latitude": 39.50,
                "longitude": -0.35,
                "altitude_m": None
            }
        }