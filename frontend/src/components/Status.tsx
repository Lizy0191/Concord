export function Status({ value }: { value: string }) {
  const kind =
    value === "READY" || value === "COMPLETED" || value === "enabled"
      ? "ready"
      : value === "BLOCKED" || value === "FAILED" || value === "unhealthy"
        ? "blocked"
        : "neutral";
  return (
    <span className={`status status-${kind}`}>
      <span aria-hidden="true" className="status-dot" />
      {value.replaceAll("_", " ")}
    </span>
  );
}
