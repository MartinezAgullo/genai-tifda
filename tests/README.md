# Test Suite

## Overview

This directory contains the TIFDA test suite, organized by functionality and dependencies. 
Tests are recommended to be executed in the specified order.

## Test Execution

### 1. Unit Tests (No External Dependencies)

**test_parsers.py**
- Validates all sensor data parsers (ASTERIX, Drone, Radio, Manual)
- Tests message validation, format detection, and entity extraction
- Execution: `uv run python -m tests.test_parsers`

### 2. Integration Tests (Require External Services)

#### Mapa Integration (requires mapa-puntos-interes service)

**test_radar.py**
- End-to-end pipeline test with simulated radar data
- Verifies complete TIFDA workflow from ingestion to dissemination
- Execution: `uv run python -m tests.test_radar`


**test_mapa_sync.py**
- Manual integration test for COP synchronization
- Tests entity creation, updates, batch operations, and removal
- Includes cleanup utilities for test data
- Execution: `uv run python -m tests.test_mapa_sync`

**test_integrations.py**
- Unit tests for mapa client operations
- Tests HTTP operations, upsert logic, and entity format conversion
- Execution: `uv run python -m tests.test_integrations`

#### MQTT Integration (requires MQTT broker)

**test_mqtt_flux.py**
- Tests transmission node with real MQTT publishing
- Validates message dissemination and delivery statistics
- Execution: `uv run python -m tests.test_mqtt_flux`

**test_mqtt_integration.py**
- Comprehensive MQTT integration test suite
- Tests client connection, publishing, subscription, and transmission node integration
- Interactive test runner with guided execution
- Execution: `uv run python -m tests.test_mqtt_integration`

## Prerequisites

### For Mapa Tests
```bash
# Terminal 1: Start mapa-puntos-interes
cd /path/to/mapa-puntos-interes
npm run dev
```

### For MQTT Tests
```bash
# Terminal 1: Start MQTT broker
mosquitto -c mqtt/config/mosquitto.conf
```

## Complete Test Sequence

```bash
# 1. Unit tests (no dependencies)
uv run python -m tests.test_parsers
uv run python -m tests.test_radar

# 2. Mapa integration (requires mapa-puntos-interes running)
uv run python -m tests.test_mapa_sync
uv run python -m tests.test_integrations

# 3. MQTT integration (requires mosquitto running)
uv run python -m tests.test_mqtt_flux
uv run python -m tests.test_mqtt_integration
```

## Notes

- Unit tests can run independently without external services
- Integration tests require their respective services to be running
- test_mapa_sync.py includes automated cleanup of test data
- test_mqtt_integration.py provides an interactive test runner with detailed diagnostics


<!-- Run it using the Python module execution flag, replacing the path separators with dots:

```bash
cd /Users/pablo/Desktop/Scripts/tifda
uv run python -m tests.test_radar
``````
Explanation: When you use python -m tests.test_radar, the project root (tifda) is added to the system path, allowing imports like from src.tifda_app import tifda_app to resolve correctly. -->