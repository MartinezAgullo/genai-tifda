"""
ASTERIX Parser
==============

Parser for ASTERIX radar format (simplified JSON representation).
ASTERIX is the standard for radar data exchange in European airspace.
"""

from typing import List, Dict, Any
from datetime import datetime, timezone

from src.models import EntityCOP, Location, SensorMessage
from src.parsers.base_parser import BaseParser


class ASTERIXParser(BaseParser):
    """
    Parser for ASTERIX radar format.
    
    Handles radar track data in JSON format representing ASTERIX messages.
    """
    
    def can_parse(self, sensor_msg: SensorMessage) -> bool:
        """Check if message is ASTERIX format"""
        # Check sensor type
        if sensor_msg.sensor_type != "radar":
            return False
        
        # Check for ASTERIX format indicator
        data = sensor_msg.data
        return (
            isinstance(data, dict) and
            data.get("format") == "asterix" and
            "tracks" in data
        )
    
    def validate(self, sensor_msg: SensorMessage) -> tuple[bool, str]:
        """Validate ASTERIX message structure"""
        data = sensor_msg.data
        
        # Check required top-level fields
        if "tracks" not in data:
            return False, "Missing 'tracks' array"
        
        if not isinstance(data["tracks"], list):
            return False, "'tracks' must be an array"
        
        # Validate each track
        for i, track in enumerate(data["tracks"]):
            if not isinstance(track, dict):
                return False, f"Track {i} must be an object"
            
            # Required fields
            required = ["track_id", "location", "speed_kmh"]
            missing = [field for field in required if field not in track]
            if missing:
                return False, f"Track {i} missing required fields: {missing}"
            
            # Validate location
            location = track.get("location")
            if not isinstance(location, dict):
                return False, f"Track {i} location must be an object"
            
            if "lat" not in location or "lon" not in location:
                return False, f"Track {i} location must have 'lat' and 'lon'"
        
        return True, ""
    
    def parse(self, sensor_msg: SensorMessage) -> List[EntityCOP]:
        """Parse ASTERIX tracks into EntityCOP objects"""
        data = sensor_msg.data
        entities = []
        
        # Get system-level metadata
        system_id = data.get("system_id", sensor_msg.sensor_id)
        is_simulated = data.get("is_simulated", False)
        
        # Determine base classification for radar data
        # Radar data is typically SECRET or CONFIDENTIAL
        base_classification = data.get("classification_level", "SECRET")
        
        for track in data["tracks"]:
            # Build entity ID
            track_id = track["track_id"]
            entity_id = f"{sensor_msg.sensor_id}_{track_id}"
            
            # Parse location
            loc_data = track["location"]
            location = Location(
                lat=loc_data["lat"],
                lon=loc_data["lon"],
                alt=track.get("altitude_m")
            )
            
            # Determine entity type (radar detects air targets)
            entity_type = "aircraft"  # Default for radar
            if track.get("altitude_m", 0) < 100:
                entity_type = "ground_vehicle"  # Low altitude might be ground
            
            # Parse IFF classification
            iff_classification = track.get("classification", "unknown")
            if iff_classification not in ["friendly", "hostile", "neutral", "unknown"]:
                iff_classification = "unknown"
            
            # Build metadata
            metadata = {
                "track_id": track_id,
                "system_id": system_id,
                "is_simulated": is_simulated,
                "altitude_m": track.get("altitude_m"),
                "speed_kmh": track["speed_kmh"],
                "heading": track.get("heading"),
                "sensor_type": "radar"
            }
            
            # Add quality data if available
            if "quality" in track:
                quality = track["quality"]
                metadata["quality"] = {
                    "accuracy_m": quality.get("accuracy_m"),
                    "plot_count": quality.get("plot_count"),
                    "ssr_code": quality.get("ssr_code")
                }
                
                # Higher plot count = higher confidence
                plot_count = quality.get("plot_count", 1)
                confidence = min(0.5 + (plot_count * 0.1), 0.95)
            else:
                confidence = 0.8  # Default radar confidence
            
            # Determine information classification
            # If SSR code present (transponder), might be friendlier data
            if metadata.get("quality", {}).get("ssr_code"):
                info_classification = "CONFIDENTIAL"
            else:
                info_classification = base_classification
            
            # Create entity
            entity = self._create_entity(
                entity_id=entity_id,
                entity_type=entity_type,
                location=location,
                timestamp=sensor_msg.timestamp,
                sensor_msg=sensor_msg,
                classification=iff_classification,
                information_classification=info_classification,
                confidence=confidence,
                metadata=metadata,
                speed_kmh=track["speed_kmh"],
                heading=track.get("heading"),
                comments=f"Radar track {track_id} from {system_id}"
            )
            
            entities.append(entity)
        
        return entities