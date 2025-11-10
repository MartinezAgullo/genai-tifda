"""
Pipeline Visualization Extension for Gradio UI
===============================================

Adds a "Pipeline Flow" tab showing real-time node execution and data flow.

This extends the existing gradio_interface.py with visualization.
Add this code to your gradio_interface.py in the create_interface() function.
"""

import gradio as gr
from datetime import datetime, timezone
from typing import Dict, List, Any

# ==================== PIPELINE MONITORING ====================

class PipelineMonitor:
    """Monitor pipeline execution in real-time"""
    
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.max_events = 100
    
    def add_event(self, node: str, event_type: str, data: Dict[str, Any]):
        """Add a pipeline event"""
        self.events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": node,
            "event_type": event_type,
            "data": data
        })
        
        # Keep only last N events
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def get_recent_events(self, n: int = 50) -> List[Dict[str, Any]]:
        """Get recent events"""
        return self.events[-n:]
    
    def clear(self):
        """Clear all events"""
        self.events = []


# Global monitor instance
pipeline_monitor = PipelineMonitor()


# ==================== VISUALIZATION FUNCTIONS ====================

def get_pipeline_nodes() -> List[str]:
    """Get list of TIFDA pipeline nodes"""
    return [
        "firewall",
        "parser",
        "multimodal",
        "normalizer",
        "merge",
        "cop_update",
        "threat_eval",
        "human_review",
        "dissemination_router",
        "format_adapter",
        "transmission"
    ]


def format_pipeline_diagram() -> str:
    """
    Create visual pipeline diagram showing data flow.
    
    Returns:
        HTML string with pipeline visualization
    """
    nodes = get_pipeline_nodes()
    
    html = """
    <div style='background: #1a1a1a; padding: 30px; border-radius: 12px;'>
        <h2 style='color: #fff; margin-top: 0;'>TIFDA Pipeline Architecture</h2>
        <div style='display: flex; flex-direction: column; gap: 15px;'>
    """
    
    node_descriptions = {
        "firewall": "🛡️ Security validation & input sanitization",
        "parser": "📄 Text parsing & entity extraction",
        "multimodal": "🖼️ Image/Audio/Video processing",
        "normalizer": "📏 COP format normalization",
        "merge": "🔀 Duplicate detection & fusion",
        "cop_update": "🗺️ Common Operational Picture update",
        "threat_eval": "⚠️ Threat assessment (LLM)",
        "human_review": "👤 Human-in-the-loop review",
        "dissemination_router": "🔐 Access control & routing",
        "format_adapter": "📝 Format conversion (Link16, JSON)",
        "transmission": "📡 MQTT/API transmission"
    }
    
    for i, node in enumerate(nodes):
        description = node_descriptions.get(node, "")
        
        # Node card
        html += f"""
        <div style='
            display: flex;
            align-items: center;
            background: #2a2a2a;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        '>
            <div style='flex: 1;'>
                <div style='color: #fff; font-weight: bold; font-size: 16px;'>
                    {i+1}. {node.upper()}
                </div>
                <div style='color: #999; font-size: 14px; margin-top: 5px;'>
                    {description}
                </div>
            </div>
            <div style='
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: #667eea;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
            '>
                {i+1}
            </div>
        </div>
        """
        
        # Arrow (except for last node)
        if i < len(nodes) - 1:
            html += """
            <div style='text-align: center; color: #667eea; font-size: 24px;'>
                ↓
            </div>
            """
    
    html += """
        </div>
    </div>
    """
    
    return html


def format_event_log() -> str:
    """
    Format recent pipeline events as a log.
    
    Returns:
        HTML string with event log
    """
    events = pipeline_monitor.get_recent_events(50)
    
    if not events:
        return """
        <div style='padding: 20px; text-align: center; color: #666;'>
            📭 No pipeline events yet. Run a test to see events here.
        </div>
        """
    
    html = "<div style='display: flex; flex-direction: column-reverse; gap: 10px;'>"
    
    for event in reversed(events):
        timestamp = event.get("timestamp", "")
        node = event.get("node", "unknown")
        event_type = event.get("event_type", "")
        data = event.get("data", {})
        
        # Time display (HH:MM:SS)
        time_str = timestamp[11:19] if len(timestamp) > 19 else timestamp
        
        # Color based on event type
        color_map = {
            "start": "#4CAF50",
            "complete": "#2196F3",
            "error": "#f44336",
            "waiting": "#FF9800"
        }
        color = color_map.get(event_type, "#9E9E9E")
        
        # Icon based on node
        icon_map = {
            "firewall": "🛡️",
            "parser": "📄",
            "threat_eval": "⚠️",
            "human_review": "👤",
            "transmission": "📡"
        }
        icon = icon_map.get(node, "⚙️")
        
        html += f"""
        <div style='
            display: flex;
            gap: 15px;
            padding: 12px;
            background: #f5f5f5;
            border-left: 4px solid {color};
            border-radius: 4px;
            font-family: monospace;
        '>
            <div style='color: #666; font-size: 12px; width: 80px;'>
                {time_str}
            </div>
            <div style='font-size: 18px;'>
                {icon}
            </div>
            <div style='flex: 1;'>
                <div style='font-weight: bold; color: #333;'>
                    {node.upper()}
                </div>
                <div style='color: #666; font-size: 13px;'>
                    {event_type}: {data.get('message', '')}
                </div>
            </div>
        </div>
        """
    
    html += "</div>"
    return html


