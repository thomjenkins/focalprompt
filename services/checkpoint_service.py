#!/usr/bin/env python3
"""
Checkpoint management service.

Handles saving, loading, and listing checkpoints for batch operations.
"""

import os
import json
import re
import sys
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime


# Filename components for checkpoint paths. Anything outside this charset can
# introduce separators or ``..`` segments and escape the checkpoint directory.
_CHECKPOINT_COMPONENT_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')

# Whitelist of checkpoint kinds (must match get_checkpoint_path docstring).
ALLOWED_CHECKPOINT_TYPES = frozenset({
    'batch_analysis',
    'batch_agents',
    'single_ablation',
    'single_assessment',
})


def validate_checkpoint_identifiers(session_id: str, checkpoint_type: str) -> None:
    """
    Reject session_id / checkpoint_type values that are unsafe as path components.

    Both must match ``^[A-Za-z0-9_-]{1,64}$``. ``checkpoint_type`` must also be
    in ``ALLOWED_CHECKPOINT_TYPES``. Raises ``ValueError`` without echoing the
    rejected value.
    """
    if not isinstance(session_id, str) or not _CHECKPOINT_COMPONENT_RE.fullmatch(session_id):
        raise ValueError('Invalid session_id')
    if not isinstance(checkpoint_type, str) or not _CHECKPOINT_COMPONENT_RE.fullmatch(checkpoint_type):
        raise ValueError('Invalid checkpoint_type')
    if checkpoint_type not in ALLOWED_CHECKPOINT_TYPES:
        raise ValueError('Invalid checkpoint_type')


