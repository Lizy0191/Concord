import { lazy, Suspense } from "react";
import {
  Building2,
  Network,
  Layers3,
  FileText,
  Map,
  SlidersHorizontal,
  Workflow,
} from "lucide-react";
import type { Workspace } from "../api/client";
import { ViewerBoundary } from "../components/ViewerBoundary";
import { Inspector } from "../features/Inspector";
import { WorkPackages } from "../features/WorkPackages";
import { Documents } from "../features/Documents";
import { Capabilities } from "../features/Capabilities";
import { Operations } from "../features/Operations";

const ImpactGraph = lazy(() => import("../features/ImpactGraph"));
const BIMWorkspace = lazy(() => import("../viewers/BIMWorkspace"));
const GISWorkspace = lazy(() => import("../viewers/GISWorkspace"));
const tabs = [
  { id: "operations", label: "Operations", Icon: Workflow },
  { id: "impact", label: "Impact graph", Icon: Network },
  { id: "packages", label: "Work packages", Icon: Layers3 },
  { id: "documents", label: "Documents", Icon: FileText },
  { id: "bim", label: "BIM", Icon: Building2 },
  { id: "gis", label: "Site", Icon: Map },
  { id: "capabilities", label: "Capabilities", Icon: SlidersHorizontal },
] as const;
export type WorkspaceTab = (typeof tabs)[number]["id"];

export function WorkspaceViews({
  project,
  data,
  selected,
  selectedConstraint,
  tab,
  busy,
  perform,
  onTab,
  onSelected,
  onConstraint,
}: {
  project: string;
  data: Workspace;
  selected: string;
  selectedConstraint: string;
  tab: WorkspaceTab;
  busy: boolean;
  perform: (operation: () => Promise<unknown>) => Promise<void>;
  onTab: (tab: WorkspaceTab) => void;
  onSelected: (id: string) => void;
  onConstraint: (id: string) => void;
}) {
  return (
    <>
      <nav className="workspace-tabs" aria-label="Workspace views">
        {tabs.map(({ id, label, Icon }) => (
          <button
            key={id}
            className={tab === id ? "active" : ""}
            onClick={() => onTab(id)}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </nav>
      <div className="workspace-body">
        <div className="central-workspace">
          <ViewerBoundary key={`${project}:${tab}`}>
            <Suspense
              fallback={
                <div className="loading-view">Loading workspace module...</div>
              }
            >
              {tab === "operations" && (
                <Operations project={project} perform={perform} />
              )}
              {tab === "impact" && (
                <ImpactGraph
                  workspace={data}
                  selected={selected}
                  onConstraint={onConstraint}
                />
              )}
              {tab === "packages" && (
                <WorkPackages workspace={data} onSelect={onSelected} />
              )}
              {tab === "documents" && (
                <Documents project={project} perform={perform} />
              )}
              {tab === "capabilities" && <Capabilities />}
              {tab === "bim" && (
                <BIMWorkspace
                  project={project}
                  impacted={data.analysis?.impact.element_ids ?? []}
                />
              )}
              {tab === "gis" && (
                <GISWorkspace
                  project={project}
                  selected={selected}
                  onSelected={onSelected}
                />
              )}
            </Suspense>
          </ViewerBoundary>
        </div>
        <Inspector
          busy={busy}
          workspace={data}
          selected={selected}
          selectedConstraint={selectedConstraint}
          perform={perform}
        />
      </div>
    </>
  );
}
