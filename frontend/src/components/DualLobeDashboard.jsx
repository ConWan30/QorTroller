/**
 * Dual-Lobe Real-Time Dashboard Component
 * 
 * A React component for visualizing Dual-Lobe Retina metrics in real-time.
 * This component connects to the dashboard backend and displays live metrics.
 * 
 * Usage:
 *   import DualLobeDashboard from './DualLobeDashboard';
 *   
 *   function App() {
 *     return <DualLobeDashboard apiUrl="/operator/dual-lobe" />
 *   }
 * 
 * Features:
 * - Real-time health monitoring
 * - L0 poll rate visualization
 * - Causal coherence metrics
 * - Fusion verdict tracking
 * - Thread C safety status
 * - ONNX/MediaPipe integration status
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';

// Default styles
const styles = {
  container: {
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '24px',
    background: '#0a0a0a',
    color: '#e0e0e0',
    borderRadius: '12px',
  },
  header: {
    marginBottom: '24px',
    paddingBottom: '16px',
    borderBottom: '1px solid #333',
  },
  title: {
    fontSize: '28px',
    fontWeight: 700,
    color: '#fff',
    margin: 0,
  },
  subtitle: {
    fontSize: '14px',
    color: '#888',
    margin: '8px 0 0 0',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: '20px',
    marginBottom: '24px',
  },
  card: {
    background: '#141414',
    borderRadius: '12px',
    padding: '20px',
    border: '1px solid #222',
    transition: 'border-color 0.2s, box-shadow 0.2s',
  },
  cardHeader: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#aaa',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    marginBottom: '16px',
  },
  metric: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  metricLabel: {
    fontSize: '12px',
    color: '#666',
  },
  metricValue: {
    fontSize: '28px',
    fontWeight: 600,
    color: '#fff',
  },
  status: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 12px',
    borderRadius: '20px',
    fontSize: '12px',
    fontWeight: 600,
    textTransform: 'uppercase',
  },
  statusHealthy: {
    background: '#004d2a',
    color: '#00ff88',
  },
  statusDegraded: {
    background: '#4d2a00',
    color: '#ff8800',
  },
  statusCritical: {
    background: '#4d0000',
    color: '#ff4444',
  },
  statusDisabled: {
    background: '#222',
    color: '#666',
  },
  progressBar: {
    width: '100%',
    height: '8px',
    background: '#222',
    borderRadius: '4px',
    overflow: 'hidden',
    marginTop: '8px',
  },
  progressFill: {
    height: '100%',
    borderRadius: '4px',
    transition: 'width 0.3s ease',
  },
  progressFillHealthy: {
    background: 'linear-gradient(90deg, #00ff88, #00cc6a)',
  },
  progressFillWarning: {
    background: 'linear-gradient(90deg, #ff8800, #cc6600)',
  },
  progressFillCritical: {
    background: 'linear-gradient(90deg, #ff4444, #cc0000)',
  },
  chart: {
    width: '100%',
    height: '200px',
    background: '#111',
    borderRadius: '8px',
    marginTop: '12px',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    marginTop: '12px',
  },
  tableRow: {
    borderBottom: '1px solid #222',
  },
  tableCell: {
    padding: '12px',
    textAlign: 'left',
    fontSize: '14px',
  },
  tableHeader: {
    color: '#888',
    fontSize: '12px',
    textTransform: 'uppercase',
    fontWeight: 600,
  },
  refreshIndicator: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '12px',
    color: '#666',
    marginLeft: 'auto',
  },
  refreshDot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: '#00ff88',
    animation: 'pulse 2s infinite',
  },
};

// Status component
const Status = ({ status, text }) => {
  const statusStyle = {
    ...styles.status,
    ...(status === 'healthy' ? styles.statusHealthy :
        status === 'degraded' ? styles.statusDegraded :
        status === 'critical' ? styles.statusCritical :
        styles.statusDisabled),
  };
  
  const dotColor = status === 'healthy' ? '#00ff88' :
                   status === 'degraded' ? '#ff8800' :
                   status === 'critical' ? '#ff4444' :
                   '#666';
  
  return (
    <span style={statusStyle}>
      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: dotColor }} />
      {text || status}
    </span>
  );
};

Status.propTypes = {
  status: PropTypes.oneOf(['healthy', 'degraded', 'critical', 'disabled']),
  text: PropTypes.string,
};

// Progress bar component
const ProgressBar = ({ value, max, status }) => {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  
  const fillStyle = {
    ...styles.progressFill,
    ...(status === 'healthy' ? styles.progressFillHealthy :
        status === 'warning' ? styles.progressFillWarning :
        styles.progressFillCritical),
    width: `${percentage}%`,
  };
  
  return (
    <div style={styles.progressBar}>
      <div style={fillStyle} />
    </div>
  );
};

ProgressBar.propTypes = {
  value: PropTypes.number.isRequired,
  max: PropTypes.number.isRequired,
  status: PropTypes.oneOf(['healthy', 'warning', 'critical']),
};

// Metric component
const Metric = ({ label, value, unit, status, children }) => {
  return (
    <div style={styles.metric}>
      <span style={styles.metricLabel}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={styles.metricValue}>{value}{unit && <span style={{ fontSize: '16px', color: '#888' }}>{unit}</span>}</span>
        {status && <Status status={status} />}
      </div>
      {children}
    </div>
  );
};

Metric.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  unit: PropTypes.string,
  status: PropTypes.string,
  children: PropTypes.node,
};

// Section card component
const SectionCard = ({ title, children, style }) => {
  return (
    <div style={{ ...styles.card, ...style }}>
      <div style={styles.cardHeader}>{title}</div>
      {children}
    </div>
  );
};

SectionCard.propTypes = {
  title: PropTypes.string.isRequired,
  children: PropTypes.node,
  style: PropTypes.object,
};

// Health Overview Section
const HealthOverview = ({ health }) => {
  if (!health) return null;
  
  const pollRateStatus = health.l0_poll_rate_hz >= 990 ? 'healthy' :
                         health.l0_poll_rate_hz >= 950 ? 'degraded' : 'critical';
  
  const overallStatus = !health.thread_c_safe ? 'critical' :
                        pollRateStatus === 'critical' ? 'critical' :
                        pollRateStatus === 'degraded' ? 'degraded' : 'healthy';
  
  return (
    <SectionCard title="System Health">
      <Metric
        label="Overall Status"
        value={''}
        status={overallStatus}
        text={overallStatus.charAt(0).toUpperCase() + overallStatus.slice(1)}
      />
      
      <div style={{ marginTop: '16px' }}>
        <Metric
          label="L0 Poll Rate"
          value={health.l0_poll_rate_hz?.toFixed(1) || 0}
          unit="Hz"
          status={pollRateStatus}
        >
          <ProgressBar
            value={health.l0_poll_rate_hz || 0}
            max={1000}
            status={pollRateStatus}
          />
        </Metric>
      </div>
      
      <div style={{ marginTop: '16px' }}>
        <Metric
          label="Thread C Safety"
          value={''}
          status={health.thread_c_safe ? 'healthy' : 'critical'}
          text={health.thread_c_safe ? 'Safe' : 'Unsafe'}
        />
      </div>
      
      <div style={{ marginTop: '16px' }}>
        <Metric
          label="Fusion Verdict"
          value={health.last_fusion_verdict || 'N/A'}
          status={health.last_fusion_verdict === 'LIVE_COHERENT' ? 'healthy' :
                  health.last_fusion_verdict === 'LIVE_COUPLED' ? 'degraded' :
                  'critical'}
        />
      </div>
    </SectionCard>
  );
};

HealthOverview.propTypes = {
  health: PropTypes.object,
};

// Screen Lobe Section
const ScreenLobeSection = ({ metrics }) => {
  if (!metrics?.screen_lobe) return null;
  
  const sl = metrics.screen_lobe;
  
  return (
    <SectionCard title="Screen Lobe (OCR)">
      <Metric
        label="HUD Parses"
        value={sl.hud_parse_count || 0}
        unit=""
      />
      <Metric
        label="Events Detected"
        value={Object.values(sl.events_detected || {}).reduce((a, b) => a + b, 0)}
        unit=""
      />
      <Metric
        label="OCR Dropouts"
        value={sl.ocr_dropout_count || 0}
        unit=""
        status={sl.ocr_dropout_count > 10 ? 'degraded' : 'healthy'}
      />
      <Metric
        label="Motion Vectors"
        value={sl.motion_vectors_computed || 0}
        unit=""
      />
    </SectionCard>
  );
};

ScreenLobeSection.propTypes = {
  metrics: PropTypes.object,
};

// Controller Lobe Section
const ControllerLobeSection = ({ metrics }) => {
  if (!metrics?.controller_lobe) return null;
  
  const cl = metrics.controller_lobe;
  
  const pollRateStatus = cl.poll_rate_hz >= 990 ? 'healthy' :
                         cl.poll_rate_hz >= 950 ? 'degraded' : 'critical';
  
  return (
    <SectionCard title="Controller Lobe (HID)">
      <Metric
        label="Poll Rate"
        value={cl.poll_rate_hz?.toFixed(1) || 0}
        unit="Hz"
        status={pollRateStatus}
      >
        <ProgressBar
          value={cl.poll_rate_hz || 0}
          max={1000}
          status={pollRateStatus}
        />
      </Metric>
      <Metric
        label="Input Events"
        value={cl.input_events || 0}
        unit=""
      />
      <Metric
        label="Trigger Onsets"
        value={cl.trigger_onsets || 0}
        unit=""
      />
      <Metric
        label="Stick Jumps"
        value={cl.stick_jumps || 0}
        unit=""
      />
    </SectionCard>
  );
};

ControllerLobeSection.propTypes = {
  metrics: PropTypes.object,
};

// Coherence Section
const CoherenceSection = ({ metrics }) => {
  if (!metrics?.coherence) return null;
  
  const c = metrics.coherence;
  const total = c.n_matched_total + (c.n_required_total - c.n_matched_total);
  const ratio = total > 0 ? c.n_matched_total / total : 0;
  
  const ratioStatus = ratio >= 0.8 ? 'healthy' :
                      ratio >= 0.5 ? 'warning' : 'critical';
  
  return (
    <SectionCard title="Causal Coherence">
      <Metric
        label="Assessments"
        value={c.assessments || 0}
        unit=""
      />
      <Metric
        label="Coherence Ratio"
        value={(c.coherence_ratio_avg * 100).toFixed(1)}
        unit="%"
        status={ratioStatus}
      >
        <ProgressBar value={c.coherence_ratio_avg * 100} max={100} status={ratioStatus} />
      </Metric>
      <Metric
        label="Last Verdict"
        value={c.last_verdict || 'N/A'}
        status={c.last_verdict === 'COHERENT' ? 'healthy' :
                c.last_verdict === 'ORPHAN_OUTCOME' ? 'critical' :
                'degraded'}
      />
      <Metric
        label="Matched Outcomes"
        value={c.n_matched_total || 0}
        unit=""
      />
    </SectionCard>
  );
};

CoherenceSection.propTypes = {
  metrics: PropTypes.object,
};

// Fusion Section
const FusionSection = ({ metrics }) => {
  if (!metrics?.fusion) return null;
  
  const f = metrics.fusion;
  
  return (
    <SectionCard title="Tri-Channel Fusion">
      <Metric
        label="Assessments"
        value={f.assessments || 0}
        unit=""
      />
      <Metric
        label="Last Verdict"
        value={f.last_verdict || 'N/A'}
        status={f.last_verdict === 'LIVE_COHERENT' ? 'healthy' :
                f.last_verdict === 'LIVE_COUPLED' ? 'degraded' :
                'critical'}
      />
      <Metric
        label="Coupling Score"
        value={(f.coupling_score_avg * 100).toFixed(1)}
        unit="%"
      >
        <ProgressBar value={f.coupling_score_avg * 100} max={100} status="healthy" />
      </Metric>
      <Metric
        label="Negative Control"
        value={(f.negative_control_avg * 100).toFixed(1)}
        unit="%"
      />
    </SectionCard>
  );
};

FusionSection.propTypes = {
  metrics: PropTypes.object,
};

// Thread C Section
const ThreadCSection = ({ metrics }) => {
  if (!metrics?.thread_c) return null;
  
  const tc = metrics.thread_c;
  
  return (
    <SectionCard title="Thread C Isolation">
      <Metric
        label="Invocations"
        value={tc.invocations || 0}
        unit=""
      />
      <Metric
        label="Blocked"
        value={tc.blocked || 0}
        unit=""
        status={tc.blocked > 0 ? 'critical' : 'healthy'}
      />
      <Metric
        label="Avg Latency"
        value={(tc.avg_latency_ms * 1000).toFixed(2)}
        unit="ms"
      />
      <Metric
        label="Safety Status"
        value={''}
        status={tc.safe ? 'healthy' : 'critical'}
        text={tc.safe ? 'Safe' : 'Unsafe'}
      />
    </SectionCard>
  );
};

ThreadCSection.propTypes = {
  metrics: PropTypes.object,
};

// Integration Section
const IntegrationSection = ({ metrics }) => {
  if (!metrics) return null;
  
  return (
    <SectionCard title="Integration Status">
      <Metric
        label="MediaPipe"
        value={''}
        status={metrics.mediapipe?.enabled ? 'healthy' : 'disabled'}
        text={metrics.mediapipe?.enabled ? 'Enabled' : 'Disabled'}
      />
      <Metric
        label="ONNX Runtime"
        value={''}
        status={metrics.onnx?.enabled ? 'healthy' : 'disabled'}
        text={metrics.onnx?.enabled ? 'Enabled' : 'Disabled'}
      />
      <Metric
        label="Retina Capture"
        value={''}
        status={metrics.retina_capture_enabled ? 'healthy' : 'disabled'}
        text={metrics.retina_capture_enabled ? 'Enabled' : 'Disabled'}
      />
      <Metric
        label="Retina Perception"
        value={''}
        status={metrics.retina_perception_enabled ? 'healthy' : 'disabled'}
        text={metrics.retina_perception_enabled ? 'Enabled' : 'Disabled'}
      />
    </SectionCard>
  );
};

IntegrationSection.propTypes = {
  metrics: PropTypes.object,
};

// Main Dashboard Component
const DualLobeDashboard = ({ apiUrl, refreshInterval }) => {
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch health
      const healthResponse = await fetch(`${apiUrl}/health`);
      if (!healthResponse.ok) throw new Error(`Health API returned ${healthResponse.status}`);
      const healthData = await healthResponse.json();
      setHealth(healthData);
      
      // Fetch metrics
      const metricsResponse = await fetch(`${apiUrl}/metrics`);
      if (!metricsResponse.ok) throw new Error(`Metrics API returned ${metricsResponse.status}`);
      const metricsData = await metricsResponse.json();
      setMetrics(metricsData);
      
      setLastRefresh(new Date());
    } catch (err) {
      setError(err.message);
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);
  
  useEffect(() => {
    // Initial fetch
    fetchData();
    
    // Set up periodic refresh
    const interval = setInterval(fetchData, refreshInterval);
    
    return () => clearInterval(interval);
  }, [fetchData, refreshInterval]);
  
  if (loading && !health && !metrics) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h1 style={styles.title}>QorTroller Dual-Lobe Dashboard</h1>
          <p style={styles.subtitle}>Loading...</p>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h1 style={styles.title}>QorTroller Dual-Lobe Dashboard</h1>
          <p style={{ ...styles.subtitle, color: '#ff4444' }}>Error: {error}</p>
        </div>
      </div>
    );
  }
  
  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>QorTroller Dual-Lobe Dashboard</h1>
        <p style={styles.subtitle}>
          Real-time monitoring for CPU-optimized Trio-Retina inference framework
        </p>
        <div style={styles.refreshIndicator}>
          <span style={styles.refreshDot} />
          Last updated: {lastRefresh?.toLocaleTimeString() || 'Never'}
        </div>
      </div>
      
      {/* Health Overview */}
      <div style={styles.grid}>
        <HealthOverview health={health || metrics?.health_summary} />
        <IntegrationSection metrics={metrics} />
      </div>
      
      {/* Detailed Metrics */}
      <div style={styles.grid}>
        <ControllerLobeSection metrics={metrics} />
        <ScreenLobeSection metrics={metrics} />
        <CoherenceSection metrics={metrics} />
        <FusionSection metrics={metrics} />
        <ThreadCSection metrics={metrics} />
      </div>
      
      {/* Footer */}
      <div style={{ 
        marginTop: '24px', 
        paddingTop: '16px', 
        borderTop: '1px solid #333',
        fontSize: '12px', 
        color: '#666',
        textAlign: 'center',
      }}>
        QorTroller — Core Controllers of their gaming data | V.A.P.I. Reference Implementation
      </div>
    </div>
  );
};

DualLobeDashboard.propTypes = {
  apiUrl: PropTypes.string,
  refreshInterval: PropTypes.number,
};

DualLobeDashboard.defaultProps = {
  apiUrl: '/operator/dual-lobe',
  refreshInterval: 1000, // 1 second
};

// Add CSS animation for pulse effect
const styleElement = document.createElement('style');
styleElement.textContent = `
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
`;
document.head.appendChild(styleElement);

export default DualLobeDashboard;
