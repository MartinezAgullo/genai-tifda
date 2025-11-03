"""
MQTT Integration Test
======================

Test script to verify MQTT integration with TIFDA transmission node.

Tests:
1. MQTT client connection
2. Message publishing
3. transmission_node integration
4. Error handling

Requirements:
- MQTT broker running (mosquitto or similar)
- paho-mqtt installed
"""

import sys
import os
import logging
from datetime import datetime
from time import sleep

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_mqtt_client():
    """Test 1: Basic MQTT client connection and publish"""
    print("\n" + "=" * 70)
    print("TEST 1: MQTT Client Connection")
    print("=" * 70)
    
    try:
        from src.integrations.mqtt_client import MQTTConfig, MQTTClient
        
        # Create simple config (local broker, no auth)
        config = MQTTConfig(
            host="localhost",
            port=1883,
            client_id="tifda-test",
            username=None,
            password=None,
            use_tls=False
        )
        
        print(f"📡 Connecting to MQTT broker at {config.host}:{config.port}...")
        
        # Create and connect client
        client = MQTTClient(config)
        success = client.connect(blocking=True, timeout=10)
        
        if not success:
            print("❌ Failed to connect to MQTT broker")
            print("   Make sure broker is running: mosquitto -c mosquitto.conf")
            return False
        
        print("✅ Connected successfully")
        
        # Test publish
        print("\n📤 Publishing test message...")
        test_topic = "tifda/test"
        test_payload = '{"message": "Hello from TIFDA!", "timestamp": "' + datetime.utcnow().isoformat() + '"}'
        
        success = client.publish(test_topic, test_payload, qos=0)
        
        if success:
            print(f"✅ Published to '{test_topic}'")
        else:
            print(f"❌ Publish failed")
            return False
        
        # Disconnect
        client.disconnect()
        print("✅ Disconnected")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mqtt_publisher():
    """Test 2: MQTTPublisher with OutgoingMessage"""
    print("\n" + "=" * 70)
    print("TEST 2: MQTT Publisher")
    print("=" * 70)
    
    try:
        from src.integrations.mqtt_publisher import get_mqtt_publisher
        from src.models.dissemination import OutgoingMessage
        
        print("📡 Getting MQTT publisher...")
        publisher = get_mqtt_publisher()
        
        # Health check
        is_healthy, msg = publisher.health_check()
        print(f"Health check: {msg}")
        
        if not is_healthy:
            print("❌ Publisher not healthy")
            return False
        
        # Create test message
        test_message = OutgoingMessage(
            message_id="test_001",
            decision_id="test_dec_001",
            recipient_id="test_recipient",
            format_type="json",
            content={
                "test": True,
                "message": "Test message from MQTTPublisher",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "threat_level": "low",
                    "confidence": 0.95
                }
            },
            timestamp=datetime.utcnow()
        )
        
        print(f"\n📤 Publishing message '{test_message.message_id}'...")
        
        # Publish
        result = publisher.publish_message(test_message)
        
        if result.success:
            print(f"✅ Published successfully")
            print(f"   Topic: {result.topic}")
            print(f"   Timestamp: {result.timestamp}")
        else:
            print(f"❌ Publish failed: {result.error}")
            return False
        
        # Get stats
        stats = publisher.get_stats()
        print(f"\n📊 Publisher stats:")
        print(f"   Total published: {stats['total_published']}")
        print(f"   Total failed: {stats['total_failed']}")
        print(f"   Connected: {stats['connected']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_transmission_node():
    """Test 3: Full transmission_node integration"""
    print("\n" + "=" * 70)
    print("TEST 3: Transmission Node Integration")
    print("=" * 70)
    
    try:
        from src.core.state import create_initial_state
        from src.models.dissemination import OutgoingMessage
        from src.nodes.transmission_node import transmission_node
        
        print("🔧 Creating test state...")
        
        # Create state
        state = create_initial_state()
        state["sensor_metadata"] = {"sensor_id": "test_sensor"}
        
        # Create test messages
        state["pending_transmissions"] = [
            OutgoingMessage(
                message_id="integration_test_001",
                decision_id="test_dec_001",
                recipient_id="command_center",
                format_type="json",
                content={
                    "entities": [
                        {"id": "T001", "type": "aircraft", "classification": "unknown"}
                    ],
                    "threat_level": "medium",
                    "test": True
                },
                timestamp=datetime.utcnow()
            ),
            OutgoingMessage(
                message_id="integration_test_002",
                decision_id="test_dec_001",
                recipient_id="mapa",
                format_type="json",
                content={
                    "cop_update": True,
                    "entity_count": 1,
                    "test": True
                },
                timestamp=datetime.utcnow()
            )
        ]
        
        print(f"📡 Transmitting {len(state['pending_transmissions'])} messages...")
        
        # Execute transmission node
        result = transmission_node(state)
        
        # Check results
        if "error" in result and result["error"]:
            print(f"❌ Transmission failed: {result['error']}")
            return False
        
        transmission_log = result.get("transmission_log", [])
        
        print(f"\n✅ Transmission complete")
        print(f"   Messages processed: {len(transmission_log)}")
        
        # Show results
        for log_entry in transmission_log:
            status = "✅" if log_entry.get("success") else "❌"
            print(f"   {status} {log_entry['message_id']} → {log_entry.get('topic', 'N/A')}")
            if not log_entry.get("success"):
                print(f"      Error: {log_entry.get('error', 'Unknown error')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_subscriber():
    """Test 4: MQTT subscriber (listen for test messages)"""
    print("\n" + "=" * 70)
    print("TEST 4: MQTT Subscriber (optional)")
    print("=" * 70)
    
    try:
        from src.integrations.mqtt_client import MQTTConfig, MQTTClient
        
        received_messages = []
        
        def on_message(client, userdata, msg):
            """Callback for received messages"""
            payload = msg.payload.decode()
            print(f"📥 Received on '{msg.topic}': {payload[:100]}...")
            received_messages.append((msg.topic, payload))
        
        # Create subscriber
        config = MQTTConfig(
            host="localhost",
            port=1883,
            client_id="tifda-test-subscriber"
        )
        
        print(f"📡 Connecting subscriber to {config.host}:{config.port}...")
        
        client = MQTTClient(config, on_message=on_message)
        if not client.connect(blocking=True):
            print("❌ Failed to connect subscriber")
            return False
        
        # Subscribe to all TIFDA topics
        test_topic = "tifda/#"  # Wildcard: all tifda topics
        print(f"📥 Subscribing to '{test_topic}'...")
        client.subscribe(test_topic, qos=0)
        
        print("\n⏳ Listening for 5 seconds...")
        print("   (Run test_mqtt_client() or test_transmission_node() in another terminal)")
        
        sleep(5)
        
        # Disconnect
        client.disconnect()
        
        print(f"\n📊 Received {len(received_messages)} message(s)")
        for topic, payload in received_messages[:3]:
            print(f"   - {topic}: {payload[:80]}...")
        
        if len(received_messages) == 0:
            print("   ℹ️  No messages received (this is normal if no publishers are active)")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all MQTT integration tests"""
    print("\n" + "=" * 70)
    print("TIFDA MQTT INTEGRATION TESTS")
    print("=" * 70)
    
    print("\nPrerequisites:")
    print("  1. MQTT broker running (mosquitto -c mosquitto.conf)")
    print("  2. paho-mqtt installed (uv add paho-mqtt)")
    print("  3. TIFDA src/ directory in PYTHONPATH")
    print()
    
    input("Press Enter to start tests...")
    
    results = {}
    
    # Test 1: Basic client
    results["mqtt_client"] = test_mqtt_client()
    
    # Test 2: Publisher
    if results["mqtt_client"]:
        results["mqtt_publisher"] = test_mqtt_publisher()
    else:
        print("\n⏭️  Skipping test 2 (client test failed)")
        results["mqtt_publisher"] = False
    
    # Test 3: Transmission node
    if results["mqtt_publisher"]:
        results["transmission_node"] = test_transmission_node()
    else:
        print("\n⏭️  Skipping test 3 (publisher test failed)")
        results["transmission_node"] = False
    
    # Test 4: Subscriber (optional)
    print("\n" + "-" * 70)
    subscribe_test = input("Run subscriber test? (y/n): ").lower().strip()
    if subscribe_test == 'y':
        results["subscriber"] = test_subscriber()
    else:
        results["subscriber"] = None
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, result in results.items():
        if result is None:
            status = "⏭️  SKIPPED"
        elif result:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        
        print(f"{status}: {test_name}")
    
    # Overall result
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    
    print()
    if failed == 0:
        print("🎉 All tests passed!")
        # print("\nNext steps:")
        # print("1. Configure recipients in config.py")
        # print("2. Run TIFDA pipeline with real sensor data")
        # print("3. Monitor MQTT topics with: mosquitto_sub -t 'tifda/#' -v")
    else:
        print(f"⚠️  {failed} test(s) failed")
        print("\nTroubleshooting:")
        print("1. Check MQTT broker is running: ps aux | grep mosquitto")
        print("2. Test broker: mosquitto_sub -t 'test' -v (in one terminal)")
        print("                mosquitto_pub -t 'test' -m 'hello' (in another)")
        print("3. Check firewall/network settings")
        print("4. Review logs above for specific errors")
    
    print("=" * 70)


if __name__ == "__main__":
    run_all_tests()