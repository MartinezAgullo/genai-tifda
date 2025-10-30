"""
TIFDA Application
=================
Complete pipeline from sensor input to dissemination.
"""

from dotenv import load_dotenv
load_dotenv()               

from datetime import datetime
from langgraph.graph import StateGraph, END
from src.core.state import TIFDAState, create_state_from_sensor_event
from src.models.sensor_formats import SensorMessage

# Import all nodes
from src.nodes.firewall_node import firewall_node
from src.nodes.parser_node import parser_node, should_route_to_multimodal
from src.nodes.multimodal_parser_node import multimodal_parser_node
from src.nodes.cop_normalizer_node import cop_normalizer_node
from src.nodes.cop_merge_node import cop_merge_node
from src.nodes.cop_update_node import cop_update_node
from src.nodes.threat_evaluator_node import threat_evaluator_node
from src.nodes.human_review_node import human_review_node
from src.nodes.dissemination_router_node import dissemination_router_node
from src.nodes.format_adapter_node import format_adapter_node
from src.nodes.transmission_node import transmission_node


def create_tifda_graph():
    """Create the complete TIFDA graph."""
    graph = StateGraph(TIFDAState)
    
    # Add all nodes
    graph.add_node("firewall", firewall_node)
    graph.add_node("parser", parser_node)
    graph.add_node("multimodal", multimodal_parser_node)
    graph.add_node("normalizer", cop_normalizer_node)
    graph.add_node("merge", cop_merge_node)
    graph.add_node("cop_update", cop_update_node)
    graph.add_node("threat_eval", threat_evaluator_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("dissemination_router", dissemination_router_node)
    graph.add_node("format_adapter", format_adapter_node)
    graph.add_node("transmission", transmission_node)
    
    # Set entry point
    graph.set_entry_point("firewall")
    
    # Phase 1 edges
    graph.add_conditional_edges(
        "firewall",
        lambda s: "parser" if s["firewall_passed"] else END,
        {"parser": "parser", END: END}
    )
    
    graph.add_conditional_edges(
        "parser",
        should_route_to_multimodal,
        {"multimodal": "multimodal", "normalizer": "normalizer"}
    )
    
    graph.add_edge("multimodal", "normalizer")
    graph.add_edge("normalizer", "merge")
    graph.add_edge("merge", "cop_update")
    
    # Phase 2 edges
    graph.add_edge("cop_update", "threat_eval")
    graph.add_edge("threat_eval", "human_review")
    graph.add_edge("human_review", "dissemination_router")
    graph.add_edge("dissemination_router", "format_adapter")
    graph.add_edge("format_adapter", "transmission")
    graph.add_edge("transmission", END)
    
    return graph.compile()


# Create the app
tifda_app = create_tifda_graph()

def run_pipeline(sensor_input: dict) -> dict:
    """
    Run complete TIFDA pipeline from sensor input to dissemination.
    
    Args:
        sensor_input: Dict with sensor data
            {
                "sensor_id": str,
                "sensor_type": str,
                "data": str or dict,
                "timestamp": str (optional),
                "metadata": dict (optional)
            }
    
    Returns:
        Final state dict with results
    
    Example:
        result = run_pipeline({
            "sensor_id": "radar_01",
            "sensor_type": "radar",
            "data": "Aircraft at 39.5N, 0.4W"
        })
    """
    # Convert dict to SensorMessage if needed
    if isinstance(sensor_input, dict):
        sensor_message = SensorMessage(
            sensor_id=sensor_input.get("sensor_id", "unknown"),
            sensor_type=sensor_input.get("sensor_type", "unknown"),
            timestamp=sensor_input.get("timestamp", datetime.utcnow().isoformat()),
            data=sensor_input.get("data", ""),
            metadata=sensor_input.get("metadata", {})
        )
    else:
        sensor_message = sensor_input
    
    # Create initial state from sensor message
    initial_state = create_state_from_sensor_event(sensor_message)
    
    # Run the graph
    final_state = tifda_app.invoke(initial_state)
    
    return final_state