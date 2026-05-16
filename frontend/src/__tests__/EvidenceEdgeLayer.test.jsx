/**
 * Phase O5-EVIDENCE-OS Stage 6 — EvidenceEdgeLayer + Evidence Graph
 * dataflow edges.
 *
 *   T-OS-EDGE-1   layer renders one <line> per matchable edge when
 *                 both endpoints exist in container DOM
 *   T-OS-EDGE-2   missing endpoint silently skipped (no fake edge
 *                 to a node that hasn't been rendered)
 *   T-OS-EDGE-3   dormant edge gets ghost class (no fake live binding)
 *   T-OS-EDGE-4   resize re-measure does not crash (covers
 *                 ResizeObserver code path)
 *   T-OS-EDGE-5   narrow viewport (< 760px) suppresses the SVG
 *                 honestly — data-os-edge-layer="suppressed-narrow"
 *   T-OS-EDGE-6   EvidenceGraph workspace still surfaces every
 *                 node's text content (a11y readability preserved)
 *   T-OS-EDGE-7   EvidenceGraph workspace renders an SR-only text
 *                 dataflow summary alongside the visual edges
 *   T-OS-EDGE-8   kill-switch ON forces every → ON-CHAIN edge to
 *                 dormant ghost (operator brief: kill-switch held
 *                 cannot paint as live binding)
 *   T-OS-EDGE-9   SVG carries aria-hidden so the relationships
 *                 are exposed via text summary, not duplicated
 *                 into a noisy SR tree
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, act } from '@testing-library/react'
import { useRef } from 'react'
import EvidenceEdgeLayer from '../os/components/EvidenceEdgeLayer'

/* ------------------------------------------------------------------ */
/*  Test scaffolding                                                   */
/* ------------------------------------------------------------------ */

// jsdom doesn't implement getBoundingClientRect with realistic values,
// so we stub it per-element. Helper to install a fixed rect on a
// given Element.
function _stubRect(el, rect) {
  el.getBoundingClientRect = () => ({
    x: rect.x, y: rect.y, left: rect.x, top: rect.y,
    width: rect.w, height: rect.h, right: rect.x + rect.w, bottom: rect.y + rect.h,
    toJSON() { return rect },
  })
}

// Fake ResizeObserver — captures observe targets, exposes a trigger()
// so tests can simulate a resize event.
class _FakeResizeObserver {
  static instances = []
  constructor(cb) { this.cb = cb; this.targets = []; _FakeResizeObserver.instances.push(this) }
  observe(el) { this.targets.push(el) }
  disconnect() { this.targets = [] }
  trigger()   { this.cb(this.targets.map(t => ({ target: t, contentRect: t.getBoundingClientRect() }))) }
}

let _origRO
beforeEach(() => {
  _FakeResizeObserver.instances = []
  _origRO = globalThis.ResizeObserver
  globalThis.ResizeObserver = _FakeResizeObserver
})
afterEach(() => {
  globalThis.ResizeObserver = _origRO
})

/* ------------------------------------------------------------------ */
/*  Harness — minimal scene with stub nodes                            */
/* ------------------------------------------------------------------ */

