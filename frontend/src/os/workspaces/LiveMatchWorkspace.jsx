/**
 * Evidence OS — Live Match workspace (placeholder vertical slice)
 *
 * Future: frame-rate cognition feed — APOP state, GIC head, current
 * trigger pulls, controller orientation streaming via /ws/records.
 * For first slice: honest EmptyState pointing to the available hooks.
 */
import WorkspaceHeader from '../components/WorkspaceHeader'
import EmptyState from '../components/EmptyState'

export default function LiveMatchWorkspace() {
  return (
    <>
      <WorkspaceHeader
        title="Live Match"
        description="Frame-rate cognition feed — APOP state, current GIC head, trigger telemetry, controller orientation. Coming in next vertical slice."
      />
      <div style={{ padding: 32 }}>
        <EmptyState
          title="Live Match — vertical slice pending"
          body={
            <>
              The substrate is fully wired in <code>bridgeApi.js</code>:
              {' '}<code>useBrpRecordPulse</code> streams /ws/records,
              {' '}<code>useActivePlayOccupancy</code> exposes the SPC-derived
              APOP state, <code>useBrpControllerOrientation</code> renders
              live IMU/accel quaternion. This workspace will compose those
              hooks into a single live-match instrument view.
            </>
          }
          source="bridgeApi.js · /ws/records + /agent/active-play-occupancy"
        />
      </div>
    </>
  )
}
