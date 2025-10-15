# HumanFeedback, ReviewDecision
"""
Human Feedback Models
=====================

Data structures for human-in-the-loop review and feedback.
Used for model-based reflex learning.
"""

from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class HumanFeedback(BaseModel):
    """
    Human feedback on an AI decision
    
    Used to improve threat evaluation and dissemination policy over time.
    """
    feedback_id: str = Field(..., description="Unique feedback identifier")
    timestamp: datetime = Field(..., description="When feedback was provided")
    
    # What decision is being reviewed
    decision_type: Literal["threat_assessment", "dissemination", "classification"] = Field(
        ...,
        description="Type of decision being reviewed"
    )
    decision_id: str = Field(..., description="ID of the original decision")
    
    # Human's evaluation
    approved: bool = Field(..., description="Whether human approved the decision")
    confidence: Optional[float] = Field(
        None,  # Era obligatorio
        ge=0.0,
        le=1.0,
        description="Human's confidence in their own judgment (optional)"
    )
    
    # Corrections (if any)
    corrections: Optional[Dict[str, Any]] = Field(
        None,
        description="Corrections made by human (if decision was modified)"
    )
    
    reasoning: str = Field(..., description="Human's reasoning for approval/rejection")
    
    # Context (for similarity matching in future)
    context_snapshot: Dict = Field(
        ...,
        description="COP state and other context when decision was made"
    )
    
    reviewer_id: str = Field(..., description="ID of the human reviewer")
    
    class Config:
        json_schema_extra = {
            "example": {
                "feedback_id": "feedback_001",
                "timestamp": "2025-10-15T14:35:00Z",
                "decision_type": "threat_assessment",
                "decision_id": "threat_001",
                "approved": False,
                "confidence": 0.95,
                "corrections": {
                    "threat_level": "medium",  # Was "high"
                    "reasoning": "Aircraft identified as civilian medevac"
                },
                "reasoning": "Visual confirmation shows civilian markings, not military",
                "context_snapshot": {"entities": [], "threats": []},
                "reviewer_id": "operator_charlie"
            }
        }


class ReviewDecision(BaseModel):
    """
    Human review decision for items awaiting approval
    """
    review_id: str = Field(..., description="Unique review identifier")
    timestamp: datetime = Field(..., description="When review was conducted")
    
    item_type: Literal["dissemination", "threat_assessment"] = Field(
        ...,
        description="What is being reviewed"
    )
    item_id: str = Field(..., description="ID of item being reviewed")
    
    decision: Literal["approve", "reject", "modify"] = Field(
        ...,
        description="Review decision"
    )
    
    modifications: Optional[Dict[str, Any]] = Field(
        None,
        description="Modifications if decision is 'modify'"
    )
    
    comments: Optional[str] = Field(None, description="Additional comments")
    reviewer_id: str = Field(..., description="ID of reviewer")
    
    class Config:
        json_schema_extra = {
            "example": {
                "review_id": "review_001",
                "timestamp": "2025-10-15T14:35:00Z",
                "item_type": "dissemination",
                "item_id": "diss_001",
                "decision": "approve",
                "modifications": None,
                "comments": "Threat is confirmed, allies must be notified",
                "reviewer_id": "operator_charlie"
            }
        }