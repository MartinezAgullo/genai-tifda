"""
Review Service
==============

Thread-safe state management for human review pipeline.

Handles reading/writing shared state between:
- TIFDA pipeline (writes pending items, reads decisions)
- Gradio UI (reads pending items, writes decisions)

Uses file locking to prevent race conditions.
"""

import json
import fcntl
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ==================== FILE LOCKING ====================

@contextmanager
def locked_file(file_path: Path, mode: str = "r"):
    """
    Context manager for thread-safe file access with locking.
    
    Args:
        file_path: Path to file
        mode: File mode ('r', 'w', 'r+')
        
    Yields:
        Open file handle with exclusive lock
        
    Example:
        with locked_file(state_file, 'r') as f:
            data = json.load(f)
    """
    f = open(file_path, mode)
    try:
        # Acquire exclusive lock (blocks until available)
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield f
    finally:
        # Release lock and close file
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


# ==================== STATE MANAGEMENT ====================

class ReviewService:
    """
    Service for managing shared review state.
    
    Thread-safe operations for pipeline-UI communication.
    """
    
    def __init__(self, state_file: Path):
        """
        Initialize review service.
        
        Args:
            state_file: Path to shared state JSON file
        """
        self.state_file = Path(state_file)
        
        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize file if it doesn't exist
        if not self.state_file.exists():
            self._initialize_state()
            logger.info(f"✅ Initialized shared state: {self.state_file}")
        else:
            logger.info(f"📂 Using existing shared state: {self.state_file}")
    
    def _initialize_state(self):
        """Create initial empty state file."""
        initial_state = {
            "pending_review_items": [],
            "human_decisions": [],
            "last_updated": None,
            "pipeline_active": False
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(initial_state, f, indent=2)
    
    def read_state(self) -> Dict[str, Any]:
        """
        Read current state (thread-safe).
        
        Returns:
            State dictionary
        """
        try:
            with locked_file(self.state_file, 'r') as f:
                state = json.load(f)
                return state
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse state file: {e}")
            # Return empty state if file is corrupted
            return {
                "pending_review_items": [],
                "human_decisions": [],
                "last_updated": None,
                "pipeline_active": False
            }
        except Exception as e:
            logger.error(f"❌ Error reading state: {e}")
            raise
    
    def write_state(self, state: Dict[str, Any]):
        """
        Write entire state (thread-safe).
        
        Args:
            state: Complete state dictionary
        """
        try:
            with locked_file(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                f.flush()  # Ensure written to disk
        except Exception as e:
            logger.error(f"❌ Error writing state: {e}")
            raise
    
    # ============ PIPELINE OPERATIONS (Write pending, Read decisions) ============
    
    def add_pending_items(self, items: List[Dict[str, Any]]):
        """
        Add items for human review (called by pipeline).
        
        Args:
            items: List of review items (threats, dissemination decisions)
        """
        state = self.read_state()
        
        # Add new items
        state["pending_review_items"].extend(items)
        state["last_updated"] = datetime.utcnow().isoformat()
        state["pipeline_active"] = True
        
        self.write_state(state)
        
        logger.info(f"📥 Added {len(items)} items for review (total pending: {len(state['pending_review_items'])})")
    
    def get_decisions(self, clear_after_read: bool = True) -> List[Dict[str, Any]]:
        """
        Get human decisions (called by pipeline).
        
        Args:
            clear_after_read: If True, clear decisions after reading
            
        Returns:
            List of human decisions
        """
        state = self.read_state()
        decisions = state["human_decisions"]
        
        if clear_after_read and decisions:
            # Clear decisions after pipeline reads them
            state["human_decisions"] = []
            state["last_updated"] = datetime.utcnow().isoformat()
            self.write_state(state)
            
            logger.info(f"✅ Pipeline retrieved {len(decisions)} decisions")
        
        return decisions
    
    def clear_pending_items(self):
        """Clear all pending items (called by pipeline after processing)."""
        state = self.read_state()
        cleared_count = len(state["pending_review_items"])
        
        state["pending_review_items"] = []
        state["last_updated"] = datetime.utcnow().isoformat()
        self.write_state(state)
        
        logger.info(f"🗑️  Cleared {cleared_count} pending items")
    
    # ============ UI OPERATIONS (Read pending, Write decisions) ============
    
    def get_pending_items(self) -> List[Dict[str, Any]]:
        """
        Get items awaiting review (called by UI).
        
        Returns:
            List of pending review items
        """
        state = self.read_state()
        return state["pending_review_items"]
    
    def submit_decision(self, decision: Dict[str, Any]):
        """
        Submit a human decision (called by UI).
        
        Args:
            decision: Decision dictionary with keys:
                - item_id: str
                - decision: "approve" | "reject" | "flag"
                - comments: str
                - reviewer_id: str
                - timestamp: str
        """
        state = self.read_state()
        
        # Add decision
        state["human_decisions"].append(decision)
        
        # Remove item from pending
        item_id = decision.get("item_id")
        state["pending_review_items"] = [
            item for item in state["pending_review_items"]
            if item.get("item_id") != item_id
        ]
        
        state["last_updated"] = datetime.utcnow().isoformat()
        
        self.write_state(state)
        
        logger.info(f"✅ Operator submitted decision for {item_id}: {decision.get('decision')}")
    
    def submit_bulk_decisions(self, decisions: List[Dict[str, Any]]):
        """
        Submit multiple decisions at once (called by UI "Approve All").
        
        Args:
            decisions: List of decision dictionaries
        """
        state = self.read_state()
        
        # Add all decisions
        state["human_decisions"].extend(decisions)
        
        # Remove items from pending
        decided_ids = {d.get("item_id") for d in decisions}
        state["pending_review_items"] = [
            item for item in state["pending_review_items"]
            if item.get("item_id") not in decided_ids
        ]
        
        state["last_updated"] = datetime.utcnow().isoformat()
        
        self.write_state(state)
        
        logger.info(f"✅ Operator submitted {len(decisions)} bulk decisions")
    
    # ============ TIMEOUT HANDLING ============
    
    def auto_approve_timed_out_items(self, timeout_seconds: int) -> int:
        """
        Auto-approve items that have been pending longer than timeout.
        
        Args:
            timeout_seconds: Timeout in seconds (0 = disabled)
            
        Returns:
            Number of items auto-approved
        """
        if timeout_seconds <= 0:
            return 0  # Timeout disabled
        
        state = self.read_state()
        now = datetime.utcnow()
        auto_approved = []
        
        remaining_items = []
        for item in state["pending_review_items"]:
            # Check if item has timed out
            added_at = datetime.fromisoformat(item.get("added_at", now.isoformat()))
            elapsed = (now - added_at).total_seconds()
            
            if elapsed >= timeout_seconds:
                # Auto-approve
                decision = {
                    "item_id": item.get("item_id"),
                    "decision": "approve",
                    "comments": f"Auto-approved after {timeout_seconds}s timeout",
                    "reviewer_id": "system_timeout",
                    "timestamp": now.isoformat(),
                    "auto_approved": True
                }
                auto_approved.append(decision)
            else:
                remaining_items.append(item)
        
        if auto_approved:
            state["human_decisions"].extend(auto_approved)
            state["pending_review_items"] = remaining_items
            state["last_updated"] = now.isoformat()
            self.write_state(state)
            
            logger.warning(f"⏰ Auto-approved {len(auto_approved)} items due to timeout")
        
        return len(auto_approved)
    
    # ============ STATUS ============
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current review status.
        
        Returns:
            Status dictionary with counts and timestamps
        """
        state = self.read_state()
        
        return {
            "pending_count": len(state["pending_review_items"]),
            "decisions_count": len(state["human_decisions"]),
            "last_updated": state.get("last_updated"),
            "pipeline_active": state.get("pipeline_active", False)
        }


# ==================== TESTING ====================

def test_review_service():
    """Test the review service"""
    import tempfile
    from pathlib import Path
    
    print("\n" + "=" * 70)
    print("REVIEW SERVICE TEST")
    print("=" * 70 + "\n")
    
    # Create temporary state file
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "test_state.json"
        service = ReviewService(state_file)
        
        # Test 1: Add pending items
        print("Test 1: Add pending items")
        items = [
            {
                "item_id": "threat_001",
                "item_type": "threat_assessment",
                "threat_level": "critical",
                "added_at": datetime.utcnow().isoformat()
            },
            {
                "item_id": "threat_002",
                "item_type": "threat_assessment",
                "threat_level": "high",
                "added_at": datetime.utcnow().isoformat()
            }
        ]
        service.add_pending_items(items)
        
        status = service.get_status()
        print(f"  Pending: {status['pending_count']}")
        assert status['pending_count'] == 2
        
        # Test 2: Get pending items
        print("\nTest 2: Get pending items")
        pending = service.get_pending_items()
        print(f"  Retrieved: {len(pending)} items")
        assert len(pending) == 2
        
        # Test 3: Submit decision
        print("\nTest 3: Submit decision")
        decision = {
            "item_id": "threat_001",
            "decision": "approve",
            "comments": "Confirmed critical threat",
            "reviewer_id": "operator_alpha",
            "timestamp": datetime.utcnow().isoformat()
        }
        service.submit_decision(decision)
        
        status = service.get_status()
        print(f"  Pending: {status['pending_count']}")
        print(f"  Decisions: {status['decisions_count']}")
        assert status['pending_count'] == 1
        assert status['decisions_count'] == 1
        
        # Test 4: Pipeline retrieves decisions
        print("\nTest 4: Pipeline retrieves decisions")
        decisions = service.get_decisions(clear_after_read=True)
        print(f"  Retrieved: {len(decisions)} decisions")
        assert len(decisions) == 1
        
        status = service.get_status()
        print(f"  Decisions after clear: {status['decisions_count']}")
        assert status['decisions_count'] == 0
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_review_service()