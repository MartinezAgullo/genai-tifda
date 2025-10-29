"""
Human Review Node
=================

Eighth node in the TIFDA pipeline - Human-in-the-Loop (HITL) review.

This node:
1. Presents threat assessments to human operators for review
2. Collects approve/reject/modify decisions
3. Implements configurable review policies (auto-approve, require review)
4. Stores operator feedback for learning
5. Routes approved threats to dissemination

This is where humans validate AI assessments - critical for maintaining
trust and accountability in tactical decision-making.

Current Implementation:
- MOCK MODE: Auto-approves threats based on configurable policy
- Records simulated operator decisions
- Ready for integration with real UI (Gradio, web interface)

Future Integration:
- Real-time operator interface
- Multi-operator consensus
- Feedback collection for model improvement

Node Signature:
    Input: TIFDAState with current_threats
    Output: Updated TIFDAState with approved_threats and review_log
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import time

from langsmith import traceable

from src.core.state import TIFDAState, log_decision, add_notification
from src.models import ThreatAssessment

# Configure logging
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

# Review policy
REVIEW_POLICY = "auto_approve_high"  # Options: "require_all", "auto_approve_low", "auto_approve_high"

# Auto-approval thresholds
AUTO_APPROVE_CONFIDENCE_THRESHOLD = 0.85  # Auto-approve if confidence >= 0.85
AUTO_APPROVE_THREAT_LEVELS = ["low"]  # Auto-approve these threat levels

# Mock review delay (simulates operator review time)
MOCK_REVIEW_DELAY_SEC = 0.5  # 500ms per threat

# Operator information (mock)
MOCK_OPERATOR_ID = "operator_alpha"
MOCK_OPERATOR_RANK = "Captain"


# ==================== REVIEW POLICIES ====================

def _should_require_review(threat: ThreatAssessment, policy: str) -> bool:
    """
    Determine if a threat requires human review based on policy.
    
    Args:
        threat: ThreatAssessment to check
        policy: Review policy name
        
    Returns:
        True if human review required, False if can auto-approve
    """
    if policy == "require_all":
        # All threats require review
        return True
    
    elif policy == "auto_approve_low":
        # Auto-approve low and none, require review for medium/high/critical
        return threat.threat_level not in ["low", "none"]
    
    elif policy == "auto_approve_high":
        # Auto-approve if high confidence AND low/none threat
        # Require review for medium/high/critical OR low confidence
        is_low_threat = threat.threat_level in AUTO_APPROVE_THREAT_LEVELS
        is_high_confidence = threat.confidence >= AUTO_APPROVE_CONFIDENCE_THRESHOLD
        
        return not (is_low_threat and is_high_confidence)
    
    else:
        # Unknown policy - default to requiring review
        logger.warning(f"⚠️  Unknown review policy: {policy}, defaulting to require_all")
        return True


def _mock_operator_review(threat: ThreatAssessment) -> Dict[str, Any]:
    """
    Simulate operator review of threat assessment.
    
    This is a MOCK implementation that simulates an operator reviewing
    the threat and making a decision. In production, this would be replaced
    with a real UI interaction (Gradio, web interface, etc.)
    
    Mock Decision Logic:
    - CRITICAL/HIGH threats → Always approved
    - MEDIUM threats → Approved if confidence > 0.7
    - LOW threats → Approved if confidence > 0.6
    - NONE threats → Rejected
    
    Args:
        threat: ThreatAssessment to review
        
    Returns:
        Review decision dictionary:
            - approved: bool
            - action: str (approve/reject/modify)
            - operator_id: str
            - operator_comments: str
            - review_timestamp: datetime
            - review_duration_sec: float
    """
    # Simulate review time
    review_start = time.time()
    time.sleep(MOCK_REVIEW_DELAY_SEC)
    review_end = time.time()
    
    # Mock decision logic
    if threat.threat_level == "critical":
        approved = True
        action = "approve"
        comments = "CRITICAL threat confirmed - immediate action authorized"
    
    elif threat.threat_level == "high":
        approved = True
        action = "approve"
        comments = "HIGH threat confirmed - dissemination approved"
    
    elif threat.threat_level == "medium":
        if threat.confidence > 0.7:
            approved = True
            action = "approve"
            comments = "MEDIUM threat approved - monitor situation"
        else:
            approved = False
            action = "reject"
            comments = "MEDIUM threat rejected - insufficient confidence, requires additional intelligence"
    
    elif threat.threat_level == "low":
        if threat.confidence > 0.6:
            approved = True
            action = "approve"
            comments = "LOW threat approved for information sharing"
        else:
            approved = False
            action = "reject"
            comments = "LOW threat rejected - low confidence assessment"
    
    else:  # "none"
        approved = False
        action = "reject"
        comments = "No threat detected - dissemination not required"
    
    return {
        "approved": approved,
        "action": action,
        "operator_id": MOCK_OPERATOR_ID,
        "operator_rank": MOCK_OPERATOR_RANK,
        "operator_comments": comments,
        "review_timestamp": datetime.utcnow(),
        "review_duration_sec": review_end - review_start,
        "review_mode": "mock"  # Indicates this was a simulated review
    }


@traceable(name="human_review_node")
def human_review_node(state: TIFDAState) -> Dict[str, Any]:
    """
    Human-in-the-Loop review node.
    
    Presents threat assessments to human operators for validation.
    Operators can approve, reject, or modify threat assessments before
    dissemination to downstream systems.
    
    Current Implementation: MOCK MODE
    - Simulates operator review with configurable policy
    - Auto-approves based on threat level and confidence
    - Records review decisions for audit
    
    Future Integration Points:
    - Replace mock with real UI (Gradio, Streamlit, web interface)
    - Multi-operator consensus mechanism
    - Feedback collection for model improvement
    - Integration with command center displays
    
    Review Policies:
    - "require_all": All threats require operator review
    - "auto_approve_low": Auto-approve low/none, review medium+
    - "auto_approve_high": Auto-approve low threats with high confidence
    
    Args:
        state: Current TIFDA state containing:
            - current_threats: List[ThreatAssessment] from threat_evaluator_node
        
    Returns:
        Dictionary with updated state fields:
            - approved_threats: List[ThreatAssessment] (approved for dissemination)
            - rejected_threats: List[ThreatAssessment] (not approved)
            - review_log: List[Dict] (operator review decisions)
            - decision_reasoning: str (markdown)
            - notification_queue: List[str]
            - decision_log: List[Dict]
    """
    logger.info("=" * 70)
    logger.info("HUMAN REVIEW NODE - HITL Threat Validation")
    logger.info("=" * 70)
    
    # ============ VALIDATION ============
    
    current_threats = state.get("current_threats", [])
    sensor_metadata = state.get("sensor_metadata", {})
    sensor_id = sensor_metadata.get("sensor_id", "unknown")
    
    if not current_threats:
        logger.info("✅ No threats to review")
        return {
            "approved_threats": [],
            "rejected_threats": [],
            "review_log": [],
            "decision_reasoning": "## ✅ No Threats to Review\n\nNo threat assessments from previous node."
        }
    
    logger.info(f"📋 Reviewing {len(current_threats)} threat assessments")
    logger.info(f"   Policy: {REVIEW_POLICY}")
    logger.info(f"   Mode: MOCK (simulated operator)")
    
    # ============ CATEGORIZE THREATS ============
    
    # Separate threats by review requirement
    auto_approved_threats = []
    requires_review_threats = []
    
    for threat in current_threats:
        if _should_require_review(threat, REVIEW_POLICY):
            requires_review_threats.append(threat)
        else:
            auto_approved_threats.append(threat)
    
    logger.info(f"\n📊 Review categorization:")
    logger.info(f"   Auto-approved: {len(auto_approved_threats)}")
    logger.info(f"   Requires review: {len(requires_review_threats)}")
    
    # ============ PROCESS REVIEWS ============
    
    approved_threats = []
    rejected_threats = []
    review_log = []
    
    # Auto-approved threats
    for threat in auto_approved_threats:
        logger.info(f"\n✅ Auto-approved: {threat.threat_source_id} ({threat.threat_level})")
        logger.info(f"   Confidence: {threat.confidence:.2f}")
        
        approved_threats.append(threat)
        
        review_log.append({
            "assessment_id": threat.assessment_id,
            "threat_source_id": threat.threat_source_id,
            "threat_level": threat.threat_level,
            "approved": True,
            "action": "auto_approve",
            "operator_id": "system",
            "operator_comments": f"Auto-approved based on policy: {REVIEW_POLICY}",
            "review_timestamp": datetime.utcnow(),
            "review_duration_sec": 0.0,
            "review_mode": "auto"
        })
    
    # Threats requiring operator review (MOCK)
    for threat in requires_review_threats:
        logger.info(f"\n🔍 Reviewing: {threat.threat_source_id} ({threat.threat_level})")
        logger.info(f"   Confidence: {threat.confidence:.2f}")
        logger.info(f"   Reasoning: {threat.reasoning[:100]}...")
        
        # Get mock operator review
        review_decision = _mock_operator_review(threat)
        
        logger.info(f"   ✅ Decision: {review_decision['action'].upper()}")
        logger.info(f"   👤 Operator: {review_decision['operator_id']} ({review_decision['operator_rank']})")
        logger.info(f"   💬 Comments: {review_decision['operator_comments']}")
        
        # Store review
        review_log.append({
            "assessment_id": threat.assessment_id,
            "threat_source_id": threat.threat_source_id,
            "threat_level": threat.threat_level,
            **review_decision
        })
        
        # Categorize result
        if review_decision["approved"]:
            approved_threats.append(threat)
        else:
            rejected_threats.append(threat)
    
    # ============ RESULTS ============
    
    logger.info(f"\n📊 Review complete:")
    logger.info(f"   ✅ Approved: {len(approved_threats)}")
    logger.info(f"   ❌ Rejected: {len(rejected_threats)}")
    logger.info(f"   📝 Reviews logged: {len(review_log)}")
    
    # ============ BUILD REASONING ============
    
    reasoning = f"""## 👤 Human Review Complete

