#!/usr/bin/env python3
"""
Test Script: mapa API v2 Compatibility
======================================

Verifies that TIFDA's EntityCOP.to_mapa_punto_interes() generates
payloads compatible with the new mapa-puntos-interes API v2.
The v2 is that with the new 'categoria' field and updated structure.
Also the one using APP6 nato symbolology.

Run: python test_mapa_v2_compatibility.py
"""

from datetime import datetime, timezone
import json
import sys

# Add src to path
sys.path.insert(0, 'src')

from src.models.cop_entities import EntityCOP, Location

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ️  {text}{RESET}")


# Valid mapa API v2 categories (lowercase enum)
VALID_CATEGORIES = [
    'missile', 'fighter', 'bomber', 'aircraft', 'helicopter', 'uav',
    'tank', 'artillery', 'ship', 'destroyer', 'submarine', 'ground_vehicle',
    'apc', 'infantry', 'person', 'base', 'building', 'infrastructure', 'default'
]

# Removed fields (should NOT be in payload)
REMOVED_FIELDS = ['ciudad', 'provincia', 'direccion', 'telefono', 'email', 'website']

# Required new fields
REQUIRED_FIELDS = ['country', 'alliance']


def test_entity_type(entity_type, classification="hostile", expected_categoria=None):
    """Test a single entity type"""
    
    # Create entity
    entity = EntityCOP(
        entity_id=f"test_{entity_type}",
        entity_type=entity_type,
        location=Location(lat=39.5, lon=-0.4, alt=1000),
        timestamp=datetime.now(timezone.utc),
        classification=classification,
        confidence=0.9,
        metadata={"country": "Spain"}
    )
    
    # Convert to mapa format
    punto_data = entity.to_mapa_punto_interes()
    
    # Check categoria
    categoria = punto_data.get('categoria')
    
    if categoria not in VALID_CATEGORIES:
        print_error(f"{entity_type:20s} → {categoria:20s} (INVALID)")
        return False
    
    if expected_categoria and categoria != expected_categoria:
        print_warning(f"{entity_type:20s} → {categoria:20s} (Expected: {expected_categoria})")
        return False
    
    print_success(f"{entity_type:20s} → {categoria:20s}")
    return True


def test_removed_fields():
    """Test that removed fields are NOT in payload"""
    print_header("TEST 1: Removed Fields")
    
    entity = EntityCOP(
        entity_id="test",
        entity_type="aircraft",
        location=Location(lat=39.5, lon=-0.4),
        timestamp=datetime.now(timezone.utc),
        classification="friendly",
        confidence=0.9
    )
    
    punto_data = entity.to_mapa_punto_interes()
    
    all_good = True
    for field in REMOVED_FIELDS:
        if field in punto_data:
            print_error(f"Field '{field}' should NOT be in payload")
            all_good = False
    
    if all_good:
        print_success("No removed fields in payload")
    
    return all_good


def test_new_fields():
    """Test that new required fields ARE in payload"""
    print_header("TEST 2: New Required Fields")
    
    entity = EntityCOP(
        entity_id="test",
        entity_type="aircraft",
        location=Location(lat=39.5, lon=-0.4),
        timestamp=datetime.now(timezone.utc),
        classification="hostile",
        confidence=0.9,
        metadata={"country": "Russia"}
    )
    
    punto_data = entity.to_mapa_punto_interes()
    
    all_good = True
    
    # Check country
    if 'country' not in punto_data:
        print_error("Field 'country' missing from payload")
        all_good = False
    else:
        country = punto_data['country']
        if country == "Russia":
            print_success(f"country = '{country}' (from metadata)")
        else:
            print_warning(f"country = '{country}' (expected 'Russia')")
    
    # Check alliance
    if 'alliance' not in punto_data:
        print_error("Field 'alliance' missing from payload")
        all_good = False
    else:
        alliance = punto_data['alliance']
        if alliance == "hostile":
            print_success(f"alliance = '{alliance}' (matches classification)")
        else:
            print_error(f"alliance = '{alliance}' (expected 'hostile')")
            all_good = False
    
    return all_good