def format_node_statistics() -> str:
    """
    Show statistics about node execution.
    
    Returns:
        HTML string with node statistics
    """
    events = pipeline_monitor.get_recent_events(100)
    
    if not events:
        return "<div style='padding: 20px; color: #666;'>No statistics available yet</div>"
    
    # Count events per node
    node_counts = {}
    for event in events:
        node = event.get("node", "unknown")
        node_counts[node] = node_counts.get(node, 0) + 1
    
    # Sort by count
    sorted_nodes = sorted(node_counts.items(), key=lambda x: x[1], reverse=True)
    
    html = """
    <div style='background: #f9f9f9; padding: 20px; border-radius: 8px;'>
        <h3 style='margin-top: 0;'>Node Activity (Last 100 Events)</h3>
        <div style='display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;'>
    """
    
    for node, count in sorted_nodes:
        html += f"""
        <div style='
            background: white;
            padding: 15px;
            border-radius: 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        '>
            <div style='font-weight: bold; color: #333; margin-bottom: 5px;'>
                {node.upper()}
            </div>
            <div style='font-size: 24px; color: #667eea; font-weight: bold;'>
                {count}
            </div>
            <div style='font-size: 12px; color: #999;'>
                events
            </div>
        </div>
        """
    
    html += """
        </div>
    </div>
    """
    
    return html


# ==================== ADD TO create_interface() ====================

def create_pipeline_visualization_tab():
    """
    Create the Pipeline Flow tab.
    
    Add this inside your with gr.Tabs(): block in create_interface()
    """
    with gr.Tab("🔄 Pipeline Flow"):
        gr.Markdown("### Real-time Pipeline Visualization")
        
        # Pipeline diagram
        with gr.Accordion("📊 Pipeline Architecture", open=True):
            pipeline_diagram = gr.HTML(format_pipeline_diagram())
        
        # Node statistics
        with gr.Accordion("📈 Node Statistics", open=False):
            stats_html = gr.HTML(format_node_statistics())
        
        # Event log
        gr.Markdown("### 📜 Event Log (Real-time)")
        event_log_html = gr.HTML(format_event_log())
        
        # Refresh buttons
        with gr.Row():
            refresh_log_btn = gr.Button("🔄 Refresh Log")
            clear_log_btn = gr.Button("🗑️ Clear Log")
        
        # Wire up buttons
        refresh_log_btn.click(
            lambda: (format_event_log(), format_node_statistics()),
            inputs=[],
            outputs=[event_log_html, stats_html]
        )
        
        clear_log_btn.click(
            lambda: (pipeline_monitor.clear(), format_event_log(), format_node_statistics()),
            inputs=[],
            outputs=[event_log_html, stats_html]
        )
    
    return event_log_html, stats_html


# ==================== USAGE INSTRUCTIONS ====================

"""
To add this to your gradio_interface.py:

1. Add these imports at the top:
   from datetime import datetime, timezone
   from typing import Dict, List, Any

2. Copy the PipelineMonitor class and format functions

3. In create_interface(), find the line:
   with gr.Tabs():

4. After your existing tabs, add:
   
   # ============ TAB 3: PIPELINE FLOW ============
   event_log_html, stats_html = create_pipeline_visualization_tab()

5. To log events from your pipeline nodes, add this to each node:
   
   from src.ui.gradio_interface import pipeline_monitor
   
   pipeline_monitor.add_event(
       node="threat_eval",
       event_type="complete",
       data={"message": f"Evaluated {len(threats)} threats", "count": len(threats)}
   )

6. Done! The Pipeline Flow tab will show real-time events.
"""