"""
Image Analysis Tools
====================

Tools for analyzing images from drones, cameras, and other visual sensors
using Vision Language Models (VLMs).

Capabilities:
- Military asset detection (vehicles, aircraft, personnel)
- Terrain analysis
- Infrastructure assessment
- Threat identification
- Damage assessment

The prompt is intentionally generic - tactical prompts should be constructed
by the calling node based on mission context.

Supports multiple VLM providers (OpenAI, Anthropic, Mistral, Qwen, etc.)
through LangChain's unified interface.
"""

import os
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
from io import BytesIO

from langsmith import traceable
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage


# ==================== IMAGE ENCODING ====================

def encode_image_to_base64(image_path: str) -> Optional[str]:
    """
    Encode image file to base64 string for GPT-4V
    
    Args:
        image_path: Path to image file
        
    Returns:
        Base64 encoded string or None if error
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"❌ Error encoding image: {e}")
        return None


def get_image_mime_type(image_path: str) -> str:
    """
    Get MIME type from image file extension
    
    Args:
        image_path: Path to image file
        
    Returns:
        MIME type string (e.g., 'image/jpeg')
    """
    extension = Path(image_path).suffix.lower()
    
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff'
    }
    
    return mime_types.get(extension, 'image/jpeg')  # Default to jpeg


def validate_image_file(image_path: str) -> tuple[bool, Optional[str]]:
    """
    Validate image file exists and is a supported format
    
    Args:
        image_path: Path to check
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check existence
    if not os.path.exists(image_path):
        return False, f"Image file not found: {image_path}"
    
    # Check format
    supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    extension = Path(image_path).suffix.lower()
    
    if extension not in supported_extensions:
        return False, f"Unsupported image format: {extension}. Supported: {supported_extensions}"
    
    # Check file size (VLMs typically have ~20MB limits)
    file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
    if file_size_mb > 20:  # Most VLM providers recommend < 20MB
        return False, f"Image too large: {file_size_mb:.1f}MB (max 20MB)"
    
    return True, None


# ==================== CORE VISION FUNCTIONS ====================

@traceable(name="analyze_image")
def analyze_image(
    image_path: str,
    prompt: str,
    model: str = "gpt-4o",
    max_tokens: int = 1000,
    temperature: float = 0.0,
    detail: str = "high"
) -> Dict[str, Any]:
    """
    Analyze image using a Vision Language Model (VLM)
    
    This is the LOW-LEVEL function - prompts should be constructed by the caller.
    Supports any VLM provider through LangChain (OpenAI, Anthropic, Mistral, Qwen, etc.)
    
    Args:
        image_path: Path to image file
        prompt: Analysis prompt (constructed by calling node)
        model: Model identifier (gpt-4o, claude-3-5-sonnet, etc.)
        max_tokens: Maximum tokens in response
        temperature: Generation temperature (0.0 = deterministic)
        detail: Image detail level ("low" or "high")
        
    Returns:
        Dict with:
            - success: bool
            - analysis: str (VLM response)
            - model_used: str
            - error: Optional[str]
    """
    try:
        # Validate image
        is_valid, error_msg = validate_image_file(image_path)
        if not is_valid:
            return {
                "success": False,
                "analysis": "",
                "model_used": model,
                "error": error_msg
            }
        
        # Encode image
        base64_image = encode_image_to_base64(image_path)
        if not base64_image:
            return {
                "success": False,
                "analysis": "",
                "model_used": model,
                "error": "Failed to encode image to base64"
            }
        
        # Get MIME type
        mime_type = get_image_mime_type(image_path)
        
        # Create LangChain ChatOpenAI client
        llm = ChatOpenAI(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Construct message with image
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}",
                        "detail": detail
                    }
                }
            ]
        )
        
        # Call GPT-4V
        print(f"🖼️  Analyzing image with {model}...")
        response = llm.invoke([message])
        
        analysis_text = response.content
        
        return {
            "success": True,
            "analysis": analysis_text,
            "model_used": model,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "analysis": "",
            "model_used": model,
            "error": f"Vision analysis failed: {str(e)}"
        }


