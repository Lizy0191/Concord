import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, readSource } from "../api/client";

/** Local viewing, explicit project import, and generation-fenced source reopening. */
export function useBIMSource(project: string) {
  const cache = useQueryClient();
  const [selected, setSelected] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState("");
  const active = useRef(false);
  const epoch = useRef(0);
  useEffect(() => {
    setFile(null);
    setSelected("");
    setError("");
    setNotice("");
    setRunId("");
    setBusy(false);
    active.current = false;
    return () => {
      epoch.current++;
    };
  }, [project]);
  const imported = useQuery({
    queryKey: ["bim-import", project, runId],
    queryFn: () => api.run(runId),
    enabled: !!runId,
    refetchInterval: (query) =>
      ["QUEUED", "RUNNING"].includes(query.state.data?.status ?? "QUEUED")
        ? 1500
        : false,
  });
  useEffect(() => {
    if (imported.data?.status === "COMPLETED") {
      void cache.invalidateQueries({ queryKey: ["bim", project] });
      void cache.invalidateQueries({ queryKey: ["workspace", project] });
    }
  }, [imported.data?.status, cache, project]);

  async function importSource() {
    if (!file || active.current) return;
    active.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    const current = epoch.current;
    try {
      const run = await api.uploadIFC(project, file);
      if (current !== epoch.current) return;
      setRunId(run.id);
      setNotice("Import submitted. Inspect the durable result in Operations.");
      await cache.invalidateQueries({ queryKey: ["workspace", project] });
      await cache.invalidateQueries({ queryKey: ["runs", project] });
    } catch (cause) {
      if (current === epoch.current)
        setError(cause instanceof Error ? cause.message : "Import failed");
    } finally {
      if (current === epoch.current) {
        active.current = false;
        setBusy(false);
      }
    }
  }
  async function openImported() {
    if (active.current) return;
    active.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    const current = epoch.current;
    try {
      const blob = await readSource(
        `/api/projects/${encodeURIComponent(project)}/bim/content`,
      );
      if (current === epoch.current)
        setFile(new File([blob], "project-import.ifc"));
    } catch (cause) {
      if (current === epoch.current)
        setError(
          cause instanceof Error ? cause.message : "No imported IFC source",
        );
    } finally {
      if (current === epoch.current) {
        active.current = false;
        setBusy(false);
      }
    }
  }
  function chooseFile(chosen: File | undefined) {
    setError("");
    setNotice("");
    setSelected("");
    setRunId("");
    if (
      chosen &&
      (chosen.size > 25 * 1024 * 1024 ||
        !chosen.size ||
        !chosen.name.toLowerCase().endsWith(".ifc"))
    ) {
      setFile(null);
      setError("Choose a nonempty IFC file no larger than 25 MiB.");
    } else setFile(chosen ?? null);
  }
  return {
    selected,
    setSelected,
    file,
    setFile,
    error,
    notice,
    busy,
    imported,
    importSource,
    openImported,
    chooseFile,
  };
}
