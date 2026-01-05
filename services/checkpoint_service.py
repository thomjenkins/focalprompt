#!/usr/bin/env python3
"""
Checkpoint management service.

Handles saving, loading, and listing checkpoints for batch operations.
"""

import os
import json
from typing import Optional, Dict, List
from datetime import datetime


class CheckpointService:
    """Service for managing checkpoints."""
    
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        """
        Initialize checkpoint service.
        
        Args:
            checkpoint_dir: Directory to store checkpoints
        """
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)
    
    def get_checkpoint_path(self, session_id: str, checkpoint_type: str = 'batch_analysis') -> str:
        """
        Get checkpoint file path for a session.
        
        Args:
            session_id: Session identifier
            checkpoint_type: Type of checkpoint ('batch_analysis', 'batch_agents', 'single_ablation', 'single_assessment')
            
        Returns:
            Full path to checkpoint file
        """
        return os.path.join(self.checkpoint_dir, f"{checkpoint_type}_{session_id}.json")
    
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
        except Exception as e:
            print(f"Error saving checkpoint {session_id}: {e}")
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
        checkpoints = []
        if os.path.exists(self.checkpoint_dir):
            # Map checkpoint types to their file prefixes
            prefix_map = {
                'batch_analysis': 'batch_analysis_',
                'batch_agents': 'batch_agents_',
                'single_ablation': 'single_ablation_',
                'single_assessment': 'single_assessment_'
            }
            prefix = prefix_map.get(checkpoint_type, 'batch_analysis_')
            
            for filename in os.listdir(self.checkpoint_dir):
                if filename.startswith(prefix) and filename.endswith('.json'):
                    session_id = filename.replace(prefix, '').replace('.json', '')
                    checkpoint_path = self.get_checkpoint_path(session_id, checkpoint_type)
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


