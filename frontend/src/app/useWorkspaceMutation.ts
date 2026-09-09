import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

/** Serialize workspace mutations and reconcile the authoritative server state. */
export function useWorkspaceMutation() {
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false);
  const mutationActive = useRef(false);
  const [error, setError] = useState("");
  async function perform(operation: () => Promise<unknown>) {
    if (mutationActive.current) return;
    mutationActive.current = true;
    setBusy(true);
    setError("");
    try {
      await operation();
      await cache.invalidateQueries({ queryKey: ["workspace"] });
      await Promise.all(
        ["timeline", "runs", "documents", "bim", "job"].map((key) =>
          cache.invalidateQueries({ queryKey: [key] }),
        ),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Operation failed");
      await cache.invalidateQueries({ queryKey: ["workspace"] });
    } finally {
      mutationActive.current = false;
      setBusy(false);
    }
  }
  return { perform, busy, error, setError };
}
