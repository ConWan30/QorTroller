/**
 * Evidence OS — Operator Queue (placeholder vertical slice)
 *
 * Future: drafts awaiting operator decision, sorted by SLA + agent.
 * Reuses useOperatorDrafts + useReviewDraft from bridgeApi.js.
 */
import WorkspaceHeader from '../components/WorkspaceHeader'
import EmptyState from '../components/EmptyState'

export default function OperatorQueueWorkspace() {
  return (
    <>
      <WorkspaceHeader
        title="Operator Queue"
        description="Drafts from the Sentry / Guardian / Curator fleet awaiting your decision. Acceptance feeds disagreement_rate; rejection blocks O2→O3 advancement until reasons clear."
      />
      <div style={{ padding: 32 }}>
        <EmptyState
          title="Operator Queue — vertical slice pending"
          body={
            <>
              <code>useOperatorDrafts</code> and <code>useReviewDraft</code>{' '}
              are already shipped in bridgeApi.js. This workspace will
              render a sortable queue with per-row decision controls
              and acceptance / disagreement_rate impact preview.
            </>
          }
          source="/operator/operator-agent-drafts · POST /operator/operator-agent-draft-review"
        />
      </div>
    </>
  )
}
