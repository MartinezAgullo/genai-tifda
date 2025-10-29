"""
TIFDA MQTT Client
=================

Enhanced MQTT client wrapper with TLS, authentication, and error handling.
Based on paho-mqtt library.
"""

import paho.mqtt.client as mqtt
import ssl
import time
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MQTTConfig:
    """MQTT connection configuration"""
    host: str = "localhost"
    port: int = 1883
    client_id: str = "tifda-client"
    
    # Authentication
    username: Optional[str] = None
    password: Optional[str] = None
    
    # TLS/SSL
    use_tls: bool = False
    ca_certs: Optional[str] = None  # Path to CA certificate
    certfile: Optional[str] = None  # Path to client certificate
    keyfile: Optional[str] = None   # Path to client private key
    tls_insecure: bool = False      # Set True to skip hostname verification (POC only!)
    
    # Connection settings
    keepalive: int = 60
    clean_session: bool = True
    reconnect_on_failure: bool = True
    max_reconnect_attempts: int = 5
    reconnect_delay: int = 2  # seconds


class MQTTClient:
    """
    Enhanced MQTT client for TIFDA with TLS and authentication support.
    
    Usage:
        config = MQTTConfig(
            host="localhost",
            port=8883,
            use_tls=True,
            username="tifda",
            password="secret"
        )
        
        client = MQTTClient(config)
        client.connect()
        client.publish("tifda/test", "Hello")
        client.disconnect()
    """
    
    def __init__(
        self,
        config: MQTTConfig,
        on_connect: Optional[Callable] = None,
        on_message: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
        on_publish: Optional[Callable] = None
    ):
        """
        Initialize MQTT client.
        
        Args:
            config: MQTT configuration
            on_connect: Callback for connection events
            on_message: Callback for received messages
            on_disconnect: Callback for disconnection events
            on_publish: Callback for publish confirmations
        """
        self.config = config
        self._connected = False
        self._reconnect_attempts = 0
        
        # Create paho MQTT client
        self.client = mqtt.Client(
            client_id=config.client_id,
            clean_session=config.clean_session
        )
        
        # Set callbacks
        self.client.on_connect = self._on_connect_wrapper
        self.client.on_disconnect = self._on_disconnect_wrapper
        self.client.on_message = on_message if on_message else self._default_on_message
        self.client.on_publish = on_publish
        
        # Store user callbacks
        self._user_on_connect = on_connect
        self._user_on_disconnect = on_disconnect
        
        # Configure authentication
        if config.username and config.password:
            self.client.username_pw_set(config.username, config.password)
            logger.info(f"MQTT authentication configured for user: {config.username}")
        
        # Configure TLS
        if config.use_tls:
            self._configure_tls()
    
    def _configure_tls(self):
        """Configure TLS/SSL settings"""
        tls_kwargs = {}
        
        # CA certificates
        if self.config.ca_certs:
            tls_kwargs['ca_certs'] = self.config.ca_certs
        
        # Client certificates
        if self.config.certfile:
            tls_kwargs['certfile'] = self.config.certfile
        if self.config.keyfile:
            tls_kwargs['keyfile'] = self.config.keyfile
        
        # Set TLS version (use TLS 1.2 minimum)
        tls_kwargs['cert_reqs'] = ssl.CERT_REQUIRED
        tls_kwargs['tls_version'] = ssl.PROTOCOL_TLS
        
        # Apply TLS configuration
        try:
            self.client.tls_set(**tls_kwargs)
            
            # For POC: allow insecure connections (skip hostname verification)
            if self.config.tls_insecure:
                self.client.tls_insecure_set(True)
                logger.warning("⚠️ TLS hostname verification disabled (POC mode)")
            
            logger.info("✅ TLS/SSL configured")
        except Exception as e:
            logger.error(f"❌ Failed to configure TLS: {e}")
            raise
    
    def _on_connect_wrapper(self, client, userdata, flags, rc):
        """Internal connection callback wrapper"""
        if rc == 0:
            self._connected = True
            self._reconnect_attempts = 0
            logger.info(f"✅ Connected to MQTT broker at {self.config.host}:{self.config.port}")
            
            # Call user callback if provided
            if self._user_on_connect:
                self._user_on_connect(client, userdata, flags, rc)
        else:
            self._connected = False
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            error_msg = error_messages.get(rc, f"Unknown error code: {rc}")
            logger.error(f"❌ MQTT connection failed: {error_msg}")
    
    def _on_disconnect_wrapper(self, client, userdata, rc):
        """Internal disconnection callback wrapper"""
        self._connected = False
        
        if rc != 0:
            logger.warning(f"⚠️ Unexpected MQTT disconnection (code: {rc})")
            
            # Attempt reconnection if enabled
            if self.config.reconnect_on_failure:
                self._attempt_reconnect()
        else:
            logger.info("MQTT client disconnected normally")
        
        # Call user callback if provided
        if self._user_on_disconnect:
            self._user_on_disconnect(client, userdata, rc)
    
    def _default_on_message(self, client, userdata, msg):
        """Default message handler (just logs)"""
        logger.debug(f"Received message on topic '{msg.topic}': {msg.payload.decode()}")
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to broker"""
        if self._reconnect_attempts >= self.config.max_reconnect_attempts:
            logger.error(f"❌ Max reconnection attempts ({self.config.max_reconnect_attempts}) reached")
            return
        
        self._reconnect_attempts += 1
        delay = self.config.reconnect_delay * self._reconnect_attempts
        
        logger.info(f"🔄 Reconnection attempt {self._reconnect_attempts}/{self.config.max_reconnect_attempts} in {delay}s...")
        time.sleep(delay)
        
        try:
            self.client.reconnect()
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {e}")
    
    def connect(self, blocking: bool = True, timeout: int = 10) -> bool:
        """
        Connect to MQTT broker.
        
        Args:
            blocking: If True, wait for connection to complete
            timeout: Connection timeout in seconds (for blocking mode)
            
        Returns:
            True if connected successfully
        """
        try:
            logger.info(f"🔌 Connecting to MQTT broker at {self.config.host}:{self.config.port}...")
            
            self.client.connect(
                host=self.config.host,
                port=self.config.port,
                keepalive=self.config.keepalive
            )
            
            # Start network loop
            self.client.loop_start()
            
            if blocking:
                # Wait for connection
                start_time = time.time()
                while not self._connected and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                
                if not self._connected:
                    logger.error(f"❌ Connection timeout after {timeout}s")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("MQTT client disconnected")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    def publish(
        self,
        topic: str,
        payload: str,
        qos: int = 0,
        retain: bool = False
    ) -> bool:
        """
        Publish message to topic.
        
        Args:
            topic: MQTT topic
            payload: Message payload (string or bytes)
            qos: Quality of Service (0, 1, or 2)
            retain: Retain message on broker
            
        Returns:
            True if published successfully
        """
        if not self._connected:
            logger.error("❌ Cannot publish: Not connected to broker")
            return False
        
        try:
            result = self.client.publish(
                topic=topic,
                payload=payload,
                qos=qos,
                retain=retain
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"📤 Published to '{topic}': {payload[:100]}...")
                return True
            else:
                logger.error(f"❌ Publish failed with code: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Publish error: {e}")
            return False
    
    def subscribe(self, topic: str, qos: int = 0):
        """
        Subscribe to topic.
        
        Args:
            topic: MQTT topic (supports wildcards)
            qos: Quality of Service
        """
        if not self._connected:
            logger.error("❌ Cannot subscribe: Not connected to broker")
            return
        
        try:
            self.client.subscribe(topic, qos)
            logger.info(f"📥 Subscribed to topic: {topic}")
        except Exception as e:
            logger.error(f"❌ Subscribe error: {e}")
    
    def unsubscribe(self, topic: str):
        """Unsubscribe from topic"""
        try:
            self.client.unsubscribe(topic)
            logger.info(f"Unsubscribed from topic: {topic}")
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._connected
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# ==================== CONVENIENCE FUNCTIONS ====================

def create_mqtt_client_from_config(
    host: str = "localhost",
    port: int = 1883,
    client_id: str = "tifda",
    username: Optional[str] = None,
    password: Optional[str] = None,
    use_tls: bool = False,
    **kwargs
) -> MQTTClient:
    """
    Create MQTT client with simple parameters.
    
    Args:
        host: Broker hostname
        port: Broker port
        client_id: Client identifier
        username: Username for authentication
        password: Password for authentication
        use_tls: Enable TLS/SSL
        **kwargs: Additional MQTTConfig parameters
        
    Returns:
        Configured MQTTClient instance
    """
    config = MQTTConfig(
        host=host,
        port=port,
        client_id=client_id,
        username=username,
        password=password,
        use_tls=use_tls,
        **kwargs
    )
    
    return MQTTClient(config)