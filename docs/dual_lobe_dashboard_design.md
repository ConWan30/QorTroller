# Dual-Lobe Real-Time Dashboard

Real-time monitoring dashboard for the QorTroller Dual-Lobe Retina Capture Rig.

## Overview

The Dual-Lobe Dashboard provides live visibility into the CPU-optimized inference framework for Trio-Retina, including:

- **System Health** — Overall status, L0 poll rate, Thread C safety
- **Screen Lobe (OCR)** — HUD parsing statistics, event detection, motion tracking
- **Controller Lobe (HID)** — Poll rate monitoring, input events, trigger onsets
- **Causal Coherence** — Assessment counts, coherence ratios, verdict distribution
- **Tri-Channel Fusion** — Fusion verdicts, coupling scores, negative control
- **Thread C Isolation** — Invocation counts, blocking status, latency metrics
- **Integration Status** — MediaPipe, ONNX Runtime, Retina feature status

## Quick Start

### Option 1: Standalone Dashboard Server

```bash
# Start the dashboard server
cd /c/Users/Contr/vapi-pebble-prototype/QorTroller
python scripts/dashboard_dual_lobe.py

# Access the dashboard
# With FastAPI: http://localhost:8080
# With simple server: http://localhost:8080
```

**Environment Variables:**
- `DASHBOARD_HOST` — Host to bind to (default: `0.0.0.0`)
- `DASHBOARD_PORT` — Port to listen on (default: `8080`)

### Option 2: Integrated with Bridge

The dashboard can be integrated with the existing VAPI Bridge FastAPI server:

```python
# In bridge/vapi_bridge/operator_api.py
from scripts.dashboard_dual_lobe import DualLobeDashboard

# Create dashboard instance
dashboard = DualLobeDashboard()

# Mount endpoints
app.mount("/operator/dual-lobe", dashboard.app)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard info and available endpoints |
| `/health` | GET | Health summary (status, poll rate, safety) |
| `/metrics` | GET | Full metrics (all lobes, coherence, fusion, Thread C) |
| `/state` | GET | Complete dashboard state |
| `/history` | GET | Time-series history (coherence, fusion, poll rate) |

### Example Responses

#### Health Endpoint

```json
{
  "status": "healthy",
  "l0_poll_rate_hz": 1000.0,
  "thread_c_safe": true,
  "mediapipe_enabled": true,
  "onnx_enabled": true,
  "retina_capture_enabled": false,
  "retina_perception_enabled": false,
  "last_coupling_score": 0.95,
  "last_coherence_verdict": "COHERENT",
  "last_fusion_verdict": "LIVE_COHERENT"
}
```

#### Metrics Endpoint

```json
{
  "timestamp": "2026-07-26T15:26:00.127Z",
  "uptime_seconds": 3600.5,
  "screen_lobe": {
    "hud_parse_count": 1000,
    "hud_parse_errors": 0,
    "events_detected": {
      "scene.down_advanced": 250,
      "scene.first_down": 100,
      "scene.score_changed": 50,
      "scene.playclock_reset": 30,
      "scene.quarter_changed": 10
    },
    "ocr_dropout_count": 5,
    "motion_vectors_computed": 6000
  },
  "controller_lobe": {
    "input_events": 15000,
    "trigger_onsets": 4500,
    "stick_jumps": 7500,
    "poll_rate_hz": 1000.0,
    "poll_rate_min": 995.0,
    "poll_rate_max": 1000.0
  },
  "coherence": {
    "assessments": 500,
    "verdict_distribution": {
      "COHERENT": 450,
      "ORPHAN_OUTCOME": 25,
      "ORPHAN_INPUT": 15,
      "INSUFFICIENT": 10
    },
    "coherence_ratio_avg": 0.95,
    "last_verdict": "COHERENT"
  },
  "fusion": {
    "assessments": 500,
    "verdict_distribution": {
      "LIVE_COHERENT": 450,
      "LIVE_COUPLED": 30,
      "REPLAY_OR_RELAY": 20
    },
    "coupling_score_avg": 0.95,
    "last_verdict": "LIVE_COHERENT"
  },
  "thread_c": {
    "invocations": 1000,
    "blocked": 0,
    "avg_latency_ms": 2.5,
    "safe": true
  },
  "onnx": {
    "invocations": 500,
    "success_count": 500,
    "error_count": 0,
    "avg_latency_ms": 5.0,
    "enabled": true
  },
  "mediapipe": {
    "frames_processed": 6000,
    "motion_vectors_extracted": 6000,
    "tracking_success_count": 5950,
    "enabled": true
  }
}
```

## Frontend Integration

### React Component

A pre-built React component is available at `frontend/src/components/DualLobeDashboard.jsx`:

```jsx
import DualLobeDashboard from './components/DualLobeDashboard';

