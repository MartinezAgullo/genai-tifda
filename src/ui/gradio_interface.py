"""
Gradio Human Review Interface
==============================

Real-time UI for human-in-the-loop threat review.

Features:
- View pending threats sorted by priority
- Approve/Reject/Flag individual threats
- Add operator comments
- Review dissemination recipients
- Approve all with one click
- Auto-refresh every 5 seconds
- Review history tab
"""

import gradio as gr
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.core.config import get_config
from src.ui.review_service import ReviewService

logger = logging.getLogger(__name__)


# ==================== CONFIGURATION ====================

config = get_config()
review_service = ReviewService(config.shared_state_file)

THREAT_COLORS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "none": "⚪"
}

PRIORITY_ORDER = ["critical", "high", "medium", "low", "none"]


# ==================== STATE MANAGEMENT ====================

class UIState:
    """Global UI state"""
    selected_threat_id: Optional[str] = None
    review_history: List[Dict[str, Any]] = []
    last_refresh: Optional[datetime] = None


ui_state = UIState()


# ==================== DATA FETCHING ====================

def fetch_pending_threats() -> List[Dict[str, Any]]:
    """
    Fetch pending threats from review service.
    
    Returns:
        List of threat dictionaries sorted by priority
    """
    pending = review_service.get_pending_items()
    
    # Filter only threat assessments
    threats = [item for item in pending if item.get("item_type") == "threat_assessment"]
    
    # Sort by priority (critical first)
    def threat_priority(threat: Dict) -> int:
        level = threat.get("threat_level", "none")
        try:
            return PRIORITY_ORDER.index(level)
        except ValueError:
            return 999
    
    threats.sort(key=threat_priority)
    
    return threats


def fetch_pending_dissemination() -> List[Dict[str, Any]]:
    """
    Fetch pending dissemination decisions.
    
    Returns:
        List of dissemination decision dictionaries
    """
    pending = review_service.get_pending_items()
    
    # Filter only dissemination decisions
    decisions = [item for item in pending if item.get("item_type") == "dissemination"]
    
    return decisions


def get_statistics() -> Dict[str, int]:
    """
    Get review statistics.
    
    Returns:
        Dictionary with counts by threat level
    """
    threats = fetch_pending_threats()
    
    stats = {
        "total": len(threats),
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0
    }
    
    for threat in threats:
        level = threat.get("threat_level", "none")
        if level in stats:
            stats[level] += 1
    
    return stats


# ==================== UI COMPONENTS ====================

def format_threat_list() -> str:
    """
    Format threat list for display.
    
    Returns:
        HTML string with threat cards
    """
    threats = fetch_pending_threats()
    
    if not threats:
        return "<div style='padding: 20px; text-align: center; color: #666;'>✅ No pending threats</div>"
    
    html = "<div style='display: flex; flex-direction: column; gap: 10px;'>"
    
    for threat in threats:
        threat_id = threat.get("item_id", "unknown")
        threat_level = threat.get("threat_level", "none")
        source_id = threat.get("threat_source_id", "Unknown")
        confidence = threat.get("confidence", 0) * 100
        
        color_map = {
            "critical": "#ff4444",
            "high": "#ff8800",
            "medium": "#ffcc00",
            "low": "#44ff44",
            "none": "#cccccc"
        }
        color = color_map.get(threat_level, "#cccccc")
        
        emoji = THREAT_COLORS.get(threat_level, "⚪")
        
        html += f"""
        <div style='
            border: 2px solid {color};
            border-radius: 8px;
            padding: 15px;
            background: white;
            cursor: pointer;
        ' onclick='selectThreat("{threat_id}")'>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
                <div>
                    <span style='font-size: 20px;'>{emoji}</span>
                    <strong style='font-size: 16px; margin-left: 10px;'>{threat_level.upper()}</strong>
                </div>
                <div style='color: #666; font-size: 14px;'>
                    Confidence: {confidence:.0f}%
                </div>
            </div>
            <div style='margin-top: 10px; color: #333;'>
                Source: <code>{source_id}</code>
            </div>
            <div style='margin-top: 5px; font-size: 12px; color: #666;'>
                ID: {threat_id}
            </div>
        </div>
        """
    
    html += "</div>"
    return html


