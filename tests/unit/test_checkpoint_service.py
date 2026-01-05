"""
Unit tests for CheckpointService.
"""

import pytest
import os
import json
import tempfile
import shutil
from services.checkpoint_service import CheckpointService


@pytest.fixture
def temp_checkpoint_dir():
    """Create a temporary checkpoint directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def test_save_and_load_checkpoint(temp_checkpoint_dir):
    """Test saving and loading a checkpoint."""
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    
    test_data = {
        'session_id': 'test123',
        'data': 'test data',
        'complete': False
    }
    
    # Save
    success = service.save_checkpoint('test123', test_data, 'batch_analysis')
    assert success
    
    # Load
    loaded = service.load_checkpoint('test123', 'batch_analysis')
    assert loaded is not None
    assert loaded['session_id'] == 'test123'
    assert loaded['data'] == 'test data'


def test_list_checkpoints(temp_checkpoint_dir):
    """Test listing checkpoints."""
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    
    # Save a few checkpoints
    for i in range(3):
        service.save_checkpoint(f'session{i}', {'data': f'test{i}'}, 'batch_analysis')
    
    checkpoints = service.list_checkpoints('batch_analysis')
    assert len(checkpoints) == 3


def test_delete_checkpoint(temp_checkpoint_dir):
    """Test deleting a checkpoint."""
    service = CheckpointService(checkpoint_dir=temp_checkpoint_dir)
    
    # Save
    service.save_checkpoint('test123', {'data': 'test'}, 'batch_analysis')
    
    # Delete
    deleted = service.delete_checkpoint('test123', 'batch_analysis')
    assert deleted
    
    # Verify deleted
    loaded = service.load_checkpoint('test123', 'batch_analysis')
    assert loaded is None


