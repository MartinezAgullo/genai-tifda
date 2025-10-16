# TIFDA Security Layer

The TIFDA Security Layer provides **multi-layer security validation** using the `firewall.py` component to protect against malicious input and policy violations in a data processing pipeline.

The system performs three primary types of validation:

---

## 1. Sensor Input Validation

Validates incoming `SensorMessage` data to ensure **trustworthiness and integrity**.

| Check | Focus |
| :--- | :--- |
| **Authorization** | Sensor must be **whitelisted** and **enabled**. |
| **Integrity** | Message structure is valid, and the timestamp isn't in the future. |
| **Security Scan** | **Prompt Injection** detection in all text fields (e.g., against instruction overrides, role-playing, jailbreaks). |
| **Data Bounds** | Geographic **coordinates are valid** (lat/lon in range). |

---

## 2. Entity Validation

Validates processed **Entities** (`EntityCOP`) before they are added to the Common Operating Picture.

| Check | Focus |
| :--- | :--- |
| **Classification** | Entity classification (e.g., friendly, hostile) is valid. |
| **Integrity** | Coordinates are within bounds, confidence is in $[0.0, 1.0]$, and speed/heading values are valid. |
| **Security Scan** | Scans entity **comments** for Prompt Injection attempts. |

---

## 3. Dissemination Validation

Enforces security policies when transmitting data to a recipient.

| Check | Focus |
| :--- | :--- |
| **Clearance Policy** | Ensures the **Recipient Clearance** is **sufficient** for the data's **Classification Level** to prevent unauthorized access. |
| **Data Flow** | Confirms the information subset to be shared is not empty. |

---

## Threats Mitigated

The firewall specifically targets **Prompt Injection**, **Malformed Data Structures** (invalid coordinates/ranges), and **Classification Violations** (insufficient clearance).

The validation process is integrated into the data pipeline (e.g., `firewall_node.py`) to gate the processing of all sensor events.