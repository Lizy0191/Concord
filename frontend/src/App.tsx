import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Building2, AlertTriangle } from "lucide-react";
import { api, setToken, type DTO } from "./api/client";
import { Button } from "./components/ui/button";
import { Timeline } from "./features/Timeline";
import { EventComposer } from "./features/EventComposer";
import { DemoControls } from "./app/DemoControls";
import { ProjectSidebar } from "./app/ProjectSidebar";
import { WorkspaceHeader } from "./app/WorkspaceHeader";
import { WorkspaceViews, type WorkspaceTab } from "./app/WorkspaceViews";
import { useWorkspace } from "./app/useWorkspace";
import { useWorkspaceMutation } from "./app/useWorkspaceMutation";

export function App() {
  const cache = useQueryClient();
  const [project, setProject] = useState("harbor-east");
  const [selected, setSelected] = useState("WP-200");
  const [selectedConstraint, setSelectedConstraint] = useState("");
  const [tab, setTab] = useState<WorkspaceTab>("impact");
  const [eventDialog, setEventDialog] = useState(false);
  const [token, updateToken] = useState("");
  const { profile, projects, workspace } = useWorkspace(project);
  const { perform, busy, error, setError } = useWorkspaceMutation();
  const data = workspace.data;
  function createEvent(event: DTO<"ProjectEvent-Input">) {
    setSelected(event.work_package_id);
    setSelectedConstraint("");
    setTab("impact");
    setEventDialog(false);
    void perform(() => api.events(project, event));
  }
  const wp =
    data?.state.work_packages.find((p) => p.id === selected) ??
    data?.state.work_packages[0];
  if (!data || !wp)
    return (
      <div className="startup">
        <Building2 size={36} />
        <h1>Construction Coordination Agent</h1>
        {workspace.isPending ? (
          <p>Connecting to the project workspace...</p>
        ) : (
          <>
            <p role="alert">
              {workspace.error?.message ?? "No project has been seeded."}
            </p>
            <p>Start the Python API, then use the configured bearer token.</p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setToken(token);
                void cache.invalidateQueries();
              }}
            >
              <input
                type="password"
                aria-label="API token"
                value={token}
                onChange={(e) => updateToken(e.target.value)}
                placeholder="API bearer token"
              />
              <Button type="submit">Connect</Button>
            </form>
          </>
        )}
      </div>
    );
  return (
    <div className="application-shell" aria-busy={busy}>
      <ProjectSidebar
        data={data}
        project={project}
        projects={projects.data}
        selected={wp.id}
        onProject={setProject}
        onSelect={(id) => {
          setSelected(id);
          setSelectedConstraint("");
        }}
        onReset={() => void perform(api.reset)}
      />
      <main className="main-shell">
        <WorkspaceHeader
          data={data}
          wp={wp}
          profile={profile.data}
          busy={busy}
          onRecheck={() => void perform(() => api.recheck(project))}
          onEvent={() => setEventDialog(true)}
        />
        <DemoControls project={project} busy={busy} createEvent={createEvent} />
        {(error || data.stale) && (
          <div className="alert" role="alert">
            <AlertTriangle size={16} />
            {error || "This analysis is stale. Re-check before taking action."}
            <button onClick={() => setError("")} aria-label="Dismiss error">
              x
            </button>
          </div>
        )}
        <WorkspaceViews
          project={project}
          data={data}
          selected={wp.id}
          selectedConstraint={selectedConstraint}
          tab={tab}
          busy={busy}
          perform={perform}
          onTab={setTab}
          onSelected={setSelected}
          onConstraint={setSelectedConstraint}
        />
        <Timeline run={data.run} perform={perform} />
        <footer className="statusbar">
          <span>
            Revision-aware coordination / Not a final safety authority
          </span>
          <span>
            State v{data.state.version} / {data.analysis?.evidence.length ?? 0}{" "}
            evidence items
          </span>
        </footer>
      </main>
      {eventDialog && (
        <EventComposer
          wp={wp}
          project={project}
          onCreate={createEvent}
          onClose={() => setEventDialog(false)}
        />
      )}
    </div>
  );
}
