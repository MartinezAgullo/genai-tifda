#  GenAI-Enabled Tactical Information Fusion and Dissemination Agent (TIFDA)

The TIFDA (Tactical Information Fusion and Dissemination Agent) project aims to create a GenAI agent-based tool that functions as a processing and distribution center for tactical information in a combat environment.

Its main functions are:

1. Ingest multimodal data from diverse sources.

2. Convert this data into a valid format to be used as Common Operational Picture (COP) by the Battle Management System (BMS).

3. Selectively distribute only the essential information to the relevant output actors, utilizing their specific formats.

* * * * *

## ⚙️ Technical Details
----------------------
| Feature | Description |
| --- | --- |
| **Architecture** | Multi-Agent System |
| **Agent Framework** | LangGraph |
| **Inputs/Outputs** | Inputs are simulated and transmitted via an MQTT broker, mixing different signal types to create realistic, complex scenarios. Outputs are tailored to specific recipient formats. |
| **Dependencies** | Managed using UV. |
| **Visualization** | Future development (to do) includes a COP Visualization Module (using Folium) to display the COP with NATO Joint Military Symbology (APP-6E) |

* * * * *

## 📂 Project Scaffolding
----------------------
```
.
├── README.md
├── data
├── mqtt                    # MQTT scenarios and sensor simulators
│   ├── scenarios
│   └── sensor_simulators
├── output                  # Generated reports and assessments
│   ├── dissemination_reports
│   └── threat_assessments
├── pyproject.toml
├── uv.lock
└── src                     # Main source code directory
    ├── agents              # GenAI agents (Threat Evaluator, Orchestrator)
    ├── core                # Core logic, middleware, and message queue mgmt
    ├── models              # Pydantic data models (COP, Sensor formats, Dissemination)
    │   ├── cop_entities.py
    │   ├── dissemination.py
    │   ├── human_feedback.py
    │   └── sensor_formats.py
    ├── nodes               # LangGraph state nodes and functions
    ├── parsers             # Logic for normalizing raw sensor inputs to COP
    ├── security            # Security and policy enforcement logic
    ├── tools               # Helper utilities for agents
    ├── ui                  # User interface elements (Gradio)
    └── visualization       # COP map rendering (Folium, APP-6E)
```

<!-- 
tree -I "__pycache__|__init__.py|uv.lock|README.md|tests|*.log|*.db*|*.png|*.PNG" 
-->