function App() {
  return (
    <div>
      <h1>QorTroller Monitoring</h1>
      <DualLobeDashboard 
        apiUrl="/operator/dual-lobe" 
        refreshInterval={1000} 
      />
    </div>
  );
}
```

**Props:**
- `apiUrl` — Base URL for dashboard API (default: `/operator/dual-lobe`)
- `refreshInterval` — Refresh interval in milliseconds (default: `1000`)

### Standalone HTML

For quick testing, create a simple HTML file:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Dual-Lobe Dashboard</title>
  <style>
    body { margin: 0; padding: 20px; background: #0a0a0a; color: #e0e0e0; }
  </style>
</head>
<body>
  <div id="dashboard"></div>
  
  <script>
    async function fetchAndDisplay() {
      const response = await fetch('http://localhost:8080/metrics');
      const data = await response.json();
      
      const dashboard = document.getElementById('dashboard');
      dashboard.innerHTML = `
        <pre style="background: #141414; padding: 20px; border-radius: 8px;">
${JSON.stringify(data, null, 2)}
        </pre>
      `;
    }
    
    fetchAndDisplay();
    setInterval(fetchAndDisplay, 1000);
  </script>
</body>
</html>
```

## Metrics Reference

### Screen Lobe Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `hud_parse_count` | Counter | Total HUD text parses |
| `hud_parse_errors` | Counter | HUD parse failures |
| `events_detected` | Map | Count of each event type detected |
| `ocr_dropout_count` | Counter | Times OCR failed to read a field |
| `motion_vectors_computed` | Counter | Motion vectors extracted via MediaPipe |

### Controller Lobe Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `input_events` | Counter | Total HID input events |
| `trigger_onsets` | Counter | R2/L2 trigger onsets detected |
| `stick_jumps` | Counter | Stick radial jumps detected |
| `tremor_anomalies` | Counter | Tremor anomalies detected |
| `poll_rate_hz` | Gauge | Current HID poll rate |
| `poll_rate_min` | Gauge | Minimum poll rate observed |
| `poll_rate_max` | Gauge | Maximum poll rate observed |

### Coherence Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `assessments` | Counter | Total coherence assessments |
| `verdict_distribution` | Map | Count of each verdict type |
| `coherence_ratio_avg` | Gauge | Average coherence ratio |
| `n_matched_total` | Counter | Total matched outcomes |
| `n_required_total` | Counter | Total required outcomes |

### Fusion Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `assessments` | Counter | Total fusion assessments |
| `verdict_distribution` | Map | Count of each fusion verdict |
| `coupling_score_avg` | Gauge | Average coupling score |
| `negative_control_avg` | Gauge | Average negative control score |
| `decoupled_energy_avg` | Gauge | Average decoupled energy |

### Thread C Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `invocations` | Counter | Total Thread C invocations |
| `blocked` | Counter | Times Thread C was blocked |
| `avg_latency_ms` | Gauge | Average Thread C latency |
| `min_latency_ms` | Gauge | Minimum Thread C latency |
| `max_latency_ms` | Gauge | Maximum Thread C latency |
| `safe` | Boolean | Thread C safety status |

### ONNX Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `invocations` | Counter | Total ONNX invocations |
| `success_count` | Counter | Successful ONNX invocations |
| `error_count` | Counter | Failed ONNX invocations |
| `avg_latency_ms` | Gauge | Average ONNX latency |
| `enabled` | Boolean | ONNX Runtime enabled |
| `model_loaded` | Boolean | ONNX model loaded |

### MediaPipe Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `frames_processed` | Counter | Total frames processed |
| `motion_vectors_extracted` | Counter | Motion vectors extracted |
| `tracking_success_count` | Counter | Successful tracking attempts |
| `tracking_failure_count` | Counter | Failed tracking attempts |
| `avg_confidence` | Gauge | Average tracking confidence |
| `enabled` | Boolean | MediaPipe enabled |

## Alerting Rules

### Critical Alerts

