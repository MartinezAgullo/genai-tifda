"""
Integration Tests
=================

Unit tests for mapa-puntos-interes integration.
"""

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..')
sys.path.insert(0, project_root)

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from src.models import EntityCOP, Location
from src.integrations import (
    MapaClient,
    MapaClientError,
    COPSync,
    get_mapa_client,
    get_cop_sync
)


# ==================== MAPA CLIENT TESTS ====================

class TestMapaClient:
    """Test MapaClient HTTP operations"""
    
    @patch('src.integrations.mapa_client.requests.Session')
    def test_health_check_success(self, mock_session):
        """Test successful health check"""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {'status': 'OK', 'uptime': 123}
        mock_response.raise_for_status = Mock()
        
        mock_session.return_value.request.return_value = mock_response
        
        client = MapaClient()
        is_healthy, msg = client.health_check()
        
        assert is_healthy is True
        assert "123" in msg
    
    @patch('src.integrations.mapa_client.requests.Session')
    def test_health_check_failure(self, mock_session):
        """Test health check when server unreachable"""
        mock_session.return_value.request.side_effect = Exception("Connection refused")
        
        client = MapaClient()
        is_healthy, msg = client.health_check()
        
        assert is_healthy is False
        assert "unreachable" in msg.lower()
    
    @patch('src.integrations.mapa_client.requests.Session')
    def test_create_punto_success(self, mock_session):
        """Test successful punto creation"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'success': True,
            'data': {'id': 1, 'nombre': 'test'}
        }
        mock_response.raise_for_status = Mock()
        
        mock_session.return_value.request.return_value = mock_response
        
        client = MapaClient()
        punto = client.create_punto({'nombre': 'test'})
        
        assert punto['id'] == 1
        assert punto['nombre'] == 'test'
    
    @patch('src.integrations.mapa_client.requests.Session')
    def test_upsert_creates_new(self, mock_session):
        """Test upsert creates when punto doesn't exist"""
        # Mock: find returns None (doesn't exist)
        mock_get_response = Mock()
        mock_get_response.json.return_value = {'success': True, 'data': []}
        mock_get_response.raise_for_status = Mock()
        
        # Mock: create returns new punto
        mock_post_response = Mock()
        mock_post_response.json.return_value = {
            'success': True,
            'data': {'id': 1, 'elemento_identificado': 'test_001'}
        }
        mock_post_response.raise_for_status = Mock()
        
        mock_session.return_value.request.side_effect = [
            mock_get_response,  # GET all
            mock_post_response   # POST create
        ]
        
        client = MapaClient()
        punto, was_created = client.upsert_punto({
            'elemento_identificado': 'test_001',
            'nombre': 'test'
        })
        
        assert was_created is True
        assert punto['id'] == 1
    
    @patch('src.integrations.mapa_client.requests.Session')
    def test_upsert_updates_existing(self, mock_session):
        """Test upsert updates when punto exists"""
        # Mock: find returns existing punto
        mock_get_response = Mock()
        mock_get_response.json.return_value = {
            'success': True,
            'data': [{'id': 5, 'elemento_identificado': 'test_001'}]
        }
        mock_get_response.raise_for_status = Mock()
        
        # Mock: update returns updated punto
        mock_put_response = Mock()
        mock_put_response.json.return_value = {
            'success': True,
            'data': {'id': 5, 'elemento_identificado': 'test_001', 'updated': True}
        }
        mock_put_response.raise_for_status = Mock()
        
        mock_session.return_value.request.side_effect = [
            mock_get_response,  # GET all
            mock_put_response    # PUT update
        ]
        
        client = MapaClient()
        punto, was_created = client.upsert_punto({
            'elemento_identificado': 'test_001',
            'nombre': 'test'
        })
        
        assert was_created is False
        assert punto['id'] == 5


# ==================== COP SYNC TESTS ====================