def format_threat_details(threat_id: str) -> str:
    """
    Format detailed threat information.
    
    Args:
        threat_id: Threat identifier
        
    Returns:
        HTML string with threat details
    """
    if not threat_id:
        return "<div style='padding: 20px; text-align: center; color: #666;'>Select a threat to view details</div>"
    
    threats = fetch_pending_threats()
    threat = next((t for t in threats if t.get("item_id") == threat_id), None)
    
    if not threat:
        return "<div style='padding: 20px; color: #ff4444;'>⚠️ Threat not found</div>"
    
    level = threat.get("threat_level", "none")
    emoji = THREAT_COLORS.get(level, "⚪")
    confidence = threat.get("confidence", 0) * 100
    source_id = threat.get("threat_source_id", "Unknown")
    reasoning = threat.get("reasoning", "No reasoning provided")
    affected = threat.get("affected_entities", [])
    distances = threat.get("distances_to_affected_km", {})
    
    html = f"""
    <div style='padding: 20px; background: #f5f5f5; border-radius: 8px;'>
        <h2 style='margin-top: 0;'>{emoji} {level.upper()} Threat</h2>
        
        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0;'>
            <div>
                <strong>Source:</strong><br/>
                <code>{source_id}</code>
            </div>
            <div>
                <strong>Confidence:</strong><br/>
                {confidence:.1f}%
            </div>
        </div>
        
        <div style='margin: 20px 0;'>
            <strong>Reasoning:</strong><br/>
            <div style='background: white; padding: 10px; border-radius: 4px; margin-top: 5px;'>
                {reasoning}
            </div>
        </div>
        
        <div style='margin: 20px 0;'>
            <strong>Affected Entities ({len(affected)}):</strong><br/>
            <ul style='background: white; padding: 10px 30px; border-radius: 4px; margin-top: 5px;'>
    """
    
    for entity_id in affected:
        distance = distances.get(entity_id, "unknown")
        if isinstance(distance, (int, float)):
            distance_str = f"{distance:.1f} km"
        else:
            distance_str = "unknown distance"
        html += f"<li><code>{entity_id}</code> - {distance_str}</li>"
    
    html += """
            </ul>
        </div>
    </div>
    """
    
    return html


def format_statistics_banner() -> str:
    """
    Format statistics banner.
    
    Returns:
        HTML string with statistics
    """
    stats = get_statistics()
    
    html = f"""
    <div style='
        display: flex;
        justify-content: space-around;
        padding: 15px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 8px;
        color: white;
        font-weight: bold;
    '>
        <div style='text-align: center;'>
            <div style='font-size: 24px;'>{stats['total']}</div>
            <div style='font-size: 12px; opacity: 0.9;'>TOTAL PENDING</div>
        </div>
        <div style='text-align: center;'>
            <div style='font-size: 24px;'>🔴 {stats['critical']}</div>
            <div style='font-size: 12px; opacity: 0.9;'>CRITICAL</div>
        </div>
        <div style='text-align: center;'>
            <div style='font-size: 24px;'>🟠 {stats['high']}</div>
            <div style='font-size: 12px; opacity: 0.9;'>HIGH</div>
        </div>
        <div style='text-align: center;'>
            <div style='font-size: 24px;'>🟡 {stats['medium']}</div>
            <div style='font-size: 12px; opacity: 0.9;'>MEDIUM</div>
        </div>
    </div>
    """
    
    return html


# ==================== ACTIONS ====================

