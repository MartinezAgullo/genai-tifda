"""
Drone Parser
============

Parser for drone telemetry and image data.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from src.models import EntityCOP, Location, SensorMessage
from src.parsers.base_parser import BaseParser


class DroneParser(BaseParser):
    """
    Parser for drone sensor data.
    
    Handles drone telemetry, imagery, and visual intelligence.
    """
    
    def can_parse(self, sensor_msg: SensorMessage) -> bool:
        """Check if message is drone format"""
        if sensor_msg.sensor_type != "drone":
            return False
        
        data = sensor_msg.data
        
        # Drone data must have position
        return (
            isinstance(data, dict) and
            ("latitude" in data or "lat" in data) and
            ("longitude" in data or "lon" in data)
        )
    
    def validate(self, sensor_msg: SensorMessage) -> tuple[bool, str]:
        """Validate drone message structure"""
        data = sensor_msg.data
        
        # Check required fields
        if "latitude" not in data and "lat" not in data:
            return False, "Missing latitude"
        
        if "longitude" not in data and "lon" not in data:
            return False, "Missing longitude"
        
        # Validate drone_id if present
        if "drone_id" in data and not isinstance(data["drone_id"], str):
            return False, "drone_id must be a string"
        
        return True, ""
    
    def parse(self, sensor_msg: SensorMessage) -> List[EntityCOP]:
        """Parse drone data into EntityCOP objects"""
        data = sensor_msg.data
        entities = []
        
        # Get drone position
        lat = data.get("latitude") or data.get("lat")
        lon = data.get("longitude") or data.get("lon")
        alt_agl = data.get("altitude_m_agl")
        alt_msl = data.get("altitude_m_msl")
        
        # Use MSL if available, otherwise AGL
        altitude = alt_msl if alt_msl is not None else alt_agl
        
        location = Location(lat=lat, lon=lon, alt=altitude)
        
        # Drone entity (the drone itself)
        drone_id = data.get("drone_id", f"{sensor_msg.sensor_id}_platform")
        
        # Metadata
        metadata = {
            "drone_id": drone_id,
            "flight_mode": data.get("flight_mode"),
            "altitude_m_agl": alt_agl,
            "altitude_m_msl": alt_msl,
            "heading": data.get("heading"),
            "ground_speed_kmh": data.get("ground_speed_kmh"),
            "battery_percent": data.get("battery_percent"),
            "camera_heading": data.get("camera_heading"),
            "sensor_type": "drone"
        }
        
        # Check if there's an image
        has_image = bool(data.get("image_link") or data.get("image_path"))
        if has_image:
            metadata["image_link"] = data.get("image_link") or data.get("image_path")
        
        # Drone classification (always friendly - it's our drone)
        # Information classification: drone position is typically CONFIDENTIAL
        drone_entity = self._create_entity(
            entity_id=drone_id,
            entity_type="uav",
            location=location,
            timestamp=sensor_msg.timestamp,
            sensor_msg=sensor_msg,
            classification="friendly",  # Our drone
            information_classification="CONFIDENTIAL",  # Drone positions are sensitive
            confidence=0.95,  # High confidence in own drone telemetry
            metadata=metadata,
            speed_kmh=data.get("ground_speed_kmh"),
            heading=data.get("heading"),
            comments=f"UAV {drone_id} telemetry"
        )
        
        entities.append(drone_entity)
        
        # If drone has image with visual intelligence, that will be processed
        # by multimodal tools and create additional entities
        # (handled in multimodal_parser_node, not here)
        
        return entities