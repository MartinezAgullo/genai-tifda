"""
TIFDA MQTT Publisher
====================

MQTT publisher for disseminating messages to downstream systems.
Integrates with transmission_node.py for actual message delivery.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from langsmith import traceable

# Import from the new mqtt_client (will be in src/integrations/)
from src.integrations.mqtt_client import MQTTClient, MQTTConfig
from src.models.dissemination import OutgoingMessage, RecipientConfig

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    """Result of a publish operation"""
    success: bool
    message_id: str
    topic: str
    timestamp: datetime
    error: Optional[str] = None


class MQTTPublisher:
    """
    MQTT publisher for TIFDA message dissemination.
    
    Handles:
    - Connection management to MQTT broker
    - Topic routing based on recipient
    - Message formatting (JSON)
    - QoS configuration per recipient
    - Publish confirmations and error handling
    
    Usage:
        # In transmission_node.py
        publisher = get_mqtt_publisher()
        
        for msg in pending_transmissions:
            result = publisher.publish_message(msg, recipient_config)
            if result.success:
                msg.transmitted = True
                msg.transmission_timestamp = result.timestamp
    """
    
    def __init__(self, mqtt_client: MQTTClient):
        """
        Initialize publisher with MQTT client.
        
        Args:
            mqtt_client: Connected MQTTClient instance
        """
        self.mqtt_client = mqtt_client
        self.publish_stats = {
            'total_published': 0,
            'total_failed': 0,
            'by_recipient': {},
            'by_topic': {}
        }
    
    @traceable(name="mqtt_publish_message")
    def publish_message(
        self,
        message: OutgoingMessage,
        recipient_config: Optional[Dict[str, Any]] = None
    ) -> PublishResult:
        """
        Publish OutgoingMessage to MQTT broker.
        
        Args:
            message: OutgoingMessage to publish
            recipient_config: Recipient configuration (contains MQTT settings)
            
        Returns:
            PublishResult with status
        """
        # Determine topic and QoS from recipient config
        if recipient_config and 'connection_config' in recipient_config:
            topic = recipient_config['connection_config'].get(
                'mqtt_topic',
                f"tifda/output/dissemination_reports/{message.recipient_id}"
            )
            qos = recipient_config['connection_config'].get('qos', 0)
        else:
            # Default topic structure: tifda/output/dissemination_reports/{recipient_id}
            topic = f"tifda/output/dissemination_reports/{message.recipient_id}"
            qos = 0
        
        # Format message as JSON
        try:
            payload = self._format_message_payload(message)
        except Exception as e:
            error_msg = f"Failed to format message: {e}"
            logger.error(f"❌ {error_msg}")
            self.publish_stats['total_failed'] += 1
            return PublishResult(
                success=False,
                message_id=message.message_id,
                topic=topic,
                timestamp=datetime.now(timezone.utc),
                error=error_msg
            )
        
        # Publish to MQTT
        try:
            success = self.mqtt_client.publish(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=False
            )
            
            timestamp = datetime.now(timezone.utc)
            
            if success:
                # Update stats
                self.publish_stats['total_published'] += 1
                self.publish_stats['by_recipient'][message.recipient_id] = \
                    self.publish_stats['by_recipient'].get(message.recipient_id, 0) + 1
                self.publish_stats['by_topic'][topic] = \
                    self.publish_stats['by_topic'].get(topic, 0) + 1
                
                logger.info(f"✅ Published message {message.message_id} to topic '{topic}'")
                
                return PublishResult(
                    success=True,
                    message_id=message.message_id,
                    topic=topic,
                    timestamp=timestamp
                )
            else:
                self.publish_stats['total_failed'] += 1
                error_msg = "MQTT publish returned failure"
                logger.error(f"❌ {error_msg}")
                return PublishResult(
                    success=False,
                    message_id=message.message_id,
                    topic=topic,
                    timestamp=timestamp,
                    error=error_msg
                )
                
        except Exception as e:
            self.publish_stats['total_failed'] += 1
            error_msg = f"Exception during publish: {e}"
            logger.error(f"❌ {error_msg}")
            return PublishResult(
                success=False,
                message_id=message.message_id,
                topic=topic,
                timestamp=datetime.now(timezone.utc),
                error=error_msg
            )
    
    def _format_message_payload(self, message: OutgoingMessage) -> str:
        """
        Format OutgoingMessage as JSON payload.
        
        Creates a structured JSON envelope with metadata + content.
        
        Args:
            message: OutgoingMessage to format
            
        Returns:
            JSON string ready for MQTT
        """
        # Create message envelope
        envelope = {
            # Metadata
            "message_id": message.message_id,
            "recipient_id": message.recipient_id,
            "format_type": message.format_type,
            "timestamp": message.timestamp.isoformat(),
            "source": "TIFDA",
            
            # Actual content (format-specific structure)
            "content": message.content,
            
            # Optional fields
            "decision_id": message.decision_id if hasattr(message, 'decision_id') else None
        }
        
        return json.dumps(envelope, indent=None)  # Compact JSON for MQTT
    
    @traceable(name="mqtt_publish_batch")
    def publish_batch(
        self,
        messages: List[OutgoingMessage],
        recipient_configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Publish multiple messages.
        
        Args:
            messages: List of OutgoingMessage objects
            recipient_configs: Dict mapping recipient_id -> config
            
        Returns:
            Statistics: {
                'total': int,
                'successful': int,
                'failed': int,
                'results': List[PublishResult]
            }
        """
        results = []
        successful = 0
        failed = 0
        
        for message in messages:
            # Get recipient config if available
            recipient_config = None
            if recipient_configs and message.recipient_id in recipient_configs:
                recipient_config = recipient_configs[message.recipient_id]
            
            # Publish
            result = self.publish_message(message, recipient_config)
            results.append(result)
            
            if result.success:
                successful += 1
            else:
                failed += 1
        
        return {
            'total': len(messages),
            'successful': successful,
            'failed': failed,
            'results': results
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get publishing statistics"""
        return {
            **self.publish_stats,
            'connected': self.mqtt_client.is_connected
        }
    
    def health_check(self) -> tuple[bool, str]:
        """
        Check if publisher is healthy and can publish.
        
        Returns:
            (is_healthy, message)
        """
        if not self.mqtt_client.is_connected:
            return False, "MQTT client not connected"
        
        return True, f"Publisher healthy - {self.publish_stats['total_published']} messages published"


# ==================== SINGLETON INSTANCE ====================

_mqtt_publisher: Optional[MQTTPublisher] = None


def get_mqtt_publisher(
    mqtt_config: Optional[MQTTConfig] = None,
    force_new: bool = False
) -> MQTTPublisher:
    """
    Get global MQTTPublisher instance (singleton).
    
    Args:
        mqtt_config: MQTT configuration (if None, uses default from config.py)
        force_new: Force creation of new publisher
        
    Returns:
        MQTTPublisher instance
    """
    global _mqtt_publisher
    
    if _mqtt_publisher is None or force_new:
        # Get config from TIFDA config if not provided
        if mqtt_config is None:
            from src.core.config import get_config
            config = get_config()
            mqtt_config = MQTTConfig(
                host=config.mqtt.host,
                port=config.mqtt.port,
                client_id=config.mqtt.client_id,
                username=config.mqtt.username,
                password=config.mqtt.password
            )
        
        # Create MQTT client
        mqtt_client = MQTTClient(mqtt_config)
        
        # Connect (blocking)
        if not mqtt_client.connect(blocking=True):
            raise ConnectionError("Failed to connect to MQTT broker")
        """
TIFDA MQTT Publisher
====================

MQTT publisher for disseminating messages to downstream systems.
Integrates with transmission_node.py for actual message delivery.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from langsmith import traceable

# Import from the new mqtt_client (will be in src/integrations/)
from src.integrations.mqtt_client import MQTTClient, MQTTConfig
from src.models.dissemination import OutgoingMessage, RecipientConfig

logger = logging.getLogger(__name__)


@dataclass
class PublishResult:
    """Result of a publish operation"""
    success: bool
    message_id: str
    topic: str
    timestamp: datetime
    error: Optional[str] = None


class MQTTPublisher:
    """
    MQTT publisher for TIFDA message dissemination.
    
    Handles:
    - Connection management to MQTT broker
    - Topic routing based on recipient
    - Message formatting (JSON)
    - QoS configuration per recipient
    - Publish confirmations and error handling
    
    Usage:
        # In transmission_node.py
        publisher = get_mqtt_publisher()
        
        for msg in pending_transmissions:
            result = publisher.publish_message(msg, recipient_config)
            if result.success:
                msg.transmitted = True
                msg.transmission_timestamp = result.timestamp
    """
    
    def __init__(self, mqtt_client: MQTTClient):
        """
        Initialize publisher with MQTT client.
        
        Args:
            mqtt_client: Connected MQTTClient instance
        """
        self.mqtt_client = mqtt_client
        self.publish_stats = {
            'total_published': 0,
            'total_failed': 0,
            'by_recipient': {},
            'by_topic': {}
        }
    
    @traceable(name="mqtt_publish_message")
    def publish_message(
        self,
        message: OutgoingMessage,
        recipient_config: Optional[Dict[str, Any]] = None
    ) -> PublishResult:
        """
        Publish OutgoingMessage to MQTT broker.
        
        Args:
            message: OutgoingMessage to publish
            recipient_config: Recipient configuration (contains MQTT settings)
            
        Returns:
            PublishResult with status
        """
        # Determine topic and QoS from recipient config
        if recipient_config and 'connection_config' in recipient_config:
            topic = recipient_config['connection_config'].get(
                'mqtt_topic',
                f"tifda/output/dissemination_reports/{message.recipient_id}"
            )
            qos = recipient_config['connection_config'].get('qos', 0)
        else:
            # Default topic structure: tifda/output/dissemination_reports/{recipient_id}
            topic = f"tifda/output/dissemination_reports/{message.recipient_id}"
            qos = 0
        
        # Format message as JSON
        try:
            payload = self._format_message_payload(message)
        except Exception as e:
            error_msg = f"Failed to format message: {e}"
            logger.error(f"❌ {error_msg}")
            self.publish_stats['total_failed'] += 1
            return PublishResult(
                success=False,
                message_id=message.message_id,
                topic=topic,
                timestamp=datetime.now(timezone.utc),
                error=error_msg
            )
        
        # Publish to MQTT
        try:
            success = self.mqtt_client.publish(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=False
            )
            
            timestamp = datetime.now(timezone.utc)
            
            if success:
                # Update stats
                self.publish_stats['total_published'] += 1
                self.publish_stats['by_recipient'][message.recipient_id] = \
                    self.publish_stats['by_recipient'].get(message.recipient_id, 0) + 1
                self.publish_stats['by_topic'][topic] = \
                    self.publish_stats['by_topic'].get(topic, 0) + 1
                
                logger.info(f"✅ Published message {message.message_id} to topic '{topic}'")
                
                return PublishResult(
                    success=True,
                    message_id=message.message_id,
                    topic=topic,
                    timestamp=timestamp
                )
            else:
                self.publish_stats['total_failed'] += 1
                error_msg = "MQTT publish returned failure"
                logger.error(f"❌ {error_msg}")
                return PublishResult(
                    success=False,
                    message_id=message.message_id,
                    topic=topic,
                    timestamp=timestamp,
                    error=error_msg
                )
                
        except Exception as e:
            self.publish_stats['total_failed'] += 1
            error_msg = f"Exception during publish: {e}"
            logger.error(f"❌ {error_msg}")
            return PublishResult(
                success=False,
                message_id=message.message_id,
                topic=topic,
                timestamp=datetime.now(timezone.utc),
                error=error_msg
            )
    
    def _format_message_payload(self, message: OutgoingMessage) -> str:
        """
        Format OutgoingMessage as JSON payload.
        
        Creates a structured JSON envelope with metadata + content.
        
        Args:
            message: OutgoingMessage to format
            
        Returns:
            JSON string ready for MQTT
        """
        # Create message envelope
        envelope = {
            # Metadata
            "message_id": message.message_id,
            "recipient_id": message.recipient_id,
            "format_type": message.format_type,
            "timestamp": message.timestamp.isoformat(),
            "source": "TIFDA",
            
            # Actual content (format-specific structure)
            "content": message.content,
            
            # Optional fields
            "decision_id": message.decision_id if hasattr(message, 'decision_id') else None
        }
        
        return json.dumps(envelope, indent=None)  # Compact JSON for MQTT
    
    @traceable(name="mqtt_publish_batch")
    def publish_batch(
        self,
        messages: List[OutgoingMessage],
        recipient_configs: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Publish multiple messages.
        
        Args:
            messages: List of OutgoingMessage objects
            recipient_configs: Dict mapping recipient_id -> config
            
        Returns:
            Statistics: {
                'total': int,
                'successful': int,
                'failed': int,
                'results': List[PublishResult]
            }
        """
        results = []
        successful = 0
        failed = 0
        
        for message in messages:
            # Get recipient config if available
            recipient_config = None
            if recipient_configs and message.recipient_id in recipient_configs:
                recipient_config = recipient_configs[message.recipient_id]
            
            # Publish
            result = self.publish_message(message, recipient_config)
            results.append(result)
            
            if result.success:
                successful += 1
            else:
                failed += 1
        
        return {
            'total': len(messages),
            'successful': successful,
            'failed': failed,
            'results': results
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get publishing statistics"""
        return {
            **self.publish_stats,
            'connected': self.mqtt_client.is_connected
        }
    
    def health_check(self) -> tuple[bool, str]:
        """
        Check if publisher is healthy and can publish.
        
        Returns:
            (is_healthy, message)
        """
        if not self.mqtt_client.is_connected:
            return False, "MQTT client not connected"
        
        return True, f"Publisher healthy - {self.publish_stats['total_published']} messages published"


# ==================== SINGLETON INSTANCE ====================

_mqtt_publisher: Optional[MQTTPublisher] = None


def get_mqtt_publisher(
    mqtt_config: Optional[MQTTConfig] = None,
    force_new: bool = False
) -> MQTTPublisher:
    """
    Get global MQTTPublisher instance (singleton).
    
    Args:
        mqtt_config: MQTT configuration (if None, uses default from config.py)
        force_new: Force creation of new publisher
        
    Returns:
        MQTTPublisher instance
    """
    global _mqtt_publisher
    
    if _mqtt_publisher is None or force_new:
        # Get config from TIFDA config if not provided
        if mqtt_config is None:
            from src.core.config import get_config
            config = get_config()
            mqtt_config = MQTTConfig(
                host=config.mqtt.host,
                port=config.mqtt.port,
                client_id=config.mqtt.client_id,
                username=config.mqtt.username,
                password=config.mqtt.password
            )
        
        # Create MQTT client
        mqtt_client = MQTTClient(mqtt_config)
        
        # Connect (blocking)
        if not mqtt_client.connect(blocking=True):
            raise ConnectionError("Failed to connect to MQTT broker")
        
        # Create publisher
        _mqtt_publisher = MQTTPublisher(mqtt_client)
        logger.info("✅ MQTT Publisher initialized")
    
    return _mqtt_publisher


def shutdown_mqtt_publisher():
    """Shutdown the global MQTT publisher"""
    global _mqtt_publisher
    
    if _mqtt_publisher:
        _mqtt_publisher.mqtt_client.disconnect()
        _mqtt_publisher = None
        logger.info("MQTT Publisher shutdown")
        # Create publisher
        _mqtt_publisher = MQTTPublisher(mqtt_client)
        logger.info("✅ MQTT Publisher initialized")
    
    return _mqtt_publisher


def shutdown_mqtt_publisher():
    """Shutdown the global MQTT publisher"""
    global _mqtt_publisher
    
    if _mqtt_publisher:
        _mqtt_publisher.mqtt_client.disconnect()
        _mqtt_publisher = None
        logger.info("MQTT Publisher shutdown")