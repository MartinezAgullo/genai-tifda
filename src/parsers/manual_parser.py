"""
Manual Report Parser
====================

Parser for human-generated situation reports.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from src.models import EntityCOP, Location, SensorMessage
from src.parsers.base_parser import BaseParser


class ManualParser(BaseParser):
    """
    Parser for manual operator reports.
    
    Handles SITREP, SPOTREP, SALUTE, and other military report formats.
    """
    
    def can_parse(self, sensor_msg: SensorMessage) -> bool:
        """Check if message is manual report format"""
        if sensor_msg.sensor_type != "manual":
            return False
        
        data = sensor_msg.data
        
        # Manual reports must have operator_name and content
        return (
            isinstance(data, dict) and
            "operator_name" in data and
            "content" in data
        )
    
    def validate(self, sensor_msg: SensorMessage) -> tuple[bool, str]:
        """Validate manual report structure"""
        data = sensor_msg.data
        
        # Check required fields
        required = ["operator_name", "content", "priority"]
        missing = [field for field in required if field not in data]
        if missing:
            return False, f"Missing required fields: {missing}"
        
        # Validate priority
        valid_priorities = ["low", "medium", "high", "critical"]
        if data.get("priority") not in valid_priorities:
            return False, f"Invalid priority. Must be one of: {valid_priorities}"
        
        return True, ""
    
    def parse(self, sensor_msg: SensorMessage) -> List[EntityCOP]:
        """
        Parse manual report into EntityCOP.
        
        Creates an event entity representing the reported observation.
        LLM will later extract specific entities from the report content.
        """
        data = sensor_msg.data
        entities = []
        
        # Check if report has location
        if "latitude" in data and "longitude" in data:
            location = Location(
                lat=data["latitude"],
                lon=data["longitude"],
                alt=data.get("altitude_m")
            )
        else:
            # No specific location - create at origin or skip
            # For now, skip if no location
            return entities
        
        # Build entity ID
        report_id = data.get("report_id", f"{sensor_msg.sensor_id}_report")
        entity_id = f"{sensor_msg.sensor_id}_{report_id}"
        
        # Metadata
        metadata = {
            "report_id": report_id,
            "report_type": data.get("report_type", "OTHER"),
            "priority": data["priority"],
            "operator_name": data["operator_name"],
            "content": data["content"],
            "sensor_type": "manual"
        }
        
        # Determine classification based on priority and report type
        priority = data["priority"]
        if priority == "critical":
            info_classification = "SECRET"
        elif priority == "high":
            info_classification = "CONFIDENTIAL"
        else:
            info_classification = "RESTRICTED"
        
        # Allow override if specified
        info_classification = data.get("classification_level", info_classification)
        
        # Determine confidence based on operator and priority
        # High priority reports from known operators have higher confidence
        if priority in ["critical", "high"]:
            confidence = 0.85
        else:
            confidence = 0.7
        
        # Create event entity
        report_entity = self._create_entity(
            entity_id=entity_id,
            entity_type="event",
            location=location,
            timestamp=sensor_msg.timestamp,
            sensor_msg=sensor_msg,
            classification="unknown",  # Will be determined from content
            information_classification=info_classification,
            confidence=confidence,
            metadata=metadata,
            comments=f"{data.get('report_type', 'REPORT')} from {data['operator_name']}: {data['content'][:100]}"
        )
        
        entities.append(report_entity)
        
        return entities