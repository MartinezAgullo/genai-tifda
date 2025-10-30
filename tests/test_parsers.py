"""
Parser Tests
============

Unit tests for all parsers.
"""

import pytest
from datetime import datetime

from src.models import SensorMessage, Location
from src.parsers import (
    ASTERIXParser,
    DroneParser,
    RadioParser,
    ManualParser,
    get_parser_factory
)


# ==================== ASTERIX PARSER TESTS ====================

def test_asterix_parser_can_parse():
    """Test ASTERIX parser recognition"""
    parser = ASTERIXParser()
    
    # Valid ASTERIX message
    valid_msg = SensorMessage(
        sensor_id="radar_01",
        sensor_type="radar",
        timestamp=datetime.utcnow(),
        data={
            "format": "asterix",
            "tracks": []
        }
    )
    assert parser.can_parse(valid_msg) is True
    
    # Invalid - wrong sensor type
    invalid_msg = SensorMessage(
        sensor_id="drone_01",
        sensor_type="drone",
        timestamp=datetime.utcnow(),
        data={"format": "asterix", "tracks": []}
    )
    assert parser.can_parse(invalid_msg) is False


def test_asterix_parser_validate():
    """Test ASTERIX message validation"""
    parser = ASTERIXParser()
    
    # Valid message
    valid_msg = SensorMessage(
        sensor_id="radar_01",
        sensor_type="radar",
        timestamp=datetime.utcnow(),
        data={
            "format": "asterix",
            "tracks": [
                {
                    "track_id": "T001",
                    "location": {"lat": 39.5, "lon": -0.4},
                    "speed_kmh": 450
                }
            ]
        }
    )
    is_valid, error = parser.validate(valid_msg)
    assert is_valid is True
    assert error == ""
    
    # Missing tracks
    invalid_msg = SensorMessage(
        sensor_id="radar_01",
        sensor_type="radar",
        timestamp=datetime.utcnow(),
        data={"format": "asterix"}
    )
    is_valid, error = parser.validate(invalid_msg)
    assert is_valid is False
    assert "tracks" in error


