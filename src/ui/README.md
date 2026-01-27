# Human-in-the-Loop (HITL) UI

Real-time threat review interface for tactical intelligence operators.

## Components

### `review_service.py`
**Thread-safe state management bridge** between TIFDA pipeline and Gradio UI.

**Key Functions:**
- `add_pending_items()` - Pipeline writes threats to [shared state](../../data/shared_state.json)
- `get_pending_items()` - UI reads threats for display
- `submit_decision()` - UI writes operator decisions
- `get_decisions()` - Pipeline reads operator decisions
- `auto_approve_timed_out_items()` - Timeout handling

<!-- **Thread Safety:** Uses `fcntl.flock()` for atomic file operations. -->

### `gradio_interface.py`
**Web-based operator interface** for threat review.

**Features:**
- Priority-sorted threat list (Critical → Low)
- Detailed threat view (reasoning, confidence, affected entities)
- Decision actions: Approve / Reject / Flag
- Operator comments
- Approve All bulk action
- Auto-refresh (5s)
- Review history

**Access:** http://localhost:7860

## Data Flow

```
┌─────────────┐                                    ┌─────────────┐
│   Pipeline  │                                    │  Gradio UI  │
│             │                                    │             │
│  human_     │  writes threats                    │  displays   │
│  review_    ├──────────────┐          ┌──────────┤  threats    │
│  node       │              │          │          │             │
└─────────────┘              ▼          │          └─────────────┘
                      ┌──────────────┐  │
                      │shared_state  │◄─┘
                      │   .json      │
                      │              │───┐
                      │ (file lock)  │   │
                      └──────────────┘   │
┌─────────────┐              ▲           │          ┌─────────────┐
│   Pipeline  │              │           │          │  Gradio UI  │
│             │  reads       │           └──────────┤             │
│  continues  │  decisions   │      writes decisions│  operator   │
│  processing │◄─────────────┘                      │  reviews    │
│             │                                     │             │
└─────────────┘                                     └─────────────┘
```

## Usage

```bash
uv run python -m src.ui.gradio_interface
```

```bash
# In another terminal
uv run python tests/test_hitl_radar.py
```

**Flow:**
1. Test sends threats → Pipeline processes
2. `human_review_node` writes to `data/shared_state.json`
3. UI polls and displays threats
4. Operator reviews and decides
5. UI writes decision to `shared_state.json`
6. Pipeline reads decision and continues

## Configuration

See `src/core/init_config.py`:

```python
config.enable_human_review = True          # Enable/disable HITL
config.auto_approve_timeout_seconds = 300  # Timeout (0 = wait forever)
config.ui_refresh_interval = 5             # Poll interval (seconds)
config.ui_port = 7864                      # Gradio port
config.reviewer_id = "operator_alpha"      # Operator ID
```

## State File

**Structure:**
```json
{
  "pending_review_items": [
    {
      "item_id": "threat_001",
      "threat_level": "critical",
      "threat_source_id": "hostile_aircraft",
      "confidence": 0.95,
      "reasoning": "...",
      "affected_entities": ["base_alpha"],
      "added_at": "2025-11-04T10:30:00Z"
    }
  ],
  "human_decisions": [
    {
      "item_id": "threat_001",
      "decision": "approve",
      "comments": "Confirmed threat",
      "reviewer_id": "operator_alpha",
      "timestamp": "2025-11-04T10:31:00Z"
    }
  ],
  "last_updated": "2025-11-04T10:31:00Z",
  "pipeline_active": true
}
```

## Testing

```bash
# Test ReviewService
python -m src.ui.review_service

# Test full integration (UI + Pipeline)
# Terminal 1:
uv run python -m src.ui.gradio_interface

# Terminal 2:
uv run python tests/test_hitl_radar.py
```