**Sensor**: `{sensor_id}`
**Threats Reviewed**: {len(current_threats)}
**Review Policy**: `{REVIEW_POLICY}`
**Review Mode**: MOCK (simulated operator)

### Review Summary:
- ✅ **Approved**: {len(approved_threats)}
- ❌ **Rejected**: {len(rejected_threats)}

"""
    
    if auto_approved_threats:
        reasoning += f"### Auto-Approved Threats ({len(auto_approved_threats)}):\n"
        for threat in auto_approved_threats:
            reasoning += f"- `{threat.threat_source_id}` ({threat.threat_level}) - Auto-approved by policy\n"
        reasoning += "\n"
    
    if requires_review_threats:
        reasoning += f"### Operator-Reviewed Threats ({len(requires_review_threats)}):\n"
        
        for threat in requires_review_threats:
            # Find review decision
            review = next(r for r in review_log if r["assessment_id"] == threat.assessment_id)
            
            icon = "✅" if review["approved"] else "❌"
            reasoning += f"{icon} **{threat.threat_source_id}** ({threat.threat_level})\n"
            reasoning += f"  - Decision: {review['action'].upper()}\n"
            reasoning += f"  - Operator: {review['operator_id']}\n"
            reasoning += f"  - Comments: {review['operator_comments']}\n"
            reasoning += "\n"
    
    if not approved_threats:
        reasoning += "⚠️  **No threats approved for dissemination**\n\n"
    else:
        # Count by threat level
        approved_by_level = {
            "critical": sum(1 for t in approved_threats if t.threat_level == "critical"),
            "high": sum(1 for t in approved_threats if t.threat_level == "high"),
            "medium": sum(1 for t in approved_threats if t.threat_level == "medium"),
            "low": sum(1 for t in approved_threats if t.threat_level == "low")
        }
        
        reasoning += "### Approved for Dissemination:\n"
        if approved_by_level["critical"] > 0:
            reasoning += f"- 🔴 CRITICAL: {approved_by_level['critical']}\n"
        if approved_by_level["high"] > 0:
            reasoning += f"- 🟠 HIGH: {approved_by_level['high']}\n"
        if approved_by_level["medium"] > 0:
            reasoning += f"- 🟡 MEDIUM: {approved_by_level['medium']}\n"
        if approved_by_level["low"] > 0:
            reasoning += f"- 🟢 LOW: {approved_by_level['low']}\n"
        reasoning += "\n"
    
    reasoning += """