def test_asterix_parser_parse():
    """Test ASTERIX parsing"""
    parser = ASTERIXParser()
    
    msg = SensorMessage(
        sensor_id="radar_01",
        sensor_type="radar",
        timestamp=datetime.utcnow(),
        data={
            "format": "asterix",
            "system_id": "ES_RAD_101",
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
    )
    
    entities = parser.parse(msg)
    
    assert len(entities) == 1
    entity = entities[0]
    
    assert entity.entity_id == "radar_01_T001"
    assert entity.entity_type == "aircraft"
    assert entity.classification == "unknown"
    assert entity.information_classification == "SECRET"
    assert entity.location.lat == 39.5
    assert entity.location.lon == -0.4
    assert entity.speed_kmh == 450


# ==================== DRONE PARSER TESTS ====================

def test_drone_parser_can_parse():
    """Test drone parser recognition"""
    parser = DroneParser()
    
    # Valid drone message
    valid_msg = SensorMessage(
        sensor_id="drone_alpha",
        sensor_type="drone",
        timestamp=datetime.utcnow(),
        data={
            "latitude": 39.4762,
            "longitude": -0.3747
        }
    )
    assert parser.can_parse(valid_msg) is True
    
    # Missing coordinates
    invalid_msg = SensorMessage(
        sensor_id="drone_alpha",
        sensor_type="drone",
        timestamp=datetime.utcnow(),
        data={"drone_id": "DRONE_01"}
    )
    assert parser.can_parse(invalid_msg) is False


def test_drone_parser_parse():
    """Test drone parsing"""
    parser = DroneParser()
    
    msg = SensorMessage(
        sensor_id="drone_alpha",
        sensor_type="drone",
        timestamp=datetime.utcnow(),
        data={
            "drone_id": "DRONE_ALPHA_01",
            "latitude": 39.4762,
            "longitude": -0.3747,
            "altitude_m_agl": 120,
            "ground_speed_kmh": 45,
            "heading": 90,
            "battery_percent": 78
        }
    )
    
    entities = parser.parse(msg)
    
    assert len(entities) == 1
    entity = entities[0]
    
    assert entity.entity_type == "uav"
    assert entity.classification == "friendly"
    assert entity.information_classification == "CONFIDENTIAL"
    assert entity.location.lat == 39.4762
    assert entity.speed_kmh == 45


# ==================== RADIO PARSER TESTS ====================

def test_radio_parser_can_parse():
    """Test radio parser recognition"""
    parser = RadioParser()
    
    # Valid radio message
    valid_msg = SensorMessage(
        sensor_id="radio_bravo",
        sensor_type="radio",
        timestamp=datetime.utcnow(),
        data={
            "station_id": "INTERCEPT_01",
            "frequency_mhz": 145.500,
            "channel": "tactical_01"
        }
    )
    assert parser.can_parse(valid_msg) is True


def test_radio_parser_parse_with_location():
    """Test radio parsing with location"""
    parser = RadioParser()
    
    msg = SensorMessage(
        sensor_id="radio_bravo",
        sensor_type="radio",
        timestamp=datetime.utcnow(),
        data={
            "station_id": "INTERCEPT_BRAVO_01",
            "frequency_mhz": 145.500,
            "channel": "tactical_01",
            "duration_sec": 45,
            "location": {"lat": 39.5, "lon": -0.4}
        }
    )
    
    entities = parser.parse(msg)
    
    assert len(entities) == 1
    entity = entities[0]
    
    assert entity.entity_type == "event"
    assert entity.information_classification == "SECRET"


# ==================== MANUAL PARSER TESTS ====================

def test_manual_parser_can_parse():
    """Test manual parser recognition"""
    parser = ManualParser()
    
    # Valid manual message
    valid_msg = SensorMessage(
        sensor_id="operator_charlie",
        sensor_type="manual",
        timestamp=datetime.utcnow(),
        data={
            "operator_name": "Cpt. Smith",
            "content": "Aircraft spotted",
            "priority": "high"
        }
    )
    assert parser.can_parse(valid_msg) is True


def test_manual_parser_parse():
    """Test manual report parsing"""
    parser = ManualParser()
    
    msg = SensorMessage(
        sensor_id="operator_charlie",
        sensor_type="manual",
        timestamp=datetime.utcnow(),
        data={
            "report_id": "SPOTREP_001",
            "report_type": "SPOTREP",
            "priority": "high",
            "operator_name": "Cpt. Smith",
            "content": "Visual confirmation: Single military aircraft",
            "latitude": 39.50,
            "longitude": -0.35
        }
    )
    
    entities = parser.parse(msg)
    
    assert len(entities) == 1
    entity = entities[0]
    
    assert entity.entity_type == "event"
    assert entity.information_classification == "CONFIDENTIAL"
    assert entity.metadata["priority"] == "high"


# ==================== PARSER FACTORY TESTS ====================

def test_parser_factory_get_parser():
    """Test parser factory selection"""
    factory = get_parser_factory()
    
    # ASTERIX message
    asterix_msg = SensorMessage(
        sensor_id="radar_01",
        sensor_type="radar",
        timestamp=datetime.utcnow(),
        data={"format": "asterix", "tracks": []}
    )
    parser = factory.get_parser(asterix_msg)
    assert isinstance(parser, ASTERIXParser)
    
    # Drone message
    drone_msg = SensorMessage(
        sensor_id="drone_01",
        sensor_type="drone",
        timestamp=datetime.utcnow(),
        data={"latitude": 39.5, "longitude": -0.4}
    )
    parser = factory.get_parser(drone_msg)
    assert isinstance(parser, DroneParser)


def test_parser_factory_parse():
    """Test full parsing through factory"""
    factory = get_parser_factory()
    
    msg = SensorMessage(
        sensor_id="radar_01",
        sensor_type="radar",
        timestamp=datetime.utcnow(),
        data={
            "format": "asterix",
            "tracks": [
                {
                    "track_id": "T001",
                    "location": {"lat": 39.5, "lon": -0.4},
                    "speed_kmh": 450
                }
            ]
        }
    )
    
    success, error, entities = factory.parse(msg)
    
    assert success is True
    assert error == ""
    assert len(entities) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])