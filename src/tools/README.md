# TIFDA Multimodal Tools

Tools for processing audio, images, and documents from tactical sensors.

<!-- ## Quick Start

```python
from src.tools import (
    process_audio_file,
    process_tactical_image,
    process_document
)

# Audio transcription
audio_report = process_audio_file(
    "data/radio_intercept.mp3",
    enable_diarization=True,
    num_speakers=2
)

# Image analysis
image_report = process_tactical_image(
    "data/drone_photo.jpg",
    analysis_type="asset_detection",
    model="gpt-4o"
)

# Document extraction
doc_report = process_document(
    "data/sitrep.pdf",
    max_lines=1000
)
``` -->

## Audio Tools (`audio_tools.py`)

**Main function**: `process_audio_file()`

- **Whisper medium** for transcription
- **Pyannote diarization** for speaker identification
- **Supports**: mp3, wav, m4a, flac, ogg

**Requirements**: `HF_TOKEN` in `.env` for pyannote access

## Image Tools (`image_tools.py`)

**Main function**: `process_tactical_image()`

- **VLM analysis** (gpt-4o, claude-3-5-sonnet, etc.)
- **5 analysis types**: general, asset_detection, terrain, damage, custom
- **Supports**: jpg, png, gif, bmp, webp, tiff

**Requirements**: `OPENAI_API_KEY` in `.env` (or other provider)

## Document Tools (`document_tools.py`)

**Main function**: `process_document()`

- **PDF extraction** with PyPDF2
- **DOCX parsing** with python-docx
- **TXT reading** with encoding fallback
- **Supports**: pdf, txt, docx

## Architecture

All tools follow the same pattern:

1. **Low-level functions** - Core processing logic
2. **High-level functions** - Simple interface for nodes
3. **Utility functions** - Validation, metadata, etc.
4. **LangSmith tracing** - All functions decorated with `@traceable`

## Error Handling

All tools return structured reports with clear error messages:

```
REPORT TYPE
===========
Status: FAILED
ERROR: [clear error message]
===========
```

## Provider Agnostic

Image tools support any VLM provider through LangChain:
- OpenAI (gpt-4o, gpt-4o-mini)
- Anthropic (claude-3-5-sonnet)
- Mistral (pixtral-12b)
- Qwen (qwen-vl-max)

Change provider by updating `model` parameter.