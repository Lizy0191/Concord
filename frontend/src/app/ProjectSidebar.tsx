import { Building2, ChevronRight } from "lucide-react";
import type { DTO, Workspace } from "../api/client";
import { Button } from "../components/ui/button";

export function ProjectSidebar({
  data,
  project,
  projects,
  selected,
  onProject,
  onSelect,
  onReset,
}: {
  data: Workspace;
  project: string;
  projects: DTO<"Project">[] | undefined;
  selected: string;
  onProject: (id: string) => void;
  onSelect: (id: string) => void;
  onReset: () => void;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <Building2 size={23} />
        </div>
        <div>
          <strong>CONCORD</strong>
          <span>Construction coordination</span>
        </div>
      </div>
      <div className="project-picker">
        <span className="eyebrow">ACTIVE PROJECT</span>
        <select
          aria-label="Project"
          value={project}
          onChange={(e) => onProject(e.target.value)}
        >
          {projects?.map((p) => (
            <option value={p.id} key={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <span className="project-meta">REFERENCE PROJECT / SYNTHETIC</span>
      </div>
      <div className="sidebar-section">
        <div className="sidebar-label">
          WORK PACKAGES <span>{data.state.work_packages.length}</span>
        </div>
        {data.state.areas.map((area) => (
          <div key={area.id} className="area-group">
            <div className="area-title">
              <ChevronRight size={12} />
              {area.name}
            </div>
            {data.state.work_packages
              .filter((p) => p.area_id === area.id)
              .map((p) => (
                <button
                  key={p.id}
                  className={`package-nav ${selected === p.id ? "selected" : ""}`}
                  onClick={() => {
                    onSelect(p.id);
                  }}
                >
                  <span
                    className={`nav-indicator ${data.analysis?.readiness.find((r) => r.work_package_id === p.id)?.status === "BLOCKED" ? "is-blocked" : ""}`}
                  />
                  <span>
                    <strong>{p.name}</strong>
                    <small>
                      {p.id} / {p.discipline}
                    </small>
                  </span>
                </button>
              ))}
          </div>
        ))}
      </div>
      <div className="sidebar-section">
        <div className="sidebar-label">
          RECENT EVENTS <span>{data.events.length}</span>
        </div>
        {data.events.length === 0 ? (
          <p className="sidebar-empty">
            No changes recorded.
            <br />
            The workface is ready for review.
          </p>
        ) : (
          data.events.slice(0, 4).map((e) => (
            <div className="sidebar-event" key={e.id}>
              <span>{e.kind.replaceAll("_", " ")}</span>
              <strong>{e.title}</strong>
            </div>
          ))
        )}
      </div>
      <div className="sidebar-bottom">
        <div>
          <span className="online-dot" />
          {data.analysis?.reasoning_mode === "offline"
            ? "Offline reasoning"
            : "Model reasoning"}
        </div>
        <small>Local-first / Evidence-backed</small>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (
              window.confirm(
                "Reset synthetic facts? Audit history is retained.",
              )
            )
              onReset();
          }}
        >
          Reset demo
        </Button>
      </div>
    </aside>
  );
}
