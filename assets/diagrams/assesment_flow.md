New Entity Detected
        │
        ▼
  Should Assess? ───► No ──► Skip
        │ Yes
        ▼
  Quick Rules Check
        │
   ┌────┴────┐
   │         │
 Obvious   Ambiguous
   │         │
   │         ▼
   │    LLM Reasoning
   │         │
   └────┬────┘
        ▼
   Threat Assessment
   (critical/high/medium/low/none)
        │
        ▼
   Human Review
        │
        ▼
   Dissemination Router