class TestCOPSync:
    """Test COP synchronization"""
    
    def test_sync_entity_converts_format(self):
        """Test entity is converted to mapa format"""
        entity = EntityCOP(
            entity_id="radar_01_T001",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4, alt=5000),
            timestamp=datetime.now(timezone.utc),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.9,
            source_sensors=["radar_01"]
        )
        
        # Get mapa format
        punto_data = entity.to_mapa_punto_interes()
        
        assert punto_data['elemento_identificado'] == "radar_01_T001"
        assert punto_data['categoria'] == "Avion"
        assert punto_data['prioridad'] == 9  # hostile = 9
        assert punto_data['latitud'] == 39.5
        assert punto_data['longitud'] == -0.4
    
    @patch('src.integrations.cop_sync.get_mapa_client')
    def test_sync_entity_success(self, mock_get_client):
        """Test successful entity sync"""
        # Mock client
        mock_client = Mock()
        mock_client.health_check.return_value = (True, "Mock connection successful")
        mock_client.upsert_punto.return_value = (
            {'id': 1, 'elemento_identificado': 'test_001'},
            True
        )
        mock_get_client.return_value = mock_client
        
        entity = EntityCOP(
            entity_id="test_001",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4),
            timestamp=datetime.now(timezone.utc),
            classification="unknown",
            confidence=0.8,
            source_sensors=["test"]
        )
        
        sync = COPSync()
        success, msg = sync.sync_entity(entity)
        
        assert success is True
        assert "test_001" in msg
        assert sync.sync_stats['total_created'] == 1
    
    @patch('src.integrations.cop_sync.get_mapa_client')
    def test_sync_batch(self, mock_get_client):
        """Test batch entity sync"""
        mock_client = Mock()
        mock_client.health_check.return_value = (True, "Mock connection successful")
        mock_client.batch_upsert.return_value = {
            'created': 2,
            'updated': 1,
            'failed': 0,
            'errors': []
        }
        mock_get_client.return_value = mock_client
        
        entities = [
            EntityCOP(
                entity_id=f"test_{i}",
                entity_type="aircraft",
                location=Location(lat=39.5, lon=-0.4),
                timestamp=datetime.now(timezone.utc),
                classification="unknown",
                confidence=0.8,
                source_sensors=["test"]
            )
            for i in range(3)
        ]
        
        sync = COPSync()
        result = sync.sync_batch(entities)
        
        assert result['success'] is True
        assert result['count'] == 3
        assert result['created'] == 2
        assert result['updated'] == 1


# ==================== ENTITY CONVERSION TESTS ====================

class TestEntityConversion:
    """Test EntityCOP to mapa format conversion"""
    
    def test_aircraft_to_avion(self):
        """Test aircraft entity type maps to Avion category"""
        entity = EntityCOP(
            entity_id="test",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4),
            timestamp=datetime.now(timezone.utc),
            classification="unknown",
            confidence=0.8,
            source_sensors=["test"]
        )
        
        punto = entity.to_mapa_punto_interes()
        assert punto['categoria'] == "Avion"
    
    def test_tank_to_tanque(self):
        """Test tank entity type maps to Tanque category"""
        entity = EntityCOP(
            entity_id="test",
            entity_type="tank",
            location=Location(lat=39.5, lon=-0.4),
            timestamp=datetime.now(timezone.utc),
            classification="hostile",
            confidence=0.9,
            source_sensors=["test"]
        )
        
        punto = entity.to_mapa_punto_interes()
        assert punto['categoria'] == "Tanque"
        assert punto['prioridad'] == 9  # hostile
    
    def test_priority_calculation(self):
        """Test priority calculation from classification"""
        classifications_and_priorities = [
            ("hostile", 9),
            ("unknown", 6),
            ("neutral", 3),
            ("friendly", 2)
        ]
        
        for classification, expected_priority in classifications_and_priorities:
            entity = EntityCOP(
                entity_id="test",
                entity_type="aircraft",
                location=Location(lat=39.5, lon=-0.4),
                timestamp=datetime.now(timezone.utc),
                classification=classification,
                confidence=0.8,
                source_sensors=["test"]
            )
            
            punto = entity.to_mapa_punto_interes()
            assert punto['prioridad'] == expected_priority
    
    def test_observations_include_metadata(self):
        """Test observations field includes key metadata"""
        entity = EntityCOP(
            entity_id="test",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4, alt=5000),
            timestamp=datetime.now(timezone.utc),
            classification="hostile",
            information_classification="SECRET",
            confidence=0.92,
            source_sensors=["radar_01", "drone_alpha"],
            speed_kmh=450,
            heading=270
        )
        
        punto = entity.to_mapa_punto_interes()
        obs = punto['observaciones']
        
        assert "hostile" in obs
        assert "SECRET" in obs
        assert "0.92" in obs
        assert "radar_01" in obs
        assert "450.0 km/h" in obs
        assert "270.0°" in obs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])