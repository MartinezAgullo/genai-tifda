"""
Radio Parser
============

Parser for radio intercept and communications intelligence.
"""

from typing import List, Dict, Any
from datetime import datetime, timezone

from src.models import EntityCOP, Location, SensorMessage
from src.parsers.base_parser import BaseParser


class RadioParser(BaseParser):
    """
    Parser for radio intercept data.
    
    Handles radio communications metadata and COMINT (communications intelligence).
    Does not create entities directly - audio transcription is handled by multimodal tools.
    This parser creates metadata entities for the intercept event itself.
    """
    
    def can_parse(self, sensor_msg: SensorMessage) -> bool:
        """Check if message is radio format"""
        if sensor_msg.sensor_type != "radio":
            return False
        
        data = sensor_msg.data
        
        # Radio data must have station_id and frequency
        return (
            isinstance(data, dict) and
            "station_id" in data and
            "frequency_mhz" in data
        )
    
    def validate(self, sensor_msg: SensorMessage) -> tuple[bool, str]:
        """Validate radio message structure"""
        data = sensor_msg.data
        
        # Check required fields
        required = ["station_id", "frequency_mhz", "channel"]
        missing = [field for field in required if field not in data]
        if missing:
            return False, f"Missing required fields: {missing}"
        
        return True, ""
    
    def parse(self, sensor_msg: SensorMessage) -> List[EntityCOP]:
        """
        Parse radio intercept data.
        
        Creates an "event" entity representing the intercept.
        Actual transcription and entity extraction from audio is handled by multimodal tools.
        """
        data = sensor_msg.data
        entities = []
        
        # Radio intercept station location (if available)
        # If not provided, we can't create a geographic entity
        if "location" in data:
            loc_data = data["location"]
            location = Location(
                lat=loc_data.get("lat", 0),
                lon=loc_data.get("lon", 0),
                alt=loc_data.get("alt")
            )
        else:
            # No location - skip entity creation
            # Audio transcription will still happen in multimodal_parser_node
            return entities
        
        # Create event entity for the intercept
        station_id = data["station_id"]
        entity_id = f"{sensor_msg.sensor_id}_{station_id}_intercept"
        
        # Metadata
        metadata = {
            "station_id": station_id,
            "frequency_mhz": data["frequency_mhz"],
            "bandwidth_khz": data.get("bandwidth_khz"),
            "modulation_type": data.get("modulation_type"),
            "channel": data["channel"],
            "duration_sec": data.get("duration_sec"),
            "signal_strength": data.get("signal_strength"),
            "audio_path": data.get("audio_path"),
            "sensor_type": "radio"
        }
        
        # Radio intercepts are typically SECRET or higher
        # Especially if intercepting adversary communications
        info_classification = data.get("classification_level", "SECRET")
        
        # Create event entity
        intercept_entity = self._create_entity(
            entity_id=entity_id,
            entity_type="event",  # This is an intercept event
            location=location,
            timestamp=sensor_msg.timestamp,
            sensor_msg=sensor_msg,
            classification="unknown",  # We don't know who transmitted
            information_classification=info_classification,
            confidence=0.7,  # Moderate confidence until transcription confirms
            metadata=metadata,
            comments=f"Radio intercept on {data['frequency_mhz']} MHz"
        )
        
        entities.append(intercept_entity)
        
        return entities