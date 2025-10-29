# TIFDA Nodes

LangGraph nodes for the TIFDA pipeline. Nodes execute in order from 1-11.

## Phase 1: Core Pipeline (Sensor → COP)

1. **firewall_node.py** - Security validation (prompt injection, coordinates, structure)
2. **parser_node.py** - Format detection and parsing (ASTERIX, drone, radio, manual)
3. **multimodal_parser_node.py** - Audio/image/document processing (Whisper, GPT-4V, text extraction)
4. **cop_normalizer_node.py** - Entity normalization and validation (IDs, fields, confidence)
5. **cop_merge_node.py** - Sensor fusion (duplicate detection, multi-sensor merging, confidence boosting)
6. **cop_update_node.py** - COP state update and mapa-puntos-interes sync

## Phase 2: Intelligence & Output (COP → Dissemination)

7. **threat_evaluator_node.py** - LLM-based threat assessment (gpt-4o-mini, tactical analysis)
8. **human_review_node.py** - Human-in-the-loop validation (operator approval, auto-approve policies)
9. **dissemination_router_node.py** - Access control routing (clearance, need-to-know, recipient filtering)
10. **format_adapter_node.py** - Multi-format conversion (Link16, JSON, XML, CSV)
11. **transmission_node.py** - MQTT message transmission (topic routing, QoS, delivery tracking)

---

**Pipeline Flow:**
```
Sensor → Firewall → Parser → Multimodal → Normalizer → Merge → COP Update →
Threat Eval → Human Review → Router → Format → Transmission → ✅ Complete
```

