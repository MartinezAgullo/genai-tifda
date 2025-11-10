"""
Multimodal Parser Node
======================

Third node in the TIFDA pipeline - processes audio, image, and document files.

This node:
1. Detects file references in sensor_metadata
2. Routes files to appropriate processing tools:
   - Audio → Whisper transcription + speaker diarization
   - Images → VLM tactical analysis
   - Documents → Text extraction (PDF/DOCX/TXT)
3. Enriches parsed_entities with multimodal insights
4. Updates sensor_metadata with processing results

Node Signature:
    Input: TIFDAState with parsed_entities and file references in sensor_metadata
    Output: Updated TIFDAState with enriched entities and multimodal results
"""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.tools.audio_tools import process_audio_file
from src.tools.image_tools import process_tactical_image
from src.tools.document_tools import process_document
from src.models import EntityCOP

# Configure logging
logger = logging.getLogger(__name__)


@traceable(name="multimodal_parser_node")
def multimodal_parser_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Multimodal file processing node.
    
    Processes audio, image, and document files referenced in sensor messages.
    Uses specialized tools to extract tactical information from multimedia content.
    
    Processing pipeline:
    1. Extract file references from sensor_metadata
    2. Process each file type:
       - Audio: Transcription + speaker diarization
       - Images: VLM tactical analysis (asset detection, terrain, etc.)
       - Documents: Text extraction + optional table extraction
    3. Store results in sensor_metadata["multimodal_results"]
    4. Optionally enrich parsed_entities with multimodal insights
    
    Args:
        state: Current TIFDA state with:
            - sensor_metadata["file_references"]: Dict of file paths
            - parsed_entities: List[EntityCOP] to potentially enrich
        
    Returns:
        Dictionary with updated state fields:
            - sensor_metadata: Dict (updated with multimodal_results)
            - parsed_entities: List[EntityCOP] (potentially enriched)
            - decision_reasoning: str (markdown-formatted results)
            - notification_queue: List[str] (UI notifications)
            - decision_log: List[Dict] (audit trail entry)
            - error: str (if processing fails)
    """
    logger.info("=" * 70)
    logger.info("MULTIMODAL PARSER NODE - File Processing")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    sensor_metadata = state.get("sensor_metadata", {})
    file_references = sensor_metadata.get("file_references", {})
    
    if not file_references:
        warning_msg = "No file references found in sensor_metadata"
        logger.warning(f"⚠️  {warning_msg}")
        
        # This shouldn't happen if routing is correct, but handle gracefully
        return {
            "sensor_metadata": sensor_metadata,
            "decision_reasoning": f"## ⚠️  No Multimodal Content\n\n{warning_msg}\n\nSkipping to normalizer."
        }
    
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    logger.info(f"📡 Processing files for sensor: {sensor_id}")
    logger.info(f"   File references: {list(file_references.keys())}")
    
    # ============ PROCESS EACH FILE TYPE ============
    
    multimodal_results = {}
    processing_errors = []
    
    # Process Audio Files
    if "audio" in file_references:
        audio_path = file_references["audio"]
        logger.info(f"\n🎵 Processing audio file: {audio_path}")
        
        try:
            # Check if file exists
            if not Path(audio_path).exists():
                error_msg = f"Audio file not found: {audio_path}"
                logger.error(f"❌ {error_msg}")
                processing_errors.append(error_msg)
                multimodal_results["audio"] = {
                    "success": False,
                    "error": error_msg
                }
            else:
                # Process audio with Whisper + diarization
                audio_report = process_audio_file(
                    audio_path=audio_path,
                    enable_diarization=True,  # Enable speaker identification
                    num_speakers=None,        # Auto-detect
                    language=None             # Auto-detect
                )
                
                multimodal_results["audio"] = {
                    "success": True,
                    "file_path": audio_path,
                    "report": audio_report,
                    "processed_at": datetime.now(timezone.utc).isoformat()
                }
                
                logger.info(f"✅ Audio processed successfully")
                logger.info(f"   Report length: {len(audio_report)} chars")
                
        except Exception as e:
            error_msg = f"Audio processing failed: {str(e)}"
            logger.exception(f"❌ {error_msg}")
            processing_errors.append(error_msg)
            multimodal_results["audio"] = {
                "success": False,
                "error": error_msg
            }
    
    # Process Image Files
    if "image" in file_references:
        image_path = file_references["image"]
        logger.info(f"\n🖼️  Processing image file: {image_path}")
        
        try:
            # Check if file exists
            if not Path(image_path).exists():
                error_msg = f"Image file not found: {image_path}"
                logger.error(f"❌ {error_msg}")
                processing_errors.append(error_msg)
                multimodal_results["image"] = {
                    "success": False,
                    "error": error_msg
                }
            else:
                # Process image with VLM (default: general tactical analysis)
                image_report = process_tactical_image(
                    image_path=image_path,
                    analysis_type="general",  # Can be: general, asset_detection, terrain, damage
                    model="gpt-4o"           # Provider-agnostic in code, but using GPT-4o for now
                )
                
                multimodal_results["image"] = {
                    "success": True,
                    "file_path": image_path,
                    "report": image_report,
                    "analysis_type": "general",
                    "processed_at": datetime.now(timezone.utc).isoformat()
                }
                
                logger.info(f"✅ Image processed successfully")
                logger.info(f"   Report length: {len(image_report)} chars")
                
        except Exception as e:
            error_msg = f"Image processing failed: {str(e)}"
            logger.exception(f"❌ {error_msg}")
            processing_errors.append(error_msg)
            multimodal_results["image"] = {
                "success": False,
                "error": error_msg
            }
    
    # Process Document Files
    if "document" in file_references:
        document_path = file_references["document"]
        logger.info(f"\n📄 Processing document file: {document_path}")
        
        try:
            # Check if file exists
            if not Path(document_path).exists():
                error_msg = f"Document file not found: {document_path}"
                logger.error(f"❌ {error_msg}")
                processing_errors.append(error_msg)
                multimodal_results["document"] = {
                    "success": False,
                    "error": error_msg
                }
            else:
                # Extract text from document (PDF/DOCX/TXT)
                document_report = process_document(
                    document_path=document_path,
                    max_lines=1000  # Limit to prevent huge documents
                )
                
                multimodal_results["document"] = {
                    "success": True,
                    "file_path": document_path,
                    "report": document_report,
                    "processed_at": datetime.now(timezone.utc).isoformat()
                }
                
                logger.info(f"✅ Document processed successfully")
                logger.info(f"   Report length: {len(document_report)} chars")
                
        except Exception as e:
            error_msg = f"Document processing failed: {str(e)}"
            logger.exception(f"❌ {error_msg}")
            processing_errors.append(error_msg)
            multimodal_results["document"] = {
                "success": False,
                "error": error_msg
            }
    
    # ============ ENRICH ENTITIES (Optional) ============
    
    # Get parsed entities
    parsed_entities = state.get("parsed_entities", [])
    
    # Add multimodal results to entity metadata
    # This allows downstream nodes (threat evaluator, etc.) to access multimodal insights
    enriched_entities = []
    
    for entity in parsed_entities:
        # Create a copy with enriched metadata
        enriched_metadata = entity.metadata.copy()
        enriched_metadata["multimodal_processed"] = True
        enriched_metadata["multimodal_results"] = multimodal_results
        
        # Add comments from multimodal analysis (if relevant)
        enriched_comments = entity.comments or ""
        
        # Append audio transcription summary to comments
        if "audio" in multimodal_results and multimodal_results["audio"]["success"]:
            enriched_comments += "\n[AUDIO TRANSCRIPTION AVAILABLE]"
        
        # Append image analysis summary to comments
        if "image" in multimodal_results and multimodal_results["image"]["success"]:
            enriched_comments += "\n[IMAGE ANALYSIS AVAILABLE]"
        
        # Append document content summary to comments
        if "document" in multimodal_results and multimodal_results["document"]["success"]:
            enriched_comments += "\n[DOCUMENT CONTENT AVAILABLE]"
        
        # Create enriched entity
        enriched_entity = EntityCOP(
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
            location=entity.location,
            timestamp=entity.timestamp,
            classification=entity.classification,
            information_classification=entity.information_classification,
            confidence=entity.confidence,
            source_sensors=entity.source_sensors,
            metadata=enriched_metadata,
            speed_kmh=entity.speed_kmh,
            heading=entity.heading,
            comments=enriched_comments.strip() if enriched_comments else None
        )
        
        enriched_entities.append(enriched_entity)
    
    # ============ BUILD REASONING ============
    
    successful_count = sum(1 for r in multimodal_results.values() if r.get("success", False))
    failed_count = len(multimodal_results) - successful_count
    
    reasoning = f"""## 🎬 Multimodal Processing Complete

