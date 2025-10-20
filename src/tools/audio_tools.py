"""
Audio Processing Tools
======================

Tools for transcribing and analyzing audio files from radio intercepts
and other audio sensors.

Capabilities:
- Whisper transcription (medium model for accuracy)
- Speaker diarization (pyannote.audio)
- Language detection
- Structured output for entity extraction
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from langsmith import traceable


# ==================== LAZY LOADING (Performance) ====================

_whisper_model = None
_diarization_pipeline = None


def _load_whisper_model(model_size: str = "medium"):
    """
    Lazy load Whisper model (only loads once)
    
    Args:
        model_size: Model size (tiny, base, small, medium, large)
        
    Returns:
        Whisper model instance
    """
    global _whisper_model
    
    if _whisper_model is None:
        try:
            import whisper
            print(f"🔄 Loading Whisper {model_size} model (this may take a moment)...")
            _whisper_model = whisper.load_model(model_size)
            print(f"✅ Whisper {model_size} model loaded")
        except ImportError:
            raise ImportError(
                "Whisper not installed. Install with: pip install openai-whisper"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model: {e}")
    
    return _whisper_model


def _load_diarization_pipeline():
    """
    Lazy load pyannote speaker diarization pipeline
    
    Requires HF_TOKEN environment variable.
    
    Returns:
        Pyannote pipeline instance
    """
    global _diarization_pipeline
    
    if _diarization_pipeline is None:
        try:
            from pyannote.audio import Pipeline
            
            hf_token = os.getenv("HF_TOKEN")
            if not hf_token:
                raise ValueError(
                    "HF_TOKEN not found in environment variables. "
                    "Get your token from: https://huggingface.co/settings/tokens\n"
                    "Then add to .env: HF_TOKEN=your_token_here"
                )
            
            print("🔄 Loading pyannote speaker-diarization-3.1 model...")
            _diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            print("✅ Diarization pipeline loaded")
            
        except ImportError:
            raise ImportError(
                "Pyannote.audio not installed. Install with:\n"
                "pip install pyannote.audio\n"
                "Note: Requires PyTorch"
            )
        except Exception as e:
            error_msg = str(e)
            if "gated" in error_msg.lower() or "accept" in error_msg.lower():
                raise ValueError(
                    "Access denied to pyannote model. You must:\n"
                    "1. Go to https://huggingface.co/pyannote/speaker-diarization-3.1\n"
                    "2. Accept the user agreement\n"
                    "3. Ensure your HF_TOKEN has the correct permissions"
                )
            raise RuntimeError(f"Failed to load diarization pipeline: {e}")
    
    return _diarization_pipeline


# ==================== CORE TRANSCRIPTION FUNCTIONS ====================

@traceable(name="transcribe_audio_simple")
def transcribe_audio_simple(
    audio_path: str,
    language: Optional[str] = None,
    model_size: str = "medium"
) -> Dict[str, Any]:
    """
    Simple audio transcription without speaker diarization
    
    Use this for:
    - Single speaker recordings
    - Quick transcription when speaker identity doesn't matter
    - When diarization dependencies are not available
    
    Args:
        audio_path: Path to audio file (mp3, wav, m4a, etc.)
        language: ISO language code (None = auto-detect)
        model_size: Whisper model size (medium recommended)
        
    Returns:
        Dict with:
            - success: bool
            - transcription: str (full text)
            - language: str (detected language)
            - duration: float (seconds)
            - error: Optional[str]
    """
    try:
        # Validate file exists
        if not os.path.exists(audio_path):
            return {
                "success": False,
                "transcription": "",
                "language": None,
                "duration": 0.0,
                "error": f"Audio file not found: {audio_path}"
            }
        
        # Load model
        model = _load_whisper_model(model_size)
        
        # Transcribe
        print(f"🎵 Transcribing: {Path(audio_path).name}")
        result = model.transcribe(audio_path, language=language)
        
        return {
            "success": True,
            "transcription": result["text"].strip(),
            "language": result.get("language", "unknown"),
            "duration": result.get("duration", 0.0),
            "segments": result.get("segments", []),
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "transcription": "",
            "language": None,
            "duration": 0.0,
            "error": f"Transcription failed: {str(e)}"
        }


@traceable(name="transcribe_audio_with_speakers")
def transcribe_audio_with_speakers(
    audio_path: str,
    num_speakers: Optional[int] = None,
    min_speakers: int = 1,
    max_speakers: int = 4,
    language: Optional[str] = None,
    model_size: str = "medium"
) -> Dict[str, Any]:
    """
    Audio transcription WITH speaker diarization
    
    Use this for:
    - Radio intercepts with multiple speakers
    - Tactical communications
    - When speaker identification is important
    
    Args:
        audio_path: Path to audio file
        num_speakers: Exact number of speakers (None = auto-detect)
        min_speakers: Minimum speakers (if auto-detecting)
        max_speakers: Maximum speakers (if auto-detecting)
        language: ISO language code (None = auto-detect)
        model_size: Whisper model size
        
    Returns:
        Dict with:
            - success: bool
            - transcription: str (full text with speaker labels)
            - speakers: List[Dict] (speaker segments)
            - num_speakers_detected: int
            - language: str
            - duration: float
            - error: Optional[str]
    """
    try:
        # Validate file
        if not os.path.exists(audio_path):
            return {
                "success": False,
                "transcription": "",
                "speakers": [],
                "num_speakers_detected": 0,
                "language": None,
                "duration": 0.0,
                "error": f"Audio file not found: {audio_path}"
            }
        
        # Load models
        diar_pipeline = _load_diarization_pipeline()
        whisper_model = _load_whisper_model(model_size)
        
        # Step 1: Speaker diarization
        print(f"🎵 Performing speaker diarization on: {Path(audio_path).name}")
        
        if num_speakers is not None:
            # Fixed number of speakers
            diarization = diar_pipeline(audio_path, num_speakers=num_speakers)
        else:
            # Auto-detect speakers
            diarization = diar_pipeline(
                audio_path,
                min_speakers=min_speakers,
                max_speakers=max_speakers
            )
        
        # Count unique speakers
        speakers_detected = set()
        for _, _, speaker in diarization.itertracks(yield_label=True):
            speakers_detected.add(speaker)
        num_speakers_detected = len(speakers_detected)
        
        print(f"👥 Detected {num_speakers_detected} speaker(s)")
        
        # Step 2: Transcribe each speaker segment
        print(f"📝 Transcribing segments...")
        speaker_segments = []
        
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            start_time = turn.start
            end_time = turn.end
            
            # Extract audio segment
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                
                # Use ffmpeg to extract segment
                subprocess.run([
                    "ffmpeg", "-y", "-i", audio_path,
                    "-ss", str(start_time),
                    "-to", str(end_time),
                    "-ar", "16000",  # Whisper expects 16kHz
                    "-ac", "1",       # Mono
                    tmp_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
                # Transcribe segment
                result = whisper_model.transcribe(tmp_path, language=language)
                text = result["text"].strip()
                detected_language = result.get("language", "unknown")
                
                # Clean up temp file
                os.unlink(tmp_path)
                
                if text:  # Only add non-empty segments
                    speaker_segments.append({
                        "speaker": speaker,
                        "start": round(start_time, 2),
                        "end": round(end_time, 2),
                        "duration": round(end_time - start_time, 2),
                        "text": text
                    })
        
        # Step 3: Format output
        # Create formatted transcription with speaker labels
        formatted_lines = []
        for seg in speaker_segments:
            timestamp = f"[{seg['start']:.1f}s - {seg['end']:.1f}s]"
            formatted_lines.append(f"{seg['speaker']} {timestamp}: {seg['text']}")
        
        full_transcription = "\n".join(formatted_lines)
        
        # Get total duration from last segment
        total_duration = speaker_segments[-1]["end"] if speaker_segments else 0.0
        
        return {
            "success": True,
            "transcription": full_transcription,
            "speakers": speaker_segments,
            "num_speakers_detected": num_speakers_detected,
            "language": detected_language if speaker_segments else "unknown",
            "duration": total_duration,
            "error": None
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "transcription": "",
            "speakers": [],
            "num_speakers_detected": 0,
            "language": None,
            "duration": 0.0,
            "error": f"FFmpeg error (is it installed?): {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "transcription": "",
            "speakers": [],
            "num_speakers_detected": 0,
            "language": None,
            "duration": 0.0,
            "error": f"Diarization/transcription failed: {str(e)}"
        }


# ==================== HIGH-LEVEL INTERFACE ====================

@traceable(name="process_audio_file")
def process_audio_file(
    audio_path: str,
    enable_diarization: bool = True,
    num_speakers: Optional[int] = None,
    language: Optional[str] = None
) -> str:
    """
    High-level audio processing function (auto-selects best method)
    
    This is the main function that nodes should call.
    Automatically chooses between simple transcription and diarization
    based on the enable_diarization flag.
    
    Args:
        audio_path: Path to audio file
        enable_diarization: Whether to use speaker diarization
        num_speakers: Expected number of speakers (None = auto-detect)
        language: ISO language code (None = auto-detect)
        
    Returns:
        Formatted string report suitable for LLM consumption
        
    Example return:
        ```
        AUDIO TRANSCRIPTION REPORT
        ==========================
        File: radio_transmission_001.mp3
        Duration: 45.3 seconds
        Language: en (English)
        Speakers: 2 detected
        
        TRANSCRIPTION:
        --------------
        SPEAKER_00 [0.0s - 12.5s]: Alpha team, this is command. What is your status?
        SPEAKER_01 [13.2s - 28.7s]: Command, alpha team. We have visual on three hostile vehicles...
        SPEAKER_00 [29.1s - 35.4s]: Copy that. Maintain observation and report any changes.
        SPEAKER_01 [36.0s - 45.3s]: Roger, command. Will continue surveillance.
        
        ==========================
        ```
    """
    try:
        # Choose processing method
        if enable_diarization:
            result = transcribe_audio_with_speakers(
                audio_path=audio_path,
                num_speakers=num_speakers,
                language=language
            )
        else:
            result = transcribe_audio_simple(
                audio_path=audio_path,
                language=language
            )
        
        # Check for errors
        if not result["success"]:
            return f"""