### 📝 Review Notes:
- Current implementation uses MOCK operator (simulated decisions)
- Ready for integration with real UI (Gradio, Streamlit, web interface)
- All review decisions logged for audit trail

**Next**: Route to `dissemination_router_node` for access control and distribution
"""
    
    # ============ UPDATE STATE ============
    
    # Log decision
    log_decision(
        state=state,
        node_name="human_review_node",
        decision_type="human_review",
        reasoning=f"Reviewed {len(current_threats)} threats: {len(approved_threats)} approved, {len(rejected_threats)} rejected",
        data={
            "sensor_id": sensor_id,
            "threats_reviewed": len(current_threats),
            "approved": len(approved_threats),
            "rejected": len(rejected_threats),
            "auto_approved": len(auto_approved_threats),
            "operator_reviewed": len(requires_review_threats),
            "review_policy": REVIEW_POLICY,
            "review_mode": "mock"
        }
    )
    
    # Add notifications
    if approved_threats:
        # Count critical/high threats
        critical_high = sum(1 for t in approved_threats if t.threat_level in ["critical", "high"])
        
        if critical_high > 0:
            add_notification(
                state,
                f"✅ Operator approved {critical_high} critical/high threat(s) for dissemination"
            )
        
        if len(approved_threats) > critical_high:
            add_notification(
                state,
                f"✅ {len(approved_threats) - critical_high} medium/low threat(s) approved"
            )
    
    if rejected_threats:
        add_notification(
            state,
            f"❌ Operator rejected {len(rejected_threats)} threat(s)"
        )
    
    logger.info("\n" + "=" * 70)
    logger.info(f"Review complete: {len(approved_threats)} approved, {len(rejected_threats)} rejected")
    logger.info("=" * 70 + "\n")
    
    # Return state updates
    return {
        "approved_threats": approved_threats,
        "rejected_threats": rejected_threats,
        "review_log": review_log,
        "decision_reasoning": reasoning
    }


# ==================== TESTING ====================

def test_human_review_node():
    """Test the human review node"""
    from src.core.state import create_initial_state
    from src.models import Location
    
    print("\n" + "=" * 70)
    print("HUMAN REVIEW NODE TEST")
    print("=" * 70 + "\n")
    
    # Test 1: Mix of threat levels
    print("Test 1: Review multiple threat levels")
    print("-" * 70)
    
    state = create_initial_state()
    state["sensor_metadata"] = {"sensor_id": "radar_01"}
    
    # Create threat assessments
    state["current_threats"] = [
        ThreatAssessment(
            assessment_id="threat_001",
            threat_level="critical",
            affected_entities=["base_alpha"],
            threat_source_id="hostile_aircraft_001",
            reasoning="Hostile aircraft on intercept course with base",
            confidence=0.95,
            timestamp=datetime.utcnow()
        ),
        ThreatAssessment(
            assessment_id="threat_002",
            threat_level="high",
            affected_entities=["patrol_bravo"],
            threat_source_id="hostile_vehicle_002",
            reasoning="Hostile ground vehicle approaching patrol",
            confidence=0.85,
            timestamp=datetime.utcnow()
        ),
        ThreatAssessment(
            assessment_id="threat_003",
            threat_level="medium",
            affected_entities=["radar_01"],
            threat_source_id="unknown_aircraft_003",
            reasoning="Unknown aircraft in restricted airspace",
            confidence=0.65,
            timestamp=datetime.utcnow()
        ),
        ThreatAssessment(
            assessment_id="threat_004",
            threat_level="low",
            affected_entities=[],
            threat_source_id="unknown_vehicle_004",
            reasoning="Unknown vehicle far from operations",
            confidence=0.90,
            timestamp=datetime.utcnow()
        )
    ]
    
    result = human_review_node(state)
    
    print(f"Threats reviewed: {len(state['current_threats'])}")
    print(f"Approved: {len(result['approved_threats'])}")
    print(f"Rejected: {len(result['rejected_threats'])}")
    print(f"Reviews logged: {len(result['review_log'])}")
    
    print(f"\nApproved threats:")
    for threat in result['approved_threats']:
        print(f"  - {threat.threat_source_id} ({threat.threat_level})")
    
    print(f"\nRejected threats:")
    for threat in result['rejected_threats']:
        print(f"  - {threat.threat_source_id} ({threat.threat_level})")
    
    print(f"\nReasoning preview:\n{result['decision_reasoning'][:500]}...")
    
    # Test 2: No threats
    print("\n" + "=" * 70)
    print("Test 2: No threats to review")
    print("-" * 70)
    
    state = create_initial_state()
    state["current_threats"] = []
    
    result = human_review_node(state)
    
    print(f"Approved: {len(result['approved_threats'])}")
    print(f"Reasoning: {result['decision_reasoning'][:100]}...")
    
    print("\n" + "=" * 70)
    print("HUMAN REVIEW NODE TEST COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_human_review_node()