@traceable(name="analyze_multiple_images")
def analyze_multiple_images(
    image_paths: List[str],
    prompt: str,
    model: str = "gpt-4o",
    max_tokens: int = 2000
) -> Dict[str, Any]:
    """
    Analyze multiple images together (useful for before/after comparisons)
    
    Args:
        image_paths: List of paths to image files
        prompt: Analysis prompt (should reference multiple images)
        model: OpenAI model
        max_tokens: Maximum tokens in response
        
    Returns:
        Dict with:
            - success: bool
            - analysis: str
            - images_analyzed: int
            - error: Optional[str]
    """
    try:
        if not image_paths:
            return {
                "success": False,
                "analysis": "",
                "images_analyzed": 0,
                "error": "No images provided"
            }
        
        # Validate all images
        for img_path in image_paths:
            is_valid, error_msg = validate_image_file(img_path)
            if not is_valid:
                return {
                    "success": False,
                    "analysis": "",
                    "images_analyzed": 0,
                    "error": f"Image validation failed: {error_msg}"
                }
        
        # Encode all images
        image_contents = []
        for img_path in image_paths:
            base64_image = encode_image_to_base64(img_path)
            if not base64_image:
                return {
                    "success": False,
                    "analysis": "",
                    "images_analyzed": 0,
                    "error": f"Failed to encode image: {img_path}"
                }
            
            mime_type = get_image_mime_type(img_path)
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_image}",
                    "detail": "high"
                }
            })
        
        # Create message content (text + all images)
        message_content = [{"type": "text", "text": prompt}] + image_contents
        
        # Create LLM
        llm = ChatOpenAI(
            model=model,
            max_tokens=max_tokens,
            temperature=0.0
        )
        
        # Analyze
        print(f"🖼️  Analyzing {len(image_paths)} images together with {model}...")
        message = HumanMessage(content=message_content)
        response = llm.invoke([message])
        
        return {
            "success": True,
            "analysis": response.content,
            "images_analyzed": len(image_paths),
            "model_used": model,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "analysis": "",
            "images_analyzed": 0,
            "error": f"Multi-image analysis failed: {str(e)}"
        }


# ==================== HIGH-LEVEL TACTICAL INTERFACE ====================

@traceable(name="process_tactical_image")
def process_tactical_image(
    image_path: str,
    analysis_type: str = "general",
    custom_prompt: Optional[str] = None,
    model: str = "gpt-4o"
) -> str:
    """
    HIGH-LEVEL tactical image processing function
    
    This provides some built-in tactical prompts for common use cases,
    but allows custom prompts for specific missions.
    
    Args:
        image_path: Path to image file
        analysis_type: Type of analysis:
            - "general" - General tactical assessment
            - "asset_detection" - Detect military assets
            - "terrain" - Terrain analysis
            - "damage" - Damage assessment
            - "custom" - Use custom_prompt
        custom_prompt: Custom prompt (required if analysis_type="custom")
        model: OpenAI model to use
        
    Returns:
        Formatted string report for LLM consumption
    """
    try:
        # Select prompt based on analysis type
        if analysis_type == "custom":
            if not custom_prompt:
                return """
IMAGE ANALYSIS REPORT
=====================
File: {Path(image_path).name}
Status: FAILED

ERROR: custom_prompt is required when analysis_type='custom'
=====================
"""
            prompt = custom_prompt
            
        elif analysis_type == "general":
            prompt = """
Analyze this tactical imagery and provide a detailed report including:

1. **Assets Detected**: Identify any military vehicles, aircraft, vessels, or equipment visible
   - Type (tank, APC, aircraft, etc.)
   - Estimated quantity
   - Approximate location in image

2. **Personnel**: Detect any military or civilian personnel
   - Approximate count
   - Activity/posture

3. **Infrastructure**: Identify buildings, roads, bridges, installations
   - Type and condition
   - Strategic importance

4. **Terrain**: Describe the terrain and environment
   - Type (urban, rural, desert, forest, etc.)
   - Tactical implications

5. **Threat Assessment**: Evaluate any potential threats visible
   - Classification (friendly/hostile/unknown)
   - Threat level (critical/high/medium/low/none)

6. **Additional Observations**: Any other tactically relevant information

Format your response clearly with headers and bullet points.
"""
        
        elif analysis_type == "asset_detection":
            prompt = """
Perform detailed military asset detection on this image:

For EACH asset detected, provide:
- **Asset Type**: (aircraft, tank, APC, artillery, truck, vessel, etc.)
- **Classification**: Friendly/Hostile/Unknown (if identifiable)
- **Quantity**: How many of this type are visible
- **Location**: Approximate position in image (center, left, right, top, bottom)
- **Heading**: Direction of travel/orientation if visible
- **Status**: Active/stationary/abandoned/damaged
- **Confidence**: High/Medium/Low

If NO military assets are detected, explicitly state that.

Format as a structured list for easy parsing.
"""
        
        elif analysis_type == "terrain":
            prompt = """
Analyze the terrain and geographic features in this image:

1. **Terrain Type**: (urban, suburban, rural, desert, forest, mountain, coastal, etc.)
2. **Elevation**: Flat, hilly, mountainous (estimate if possible)
3. **Vegetation**: Dense forest, sparse trees, grassland, barren, etc.
4. **Water Features**: Rivers, lakes, coastline (if any)
5. **Roads/Paths**: Quality and type of transportation routes visible
6. **Cover and Concealment**: Natural/artificial cover available
7. **Tactical Advantages**: What tactical advantages does this terrain provide?
8. **Tactical Disadvantages**: What tactical disadvantages or risks?
9. **Mobility**: Assessment of vehicle and personnel mobility

Provide a tactical assessment focused on operational implications.
"""
        
        elif analysis_type == "damage":
            prompt = """
Perform damage assessment on this image:

1. **Structures Affected**: List all damaged buildings/infrastructure
   - Damage Level: (destroyed/heavily damaged/moderately damaged/lightly damaged/intact)
   - Type of structure

2. **Equipment/Vehicles**: Any damaged or destroyed equipment visible
   - Asset type
   - Damage extent

3. **Overall Assessment**: 
   - Total structures assessed
   - Percentage destroyed/damaged
   - Most critical damage

4. **Operational Impact**: How does this damage affect tactical operations?

5. **Potential Causes**: What likely caused this damage? (combat, natural disaster, etc.)

Be specific and quantitative where possible.
"""
        
        else:
            return f"""
IMAGE ANALYSIS REPORT
=====================
File: {Path(image_path).name}
Status: FAILED

ERROR: Invalid analysis_type '{analysis_type}'. 
Valid types: general, asset_detection, terrain, damage, custom
=====================
"""
        
        # Perform analysis
        result = analyze_image_with_gpt4v(
            image_path=image_path,
            prompt=prompt,
            model=model,
            max_tokens=1500 if analysis_type == "general" else 1000
        )
        
        # Format output
        file_name = Path(image_path).name
        
        if not result["success"]:
            return f"""
IMAGE ANALYSIS REPORT
=====================
File: {file_name}
Analysis Type: {analysis_type}
Status: FAILED

ERROR: {result['error']}
=====================
"""
        
        # Success
        return f"""
IMAGE ANALYSIS REPORT
=====================
File: {file_name}
Analysis Type: {analysis_type}
Model: {result['model_used']}
Status: SUCCESS

ANALYSIS:
---------
{result['analysis']}

=====================
"""
        
    except Exception as e:
        return f"""
IMAGE ANALYSIS REPORT
=====================
File: {Path(image_path).name}
Status: CRITICAL ERROR

ERROR: {str(e)}
=====================
"""


