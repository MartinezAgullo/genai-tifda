"""
TIFDA Configuration Initialization
===================================

Your custom TIFDA configuration settings.
Modify values here to customize your TIFDA instance.

Usage:
    from src.core.init_config import initialize_config
    config = initialize_config()
"""

from src.core.config import get_config


def initialize_config():
    """
    Initialize TIFDA with your custom configuration.
    
    This function gets the global config singleton and sets your preferred values.
    Call this at the start of your application or tests.
    
    Returns:
        TIFDAConfig: Configured TIFDA instance
        
    Example:
        from src.core.init_config import initialize_config
        from src.tifda_app import run_pipeline
        
        config = initialize_config()
        result = run_pipeline(sensor_input)
    """
    config = get_config()
    
    # ============ SYSTEM CONFIGURATION ============
    config.environment = "development"
    config.log_level = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # ============ LLM CONFIGURATION ============
    config.llm.provider = "openai"  # openai, anthropic, ollama
    config.llm.model = "gpt-4o"     # gpt-4o, gpt-4o-mini, claude-3-5-sonnet-20241022
    config.llm.temperature = 0.0    # 0.0 = deterministic, 1.0 = creative
    config.llm.max_tokens = 4000
    
    # ============ MQTT CONFIGURATION ============
    config.mqtt.host = "localhost"
    config.mqtt.port = 1883
    config.mqtt.client_id = "tifda-consumer"
    # config.mqtt.username = "your_username"  # Uncomment if using auth
    # config.mqtt.password = "your_password"
    
    # ============ HUMAN-IN-THE-LOOP (HITL) CONFIGURATION ============
    
    # Enable/disable human review
    config.enable_human_review = True  # Set to False to auto-approve everything
    
    # Auto-approve timeout (seconds)
    # - Set to 0 to wait indefinitely for operator
    # - Set to positive integer to auto-approve after timeout
    config.auto_approve_timeout_seconds = 300  # 5 minutes
    
    # Reviewer identification
    config.reviewer_id = "operator_charlie"  # Change to your operator ID
    
    # ============ UI CONFIGURATION ============
    config.ui_refresh_interval = 5  # Poll shared state every N seconds
    config.ui_port = 7860          # Gradio server port
    
    # ============ INTEGRATION CONFIGURATION ============
    config.integrations.mapa_base_url = "http://localhost:3000"
    config.integrations.mapa_timeout = 5
    config.integrations.mapa_max_retries = 3
    config.integrations.mapa_auto_sync = True  # Auto-sync entities to map
    
    # ============ FEATURE FLAGS ============
    config.enable_auto_dissemination = False  # Auto-disseminate without review
    config.enable_mqtt = True                 # Enable MQTT integration
    
    # ============ PRINT CONFIGURATION ============
    print("\n" + "=" * 70)
    print("TIFDA CONFIGURATION INITIALIZED")
    print("=" * 70)
    print(f"Environment:     {config.environment}")
    print(f"Log Level:       {config.log_level}")
    print(f"LLM Model:       {config.llm.model}")
    print(f"MQTT Host:       {config.mqtt.host}:{config.mqtt.port}")
    print(f"Mapa URL:        {config.integrations.mapa_base_url}")
    print()
    print("HITL Settings:")
    print(f"  Enabled:       {config.enable_human_review}")
    print(f"  Timeout:       {config.auto_approve_timeout_seconds}s")
    print(f"  Reviewer ID:   {config.reviewer_id}")
    print(f"  UI Port:       {config.ui_port}")
    print(f"  Refresh:       {config.ui_refresh_interval}s")
    print("=" * 70 + "\n")
    
    return config


def set_hitl_mode(enabled: bool, timeout_seconds: int = 300):
    """
    Quick helper to enable/disable HITL mode.
    
    Args:
        enabled: True to enable human review, False to auto-approve all
        timeout_seconds: Auto-approve timeout (0 = wait forever)
        
    Example:
        # Enable HITL with 5 min timeout
        set_hitl_mode(True, 300)
        
        # Disable HITL (auto-approve everything)
        set_hitl_mode(False)
    """
    config = get_config()
    config.enable_human_review = enabled
    config.auto_approve_timeout_seconds = timeout_seconds
    
    if enabled:
        print(f"✅ HITL ENABLED - Timeout: {timeout_seconds}s")
    else:
        print("🔓 HITL DISABLED - Auto-approving all threats")


# ==================== USAGE EXAMPLES ====================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("TIFDA Configuration Initialization Test")
    print("=" * 70 + "\n")
    
    # Example 1: Initialize with defaults
    print("Example 1: Initialize with default settings")
    print("-" * 70)
    config = initialize_config()
    
    # Example 2: Override specific settings
    print("\nExample 2: Override specific settings")
    print("-" * 70)
    config.llm.model = "gpt-4o-mini"  # Use cheaper model
    config.auto_approve_timeout_seconds = 60  # 1 minute timeout
    print(f"Updated LLM model: {config.llm.model}")
    print(f"Updated timeout: {config.auto_approve_timeout_seconds}s")
    
    # Example 3: Disable HITL for testing
    print("\nExample 3: Disable HITL mode")
    print("-" * 70)
    set_hitl_mode(False)
    print(f"HITL enabled: {config.enable_human_review}")
    
    # Example 4: Re-enable HITL
    print("\nExample 4: Re-enable HITL mode")
    print("-" * 70)
    set_hitl_mode(True, 180)  # 3 minutes
    print(f"HITL enabled: {config.enable_human_review}")
    print(f"Timeout: {config.auto_approve_timeout_seconds}s")
    
    print("\n" + "=" * 70)
    print("✅ Configuration test complete")
    print("=" * 70 + "\n")