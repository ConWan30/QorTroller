"""QuickSilver client adapter for LLM routing.

Adapts the existing QuickSilver API client for use in router orchestration.
"""
from __future__ import annotations

import logging
import asyncio
from typing import Optional

log = logging.getLogger(__name__)

# Fail-open module-level binding so tests can patch
# vapi_bridge.llm_routing.qs_client.QorTrollerAI.
try:
    from ..vapi_llm_client import QorTrollerAI
except Exception:
    QorTrollerAI = None  # type: ignore[assignment]


class QuickSilverClient:
    """Adapter for the QuickSilver API client in router orchestration."""
    
    def __init__(self):
        self._qs_client = None
        self._initialize_qs_client()
    
    def _initialize_qs_client(self):
        """Initialize the QuickSilver client."""
        try:
            if QorTrollerAI is None:
                raise ImportError("vapi_llm_client unavailable (import failed at module load)")
            self._qs_client = QorTrollerAI()
            log.info("QuickSilver client adapter initialized")
        except Exception as e:
            log.warning(f"QuickSilver client initialization failed: {e}")
            self._qs_client = None
    
    async def generate(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Generate response using QuickSilver client."""
        if self._qs_client is None:
            raise Exception("QuickSilver client not available")
        
        try:
            # Run the synchronous QS client in thread pool
            result = await asyncio.to_thread(
                self._qs_client.generic_chat,
                system_prompt,
                prompt
            )
            return result
        except Exception as e:
            log.error(f"QuickSilver generation failed: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if QuickSilver client is available."""
        return self._qs_client is not None