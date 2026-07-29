"""Local NIM client adapter for LLM routing.

Adapts the hardened NIM client for use in the router orchestration.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


class LocalLLMClient:
    """Adapter for the hardened NIM client in router orchestration."""
    
    def __init__(self):
        self._nim_client = None
        self._initialize_nim_client()
    
    def _initialize_nim_client(self):
        """Initialize the hardened NIM client."""
        try:
            from ..agentic_stewards.nim_client_hardened import HardenedNIMClient, NIMConfig
            import os
            
            config = NIMConfig(
                api_key=os.environ.get("NIM_API_KEY", ""),
                enabled=os.environ.get("AGENTIC_REASONING_ENABLED", "false").lower() == "true",
                environment=os.environ.get("QORTROLLER_ENV", "dev")
            )
            
            # Create a mock store for the client (router handles provenance separately)
            class MockStore:
                def insert_nim_audit_log(self, metadata):
                    pass  # Router handles provenance separately
                
                def _conn(self):
                    return self
                
                def __enter__(self):
                    return self
                    
                def __exit__(self, *args):
                    pass
            
            self._nim_client = HardenedNIMClient(config, MockStore())
            log.info("Local NIM client adapter initialized")
            
        except Exception as e:
            log.warning(f"Local NIM client initialization failed: {e}")
            self._nim_client = None
    
    async def generate(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Generate response using local NIM client."""
        if self._nim_client is None:
            raise Exception("Local NIM client not available")
        
        try:
            result = await self._nim_client.generate_reasoning(
                device_id="router",
                prompt=prompt,
                system=system_prompt
            )
            return result
        except Exception as e:
            log.error(f"Local NIM generation failed: {e}")
            raise
    
    def is_available(self) -> bool:
        """Check if local NIM client is available."""
        return self._nim_client is not None and self._nim_client._config.enabled