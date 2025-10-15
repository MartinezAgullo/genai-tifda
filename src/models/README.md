<!-- src/models/README.md -->
# TIFDA Data Models

Pydantic models defining all data structures in the TIFDA system.

## Files

### `cop_entities.py`
Core Common Operational Picture (COP) data structures:
- **`Location`** - Geographic coordinates (lat/lon/alt)
- **`EntityCOP`** - Tracked battlefield entities (aircraft, vehicles, infrastructure)
- **`ThreatAssessment`** - Risk evaluation for entities
- **`COPSnapshot`** - Full COP state snapshot for checkpointing

### `sensor_formats.py`
Input data structures from sensors:
- **`SensorMessage`** - Base MQTT message wrapper (all sensors)
- **`ASTERIXMessage`** - Radar track data (ASTERIX format)
- **`DroneData`** - Drone telemetry and imagery
- **`RadioData`** - Radio intercept metadata
- **`ManualReport`** - Human operator reports

### `dissemination.py`
Output and distribution models:
- **`DisseminationDecision`** - Who receives what information (need-to-know)
- **`OutgoingMessage`** - Formatted messages for downstream systems
- **`RecipientConfig`** - Downstream system configuration

### `human_feedback.py`
Human-in-the-loop (HITL) models:
- **`HumanFeedback`** - Human corrections for model-based learning
- **`ReviewDecision`** - Approval/rejection decisions

<!-- ## Usage
```python
from src.models import EntityCOP, SensorMessage, ThreatAssessment

# Create a COP entity
entity = EntityCOP(
    entity_id="radar_01_T001",
    entity_type="aircraft",
    location=Location(lat=39.5, lon=-0.4, alt=5000),
    timestamp=datetime.now(),
    classification="unknown",
    confidence=0.9,
    source_sensors=["radar_01"]
)

# Parse sensor message
sensor_msg = SensorMessage(**mqtt_data)
if sensor_msg.has_file_references():
    files = sensor_msg.get_file_references()
```

## Key Concepts

- **COP (Common Operational Picture)**: Unified tactical view of all entities
- **Entity**: Any tracked object (aircraft, vehicle, infrastructure, person)
- **Classification**: IFF status (friendly, hostile, neutral, unknown)
- **Dissemination**: Controlled information sharing based on need-to-know
- **HITL (Human-in-the-Loop)**: Human review and feedback for AI decisions -->