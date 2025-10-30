"""
Mapa Client
===========

HTTP client for interacting with mapa-puntos-interes API.
"""

import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import time

from langsmith import traceable


class MapaClientError(Exception):
    """Exception raised for Mapa API errors"""
    pass


class MapaClient:
    """
    HTTP client for mapa-puntos-interes REST API.
    
    Handles all communication with the map visualization service.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize Mapa client.
        
        Args:
            base_url: Base URL of mapa-puntos-interes (None = use config)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries
        """
        # Get from config if not provided
        if base_url is None:
            from src.core.config import get_config
            config = get_config()
            base_url = config.integrations.mapa_base_url
            timeout = config.integrations.mapa_timeout
            max_retries = config.integrations.mapa_max_retries
        
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api/puntos"
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TIFDA/1.0'
        })
    
    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Request URL
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
            
        Raises:
            MapaClientError: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs
                )
                
                # Raise for HTTP errors (4xx, 5xx)
                response.raise_for_status()
                
                return response
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⚠️ Timeout on attempt {attempt + 1}/{self.max_retries}, retrying in {delay}s...")
                    time.sleep(delay)
                
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"⚠️ Connection error on attempt {attempt + 1}/{self.max_retries}, retrying in {delay}s...")
                    time.sleep(delay)
                
            except requests.exceptions.HTTPError as e:
                # Don't retry on 4xx errors (client errors)
                if 400 <= e.response.status_code < 500:
                    raise MapaClientError(f"Client error: {e.response.status_code} - {e.response.text}")
                
                # Retry on 5xx errors (server errors)
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"⚠️ Server error on attempt {attempt + 1}/{self.max_retries}, retrying in {delay}s...")
                    time.sleep(delay)
        
        # All retries failed
        raise MapaClientError(f"All {self.max_retries} attempts failed: {last_exception}")
    
    @traceable(name="mapa_health_check")
    def health_check(self) -> Tuple[bool, str]:
        """
        Check if mapa-puntos-interes server is reachable.
        
        Returns:
            (is_healthy, message)
        """
        try:
            response = self._request_with_retry('GET', f"{self.base_url}/health")
            data = response.json()
            return True, f"Server OK - Uptime: {data.get('uptime', 'unknown')}s"
        except Exception as e:
            return False, f"Server unreachable: {str(e)}"
    
    @traceable(name="mapa_get_all_puntos")
    def get_all_puntos(self) -> List[Dict[str, Any]]:
        """
        Get all puntos from mapa-puntos-interes.
        
        Returns:
            List of punto dictionaries
        """
        try:
            response = self._request_with_retry('GET', self.api_url)
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            raise MapaClientError(f"Failed to get puntos: {str(e)}")
    
    @traceable(name="mapa_get_punto_by_id")
    def get_punto_by_id(self, punto_id: int) -> Optional[Dict[str, Any]]:
        """
        Get specific punto by database ID.
        
        Args:
            punto_id: Database ID (not elemento_identificado)
            
        Returns:
            Punto dictionary or None if not found
        """
        try:
            response = self._request_with_retry('GET', f"{self.api_url}/{punto_id}")
            data = response.json()
            return data.get('data')
        except MapaClientError as e:
            if "404" in str(e):
                return None
            raise
    
    @traceable(name="mapa_find_by_elemento_identificado")
    def find_by_elemento_identificado(self, elemento_id: str) -> Optional[Dict[str, Any]]:
        """
        Find punto by elemento_identificado (TIFDA entity_id).
        
        This searches all puntos and finds the one matching the elemento_identificado.
        
        Args:
            elemento_id: TIFDA entity_id (e.g., "radar_01_T001")
            
        Returns:
            Punto dictionary or None if not found
        """
        try:
            all_puntos = self.get_all_puntos()
            for punto in all_puntos:
                if punto.get('elemento_identificado') == elemento_id:
                    return punto
            return None
        except Exception as e:
            raise MapaClientError(f"Failed to find punto by elemento_identificado: {str(e)}")
    
    @traceable(name="mapa_create_punto")
    def create_punto(self, punto_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new punto in mapa-puntos-interes.
        
        Args:
            punto_data: Punto dictionary with required fields
            
        Returns:
            Created punto with database ID
            
        Raises:
            MapaClientError: If creation fails
        """
        try:
            response = self._request_with_retry(
                'POST',
                self.api_url,
                json=punto_data
            )
            data = response.json()
            
            if not data.get('success'):
                raise MapaClientError(f"Server returned success=false: {data.get('message')}")
            
            return data.get('data')
            
        except Exception as e:
            raise MapaClientError(f"Failed to create punto: {str(e)}")
    
    @traceable(name="mapa_update_punto")
    def update_punto(self, punto_id: int, punto_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing punto in mapa-puntos-interes.
        
        Args:
            punto_id: Database ID of punto to update
            punto_data: Updated punto data
            
        Returns:
            Updated punto dictionary
            
        Raises:
            MapaClientError: If update fails
        """
        try:
            print(f"\n🔍 DEBUG UPDATE:")
            print(f"    Punto ID: {punto_id}")
            print(f"    Data keys: {list(punto_data.keys())}")
            print(f"    Has longitud/latitud: {'longitud' in punto_data}, {'latitud' in punto_data}")
            if 'longitud' in punto_data and 'latitud' in punto_data:
                print(f"    Coords: ({punto_data['latitud']}, {punto_data['longitud']})")
            
            response = self._request_with_retry(
                'PUT',
                f"{self.api_url}/{punto_id}",
                json=punto_data
            )
            data = response.json()
            
            if not data.get('success'):
                raise MapaClientError(f"Server returned success=false: {data.get('message')}")
            
            return data.get('data')
            
        except Exception as e:
            raise MapaClientError(f"Failed to update punto: {str(e)}")
    
    @traceable(name="mapa_delete_punto")
    def delete_punto(self, punto_id: int) -> bool:
        """
        Delete punto from mapa-puntos-interes.
        
        Args:
            punto_id: Database ID of punto to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            MapaClientError: If deletion fails
        """
        try:
            response = self._request_with_retry(
                'DELETE',
                f"{self.api_url}/{punto_id}"
            )
            data = response.json()
            return data.get('success', False)
            
        except Exception as e:
            raise MapaClientError(f"Failed to delete punto: {str(e)}")
    
    @traceable(name="mapa_upsert_punto")
    def upsert_punto(self, punto_data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
        """
        Create or update punto (upsert operation).
        
        Uses elemento_identificado to check if punto exists.
        If exists, updates it. If not, creates it.
        
        Args:
            punto_data: Punto data with elemento_identificado
            
        Returns:
            (punto_dict, was_created)
            - punto_dict: Created or updated punto
            - was_created: True if created, False if updated
            
        Raises:
            MapaClientError: If operation fails
        """
        elemento_id = punto_data.get('elemento_identificado')
        
        if not elemento_id:
            raise MapaClientError("punto_data must include 'elemento_identificado'")
        
        # Check if exists
        existing = self.find_by_elemento_identificado(elemento_id)
        
        if existing:
            # Update existing
            punto_id = existing['id']

            update_data = punto_data.copy()
            static_keys = ['elemento_identificado', 'tipo_elemento', 'nombre', 'created_at']
            for key in static_keys:
                if key in update_data:
                    del update_data[key]

            updated = self.update_punto(punto_id, punto_data)
            return updated, False
        else:
            # Create new
            created = self.create_punto(punto_data)
            return created, True
    
    @traceable(name="mapa_batch_upsert")
    def batch_upsert(self, puntos_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Batch upsert multiple puntos.
        
        Args:
            puntos_data: List of punto dictionaries
            
        Returns:
            Statistics: {
                'created': int,
                'updated': int,
                'failed': int,
                'errors': List[str]
            }
        """
        stats = {
            'created': 0,
            'updated': 0,
            'failed': 0,
            'errors': []
        }
        
        for punto_data in puntos_data:
            try:
                _, was_created = self.upsert_punto(punto_data)
                if was_created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1
            except Exception as e:
                stats['failed'] += 1
                elemento_id = punto_data.get('elemento_identificado', 'unknown')
                stats['errors'].append(f"{elemento_id}: {str(e)}")
        
        return stats
    
    def close(self):
        """Close HTTP session"""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# ==================== SINGLETON INSTANCE ====================

_mapa_client: Optional[MapaClient] = None


def get_mapa_client(
    base_url: str = "http://localhost:3000",
    force_new: bool = False
) -> MapaClient:
    """
    Get global MapaClient instance (singleton).
    
    Args:
        base_url: Base URL of mapa-puntos-interes server
        force_new: Force creation of new client instance
        
    Returns:
        MapaClient instance
    """
    global _mapa_client
    
    if _mapa_client is None or force_new:
        _mapa_client = MapaClient(base_url=base_url)
    
    return _mapa_client