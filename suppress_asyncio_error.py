"""Suppress asyncio connection lost errors on Windows.

This script patches the asyncio proactor to silently handle
connection reset errors that are common on Windows.
"""

import sys
import asyncio
import logging

# Only apply on Windows
if sys.platform == 'win32':
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        
        # Store original method
        _original_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost
        
        def _patched_call_connection_lost(self, exc):
            """Patched version that suppresses common connection errors."""
            try:
                _original_call_connection_lost(self, exc)
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                # These are normal when clients disconnect unexpectedly
                # Log as debug instead of error
                logging.debug(f"Client disconnected: {e}")
        
        # Apply patch
        _ProactorBasePipeTransport._call_connection_lost = _patched_call_connection_lost
        print("✓ Patched asyncio to suppress connection lost errors on Windows")
    except Exception as e:
        print(f"Warning: Could not apply asyncio patch: {e}")