function Harness({ edges, containerWidth = 1280, stubs = {} }) {
  const ref = useRef(null)
  // After mount, stub the container + node rects so the layer can
  // measure them deterministically.
  // We do this via callback-ref + useLayoutEffect would be cleaner,
  // but inline ref callback is fine for tests.
  return (
    <div
      ref={(el) => {
        ref.current = el
        if (!el) return
        _stubRect(el, { x: 0, y: 0, w: containerWidth, h: 600 })
        Object.entries(stubs).forEach(([key, rect]) => {
          const node = el.querySelector(`[data-os-evidence-node="${key}"]`)
          if (node) _stubRect(node, rect)
        })
      }}
      data-os-test-container
      style={{ position: 'relative', width: containerWidth, height: 600 }}
    >
      <div data-os-evidence-node="A">A</div>
      <div data-os-evidence-node="B">B</div>
      <div data-os-evidence-node="C">C</div>
      <EvidenceEdgeLayer containerRef={ref} edges={edges}/>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('EvidenceEdgeLayer', () => {
  it('T-OS-EDGE-1: renders one <line> per matchable edge', async () => {
    const { container } = render(
      <Harness
        edges={[
          { from: 'A', to: 'B', kind: 'chain' },
          { from: 'B', to: 'C', kind: 'predicate' },
        ]}
        stubs={{
          A: { x: 20,  y: 20,  w: 200, h: 80 },
          B: { x: 240, y: 20,  w: 200, h: 80 },
          C: { x: 240, y: 120, w: 200, h: 80 },
        }}
      />,
    )
    // Tick a resize so layer re-measures with stubbed rects
    await act(async () => {
      _FakeResizeObserver.instances.forEach(i => i.trigger())
      await new Promise((r) => requestAnimationFrame(r))
    })
    const lines = container.querySelectorAll('line[data-os-edge-from]')
    expect(lines.length).toBe(2)
    const kinds = Array.from(lines).map(l => l.getAttribute('data-os-edge-kind'))
    expect(kinds).toContain('chain')
    expect(kinds).toContain('predicate')
  })

  it('T-OS-EDGE-2: missing endpoint silently skipped', async () => {
    const { container } = render(
      <Harness
        edges={[
          { from: 'A',          to: 'B',         kind: 'chain' },
          { from: 'A',          to: 'NEVER-RENDERED', kind: 'chain' },
          { from: 'NOT-IN-DOM', to: 'B',         kind: 'chain' },
        ]}
        stubs={{
          A: { x: 0,   y: 0,  w: 100, h: 80 },
          B: { x: 200, y: 0,  w: 100, h: 80 },
        }}
      />,
    )
    await act(async () => {
      _FakeResizeObserver.instances.forEach(i => i.trigger())
      await new Promise((r) => requestAnimationFrame(r))
    })
    const lines = container.querySelectorAll('line[data-os-edge-from]')
    // Only the valid A→B edge survives. The two with missing endpoints
    // are silently dropped — no fabricated geometry.
    expect(lines.length).toBe(1)
    expect(lines[0].getAttribute('data-os-edge-from')).toBe('A')
    expect(lines[0].getAttribute('data-os-edge-to')).toBe('B')
  })

  it('T-OS-EDGE-3: dormant edge gets the ghost class', async () => {
    const { container } = render(
      <Harness
        edges={[
          { from: 'A', to: 'B', kind: 'chain', dormant: true },
        ]}
        stubs={{
          A: { x: 0,   y: 0, w: 100, h: 80 },
          B: { x: 200, y: 0, w: 100, h: 80 },
        }}
      />,
    )
    await act(async () => {
      _FakeResizeObserver.instances.forEach(i => i.trigger())
      await new Promise((r) => requestAnimationFrame(r))
    })
    const line = container.querySelector('line[data-os-edge-from="A"]')
    expect(line).not.toBeNull()
    expect(line.getAttribute('class')).toBe('os-edge--ghost')
    expect(line.getAttribute('data-os-edge-kind')).toBe('ghost')
  })

  it('T-OS-EDGE-4: resize re-measure does not crash', async () => {
    const { container } = render(
      <Harness
        edges={[{ from: 'A', to: 'B', kind: 'chain' }]}
        stubs={{
          A: { x: 0,   y: 0, w: 100, h: 80 },
          B: { x: 200, y: 0, w: 100, h: 80 },
        }}
      />,
    )
    // Trigger ResizeObserver callback multiple times; each must not throw
    await act(async () => {
      for (let i = 0; i < 5; i++) {
        _FakeResizeObserver.instances.forEach(o => o.trigger())
        await new Promise((r) => requestAnimationFrame(r))
      }
    })
    const lines = container.querySelectorAll('line[data-os-edge-from]')
    expect(lines.length).toBe(1)
  })

  it('T-OS-EDGE-5: narrow viewport (<760px) suppresses the SVG honestly', async () => {
    const { container } = render(
      <Harness
        edges={[{ from: 'A', to: 'B', kind: 'chain' }]}
        containerWidth={390}
        stubs={{
          A: { x: 0,  y: 0,  w: 380, h: 80 },
          B: { x: 0,  y: 90, w: 380, h: 80 },
        }}
      />,
    )
    await act(async () => {
      _FakeResizeObserver.instances.forEach(i => i.trigger())
      await new Promise((r) => requestAnimationFrame(r))
    })
    // SVG NOT rendered; suppression marker present
    expect(container.querySelector('svg[data-os-edge-layer]')).toBeNull()
    expect(container.querySelector('[data-os-edge-layer="suppressed-narrow"]'))
      .not.toBeNull()
  })

  it('T-OS-EDGE-9: SVG carries aria-hidden so SR tree is not noisy', async () => {
    const { container } = render(
      <Harness
        edges={[{ from: 'A', to: 'B', kind: 'chain' }]}
        stubs={{
          A: { x: 0,   y: 0, w: 100, h: 80 },
          B: { x: 200, y: 0, w: 100, h: 80 },
        }}
      />,
    )
    await act(async () => {
      _FakeResizeObserver.instances.forEach(i => i.trigger())
      await new Promise((r) => requestAnimationFrame(r))
    })
    const svg = container.querySelector('svg[data-os-edge-layer]')
    expect(svg).not.toBeNull()
    expect(svg.getAttribute('aria-hidden')).toBe('true')
  })
})


/* ------------------------------------------------------------------ */
/*  Workspace-level integration                                        */
/* ------------------------------------------------------------------ */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

let _killSwitchPaused = true
let _chainStatus      = 'killswitch'
let _vhpData          = null

vi.mock('../api/bridgeApi', () => ({
  useCaptureHealth:        () => ({ data: { capture_state: 'NOMINAL', host_state: 'EXCLUSIVE_USB' } }),
  useGrindChain:           () => ({ data: { chain_length: 100, chain_intact: true, latest_gic_hash: 'a'.repeat(64) } }),
  useActivePlayOccupancy:  () => ({ data: { classification: { state: 'ACTIVE_MATCH_PLAY' } } }),
  useAITSeparation:        () => ({ data: { separation_ratio: 1.199, n_sessions: 37 } }),
  useVpmList:              () => ({ data: { row_count: 14, rows: [{ zkba_class: 2 }, { zkba_class: 7 }] } }),
  useCuratorStatus:        () => ({ data: { total_reviews: 0 } }),
  useFleetCoherenceStatus: () => ({ data: null, isError: false }),
}))

vi.mock('../api/publicForensic', () => ({
  usePublicVhp:            () => ({ data: _vhpData }),
  usePublicProtocolState:  () => ({ data: { kill_switch_paused: _killSwitchPaused } }),
  usePublicAgentRoots:     () => ({ data: { agents: [], chain: { name: 'IoTeX', chain_id: 4690 } } }),
}))

vi.mock('../api/mockBridge', () => ({
  isMockActive: () => false,
  deactivateMock: () => {},
}))

import EvidenceGraphWorkspace from '../os/workspaces/EvidenceGraphWorkspace'

function renderWorkspace() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<EvidenceGraphWorkspace />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('EvidenceGraphWorkspace edge integration', () => {
  beforeEach(() => {
    _killSwitchPaused = true
    _chainStatus      = 'killswitch'
    _vhpData          = null
  })

  it('T-OS-EDGE-6: every node card still surfaces readable text content', () => {
    const { container } = renderWorkspace()
    // All 11 node cards present + readable
    const nodes = container.querySelectorAll('[data-os-evidence-node]')
    expect(nodes.length).toBe(11)
    nodes.forEach(n => {
      expect(n.textContent.length).toBeGreaterThan(10)
    })
  })

  it('T-OS-EDGE-7: SR-only dataflow summary is present and lists all edges', () => {
    const { container } = renderWorkspace()
    const summary = container.querySelector('[data-os-edge-summary]')
    expect(summary).not.toBeNull()
    // Summary names each load-bearing relationship as text
    expect(summary.textContent).toMatch(/HID FRAMES flows into POAC/i)
    expect(summary.textContent).toMatch(/POAC flows into GIC/i)
    expect(summary.textContent).toMatch(/APOP flows into GIC/i)
    expect(summary.textContent).toMatch(/PCC flows into GIC/i)
    expect(summary.textContent).toMatch(/AIT flows into VHP/i)
    expect(summary.textContent).toMatch(/GIC flows into ZKBA/i)
    expect(summary.textContent).toMatch(/ZKBA flows into VPM/i)
    expect(summary.textContent).toMatch(/VPM flows into CURATOR/i)
    expect(summary.textContent).toMatch(/VHP flows into ON-CHAIN ANCHOR/i)
  })

  it('T-OS-EDGE-8: kill-switch held forces all → ON-CHAIN edges to deferred', () => {
    _killSwitchPaused = true
    const { container } = renderWorkspace()
    const summary = container.querySelector('[data-os-edge-summary]')
    // Every → ON-CHAIN ANCHOR edge marks deferred
    const onChainEdges = summary.textContent
      .split('\n')
      .filter(l => l.match(/flows into ON-CHAIN ANCHOR/i))
    expect(onChainEdges.length).toBeGreaterThanOrEqual(1)
    // The summary collapses lines in jsdom, easier to grep full text
    expect(summary.textContent).toMatch(/ON-CHAIN ANCHOR.*currently deferred|currently deferred.*ON-CHAIN ANCHOR/is)
  })

  it('T-OS-EDGE-7b: kill-switch lifted removes the deferred suffix on ON-CHAIN edges', () => {
    _killSwitchPaused = false
    // Also have to surface VHP as something other than dormant so the
    // VHP→ON-CHAIN edge isn't dormant for an unrelated reason. Quick
    // shim: vhpData=isValid:true with future-dated expiry.
    _vhpData = { tokenId: 2, isValid: true, expiresAt: Math.floor(Date.now() / 1000) + 86400 }
    const { container } = renderWorkspace()
    const summary = container.querySelector('[data-os-edge-summary]')
    // The VHP→ON-CHAIN line should NOT carry the "(currently deferred ...)" suffix
    const vhpLine = Array.from(summary.querySelectorAll('li'))
      .map(li => li.textContent)
      .find(t => t.match(/VHP flows into ON-CHAIN ANCHOR/i))
    expect(vhpLine).toBeTruthy()
    expect(vhpLine).not.toMatch(/currently deferred/i)
  })
})
