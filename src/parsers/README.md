# TIFDA Parsers

The TIFDA Parsers layer converts raw, **format-specific sensor data** (`SensorMessage`) into **standardized operational entities** (`EntityCOP`) for the Common Operational Picture.

---

## 🏗️ Architecture

The system uses a **Factory pattern** for selection and processing:

**`SensorMessage`** $\rightarrow$ **`ParserFactory`** $\rightarrow$ **Appropriate Parser** $\rightarrow$ **`List[EntityCOP]`**

---

## 📋 Available Parsers & Logic

| Parser | Format Focus | Entity Type | Classification Logic |
| :--- | :--- | :--- | :--- |
| **ASTERIX** | Radar track data. | `aircraft`, `ground_vehicle` | Defaults to **SECRET**. |
| **Drone** | UAV telemetry/imagery. | `uav` | Defaults to **CONFIDENTIAL** (our asset). |
| **Radio** | COMINT/Radio intercepts. | `event` | Defaults to **SECRET**. |
| **Manual** | Human operator reports (SPOTREPs). | `event` | Based on report **priority** (e.g., high $\rightarrow$ CONFIDENTIAL/SECRET). |

---

## 🔒 Information Classification

Parsers automatically assign a **security classification** (`information_classification`) to each resulting `EntityCOP`. This is determined by:

1.  **Explicit override** in the sensor message data.
2.  **Sensor Type defaults** (e.g., Radar $\rightarrow$ SECRET).
3.  **Context-based logic** (e.g., Manual report priority).

---

## 🛠️ Usage

The **`ParserFactory`** is the recommended interface. It automatically selects, validates, and parses a `SensorMessage`, returning the results or an error message.

New sensor formats can be added by **extending `BaseParser`** and registering the new parser with the factory.