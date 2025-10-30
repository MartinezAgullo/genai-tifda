# MQTT Broker

Local Mosquitto MQTT broker for TIFDA message dissemination.

## Components

- **Broker** (mosquitto): Message router that receives and distributes messages between publishers and subscribers
- **Publisher** (TIFDA `transmission_node`): Publishes dissemination reports and threat assessments to topics
- **Subscriber** (mosquitto_sub / downstream systems): Listens to topics and receives messages published by TIFDA

## Structure

```
mqtt/
├── config/
│   └── mosquitto.conf    # Broker configuration (port 1883, no auth)
├── data/                 # Message persistence (auto-created)
└── log/                  # Broker logs (auto-created)
```

## Usage

### 1. Start Broker (Terminal 1)

```bash
cd mqtt
mosquitto -c config/mosquitto.conf
```

The broker is now running and waiting for messages.

### 2. Subscribe to Messages (Terminal 2)

```bash
# All dissemination reports
mosquitto_sub -t 'tifda/output/dissemination_reports/#' -v

# Threat assessments
mosquitto_sub -t 'tifda/output/threat_assessments' -v

# Everything
mosquitto_sub -t 'tifda/output/#' -v
```

### 3. Run TIFDA Pipeline (Terminal 3)

When TIFDA runs, `transmission_node` publishes messages to the broker.

As a test, on a new terminal you can do:
```bash
mosquitto_pub -t 'tifda/output/dissemination_reports/test' -m 'Hello TIFDA!'
```

**Terminal 2** will show the messages TIFDA published in real-time.

## Flow

```
TIFDA transmission_node → mosquitto broker → mosquitto_sub (or downstream systems)
    (Publisher)              (Router)           (Subscriber)
```

**Keep**:
- Terminal 1: Broker running
- Terminal 2: Subscriber listening
- Terminal 3: Run TIFDA → messages appear in Terminal 2