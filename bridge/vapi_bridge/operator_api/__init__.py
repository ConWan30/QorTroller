"""Operator Gate API package (D-DECON-2 register-function decomposition).

``create_operator_app`` remains the public entrypoint; route domains migrate
into ``register_*_routes`` modules without changing import paths.
"""
from ._app import create_operator_app, _RateLimiter

__all__ = ["create_operator_app", "_RateLimiter"]