AUDIO TRANSCRIPTION REPORT
==========================
File: {Path(audio_path).name}
Status: FAILED

ERROR: {result['error']}
==========================
"""
        
        # Format success response
        file_name = Path(audio_path).name
        duration = result["duration"]
        language = result["language"]
        transcription = result["transcription"]
        
        if enable_diarization:
            num_speakers = result["num_speakers_detected"]
            header = f"""
AUDIO TRANSCRIPTION REPORT
==========================
File: {file_name}
Duration: {duration:.1f} seconds
Language: {language}
Speakers: {num_speakers} detected
Processing: Whisper medium + pyannote diarization

TRANSCRIPTION:
--------------
"""
        else:
            header = f"""
AUDIO TRANSCRIPTION REPORT
==========================
File: {file_name}
Duration: {duration:.1f} seconds
Language: {language}
Processing: Whisper medium (simple transcription)

TRANSCRIPTION:
--------------
"""
        
        footer = "\n==========================\n"
        
        return header + transcription + footer
        
    except Exception as e:
        return f"""
AUDIO TRANSCRIPTION REPORT
==========================
File: {Path(audio_path).name}
Status: CRITICAL ERROR

ERROR: {str(e)}
==========================
"""


# ==================== UTILITY FUNCTIONS ====================

def is_audio_file(file_path: str) -> bool:
    """
    Check if file is a supported audio format
    
    Args:
        file_path: Path to check
        
    Returns:
        True if supported audio file
    """
    audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
    return Path(file_path).suffix.lower() in audio_extensions


def get_audio_info(audio_path: str) -> Optional[Dict[str, Any]]:
    """
    Get basic audio file info without transcription
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        Dict with file metadata or None if error
    """
    try:
        import subprocess
        import json
        
        # Use ffprobe to get audio info
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        format_info = data.get("format", {})
        audio_stream = None
        
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                audio_stream = stream
                break
        
        return {
            "file_name": Path(audio_path).name,
            "file_size_mb": float(format_info.get("size", 0)) / (1024 * 1024),
            "duration_seconds": float(format_info.get("duration", 0)),
            "format": format_info.get("format_name", "unknown"),
            "codec": audio_stream.get("codec_name", "unknown") if audio_stream else "unknown",
            "sample_rate": int(audio_stream.get("sample_rate", 0)) if audio_stream else 0,
            "channels": int(audio_stream.get("channels", 0)) if audio_stream else 0
        }
        
    except Exception:
        return None