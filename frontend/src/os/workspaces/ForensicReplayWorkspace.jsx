/**
 * Evidence OS — Forensic Replay (placeholder vertical slice)
 *
 * Future: any historical session re-derivable from its on-disk wire
 * format. Reuses the entire public viewer family (/session, /gic,
 * /record, /vhp) but unified into one in-OS workspace instead of
 * separate routes.
 */
import { Link } from 'react-router-dom'
import WorkspaceHeader from '../components/WorkspaceHeader'
import EmptyState from '../components/EmptyState'

export default function ForensicReplayWorkspace() {
  return (
    <>
      <WorkspaceHeader
        title="Forensic Replay"
        description="Re-derive any historical claim. Paste a commitment hash, a grind session id, or a (device, counter) tuple — we re-execute every cryptographic primitive in your browser and surface OK / MISMATCH per layer."
      />
      <div style={{ padding: 32 }}>
        <EmptyState
          title="Forensic Replay — vertical slice pending"
          body={
            <>
              The public viewer family already lives at its own routes:
              {' '}<Link to="/session/4e5a99b1db47619e8be7cf0725c39f0440cdef95262ca7937a67c5c34984a3d8" style={{ color: 'var(--os-accent)' }}>/session/&lt;hash&gt;</Link>,
              {' '}<Link to="/gic/grind_phase235_v1" style={{ color: 'var(--os-accent)' }}>/gic/&lt;sid&gt;</Link>,
              {' '}<Link to="/algorithms" style={{ color: 'var(--os-accent)' }}>/algorithms</Link>,
              {' '}<Link to="/explorer" style={{ color: 'var(--os-accent)' }}>/explorer</Link>.
              This workspace will fold them into one in-OS surface with
              a single search bar + tabbed result panes.
            </>
          }
          source="frontend/src/api/publicForensic.js · 8 hooks + verifier catalog (15 functions)"
        />
      </div>
    </>
  )
}
