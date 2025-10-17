"""
Parser Factory
==============

Factory for creating appropriate parsers based on sensor message format.
"""

from typing import List, Optional
from src.models import SensorMessage, EntityCOP
from src.parsers.base_parser import BaseParser
from src.parsers.asterix_parser import ASTERIXParser
from src.parsers.drone_parser import DroneParser
from src.parsers.radio_parser import RadioParser
from src.parsers.manual_parser import ManualParser


class ParserFactory:
    """
    Factory for selecting and executing appropriate parser for sensor messages.
    """
    
    def __init__(self):
        """Initialize parser factory with all available parsers"""
        self.parsers: List[BaseParser] = [
            ASTERIXParser(),
            DroneParser(),
            RadioParser(),
            ManualParser(),
        ]
    
    def get_parser(self, sensor_msg: SensorMessage) -> Optional[BaseParser]:
        """
        Get appropriate parser for sensor message.
        
        Args:
            sensor_msg: Sensor message to parse
            
        Returns:
            Parser instance that can handle this format, or None if no parser found
        """
        for parser in self.parsers:
            if parser.can_parse(sensor_msg):
                return parser
        
        return None
    
    def parse(self, sensor_msg: SensorMessage) -> tuple[bool, str, List[EntityCOP]]:
        """
        Parse sensor message using appropriate parser.
        
        Args:
            sensor_msg: Sensor message to parse
            
        Returns:
            (success, error_message, entities)
            - success: True if parsing succeeded
            - error_message: Error description (empty if success)
            - entities: List of parsed EntityCOP objects
        """
        # Find appropriate parser
        parser = self.get_parser(sensor_msg)
        
        if parser is None:
            return False, f"No parser found for sensor type '{sensor_msg.sensor_type}'", []
        
        # Validate message structure
        is_valid, error = parser.validate(sensor_msg)
        if not is_valid:
            return False, f"Validation failed: {error}", []
        
        # Parse message
        try:
            entities = parser.parse(sensor_msg)
            return True, "", entities
        except Exception as e:
            return False, f"Parsing failed: {str(e)}", []
    
    def register_parser(self, parser: BaseParser):
        """
        Register a new parser.
        
        Args:
            parser: Parser instance to register
        """
        self.parsers.append(parser)


# Global parser factory instance
_parser_factory: Optional[ParserFactory] = None


def get_parser_factory() -> ParserFactory:
    """
    Get global parser factory instance (singleton).
    
    Returns:
        ParserFactory instance
    """
    global _parser_factory
    
    if _parser_factory is None:
        _parser_factory = ParserFactory()
    
    return _parser_factory