def test_all_entity_types():
    """Test all TIFDA entity types map to valid categories"""
    print_header("TEST 3: All Entity Type Mappings")
    
    test_cases = [
        # Air entities
        ("aircraft", "aircraft"),
        ("fighter", "fighter"),
        ("bomber", "bomber"),
        ("transport", "aircraft"),
        ("helicopter", "helicopter"),
        ("uav", "uav"),
        ("missile", "missile"),
        ("air_unknown", "aircraft"),
        
        # Ground entities
        ("tank", "tank"),
        ("apc", "apc"),
        ("ifv", "apc"),
        ("artillery", "artillery"),
        ("infantry", "infantry"),
        ("ground_vehicle", "ground_vehicle"),
        ("ground_unknown", "ground_vehicle"),
        
        # Sea entities
        ("ship", "ship"),
        ("carrier", "ship"),
        ("destroyer", "destroyer"),
        ("frigate", "destroyer"),
        ("corvette", "destroyer"),
        ("patrol_boat", "ship"),
        ("submarine", "submarine"),
        ("boat", "ship"),
        ("sea_unknown", "ship"),
        
        # Infrastructure
        ("command_post", "base"),
        ("radar_site", "base"),
        ("infrastructure", "infrastructure"),
        ("building", "building"),
        ("bridge", "infrastructure"),
        ("base", "base"),
        
        # Other
        ("satellite", "default"),
        ("cyber_node", "default"),
        ("person", "person"),
        ("event", "default"),
        ("unknown", "default"),
    ]
    
    passed = 0
    failed = 0
    
    for entity_type, expected_categoria in test_cases:
        if test_entity_type(entity_type, expected_categoria=expected_categoria):
            passed += 1
        else:
            failed += 1
    
    print(f"\n{GREEN}Passed: {passed}{RESET} / {RED}Failed: {failed}{RESET} / Total: {len(test_cases)}")
    
    return failed == 0


def test_alliance_mapping():
    """Test that TIFDA classifications map correctly to mapa alliance"""
    print_header("TEST 4: Alliance Mapping")
    
    test_cases = [
        ("friendly", "friendly"),
        ("hostile", "hostile"),
        ("neutral", "neutral"),
        ("unknown", "unknown"),
    ]
    
    all_good = True
    
    for classification, expected_alliance in test_cases:
        entity = EntityCOP(
            entity_id="test",
            entity_type="aircraft",
            location=Location(lat=39.5, lon=-0.4),
            timestamp=datetime.now(timezone.utc),
            classification=classification,
            confidence=0.9
        )
        
        punto_data = entity.to_mapa_punto_interes()
        alliance = punto_data.get('alliance')
        
        if alliance == expected_alliance:
            print_success(f"classification '{classification}' → alliance '{alliance}'")
        else:
            print_error(f"classification '{classification}' → alliance '{alliance}' (expected '{expected_alliance}')")
            all_good = False
    
    return all_good


def test_payload_structure():
    """Test complete payload structure"""
    print_header("TEST 5: Complete Payload Structure")
    
    entity = EntityCOP(
        entity_id="test_aircraft_001",
        entity_type="fighter",
        location=Location(lat=39.4745, lon=-0.3768, alt=5000),
        timestamp=datetime.now(timezone.utc),
        classification="hostile",
        confidence=0.95,
        comments="Test entity for payload validation",
        metadata={"country": "Unknown"}
    )
    
    punto_data = entity.to_mapa_punto_interes()
    
    print_info("Generated payload:")
    print(json.dumps(punto_data, indent=2))
    
    # Check required fields
    required = [
        'nombre', 'descripcion', 'categoria', 'country', 'alliance',
        'elemento_identificado', 'activo', 'tipo_elemento', 'prioridad',
        'observaciones', 'longitud', 'latitud'
    ]
    
    all_good = True
    for field in required:
        if field not in punto_data:
            print_error(f"Missing required field: {field}")
            all_good = False
    
    if all_good:
        print_success("All required fields present")
    
    # Check categoria is valid
    if punto_data['categoria'] in VALID_CATEGORIES:
        print_success(f"Valid categoria: {punto_data['categoria']}")
    else:
        print_error(f"Invalid categoria: {punto_data['categoria']}")
        all_good = False
    
    # Check no removed fields
    for field in REMOVED_FIELDS:
        if field in punto_data:
            print_error(f"Removed field still present: {field}")
            all_good = False
    
    return all_good


def main():
    """Run all tests"""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{'TIFDA mapa API v2 Compatibility Test':^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    print_info("Testing EntityCOP.to_mapa_punto_interes() compatibility")
    print_info(f"Valid categories: {len(VALID_CATEGORIES)}")
    
    results = []
    
    # Run all tests
    results.append(("Removed Fields", test_removed_fields()))
    results.append(("New Required Fields", test_new_fields()))
    results.append(("Entity Type Mappings", test_all_entity_types()))
    results.append(("Alliance Mapping", test_alliance_mapping()))
    results.append(("Payload Structure", test_payload_structure()))
    
    # Summary
    print_header("SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name:30s} PASSED")
        else:
            print_error(f"{test_name:30s} FAILED")
    
    print(f"\n{GREEN if passed == total else RED}{'='*70}{RESET}")
    if passed == total:
        print(f"{GREEN}ALL TESTS PASSED ({passed}/{total}){RESET}")
        print(f"{GREEN}✅ TIFDA is compatible with mapa API v2!{RESET}")
        return 0
    else:
        print(f"{RED}SOME TESTS FAILED ({passed}/{total}){RESET}")
        print(f"{RED}❌ Please update cop_entities.py{RESET}")
        return 1


if __name__ == "__main__":
    exit(main())