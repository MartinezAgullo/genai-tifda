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

- Security against prompt injection
- Classification and access control system. Use of honehypots for enemies.
- Use external tool  [mapa-puntos-interes](https://github.com/MartinezAgullo/mapa-puntos-interes) to represent the COP in a map

* * * * *

## 🏗️ TIFDA - Arquitectura Completa del Sistema
----------------------

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                            TIFDA ARCHITECTURE                                  ║
║                   Tactical Information Fusion & Decision Aid                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│                          1. INPUT LAYER (Sensors)                            │
└─────────────────────────────────────────────────────────────────────────────┘
           │
           │  SensorMessage (MQTT Topics)
           │
    ┌──────┼──────┬───────┬────────┬─────────┐
    │      │      │       │        │         │
┌───▼──┐ ┌─▼───┐ ┌▼────┐ ┌▼─────┐ ┌▼──────┐
│Radar │ │Drone│ │Radio│ │Manual│ │Other  │
│      │ │ UAV │ │COMINT│ │SITREP│ │Sensors│
└──┬───┘ └──┬──┘ └──┬──┘ └──┬───┘ └───┬───┘
   │        │       │       │         │
   └────────┴───────┴───────┴─────────┘
                    │
                    │ JSON/Binary Data
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    2. SECURITY LAYER (Firewall)                              │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │ • Sensor Authorization (Whitelist)                               │       │
│  │ • Prompt Injection Detection                                     │       │
│  │ • Coordinate Validation                                          │       │
│  │ • Classification Level Validation                                │       │
│  │ • Access Control Enforcement                                     │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    │ Validated SensorMessage
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    3. PARSING LAYER (Format Handlers)                        │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   ASTERIX    │  │    Drone     │  │    Radio     │  │   Manual     │   │
│  │   Parser     │  │   Parser     │  │   Parser     │  │   Parser     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │            │
│         └─────────────────┴─────────────────┴─────────────────┘            │
│                                    │                                         │
│                         ┌──────────▼──────────┐                             │
│                         │  ParserFactory      │                             │
│                         │  (Auto-selection)   │                             │
│                         └──────────┬──────────┘                             │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
                                     │ List[EntityCOP]
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              4. MULTIMODAL PROCESSING (LLM Tools)                            │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Audio Transcription (Whisper)                                 │         │
│  │  • Radio intercepts → Text                                     │         │
│  │  • Voice reports → Structured data                             │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Image Analysis (GPT-4V / Claude Vision)                       │         │
│  │  • Drone imagery → Entity detection                            │         │
│  │  • Visual intel → Threat identification                        │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Text Extraction (NLP)                                         │         │
│  │  • Manual reports → Structured entities                        │         │
│  │  • Free-form text → Geographic coordinates                     │         │
│  └────────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ Enhanced List[EntityCOP]
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  5. COP NORMALIZATION & MERGE                                │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  COP Normalizer (LLM Agent)                                    │         │
│  │  • Standardize entity formats                                  │         │
│  │  • Resolve coordinate systems                                  │         │
│  │  • Validate entity types                                       │         │
│  │  • Assign information_classification                           │         │
│  └────────────────┬───────────────────────────────────────────────┘         │
│                   │                                                          │
│                   ▼                                                          │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  COP Merge Logic                                               │         │
│  │  • Deduplicate entities (same track from multiple sensors)     │         │
│  │  • Fuse sensor data (Kalman filter, weighted average)          │         │
│  │  • Update confidence based on multi-sensor correlation         │         │
│  │  • Track history and velocity vectors                          │         │
│  └────────────────┬───────────────────────────────────────────────┘         │
└────────────────────┼─────────────────────────────────────────────────────────┘
                     │
                     │ Merged EntityCOP
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              6. COP STATE (In-Memory - Heart of TIFDA)                       │
│                                                                               │
│  ╔═══════════════════════════════════════════════════════════════╗          │
│  ║          cop_entities: Dict[str, EntityCOP]                   ║          │
│  ║                                                                ║          │
│  ║  {                                                             ║          │
│  ║    "radar_01_T001": EntityCOP(...),                           ║          │
│  ║    "drone_alpha_obj_05": EntityCOP(...),                      ║          │
│  ║    "manual_charlie_report": EntityCOP(...)                    ║          │
│  ║  }                                                             ║          │
│  ╚═══════════════════════════════════════════════════════════════╝          │
│                                                                               │
│  • Real-time updates from sensors                                            │
│  • Fast in-memory access for threat evaluation                              │
│  • No I/O blocking during processing                                         │
│  • Synchronizes to PostgreSQL (mapa-puntos-interes) asynchronously          │
└─────────────────────────────────────────────────────────────────────────────┘
                     │
                     │ COP State
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                7. THREAT EVALUATION (LLM Agent)                              │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Threat Evaluator Agent                                        │         │
│  │                                                                 │         │
│  │  For each entity in COP:                                       │         │
│  │    • Analyze IFF classification (hostile/unknown/neutral)      │         │
│  │    • Calculate proximity to friendly assets                    │         │
│  │    • Assess speed, heading, altitude (threat vectors)          │         │
│  │    • Cross-reference with threat database                      │         │
│  │    • Evaluate based on historical patterns                     │         │
│  │                                                                 │         │
│  │  Output:                                                        │         │
│  │    • ThreatAssessment per entity                               │         │
│  │    • Threat level: critical/high/medium/low/none               │         │
│  │    • Affected friendly assets                                  │         │
│  │    • Recommended actions (future feature)                      │         │
│  │    • Confidence score                                          │         │
│  └────────────────┬───────────────────────────────────────────────┘         │
└────────────────────┼─────────────────────────────────────────────────────────┘
                     │
                     │ List[ThreatAssessment]
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  8. HUMAN-IN-THE-LOOP (HITL) REVIEW                          │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Review Triggers:                                              │         │
│  │  • Critical threats (requires_human_review = True)             │         │
│  │  • TOP_SECRET dissemination                                    │         │
│  │  • Low confidence (<0.6)                                       │         │
│  │  • First contact with entity/sensor type                       │         │
│  │  • Conflicting sensor reports                                  │         │
│  │  • Enemy access transmission (deception ops)                   │         │
│  └────────────────┬───────────────────────────────────────────────┘         │
│                   │                                                          │
│                   ▼                                                          │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Human Operator Actions:                                       │         │
│  │  • Approve / Reject / Modify threat assessment                 │         │
│  │  • Approve / Reject dissemination decisions                    │         │
│  │  • Provide feedback for model learning                         │         │
│  │  • Override classification or confidence                       │         │
│  └────────────────┬───────────────────────────────────────────────┘         │
└────────────────────┼─────────────────────────────────────────────────────────┘
                     │
                     │ Approved Threats + Feedback
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              9. DISSEMINATION ROUTER (LLM Agent)                             │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Dissemination Policy Engine                                   │         │
│  │                                                                 │         │
│  │  For each recipient (BMS, Tactical Radio, Allied Forces):      │         │
│  │                                                                 │         │
│  │  1. Check recipient access_level:                              │         │
│  │     • top_secret_access → Can see TOP_SECRET and below         │         │
│  │     • secret_access → Can see SECRET and below                 │         │
│  │     • enemy_access → Only UNCLASSIFIED (or deception)          │         │
│  │                                                                 │         │
│  │  2. Filter entities by information_classification:             │         │
│  │     • Only send what recipient is cleared for                  │         │
│  │                                                                 │         │
│  │  3. Need-to-know analysis:                                     │         │
│  │     • Geographic relevance (in recipient's AOR?)               │         │
│  │     • Operational relevance (affects their mission?)           │         │
│  │     • Threat proximity (within threat distance?)               │         │
│  │                                                                 │         │
│  │  4. Deception operations (enemy_access):                       │         │
│  │     • Mix real UNCLASSIFIED + fake data                        │         │
│  │     • Flag as is_deception = True                              │         │
│  │     • Requires human approval                                  │         │
│  │                                                                 │         │
│  │  Output:                                                        │         │
│  │    • DisseminationDecision per recipient                       │         │
│  │    • information_subset: List[entity_ids]                      │         │
│  │    • highest_classification_sent                               │         │
│  │    • requires_human_approval (bool)                            │         │
│  └────────────────┬───────────────────────────────────────────────┘         │
└────────────────────┼─────────────────────────────────────────────────────────┘
                     │
                     │ List[DisseminationDecision]
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  10. FORMAT ADAPTERS                                         │
│                                                                               │
│  Convert EntityCOP → Recipient-specific format:                             │
│                                                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Link-16   │  │    JSON     │  │  ASTERIX    │  │     CoT     │       │
│  │   Adapter   │  │   Adapter   │  │   Adapter   │  │   Adapter   │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │                │                │                │               │
│  ┌──────▼────────┐  ┌────▼──────────┐  ┌─▼────────────┐  ┌▼───────────┐  │
│  │ Voice/Text    │  │  Custom       │  │    ...       │  │  mapa-     │  │
│  │ Adapter       │  │  Adapter      │  │              │  │  puntos    │  │
│  └───────────────┘  └───────────────┘  └──────────────┘  └────┬───────┘  │
│                                                                 │          │
│  Output: OutgoingMessage with formatted content                │          │
└─────────────────────────────────────────────────────────────────┼───────────┘
                                                                  │
                                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  11. TRANSMISSION LAYER                                      │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Transmission Methods:                                         │         │
│  │                                                                 │         │
│  │  • MQTT Publisher (primary)                                    │         │
│  │    - Publish to recipient-specific topics                      │         │
│  │    - QoS based on message criticality                          │         │
│  │                                                                 │         │
│  │  • HTTP/REST API (secondary)                                   │         │
│  │    - POST to recipient endpoints                               │         │
│  │    - Retry logic with exponential backoff                      │         │
│  │                                                                 │         │
│  │  • Radio/Voice (tactical comms)                                │         │
│  │    - Text-to-speech for voice networks                         │         │
│  │    - Pre-formatted tactical brevity                            │         │
│  └────────────────┬───────────────────────────────────────────────┘         │
└────────────────────┼─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  12. AUDIT & LOGGING                                         │
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │  Comprehensive Audit Trail:                                    │         │
│  │                                                                 │         │
│  │  • All sensor inputs (who, what, when, where)                  │         │
│  │  • Firewall decisions (blocked/allowed)                        │         │
│  │  • Entity merges and updates                                   │         │
│  │  • Threat assessments and reasoning                            │         │
│  │  • Human review decisions and feedback                         │         │
│  │  • Dissemination decisions and justifications                  │         │
│  │  • All transmissions (recipient, content, timestamp)           │         │
│  │  • Classification violations (attempted/blocked)               │         │
│  │  • Deception operations (enemy_access)                         │         │
│  │                                                                 │         │
│  │  Stored in: data/audit_logs/ (append-only)                     │         │
│  └────────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  13. OUTPUT SYSTEMS (Recipients)                             │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Allied BMS  │  │   Tactical   │  │   Command    │  │   Friendly   │   │
│  │   (NATO)     │  │    Radio     │  │     Post     │  │   Aircraft   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ mapa-puntos- │  │   Enemy      │  │   Archive    │                      │
│  │   interes    │  │   Monitor    │  │   System     │                      │
│  │  (Visual COP)│  │  (Deception) │  │              │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

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
* * * * *

## Itegration with COP visualization tool
----------------------

Integration with [mapa-puntos-interes](https://github.com/MartinezAgullo/mapa-puntos-interes)


```
┌─────────────────────────────────────────────────────────┐
│                        TIFDA                             │
│                                                          │
│  ┌────────────┐    ┌──────────────┐   ┌──────────────┐ │
│  │  Parsers   │ -> │ EntityCOP    │ ->│  COP State   │ │
│  └────────────┘    └──────────────┘   └──────┬───────┘ │
│                                               │         │
│                    ┌──────────────────────────┘         │
│                    │                                    │
│              ┌─────▼──────┐                             │
│              │ COP Sync   │                             │
│              │ (Monitor)  │                             │
│              └─────┬──────┘                             │
│                    │                                    │
│              ┌─────▼──────┐                             │
│              │Mapa Client │                             │
│              └─────┬──────┘                             │
└────────────────────┼────────────────────────────────────┘
                     │ HTTP POST/PUT/DELETE
                     │
┌────────────────────▼────────────────────────────────────┐
│              mapa-puntos-interes                         │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │  Express API │ -> │ PostgreSQL   │                   │
│  │  /api/puntos │    │  + PostGIS   │                   │
│  └──────────────┘    └──────────────┘                   │
│                                                          │
│  ┌──────────────────────────────────┐                   │
│  │      Leaflet Map Viewer          │                   │
│  └──────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

<!-- 
tree -I "__pycache__|__init__.py|uv.lock|README.md|tests|*.log|*.db*|*.png|*.PNG" 
-->