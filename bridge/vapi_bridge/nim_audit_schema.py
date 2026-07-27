"""NIM audit logging schema for comprehensive security tracking.

This module defines the database schema for NIM API call auditing,
including cost tracking, anomaly detection, and security monitoring.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

SCHEMA_TAG = "vapi-nim-audit-v1"

# SQL schema for NIM audit log
NIM_AUDIT_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS nim_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    environment TEXT NOT NULL,
    
    -- Request metadata
    endpoint TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    prompt_length INTEGER NOT NULL,
    
    -- Response metadata
    response_hash TEXT NOT NULL,
    response_length INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    
    -- Cost tracking
    estimated_cost_usd REAL NOT NULL,
    
    -- Security metadata
    api_key_version TEXT NOT NULL,
    client_ip TEXT,
    user_agent TEXT,
    
    -- Outcome
    success BOOLEAN NOT NULL,
    error_code TEXT,
    error_message TEXT,
    
    -- Anomaly detection
    anomaly_score REAL DEFAULT 0.0,
    anomaly_flags TEXT,
    
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nim_audit_call_id ON nim_audit_log(call_id);
CREATE INDEX IF NOT EXISTS idx_nim_audit_timestamp ON nim_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_nim_audit_environment ON nim_audit_log(environment);
CREATE INDEX IF NOT EXISTS idx_nim_audit_anomaly_score ON nim_audit_log(anomaly_score);
CREATE INDEX IF NOT EXISTS idx_nim_audit_created_at ON nim_audit_log(created_at);
"""

# SQL schema for LLM call consistency tracking
LLM_CALL_TRACKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_call_tracker (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    model_version TEXT NOT NULL,
    confidence REAL NOT NULL,
    timestamp REAL NOT NULL,
    
    INDEX idx_llm_input_hash ON llm_call_tracker(input_hash),
    INDEX idx_llm_timestamp ON llm_call_tracker(timestamp)
);
"""


def migrate_nim_audit_tables(conn) -> None:
    """Migrate NIM audit logging tables.
    
    Args:
        conn: SQLite connection
    """
    try:
        # Create audit log table
        conn.execute(NIM_AUDIT_LOG_SCHEMA)
        
        # Create LLM call tracker table
        conn.execute(LLM_CALL_TRACKER_SCHEMA)
        
        log.info("NIM audit tables migrated successfully")
    except Exception as e:
        log.error(f"NIM audit table migration failed: {e}")
        raise