class CheckpointService:
    """Service for managing checkpoints."""
    
    def __init__(self, checkpoint_dir: str = None):
        """
        Initialize checkpoint service.
        
        Args:
            checkpoint_dir: Directory to store checkpoints. If None, uses /tmp/checkpoints on Vercel or ./checkpoints locally.
        """
        if checkpoint_dir is None:
            # Use /tmp on Vercel (writable), or ./checkpoints locally
            if os.path.exists('/tmp') and os.access('/tmp', os.W_OK):
                checkpoint_dir = '/tmp/checkpoints'
            else:
                checkpoint_dir = "checkpoints"
        
        self.checkpoint_dir = checkpoint_dir
        try:
            os.makedirs(checkpoint_dir, exist_ok=True)
        except (OSError, PermissionError) as e:
            # If we can't create the directory, log but don't fail
            # Checkpoints will be disabled for this session
            print(f"Warning: Could not create checkpoint directory {checkpoint_dir}: {e}", file=sys.stderr)
            print("Checkpoint saving will be disabled for this session.", file=sys.stderr)
            self.checkpoint_dir = None
    
    def get_checkpoint_path(self, session_id: str, checkpoint_type: str = 'batch_analysis') -> str:
        """
        Get checkpoint file path for a session.
        
        Args:
            session_id: Session identifier
            checkpoint_type: Type of checkpoint ('batch_analysis', 'batch_agents', 'single_ablation', 'single_assessment')
            
        Returns:
            Full path to checkpoint file

        Raises:
            ValueError: If session_id or checkpoint_type is invalid, or if the
                resolved path would escape the checkpoint directory.
        """
        validate_checkpoint_identifiers(session_id, checkpoint_type)

        if self.checkpoint_dir is None:
            # Return a dummy path if checkpoint directory is not available
            base_dir = '/tmp'
        else:
            base_dir = self.checkpoint_dir

        checkpoint_path = os.path.join(base_dir, f"{checkpoint_type}_{session_id}.json")

        # Defence in depth: after join, the resolved path must stay inside base_dir.
        base_resolved = Path(base_dir).resolve()
        path_resolved = Path(checkpoint_path).resolve()
        if not path_resolved.is_relative_to(base_resolved):
            raise ValueError('Invalid checkpoint path')

        return str(path_resolved)
    
    def save_checkpoint(
        self,
        session_id: str,
        checkpoint_data: Dict,
        checkpoint_type: str = 'batch_analysis'
    ) -> bool:
        """
        Save checkpoint data to file using atomic writes.
        
        Args:
            session_id: Session identifier
            checkpoint_data: Data to save
            checkpoint_type: Type of checkpoint
            
        Returns:
            True if successful, False otherwise
        """
        # If checkpoint directory is None (couldn't be created), skip saving
        if self.checkpoint_dir is None:
            return False
        
        checkpoint_path = self.get_checkpoint_path(session_id, checkpoint_type)
        temp_path = checkpoint_path + '.tmp'
        
        try:
            # Write to temporary file first
            with open(temp_path, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # Atomic rename
            os.rename(temp_path, checkpoint_path)
            return True
        except (OSError, PermissionError) as e:
            # Don't log as error - checkpoint saving is optional
            print(f"Warning: Could not save checkpoint {session_id}: {e}", file=sys.stderr)
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False
        except Exception as e:
            print(f"Error saving checkpoint {session_id}: {e}", file=sys.stderr)
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False
    
    def load_checkpoint(
        self,
        session_id: str,
        checkpoint_type: str = 'batch_analysis'
    ) -> Optional[Dict]:
        """
        Load checkpoint data from file.
        
        Args:
            session_id: Session identifier
            checkpoint_type: Type of checkpoint
            
        Returns:
            Checkpoint data dict or None if not found/error
        """
        checkpoint_path = self.get_checkpoint_path(session_id, checkpoint_type)
        try:
            if os.path.exists(checkpoint_path):
                with open(checkpoint_path, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        print(f"Checkpoint file {session_id} is empty")
                        return None
                    
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError as e:
                        # File might be incomplete/corrupted - try to recover what we can
                        print(f"Warning: Checkpoint {session_id} has invalid JSON: {e}")
                        print(f"Attempting to recover data from incomplete file...")
                        
                        # For now, return None and let caller handle it
                        print(f"Could not recover data from corrupted checkpoint {session_id}")
                        return None
        except Exception as e:
            print(f"Error loading checkpoint: {e}")
        return None
    
    def list_checkpoints(self, checkpoint_type: str = 'batch_analysis') -> List[Dict]:
        """
        List all available checkpoints of a given type.
        
        Args:
            checkpoint_type: Type of checkpoint to list
            
        Returns:
            List of checkpoint info dicts
        """
        # Validate type up front (no session_id yet). Using a dummy legal session_id
        # keeps a single validator as the source of truth for type rules.
        validate_checkpoint_identifiers('_', checkpoint_type)

        checkpoints = []
        if self.checkpoint_dir is not None and os.path.exists(self.checkpoint_dir):
            # Map checkpoint types to their file prefixes
            prefix_map = {
                'batch_analysis': 'batch_analysis_',
                'batch_agents': 'batch_agents_',
                'single_ablation': 'single_ablation_',
                'single_assessment': 'single_assessment_'
            }
            prefix = prefix_map[checkpoint_type]
            
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith(prefix) and filename.endswith('.json'):
                    session_id = filename.replace(prefix, '').replace('.json', '')
                    try:
                        checkpoint_path = self.get_checkpoint_path(session_id, checkpoint_type)
                    except ValueError:
                        # Skip foreign/malformed filenames that are not legal session ids.
                        continue
                    try:
                        stat = os.stat(checkpoint_path)
                        checkpoint = self.load_checkpoint(session_id, checkpoint_type)
                        
                        if checkpoint:
                            # Successfully loaded checkpoint
                            checkpoint_info = {
                                'session_id': session_id,
                                'timestamp': checkpoint.get('timestamp', ''),
                                'complete': checkpoint.get('complete', False),
                                'file_size': stat.st_size,
                                'modified': stat.st_mtime,
                                'corrupted': False,
                                'type': checkpoint_type
                            }
                            
                            # Add type-specific fields
                            if checkpoint_type == 'single_assessment':
                                checkpoint_info['num_foci'] = len(checkpoint.get('result_data', {}).get('foci', []))
                                checkpoint_info['has_output'] = bool(checkpoint.get('result_data', {}).get('output'))
                            elif checkpoint_type == 'single_ablation':
                                checkpoint_info['num_foci'] = len(checkpoint.get('result_data', {}).get('influence_scores', []))
                                checkpoint_info['model'] = checkpoint.get('result_data', {}).get('model', 'unknown')
                            elif checkpoint_type == 'batch_agents':
                                checkpoint_info['completed'] = checkpoint.get('completed', 0)
                                checkpoint_info['total_pairs'] = checkpoint.get('total_pairs', 0)
                                checkpoint_info['total_results'] = len(checkpoint.get('results', []))
                            else:  # batch_analysis
                                checkpoint_info['completed'] = checkpoint.get('completed', 0)
                                checkpoint_info['total_pairs'] = checkpoint.get('total_pairs', 0)
                            
                            checkpoints.append(checkpoint_info)
                        else:
                            # File exists but couldn't be loaded (corrupted/incomplete)
                            checkpoints.append({
                                'session_id': session_id,
                                'timestamp': '',
                                'completed': 0,
                                'total_pairs': 0,
                                'complete': False,
                                'file_size': stat.st_size,
                                'modified': stat.st_mtime,
                                'corrupted': True,
                                'error': 'File exists but is corrupted or incomplete'
                            })
                    except Exception as e:
                        print(f"Error reading checkpoint {session_id}: {e}")
                        # Still add it to the list with error info
                        try:
                            stat = os.stat(checkpoint_path)
                            checkpoints.append({
                                'session_id': session_id,
                                'timestamp': '',
                                'completed': 0,
                                'total_pairs': 0,
                                'complete': False,
                                'file_size': stat.st_size,
                                'modified': stat.st_mtime,
                                'corrupted': True,
                                'error': str(e)
                            })
                        except:
                            pass
        
        # Sort by modified time (newest first)
        checkpoints.sort(key=lambda x: x.get('modified', 0), reverse=True)
        return checkpoints
    
    def delete_checkpoint(
        self,
        session_id: str,
        checkpoint_type: str = 'batch_analysis'
    ) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            session_id: Session identifier
            checkpoint_type: Type of checkpoint
            
        Returns:
            True if deleted, False if not found
        """
        checkpoint_path = self.get_checkpoint_path(session_id, checkpoint_type)
        if os.path.exists(checkpoint_path):
            try:
                os.remove(checkpoint_path)
                return True
            except Exception as e:
                print(f"Error deleting checkpoint {session_id}: {e}")
                return False
        return False


