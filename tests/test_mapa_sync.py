#!/usr/bin/env python3
"""
Test Mapa Synchronization
==========================

Manual test script for mapa-puntos-interes integration.

Prerequisites:
- mapa-puntos-interes server running on localhost:3000
- PostgreSQL database initialized

Usage:
    python scripts/test_mapa_sync.py
"""

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..')
sys.path.insert(0, project_root)

from datetime import datetime, timezone
from src.models import EntityCOP, Location
from src.integrations import get_mapa_client, get_cop_sync


def test_connection():
    """Test connection to mapa-puntos-interes"""
    print("=" * 70)
    print("TEST 1: CONNECTION")
    print("=" * 70)
    
    client = get_mapa_client()
    is_healthy, msg = client.health_check()
    
    if is_healthy:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
        print("\n⚠️ Make sure mapa-puntos-interes is running:")
        print("   cd /path/to/mapa-puntos-interes")
        print("   npm run dev")
        return False
    
    return True


def test_single_entity_sync():
    """Test syncing a single entity"""
    print("\n" + "=" * 70)
    print("TEST 2: SINGLE ENTITY SYNC")
    print("=" * 70)
    
    # Create test entity
    entity = EntityCOP(
        entity_id="test_radar_T001",
        entity_type="aircraft",
        location=Location(lat=39.5, lon=-0.4, alt=5000),
        timestamp=datetime.now(timezone.utc),
        classification="hostile",
        information_classification="SECRET",
        confidence=0.9,
        source_sensors=["test_radar"],
        speed_kmh=450,
        heading=270,
        comments="Test aircraft for integration"
    )
    
    print(f"\nEntity: {entity.entity_id}")
    print(f"  Type: {entity.entity_type}")
    print(f"  Classification: {entity.classification}")
    print(f"  Location: ({entity.location.lat}, {entity.location.lon})")
    
    # Sync to mapa
    sync = get_cop_sync()
    success, msg = sync.sync_entity(entity)
    
    if success:
        print(f"\n✅ {msg}")
    else:
        print(f"\n❌ {msg}")
        return False
    
    # Verify in mapa
    client = get_mapa_client()
    punto = client.find_by_elemento_identificado(entity.entity_id)
    
    if punto:
        print(f"\n✅ Verified in mapa:")
        print(f"   ID: {punto['id']}")
        print(f"   Categoria: {punto['categoria']}")
        print(f"   Prioridad: {punto['prioridad']}")
        print(f"   Activo: {punto['activo']}")
    else:
        print(f"\n❌ Entity not found in mapa")
        return False
    
    return True


def test_batch_sync():
    """Test syncing multiple entities"""
    print("\n" + "=" * 70)
    print("TEST 3: BATCH SYNC")
    print("=" * 70)
    
    # Create multiple test entities
    entities = []
    for i in range(5):
        entity = EntityCOP(
            entity_id=f"test_batch_{i:03d}",
            entity_type="aircraft" if i % 2 == 0 else "tank",
            location=Location(
                lat=39.5 + (i * 0.1),
                lon=-0.4 + (i * 0.1)
            ),
            timestamp=datetime.now(timezone.utc),
            classification=["friendly", "hostile", "unknown", "neutral"][i % 4],
            information_classification="CONFIDENTIAL",
            confidence=0.8 + (i * 0.02),
            source_sensors=["test_batch_sensor"]
        )
        entities.append(entity)
    
    print(f"\nCreated {len(entities)} test entities")
    
    # Batch sync
    sync = get_cop_sync()
    result = sync.sync_batch(entities)
    
    print(f"\n✅ Batch sync complete:")
    print(f"   Created: {result['created']}")
    print(f"   Updated: {result['updated']}")
    print(f"   Failed: {result['failed']}")
    
    if result['failed'] > 0:
        print(f"\n⚠️ Errors:")
        for error in result['errors']:
            print(f"   - {error}")
    
    return result['failed'] == 0