# ==================== UTILITY FUNCTIONS ====================

def is_image_file(file_path: str) -> bool:
    """
    Check if file is a supported image format
    
    Args:
        file_path: Path to check
        
    Returns:
        True if supported image file
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif'}
    return Path(file_path).suffix.lower() in image_extensions


def get_image_dimensions(image_path: str) -> Optional[tuple[int, int]]:
    """
    Get image dimensions (width, height) without loading full image
    
    Args:
        image_path: Path to image
        
    Returns:
        (width, height) tuple or None if error
    """
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size  # Returns (width, height)
    except Exception:
        return None


def resize_image_if_needed(
    image_path: str,
    max_size_mb: float = 20.0,
    output_path: Optional[str] = None
) -> str:
    """
    Resize image if it exceeds max size (for GPT-4V limits)
    
    Args:
        image_path: Path to original image
        max_size_mb: Maximum size in megabytes
        output_path: Where to save resized image (None = overwrite original)
        
    Returns:
        Path to final image (original or resized)
    """
    try:
        from PIL import Image
        
        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        
        if file_size_mb <= max_size_mb:
            return image_path  # No resize needed
        
        # Calculate scaling factor
        scale_factor = (max_size_mb / file_size_mb) ** 0.5
        
        # Resize
        with Image.open(image_path) as img:
            new_width = int(img.width * scale_factor)
            new_height = int(img.height * scale_factor)
            
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save
            save_path = output_path or image_path
            resized_img.save(save_path, quality=85, optimize=True)
            
            print(f"🖼️  Resized image: {file_size_mb:.1f}MB → {os.path.getsize(save_path) / (1024*1024):.1f}MB")
            return save_path
            
    except Exception as e:
        print(f"❌ Failed to resize image: {e}")
        return image_path  # Return original on error