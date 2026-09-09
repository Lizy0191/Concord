import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Status } from "../components/Status";
import { Button } from "../components/ui/button";

export function RunHistory({
  project,
  preferred,
  perform,
}: {
  project: string;
  preferred?: string;
  perform: (fn: () => Promise<unknown>) => Promise<void>;
}) {
  const [chosen, setChosen] = useState("");
  const runs = useQuery({
    queryKey: ["runs", project],
    queryFn: () => api.runs(project),
    refetchInterval: 2000,
  });
  const selected =
    runs.data?.find((run) => run.id === (chosen || preferred)) ??
    runs.data?.[0];
  const timeline = useQuery({
    queryKey: [
      "timeline",
      selected?.id,
      selected?.status,
      selected?.generation,
    ],
    queryFn: () => api.timeline(selected!.id),
    enabled: !!selected,
    refetchInterval:
      selected &&
      ["QUEUED", "RUNNING", "WAITING_APPROVAL"].includes(selected.status)
        ? 2000
        : false,
  });
  const job = useQuery({
    queryKey: ["job", selected?.id, selected?.status, selected?.generation],
    queryFn: () => api.job(selected!.id),
    enabled: !!selected && selected.category !== "coordination",
  });
  return (
    <section className="run-history" aria-label="Run history">
      <div className="view-heading">
        <h3>Run history & results</h3>
        <span className="muted">Most recent 200 runs</span>
      </div>
      <select
        aria-label="Inspect run"
        value={selected?.id ?? ""}
        onChange={(event) => setChosen(event.target.value)}
      >
        {runs.data?.map((run) => (
          <option key={run.id} value={run.id}>
            {run.category.replaceAll("_", " ")} / {run.status} /{" "}
            {run.id.slice(0, 8)}
          </option>
        ))}
      </select>
      {selected && (
        <>
          <div className="run-summary">
            <Status value={selected.status} />
            <code>{selected.id}</code>
            <span>{selected.runtime}</span>
            {["QUEUED", "RUNNING", "WAITING_APPROVAL"].includes(
              selected.status,
            ) && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void perform(() => api.cancel(selected.id))}
              >
                Cancel run
              </Button>
            )}
            {["QUEUED", "FAILED", "CANCELLED", "EXPIRED"].includes(
              selected.status,
            ) && (
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void perform(() => api.resume(selected.id))}
              >
                Retry / resume
              </Button>
            )}
          </div>
          {selected.error && (
            <p role="alert" className="alert">
              {selected.error}
            </p>
          )}
          {job.data && (
            <div className="job-result">
              <span className="eyebrow">
                SNAPSHOT {job.data.snapshot_id?.slice(0, 12) ?? "not captured"}
              </span>
              <h4>Result</h4>
              {job.data.result ? (
                <pre>{JSON.stringify(job.data.result, null, 2)}</pre>
              ) : (
                <p>No successful result has been committed.</p>
              )}
            </div>
          )}
          <details>
            <summary>
              Safe execution trace ({timeline.data?.length ?? 0} events)
            </summary>
            <ol className="trace-list">
              {timeline.data?.slice(-50).map((event) => (
                <li key={event.sequence}>
                  <code>{event.sequence}</code>
                  <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                </li>
              ))}
            </ol>
          </details>
        </>
      )}
      {(runs.error || job.error || timeline.error) && (
        <p role="alert">Some run details could not be loaded.</p>
      )}
    </section>
  );
}