**Sensor**: `{sensor_id}`
**Files Processed**: {len(file_references)}

### Processing Results:
"""
    
    # Audio results
    if "audio" in multimodal_results:
        result = multimodal_results["audio"]
        if result["success"]:
            reasoning += f"- ✅ **Audio**: Transcribed successfully\n"
            # Add a preview of the transcription
            report = result["report"]
            if len(report) > 200:
                reasoning += f"  ```\n  {report[:200]}...\n  ```\n"
        else:
            reasoning += f"- ❌ **Audio**: {result['error']}\n"
    
    # Image results
    if "image" in multimodal_results:
        result = multimodal_results["image"]
        if result["success"]:
            reasoning += f"- ✅ **Image**: Analyzed with VLM (general tactical analysis)\n"
            # Add a preview of the analysis
            report = result["report"]
            if len(report) > 200:
                reasoning += f"  ```\n  {report[:200]}...\n  ```\n"
        else:
            reasoning += f"- ❌ **Image**: {result['error']}\n"
    
    # Document results
    if "document" in multimodal_results:
        result = multimodal_results["document"]
        if result["success"]:
            reasoning += f"- ✅ **Document**: Text extracted successfully\n"
            # Add a preview
            report = result["report"]
            if len(report) > 200:
                reasoning += f"  ```\n  {report[:200]}...\n  ```\n"
        else:
            reasoning += f"- ❌ **Document**: {result['error']}\n"
    
    reasoning += f"""
