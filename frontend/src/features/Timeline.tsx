import { useQuery } from "@tanstack/react-query";
import { Activity, Square, RotateCcw } from "lucide-react";
import { api, type AgentRun } from "../api/client";
import { useRunStream } from "../api/stream";
import { Button } from "../components/ui/button";

export function Timeline({
  run,
  perform,
}: {
  run?: AgentRun | null;
  perform: (fn: () => Promise<unknown>) => Promise<void>;
}) {
  const active =
    !!run &&
    ["QUEUED", "RUNNING", "WAITING_APPROVAL"].includes(run.status ?? "");
  const { events, error } = useRunStream(run?.id, active, run?.generation);
  const history = useQuery({
    queryKey: ["timeline", run?.id, run?.status, run?.generation],
    queryFn: () => api.timeline(run!.id!),
    enabled: !!run?.id,
  });
  const rows = events.length
    ? events
    : ((history.data ?? []).map((row) => ({
        ...row.payload,
        sequence: row.sequence,
      })) as typeof events);
  return (
    <section className="timeline" aria-label="Agent run timeline">
      <div className="timeline-heading">
        <Activity size={15} />
        <strong>Agent run</strong>
        <span className="mono">{run?.id?.slice(0, 8) ?? "none"}</span>
        <span>{run?.status?.replaceAll("_", " ")}</span>
        <span className="timeline-runtime">{run?.runtime}</span>
        {active && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void perform(() => api.cancel(run!.id!))}
          >
            <Square size={12} />
            Cancel
          </Button>
        )}
        {run &&
          ["QUEUED", "FAILED", "CANCELLED", "EXPIRED"].includes(
            run.status ?? "",
          ) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void perform(() => api.resume(run.id!))}
            >
              <RotateCcw size={12} />
              {run.status === "QUEUED" ? "Retry dispatch" : "Resume"}
            </Button>
          )}
      </div>
      <div className="timeline-events">
        {rows.slice(-7).map((row) => (
          <div className="timeline-event" key={row.sequence}>
            <span className="timeline-tick" />
            <span className="mono">
              {row.timestamp
                ? new Date(row.timestamp).toLocaleTimeString()
                : ""}
            </span>
            <strong>
              {row.name ?? row.stepName ?? row.type?.replaceAll("_", " ")}
            </strong>
          </div>
        ))}
      </div>
      {error && (
        <small role="status" className="stream-warning">
          {error}; workspace remains available.
        </small>
      )}
      {run?.error && <p role="alert">{run.error}</p>}
    </section>
  );
}