def approve_threat(threat_id: str, comments: str) -> Tuple[str, str, str]:
    """
    Approve a threat.
    
    Args:
        threat_id: Threat to approve
        comments: Operator comments
        
    Returns:
        Tuple of (status message, updated threat list, updated details)
    """
    if not threat_id:
        return "⚠️ No threat selected", format_threat_list(), ""
    
    decision = {
        "item_id": threat_id,
        "decision": "approve",
        "comments": comments or "Approved by operator",
        "reviewer_id": config.reviewer_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        review_service.submit_decision(decision)
        ui_state.selected_threat_id = None
        
        # Add to history
        ui_state.review_history.insert(0, {
            **decision,
            "threat_id": threat_id
        })
        
        return (
            f"✅ Threat {threat_id} APPROVED",
            format_threat_list(),
            ""
        )
    except Exception as e:
        logger.error(f"Failed to approve threat: {e}")
        return f"❌ Error: {e}", format_threat_list(), format_threat_details(threat_id)


def reject_threat(threat_id: str, comments: str) -> Tuple[str, str, str]:
    """
    Reject a threat.
    
    Args:
        threat_id: Threat to reject
        comments: Operator comments
        
    Returns:
        Tuple of (status message, updated threat list, updated details)
    """
    if not threat_id:
        return "⚠️ No threat selected", format_threat_list(), ""
    
    decision = {
        "item_id": threat_id,
        "decision": "reject",
        "comments": comments or "Rejected by operator",
        "reviewer_id": config.reviewer_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        review_service.submit_decision(decision)
        ui_state.selected_threat_id = None
        
        # Add to history
        ui_state.review_history.insert(0, {
            **decision,
            "threat_id": threat_id
        })
        
        return (
            f"❌ Threat {threat_id} REJECTED",
            format_threat_list(),
            ""
        )
    except Exception as e:
        logger.error(f"Failed to reject threat: {e}")
        return f"❌ Error: {e}", format_threat_list(), format_threat_details(threat_id)


def flag_threat(threat_id: str, comments: str) -> Tuple[str, str, str]:
    """
    Flag a threat for escalation.
    
    Args:
        threat_id: Threat to flag
        comments: Operator comments
        
    Returns:
        Tuple of (status message, updated threat list, updated details)
    """
    if not threat_id:
        return "⚠️ No threat selected", format_threat_list(), ""
    
    decision = {
        "item_id": threat_id,
        "decision": "flag",
        "comments": comments or "Flagged for escalation",
        "reviewer_id": config.reviewer_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        review_service.submit_decision(decision)
        ui_state.selected_threat_id = None
        
        # Add to history
        ui_state.review_history.insert(0, {
            **decision,
            "threat_id": threat_id
        })
        
        return (
            f"🚩 Threat {threat_id} FLAGGED for escalation",
            format_threat_list(),
            ""
        )
    except Exception as e:
        logger.error(f"Failed to flag threat: {e}")
        return f"❌ Error: {e}", format_threat_list(), format_threat_details(threat_id)


def approve_all_threats() -> Tuple[str, str]:
    """
    Approve all pending threats.
    
    Returns:
        Tuple of (status message, updated threat list)
    """
    threats = fetch_pending_threats()
    
    if not threats:
        return "ℹ️ No threats to approve", format_threat_list()
    
    decisions = []
    for threat in threats:
        decisions.append({
            "item_id": threat.get("item_id"),
            "decision": "approve",
            "comments": "Bulk approved by operator",
            "reviewer_id": config.reviewer_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    try:
        review_service.submit_bulk_decisions(decisions)
        
        # Add to history
        for decision in decisions:
            ui_state.review_history.insert(0, decision)
        
        return (
            f"✅ Approved {len(decisions)} threat(s)",
            format_threat_list()
        )
    except Exception as e:
        logger.error(f"Failed to approve all: {e}")
        return f"❌ Error: {e}", format_threat_list()


def select_threat_from_list(threat_id: str) -> str:
    """
    Select a threat from the list.
    
    Args:
        threat_id: Threat ID to select
        
    Returns:
        Formatted threat details
    """
    ui_state.selected_threat_id = threat_id
    return format_threat_details(threat_id)


def refresh_ui() -> Tuple[str, str, str]:
    """
    Refresh all UI components.
    
    Returns:
        Tuple of (statistics, threat list, threat details)
    """
    ui_state.last_refresh = datetime.now(timezone.utc)
    
    return (
        format_statistics_banner(),
        format_threat_list(),
        format_threat_details(ui_state.selected_threat_id) if ui_state.selected_threat_id else ""
    )


def format_review_history() -> str:
    """
    Format review history for display.
    
    Returns:
        HTML string with review history
    """
    if not ui_state.review_history:
        return "<div style='padding: 20px; text-align: center; color: #666;'>No review history yet</div>"
    
    html = "<div style='display: flex; flex-direction: column; gap: 10px;'>"
    
    # Show last 50 items
    for item in ui_state.review_history[:50]:
        decision = item.get("decision", "unknown")
        threat_id = item.get("threat_id", item.get("item_id", "unknown"))
        comments = item.get("comments", "")
        timestamp = item.get("timestamp", "")
        reviewer = item.get("reviewer_id", "unknown")
        
        icon_map = {
            "approve": "✅",
            "reject": "❌",
            "flag": "🚩"
        }
        icon = icon_map.get(decision, "❓")
        
        color_map = {
            "approve": "#44ff44",
            "reject": "#ff4444",
            "flag": "#ffaa00"
        }
        color = color_map.get(decision, "#cccccc")
        
        html += f"""
        <div style='
            border-left: 4px solid {color};
            padding: 15px;
            background: #f9f9f9;
            border-radius: 4px;
        '>
            <div style='display: flex; justify-content: space-between;'>
                <div>
                    <span style='font-size: 18px;'>{icon}</span>
                    <strong style='margin-left: 10px;'>{decision.upper()}</strong>
                </div>
                <div style='color: #666; font-size: 12px;'>
                    {timestamp[:19] if timestamp else ""}
                </div>
            </div>
            <div style='margin-top: 10px;'>
                <code>{threat_id}</code>
            </div>
            <div style='margin-top: 5px; font-size: 14px; color: #666;'>
                {comments}
            </div>
            <div style='margin-top: 5px; font-size: 12px; color: #999;'>
                Reviewer: {reviewer}
            </div>
        </div>
        """
    
    html += "</div>"
    return html


# ==================== GRADIO INTERFACE ====================

def create_interface() -> gr.Blocks:
    """
    Create Gradio interface.
    
    Returns:
        Gradio Blocks interface
    """
    with gr.Blocks(
        title="TIFDA Human Review",
        theme=gr.themes.Soft(),
        css="""
        .container { max-width: 1400px; margin: auto; }
        .threat-card:hover { box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        """
    ) as interface:
        
        gr.Markdown("# 🎯 TIFDA Human Review Interface")
        gr.Markdown("**Real-time threat assessment review for tactical intelligence**")
        
        # Statistics banner
        stats_html = gr.HTML(format_statistics_banner())
        
        # Main tabs
        with gr.Tabs():
            # ============ TAB 1: PENDING REVIEW ============
            with gr.Tab("📋 Pending Review"):
                with gr.Row():
                    # Left: Threat list
                    with gr.Column(scale=1):
                        gr.Markdown("### Threats (Priority Order)")
                        threat_list_html = gr.HTML(format_threat_list())
                        
                        with gr.Row():
                            refresh_btn = gr.Button("🔄 Refresh", size="sm")
                            approve_all_btn = gr.Button("✅ Approve All", size="sm", variant="primary")
                    
                    # Right: Threat details & actions
                    with gr.Column(scale=1):
                        gr.Markdown("### Threat Details")
                        threat_details_html = gr.HTML(
                            "<div style='padding: 20px; text-align: center; color: #666;'>Select a threat to view details</div>"
                        )
                        
                        gr.Markdown("### Actions")
                        
                        # Hidden state for selected threat
                        selected_threat = gr.State(value=None)
                        
                        comments_input = gr.Textbox(
                            label="Operator Comments",
                            placeholder="Add your comments here...",
                            lines=3
                        )
                        
                        with gr.Row():
                            approve_btn = gr.Button("✅ Approve", variant="primary")
                            reject_btn = gr.Button("❌ Reject", variant="stop")
                            flag_btn = gr.Button("🚩 Flag", variant="secondary")
                        
                        status_msg = gr.Textbox(
                            label="Status",
                            value="",
                            interactive=False
                        )
                
                # Note: In real implementation, threat selection from HTML would
                # require JavaScript callback or Gradio's select component
                # For now, user can manually input threat ID or we use first threat
                
                # Wire up buttons
                def approve_action(comments):
                    # Get first pending threat (simplified)
                    threats = fetch_pending_threats()
                    if threats:
                        threat_id = threats[0].get("item_id")
                        return approve_threat(threat_id, comments)
                    return "⚠️ No threats pending", format_threat_list(), ""
                
                def reject_action(comments):
                    threats = fetch_pending_threats()
                    if threats:
                        threat_id = threats[0].get("item_id")
                        return reject_threat(threat_id, comments)
                    return "⚠️ No threats pending", format_threat_list(), ""
                
                def flag_action(comments):
                    threats = fetch_pending_threats()
                    if threats:
                        threat_id = threats[0].get("item_id")
                        return flag_threat(threat_id, comments)
                    return "⚠️ No threats pending", format_threat_list(), ""
                
                approve_btn.click(
                    approve_action,
                    inputs=[comments_input],
                    outputs=[status_msg, threat_list_html, threat_details_html]
                )
                
                reject_btn.click(
                    reject_action,
                    inputs=[comments_input],
                    outputs=[status_msg, threat_list_html, threat_details_html]
                )
                
                flag_btn.click(
                    flag_action,
                    inputs=[comments_input],
                    outputs=[status_msg, threat_list_html, threat_details_html]
                )
                
                refresh_btn.click(
                    refresh_ui,
                    inputs=[],
                    outputs=[stats_html, threat_list_html, threat_details_html]
                )
                
                approve_all_btn.click(
                    approve_all_threats,
                    inputs=[],
                    outputs=[status_msg, threat_list_html]
                )
            
            # ============ TAB 2: REVIEW HISTORY ============
            with gr.Tab("📜 Review History"):
                gr.Markdown("### Recent Decisions")
                history_html = gr.HTML(format_review_history())
                
                history_refresh_btn = gr.Button("🔄 Refresh History")
                history_refresh_btn.click(
                    format_review_history,
                    inputs=[],
                    outputs=[history_html]
                )
        
        # Auto-refresh timer (Gradio 4.x syntax)
        # Create a timer that triggers refresh
        def refresh_on_load():
            return refresh_ui()
        
        interface.load(
            refresh_on_load,
            inputs=None,
            outputs=[stats_html, threat_list_html, threat_details_html]
        )
        
        # Set up periodic refresh using a timer component
        timer = gr.Timer(value=config.ui_refresh_interval)
        timer.tick(
            refresh_ui,
            inputs=None,
            outputs=[stats_html, threat_list_html, threat_details_html]
        )
        
        gr.Markdown("---")
        gr.Markdown(f"**Reviewer:** {config.reviewer_id} | **Auto-refresh:** {config.ui_refresh_interval}s")
    
    return interface


# ==================== MAIN ====================

def launch_ui(share: bool = False):
    """
    Launch Gradio interface.
    
    Args:
        share: Create public share link
    """
    logger.info("=" * 70)
    logger.info("TIFDA HUMAN REVIEW UI")
    logger.info("=" * 70)
    logger.info(f"Reviewer ID: {config.reviewer_id}")
    logger.info(f"Port: {config.ui_port}")
    logger.info(f"Auto-refresh: {config.ui_refresh_interval}s")
    logger.info(f"Shared state: {config.shared_state_file}")
    
    # Check timeout setting
    if config.auto_approve_timeout_seconds > 0:
        logger.warning(f"⏰ Auto-approve timeout: {config.auto_approve_timeout_seconds}s")
    else:
        logger.info("⏰ Auto-approve timeout: DISABLED")
    
    logger.info("=" * 70 + "\n")
    
    interface = create_interface()
    
    interface.launch(
        server_name="0.0.0.0",
        server_port=config.ui_port,
        share=share,
        show_error=True
    )


if __name__ == "__main__":
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Check for share flag
    share = "--share" in sys.argv
    
    launch_ui(share=share)