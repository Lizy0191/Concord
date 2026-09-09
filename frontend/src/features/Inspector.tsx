import { useEffect, useState } from "react";
import { FileCheck2, ShieldCheck, ArrowRight, Link2 } from "lucide-react";
import { api, type Workspace } from "../api/client";
import { Button } from "../components/ui/button";
import { Status } from "../components/Status";

export function Inspector({
  workspace,
  selected,
  selectedConstraint,
  perform,
  busy = false,
}: {
  workspace: Workspace;
  busy?: boolean;
  selected: string;
  selectedConstraint: string;
  perform: (operation: () => Promise<unknown>) => Promise<void>;
}) {
  const [confirmation, setConfirmation] = useState("");
  const wp = workspace.state.work_packages.find((p) => p.id === selected)!;
  const readiness = workspace.analysis?.readiness.find(
    (r) => r.work_package_id === selected,
  );
  const constraints = (workspace.analysis?.constraints ?? []).filter(
    (c) => c.work_package_id === selected,
  );
  const proposal = workspace.proposals.find(
    (p) => p.work_package_id === selected,
  );
  const actionRun =
    workspace.analysis_run ??
    (workspace.run?.id === proposal?.run_id ? workspace.run : null);
  const inactive =
    !!actionRun &&
    (actionRun.status !== "WAITING_APPROVAL" ||
      proposal?.generation !== actionRun.generation);
  const approved =
    !!proposal &&
    workspace.approvals.some((a) => a.proposal_id === proposal.id);
  useEffect(() => setConfirmation(""), [proposal?.id]);
  const activeConstraint =
    constraints.find((c) => c.id === selectedConstraint) ?? constraints[0];
  const evidence = (workspace.analysis?.evidence ?? []).filter((e) =>
    activeConstraint?.evidence_ids.includes(e.id ?? ""),
  );
  return (
    <aside className="inspector" aria-label="Evidence and actions inspector">
      <div className="panel-heading">
        <span className="eyebrow">WORKFACE INSPECTOR</span>
        <FileCheck2 size={16} />
      </div>
      <div className="inspector-section">
        <span className="mono muted">{wp.id}</span>
        <h2>{wp.name}</h2>
        <Status
          value={workspace.stale ? "STALE" : (readiness?.status ?? "UNCHECKED")}
        />
        <dl className="properties">
          <dt>Area</dt>
          <dd>{wp.area_id}</dd>
          <dt>Owner</dt>
          <dd>{wp.owner}</dd>
          <dt>Revision</dt>
          <dd>
            {wp.accepted_revision} accepted / {wp.design_revision} current
          </dd>
          <dt>Crew</dt>
          <dd>
            {wp.available_workers} / {wp.required_workers} available
          </dd>
        </dl>
      </div>
      <div className="inspector-section">
        <h3>
          <Link2 size={14} /> Constraints{" "}
          <span className="count">{constraints.length}</span>
        </h3>
        {constraints.length === 0 ? (
          <p className="quiet-message">
            No unresolved blockers in the last checked snapshot.
          </p>
        ) : (
          constraints.map((c) => (
            <div
              className={`constraint-item ${c.id === activeConstraint?.id ? "selected" : ""}`}
              key={c.id}
            >
              <span className="eyebrow">{c.kind}</span>
              <p>{c.description}</p>
            </div>
          ))
        )}
        {evidence.map((item) => (
          <details className="evidence" open key={item.id}>
            <summary>Evidence / {item.source_revision}</summary>
            <p>{item.fact}</p>
            <div className="mono">
              {item.provider}
              <br />
              {item.source_id}
              <br />
              {new Date(item.observed_at).toLocaleString()}
            </div>
            <div className="evidence-id">
              Snapshot {item.snapshot_id.slice(0, 8)}
            </div>
          </details>
        ))}
      </div>
      <div className="inspector-section action-section">
        <h3>
          <ShieldCheck size={15} /> Controlled action
        </h3>
        {proposal ? (
          <>
            <div className="action-title">
              <strong>{proposal.title}</strong>
              <span className="risk">R{proposal.risk}</span>
            </div>
            <p>{proposal.resolution.explanation}</p>
            <div className="effect-list">
              {proposal.resolution.effects.map((effect, i) => (
                <div key={i}>
                  <ArrowRight size={12} />
                  {effect.kind.replaceAll("_", " ")}
                </div>
              ))}
            </div>
            <div className="simulation-label">
              SIMULATED EXTERNAL CONFIRMATION
            </div>
            {proposal.risk >= 4 && !approved && (
              <label className="form-label">
                Strong approval: type APPROVE R4
                <input
                  aria-label="R4 confirmation"
                  value={confirmation}
                  onChange={(event) => setConfirmation(event.target.value)}
                  placeholder="APPROVE R4"
                />
              </label>
            )}
            <div className="action-buttons">
              <Button
                disabled={
                  busy ||
                  inactive ||
                  workspace.stale ||
                  approved ||
                  (proposal.risk >= 4 && confirmation !== "APPROVE R4")
                }
                variant="secondary"
                onClick={() =>
                  void perform(() =>
                    api.approve(proposal.id!, proposal.risk >= 4, confirmation),
                  )
                }
              >
                {approved ? "Approved" : `Approve R${proposal.risk}`}
              </Button>
              <Button
                disabled={busy || inactive || workspace.stale || !approved}
                onClick={() => void perform(() => api.execute(proposal.id!))}
              >
                Execute & re-check
              </Button>
            </div>
            <div className="mono operation">
              Operation {proposal.operation_id?.slice(0, 12)}
            </div>
          </>
        ) : (
          <p className="quiet-message">
            Actions appear when evidence-backed constraints require
            coordination.
          </p>
        )}
      </div>
    </aside>
  );
}
