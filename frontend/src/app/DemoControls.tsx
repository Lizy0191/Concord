import { ChevronRight, Users } from "lucide-react";
import type { DTO } from "../api/client";

export function DemoControls({
  project,
  busy,
  createEvent,
}: {
  project: string;
  busy: boolean;
  createEvent: (event: DTO<"ProjectEvent-Input">) => void;
}) {
  return (
    <div className="demo-strip">
      <span>DEMO CONTROLS</span>
      <button
        disabled={busy}
        onClick={() =>
          createEvent({
            project_id: project,
            work_package_id: "WP-200",
            kind: "design_revision",
            title: "Duct route revised / V17",
            change: { revision: "V17" },
          })
        }
      >
        Drawing V16 <ChevronRight size={12} /> V17
      </button>
      <button
        disabled={busy}
        onClick={() =>
          createEvent({
            project_id: project,
            work_package_id: "WP-300",
            kind: "workforce",
            title: "Electrical crew shortage",
            change: { available_workers: 1 },
          })
        }
      >
        <Users size={13} /> Crew shortage
      </button>
      <span className="demo-note">
        Synthetic inputs. Deterministic outcomes.
      </span>
    </div>
  );
}
