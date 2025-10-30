# MQTT Broker

Local Mosquitto MQTT broker for TIFDA message dissemination.

## Structure

```
mqtt/
├── config/
│   └── mosquitto.conf    # Broker configuration (port 1883, no auth)
├── data/                 # Message persistence (auto-created)
└── log/                  # Broker logs (auto-created)
```

## Usage

```bash
cd mqtt
mosquitto -c config/mosquitto.conf
```
Now the broker is running and waitng for mesages.
When the TIFDA pipeline is run, it will publish to the broker. 

## Subscribe to Messages

```bash
# All dissemination reports
mosquitto_sub -t 'tifda/output/dissemination_reports/#' -v

# Threat assessments
mosquitto_sub -t 'tifda/output/threat_assessments' -v
```