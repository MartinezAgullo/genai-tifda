# Rules Module

This folder contains deterministic rule engines used by TIFDA to make fast, non-LLM decisions.

- **`classification_rules.py`**  
  Handles access control for classified information: maps access levels to classification, downgrades entities (removing sensitive fields), and filters COP entities according to recipient clearance.
    
    ```python
    CLASSIFICATION_HIERARCHY = [
        "TOP_SECRET",
        "SECRET",
        "CONFIDENTIAL",
        "RESTRICTED",
        "UNCLASSIFIED"
    ]
    ```

- **`threat_rules.py`**  
  Provides rule-based threat assessment: loads threat thresholds from [threat_thresholds.yaml](https://github.com/MartinezAgullo/genai-tifda/blob/main/config/threat_thresholds.yaml), decides obvious threat levels, computes numeric threat scores, and categorizes entity types for prioritization. These rules look at the entity (drone, aircraft, unknown object) and its behavior (distance, type, movement) and decide a threat score.

- **`dissemination_rules.py`**  
  Implements need-to-know dissemination rules: loads recipient configs from [recipients.yaml](https://github.com/MartinezAgullo/genai-tifda/blob/main/config/recipients.yaml) and distance thresholds from [threat_thresholds.yaml](https://github.com/MartinezAgullo/genai-tifda/blob/main/config/threat_thresholds.yaml), computes distances, and decides which recipients must/should never be notified about a threat.  These rules look at the recipients (external systems, teams, agencies) and decides which recipients should receive this threat notification on a need-to-know basis.