### Summary:
- ✅ Successful: {successful_count}
- ❌ Failed: {failed_count}
- 📦 Entities enriched: {len(enriched_entities)}

**Next**: Route to `cop_normalizer_node` for entity normalization
"""
    
    # ============ UPDATE STATE ============
    
    # Update sensor metadata with multimodal results
    sensor_metadata["multimodal_results"] = multimodal_results
    sensor_metadata["multimodal_processed_at"] = datetime.now(timezone.utc).isoformat()
    sensor_metadata["multimodal_success_count"] = successful_count
    sensor_metadata["multimodal_error_count"] = failed_count
    
    # Log decision
    log_decision(
        state=state,
        node_name="multimodal_parser_node",
        decision_type="multimodal_processing",
        reasoning=f"Processed {len(file_references)} files: {successful_count} successful, {failed_count} failed",
        data={
            "sensor_id": sensor_id,
            "files_processed": list(file_references.keys()),
            "successful": successful_count,
            "failed": failed_count,
            "errors": processing_errors
        }
    )
    
    # Add notifications
    if successful_count > 0:
        add_notification(
            state,
            f"✅ {sensor_id}: Processed {successful_count} file(s) successfully"
        )
    
    if failed_count > 0:
        add_notification(
            state,
            f"⚠️  {sensor_id}: {failed_count} file(s) failed to process"
        )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Multimodal processing complete: {successful_count} success, {failed_count} failed")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "parsed_entities": enriched_entities,  # Replace with enriched entities
        "sensor_metadata": sensor_metadata,
        "decision_reasoning": reasoning,
        "error": "; ".join(processing_errors) if processing_errors else None
    }


# ==================== TESTING ====================

def test_multimodal_parser_node():
    """Test the multimodal parser node"""
    from src.core.state import create_initial_state
    from src.models import Location
    
    print("\n" + "=" * 70)
    print("MULTIMODAL PARSER NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Audio file processing (simulated)
    print("Test 1: Audio file processing")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {
        "sensor_id": "radio_bravo",
        "file_references": {
            "audio": "data/sensor_data/radio_bravo/transmission_143200.mp3"
        }
    }
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="radio_bravo_event_001",
            entity_type="event",
            location=Location(lat=39.5, lon=-0.4),
            timestamp=datetime.now(timezone.utc),
            classification="unknown",
            information_classification="SECRET",
            confidence=0.8,
            source_sensors=["radio_bravo"],
            comments="Radio intercept event"
        )
    ]
    
    # Note: This will fail if file doesn't exist, but shows the flow
    result = multimodal_parser_node(state)
    
    print(f"Multimodal results: {list(result['sensor_metadata'].get('multimodal_results', {}).keys())}")
    print(f"Entities enriched: {len(result['parsed_entities'])}")
    print(f"\nReasoning preview:\n{result['decision_reasoning'][:300]}...")
    
    # Test 2: Image file processing (simulated)
    print("\n" + "=" * 70)
    print("Test 2: Image file processing")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {
        "sensor_id": "drone_alpha",
        "file_references": {
            "image": "data/sensor_data/drone_alpha/IMG_20251027_143100.jpg"
        }
    }
    state["parsed_entities"] = [
        EntityCOP(
            entity_id="drone_alpha_001",
            entity_type="uav",
            location=Location(lat=39.4762, lon=-0.3747, alt=120),
            timestamp=datetime.now(timezone.utc),
            classification="friendly",
            information_classification="UNCLASSIFIED",
            confidence=1.0,
            source_sensors=["drone_alpha"]
        )
    ]
    
    result = multimodal_parser_node(state)
    
    print(f"Multimodal results: {list(result['sensor_metadata'].get('multimodal_results', {}).keys())}")
    print(f"Success count: {result['sensor_metadata'].get('multimodal_success_count', 0)}")
    print(f"Error count: {result['sensor_metadata'].get('multimodal_error_count', 0)}")
    
    # Test 3: No file references (edge case)
    print("\n" + "=" * 70)
    print("Test 3: No file references (should warn)")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {
        "sensor_id": "radar_01"
        # No file_references
    }
    
    result = multimodal_parser_node(state)
    print(f"Warning handled: {'No file references' in result['decision_reasoning']}")
    
    print("\n" + "=" * 70)
    print("MULTIMODAL PARSER NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_multimodal_parser_node()