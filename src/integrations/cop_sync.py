"""
COP Synchronization
===================

Synchronizes TIFDA's in-memory COP state with mapa-puntos-interes.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from langsmith import traceable

from src.models import EntityCOP
from src.integrations.mapa_client import get_mapa_client, MapaClientError


class COPSyncError(Exception):
    """Exception raised for COP sync errors"""
    pass


class COPSync:
    """
    Synchronizes TIFDA COP with mapa-puntos-interes visualization.
    
    Strategy:
    - TIFDA COP (in-memory) is the source of truth
    - mapa-puntos-interes is a view/visualization layer
    - Sync happens asynchronously (non-blocking)
    """
    
    def __init__(self, mapa_base_url: Optional[str] = None):
        """
        Initialize COP sync.
        
        Args:
            mapa_base_url: Base URL of mapa-puntos-interes (None = use config)
        """
        # Get from config if not provided
        if mapa_base_url is None:
            from src.core.config import get_config
            config = get_config()
            mapa_base_url = config.integrations.mapa_base_url
        
        self.client = get_mapa_client(base_url=mapa_base_url)
        self.last_sync: Optional[datetime] = None
        self.sync_stats = {
            'total_syncs': 0,
            'total_created': 0,
            'total_updated': 0,
            'total_deleted': 0,
            'total_errors': 0
        }
    
    @traceable(name="cop_sync_entity")
    def sync_entity(self, entity: EntityCOP) -> tuple[bool, str]:
        """
        Sync single entity to mapa-puntos-interes.
        
        Args:
            entity: EntityCOP to sync
            
        Returns:
            (success, message)
        """
        try:
            # Convert to mapa format
            punto_data = entity.to_mapa_punto_interes()
            
            # Upsert (create or update)
            punto, was_created = self.client.upsert_punto(punto_data)
            
            # Update stats
            if was_created:
                self.sync_stats['total_created'] += 1
                action = "created"
            else:
                self.sync_stats['total_updated'] += 1
                action = "updated"
            
            return True, f"Entity {entity.entity_id} {action} in mapa (id={punto['id']})"
            
        except Exception as e:
            self.sync_stats['total_errors'] += 1
            error_msg = f"Failed to sync entity {entity.entity_id}: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    @traceable(name="cop_sync_batch")
    def sync_batch(self, entities: List[EntityCOP]) -> Dict[str, Any]:
        """
        Sync multiple entities to mapa-puntos-interes.
        
        Args:
            entities: List of EntityCOP objects
            
        Returns:
            Statistics dictionary
        """
        if not entities:
            return {
                'success': True,
                'count': 0,
                'created': 0,
                'updated': 0,
                'failed': 0,
                'errors': []
            }
        
        # Convert all entities to mapa format
        puntos_data = []
        conversion_errors = []
        
        for entity in entities:
            try:
                punto_data = entity.to_mapa_punto_interes()
                puntos_data.append(punto_data)
            except Exception as e:
                conversion_errors.append(f"{entity.entity_id}: {str(e)}")
        
        # Batch upsert
        try:
            stats = self.client.batch_upsert(puntos_data)
            
            # Update global stats
            self.sync_stats['total_created'] += stats['created']
            self.sync_stats['total_updated'] += stats['updated']
            self.sync_stats['total_errors'] += stats['failed']
            self.sync_stats['total_syncs'] += 1
            self.last_sync = datetime.utcnow()
            
            return {
                'success': True,
                'count': len(entities),
                'created': stats['created'],
                'updated': stats['updated'],
                'failed': stats['failed'] + len(conversion_errors),
                'errors': stats['errors'] + conversion_errors
            }
            
        except Exception as e:
            return {
                'success': False,
                'count': len(entities),
                'created': 0,
                'updated': 0,
                'failed': len(entities),
                'errors': [f"Batch sync failed: {str(e)}"] + conversion_errors
            }
    
    @traceable(name="cop_sync_full")
    def sync_full_cop(self, cop_entities: Dict[str, EntityCOP]) -> Dict[str, Any]:
        """
        Sync entire COP state to mapa-puntos-interes.
        
        This is a full synchronization - all entities in TIFDA COP
        are pushed to mapa-puntos-interes.
        
        Args:
            cop_entities: Full COP dictionary {entity_id: EntityCOP}
            
        Returns:
            Statistics dictionary
        """
        entities_list = list(cop_entities.values())
        
        print(f"🔄 Syncing {len(entities_list)} entities to mapa-puntos-interes...")
        
        result = self.sync_batch(entities_list)
        
        if result['success']:
            print(f"✅ Full COP sync complete: "
                  f"{result['created']} created, "
                  f"{result['updated']} updated, "
                  f"{result['failed']} failed")
        else:
            print(f"⚠️ Full COP sync completed with errors: {result['failed']} failed")
        
        return result
    
    @traceable(name="cop_sync_remove_entity")
    def remove_entity(self, entity_id: str) -> tuple[bool, str]:
        """
        Remove entity from mapa-puntos-interes.
        
        Args:
            entity_id: TIFDA entity_id (elemento_identificado)
            
        Returns:
            (success, message)
        """
        try:
            # Find punto by elemento_identificado
            punto = self.client.find_by_elemento_identificado(entity_id)
            
            if not punto:
                return True, f"Entity {entity_id} not found in mapa (already removed)"
            
            # Delete punto
            punto_id = punto['id']
            success = self.client.delete_punto(punto_id)
            
            if success:
                self.sync_stats['total_deleted'] += 1
                return True, f"Entity {entity_id} removed from mapa"
            else:
                return False, f"Failed to delete entity {entity_id} from mapa"
                
        except Exception as e:
            self.sync_stats['total_errors'] += 1
            error_msg = f"Failed to remove entity {entity_id}: {str(e)}"
            print(f"❌ {error_msg}")
            return False, error_msg
    
    def get_sync_stats(self) -> Dict[str, Any]:
        """
        Get synchronization statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            **self.sync_stats,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None
        }
    
    def check_connection(self) -> tuple[bool, str]:
        """
        Check connection to mapa-puntos-interes.
        
        Returns:
            (is_connected, message)
        """
        return self.client.health_check()


# ==================== SINGLETON INSTANCE ====================

_cop_sync: Optional[COPSync] = None


def get_cop_sync(mapa_base_url: str = "http://localhost:3000") -> COPSync:
    """
    Get global COPSync instance (singleton).
    
    Args:
        mapa_base_url: Base URL of mapa-puntos-interes
        
    Returns:
        COPSync instance
    """
    global _cop_sync
    
    if _cop_sync is None:
        _cop_sync = COPSync(mapa_base_url=mapa_base_url)
    
    return _cop_sync