def test_update_entity():
    """Test updating an existing entity"""
    print("\n" + "=" * 70)
    print("TEST 4: UPDATE ENTITY")
    print("=" * 70)
    
    # Create initial entity
    entity = EntityCOP(
        entity_id="test_update_001",
        entity_type="aircraft",
        location=Location(lat=39.5, lon=-0.4),
        timestamp=datetime.now(timezone.utc),
        classification="unknown",
        confidence=0.7,
        source_sensors=["test"]
    )
    
    sync = get_cop_sync()
    sync.sync_entity(entity)
    print("✅ Initial entity synced")
    
    # Update entity
    entity.classification = "hostile"
    entity.confidence = 0.95
    entity.location = Location(lat=39.6, lon=-0.5, alt=6000)
    entity.speed_kmh = 500
    
    success, msg = sync.sync_entity(entity)
    
    if success:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
        return False
    
    # Verify update
    client = get_mapa_client()
    punto = client.find_by_elemento_identificado(entity.entity_id)
    
    if punto:
        print(f"\n✅ Update verified:")
        print(f"   Prioridad: {punto['prioridad']} (should be 9 for hostile)")
        print(f"   Location: ({punto['latitud']}, {punto['longitud']})")
        assert punto['prioridad'] == 9, "Priority should be 9 for hostile"
    
    return True


def test_remove_entity():
    """Test removing an entity"""
    print("\n" + "=" * 70)
    print("TEST 5: REMOVE ENTITY")
    print("=" * 70)
    
    entity_id = "test_remove_001"
    
    # Create entity first
    entity = EntityCOP(
        entity_id=entity_id,
        entity_type="aircraft",
        location=Location(lat=39.5, lon=-0.4),
        timestamp=datetime.now(timezone.utc),
        classification="neutral",
        confidence=0.8,
        source_sensors=["test"]
    )
    
    sync = get_cop_sync()
    sync.sync_entity(entity)
    print("✅ Entity created for removal test")
    
    # Remove entity
    success, msg = sync.remove_entity(entity_id)
    
    if success:
        print(f"✅ {msg}")
    else:
        print(f"❌ {msg}")
        return False
    
    # Verify removal
    client = get_mapa_client()
    punto = client.find_by_elemento_identificado(entity_id)
    
    if punto is None:
        print("✅ Entity successfully removed from mapa")
    else:
        print("❌ Entity still exists in mapa")
        return False
    
    return True


def test_statistics():
    """Test sync statistics"""
    print("\n" + "=" * 70)
    print("TEST 6: STATISTICS")
    print("=" * 70)
    
    sync = get_cop_sync()
    stats = sync.get_sync_stats()
    
    print("\n📊 Sync Statistics:")
    print(f"   Total syncs: {stats['total_syncs']}")
    print(f"   Total created: {stats['total_created']}")
    print(f"   Total updated: {stats['total_updated']}")
    print(f"   Total deleted: {stats['total_deleted']}")
    print(f"   Total errors: {stats['total_errors']}")
    print(f"   Last sync: {stats['last_sync']}")
    
    return True


def cleanup():
    """Clean up test entities"""
    print("\n" + "=" * 70)
    print("CLEANUP")
    print("=" * 70)
    
    test_prefixes = ["test_radar", "test_batch", "test_update", "test_remove"]
    
    client = get_mapa_client()
    all_puntos = client.get_all_puntos()
    
    cleaned = 0
    for punto in all_puntos:
        elemento_id = punto.get('elemento_identificado', '')
        if any(elemento_id.startswith(prefix) for prefix in test_prefixes):
            try:
                client.delete_punto(punto['id'])
                cleaned += 1
            except Exception as e:
                print(f"⚠️ Failed to clean {elemento_id}: {e}")
    
    print(f"✅ Cleaned up {cleaned} test entities")


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 20 + "MAPA SYNC TEST SUITE" + " " * 28 + "║")
    print("╚" + "═" * 68 + "╝")
    print("\n")
    
    tests = [
        ("Connection Test", test_connection),
        ("Single Entity Sync", test_single_entity_sync),
        ("Batch Sync", test_batch_sync),
        ("Update Entity", test_update_entity),
        ("Remove Entity", test_remove_entity),
        ("Statistics", test_statistics),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
                print(f"\n❌ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name} FAILED with exception:")
            print(f"   {str(e)}")
            import traceback
            traceback.print_exc()
    
    # Cleanup
    try:
        cleanup()
    except Exception as e:
        print(f"⚠️ Cleanup failed: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {passed + failed}")
    print("=" * 70)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉\n")
        return 0
    else:
        print(f"\n⚠️ {failed} TEST(S) FAILED\n")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())