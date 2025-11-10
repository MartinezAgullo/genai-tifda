For each Approved Threat:
    For each Recipient:
        
        1. Emergency Override? ──► Yes ──► SEND
               │ No
               ▼
        
        2. Classification OK? ──► No ──► BLOCK
               │ Yes
               ▼
        
        3. Calculate Distance
               │
               ▼
        
        4. Distance < must_notify_km? ──► Yes ──► SEND (mandatory)
               │ No
               ▼
        
        5. Distance > never_notify_km? ──► Yes ──► BLOCK (too far)
               │ No
               ▼
        
        6. Ambiguous Range
               │
               ▼
        
        7. LLM Decision ──► SEND or BLOCK
               │
               ▼
        
        8. Format & Transmit