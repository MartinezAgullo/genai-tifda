"""
TIFDA Multimodal Tools
======================

Tools for processing multimodal sensor data (audio, images, documents).
All tools are provider-agnostic and support multiple model backends.
"""

# Audio tools
from src.tools.audio_tools import (
    process_audio_file,
    transcribe_audio_simple,
    transcribe_audio_with_speakers,
    is_audio_file,
    get_audio_info
)

# Image tools
from src.tools.image_tools import (
    analyze_image,
    analyze_multiple_images,
    process_tactical_image,
    is_image_file,
    get_image_dimensions,
    resize_image_if_needed
)

# Document tools
from src.tools.document_tools import (
    process_document,
    extract_text_from_document,
    is_document_file,
    get_document_info,
    extract_metadata_from_pdf,
    search_text_in_document
)


__all__ = [
    # Audio
    "process_audio_file",
    "transcribe_audio_simple",
    "transcribe_audio_with_speakers",
    "is_audio_file",
    "get_audio_info",
    
    # Image
    "analyze_image",
    "analyze_multiple_images",
    "process_tactical_image",
    "is_image_file",
    "get_image_dimensions",
    "resize_image_if_needed",
    
    # Document
    "process_document",
    "extract_text_from_document",
    "is_document_file",
    "get_document_info",
    "extract_metadata_from_pdf",
    "search_text_in_document",
]