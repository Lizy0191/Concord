import { Building2, ChevronRight, Plus, RefreshCw } from "lucide-react";
import type { DTO, Workspace, WorkPackage } from "../api/client";
import { Button } from "../components/ui/button";
import { Status } from "../components/Status";

export function WorkspaceHeader({
  data,
  wp,
  profile,
  busy,
  onRecheck,
  onEvent,
}: {
  data: Workspace;
  wp: WorkPackage;
  profile: DTO<"ProfileResponse"> | undefined;
  busy: boolean;
  onRecheck: () => void;
  onEvent: () => void;
}) {
  const readiness = data.analysis?.readiness.find(
    (r) => r.work_package_id === wp.id,
  );
  const blocked =
    data.analysis?.readiness.filter((r) => r.status === "BLOCKED").length ?? 0;
  return (
    <>
      <header className="topbar">
        <div className="breadcrumb">
          <Building2 size={16} />
          <span>Building A</span>
          <ChevronRight size={12} />
          <span>{wp.area_id}</span>
          <ChevronRight size={12} />
          <strong>{wp.id}</strong>
        </div>
        <div className="topbar-right">
          <span className="profile-tag">
            {data.run?.runtime === "diagnostic-NON-DURABLE"
              ? "DIAGNOSTIC / NON-DURABLE"
              : `${profile?.profile ?? "loading"} / ${profile?.reasoning ?? "unknown"}`}
          </span>
          <span
            className="avatar"
            title="Configured bearer principal; not enterprise identity"
          >
            CA
          </span>
        </div>
      </header>
      <section className="workspace-heading">
        <div>
          <div className="eyebrow">COORDINATION WORKSPACE</div>
          <h1>{wp.name}</h1>
          <div className="workspace-subtitle">
            <Status
              value={data.stale ? "STALE" : (readiness?.status ?? "UNCHECKED")}
            />
            <span>
              {blocked} blocked / {data.state.work_packages.length} packages
            </span>
            <span className="mono">
              SNAPSHOT v{data.analysis?.snapshot.version ?? "-"}
            </span>
          </div>
        </div>
        <div className="heading-actions">
          <Button variant="secondary" disabled={busy} onClick={onRecheck}>
            <RefreshCw size={14} /> Re-check
          </Button>
          <Button disabled={busy} onClick={onEvent}>
            <Plus size={15} /> New event
          </Button>
        </div>
      </section>
    </>
  );
}