1. **Thread C Unsafe** — `thread_c.safe == false`
2. **L0 Poll Rate Critical** — `controller_lobe.poll_rate_hz < 950`
3. **ORPHAN_OUTCOME Detected** — `coherence.last_verdict == "ORPHAN_OUTCOME"`
4. **REPLAY_OR_RELAY Detected** — `fusion.last_verdict == "REPLAY_OR_RELAY"`
5. **Thread C Blocked** — `thread_c.blocked > 0`

### Warning Alerts

1. **L0 Poll Rate Degraded** — `950 <= controller_lobe.poll_rate_hz < 990`
2. **Low Coherence Ratio** — `coherence.coherence_ratio_avg < 0.8`
3. **High OCR Dropouts** — `screen_lobe.ocr_dropout_count > 10`

### Info Alerts

1. **LIVE_COUPLED** — Fusion verdict is LIVE_COUPLED (coupling clean, insufficient outcome evidence)
2. **ORPHAN_INPUT** — Coherence verdict is ORPHAN_INPUT (input present, no outcomes)

## Performance Targets

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| L0 Poll Rate | ≥ 990 Hz | < 950 Hz |
| Thread C Safety | Always safe | Unsafe |
| Coherence Ratio | ≥ 0.8 | < 0.5 |
| Coupling Score | ≥ 0.8 | < 0.3 |
| Negative Control | < 0.2 | > 0.4 |
| Thread C Latency | < 10 ms | > 50 ms |
| ONNX Latency | < 20 ms | > 100 ms |

## Integration with Monitoring Systems

### Prometheus

```python
from prometheus_client import start_http_server, Counter, Gauge

# Initialize metrics
SCREEN_LOBE_PARSES = Counter('dual_lobe_screen_lobe_parses_total', 'HUD parses')
CONTROLLER_POLL_RATE = Gauge('dual_lobe_controller_poll_rate_hz', 'HID poll rate')
COHERENCE_RATIO = Gauge('dual_lobe_coherence_ratio', 'Coherence ratio')
THREAD_C_SAFE = Gauge('dual_lobe_thread_c_safe', 'Thread C safety (1=safe, 0=unsafe)')

# Update metrics periodically
def update_prometheus(dashboard):
    state = await dashboard.get_state()
    SCREEN_LOBE_PARSES.inc(state.screen_lobe.hud_parse_count)
    CONTROLLER_POLL_RATE.set(state.controller_lobe.poll_rate_hz)
    COHERENCE_RATIO.set(state.coherence.coherence_ratio_avg)
    THREAD_C_SAFE.set(1 if state.thread_c.safe else 0)

# Start Prometheus server on port 9090
start_http_server(9090)
```

### Grafana

Import the provided Grafana dashboard JSON file:

```bash
# Dashboard file: dashboards/dual_lobe_grafana.json
# Import via Grafana UI: Configuration > Import > Upload JSON
```

## Troubleshooting

### Dashboard Not Starting

1. **Check Python version** — Requires Python 3.10+
2. **Check dependencies** — `pip install fastapi uvicorn`
3. **Check port availability** — Try a different port

### No Data Showing

1. **Verify bridge is running** — The dashboard needs the bridge to be running
2. **Check API endpoints** — Test `/health` and `/metrics` directly
3. **Verify CORS** — Ensure CORS is configured if accessing from different origin

### High Latency

1. **Check Thread C metrics** — Look for blocking or high latency
2. **Verify L0 poll rate** — Should be ≥ 990 Hz
3. **Check ONNX model** — Ensure model is loaded and optimized

## Files

| File | Description |
|------|-------------|
| `scripts/dashboard_dual_lobe.py` | Dashboard server (FastAPI + fallback) |
| `frontend/src/components/DualLobeDashboard.jsx` | React component for frontend |
| `docs/dual_lobe_dashboard_design.md` | Detailed dashboard design (this file) |

## References

- **Commit:** [d6768f17](https://github.com/ConWan30/QorTroller/commit/d6768f17) — feat(dual-lobe): CPU-optimized inference framework
- **Test Report:** `docs/retina_dual_lobe_test_2026_07_26.md`
- **Test Suite:** `scripts/test_retina_dual_lobe_autonomous.py`
- **Brand Guidelines:** `docs/qortroller-brand-guidelines.md`

---

*QorTroller — Core Controllers of their gaming data*  
*Verifiable Autonomous Physical Intelligence (V.A.P.I.) reference implementation*
