import { useEffect, useRef, useState } from "react";
import type { DTO, WorkPackage } from "../api/client";
import { Button } from "../components/ui/button";

export function EventComposer({
  wp,
  project,
  onCreate,
  onClose,
}: {
  wp: WorkPackage;
  project: string;
  onCreate: (event: DTO<"ProjectEvent-Input">) => void;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const focusable = () =>
      Array.from(
        dialog.current?.querySelectorAll<HTMLElement>(
          "button, input, textarea, select",
        ) ?? [],
      ).filter((element) => !(element as HTMLButtonElement).disabled);
    focusable()[0]?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    dialog.current?.addEventListener("keydown", keydown);
    const element = dialog.current;
    return () => {
      element?.removeEventListener("keydown", keydown);
      previouslyFocused?.focus();
    };
  }, [onClose]);
  const [kind, setKind] =
    useState<DTO<"ProjectEvent-Input">["kind"]>("design_revision");
  const [value, setValue] = useState("V17");
  const [note, setNote] = useState("");
  function submit() {
    const change: DTO<"EventChange-Input"> = {};
    if (kind === "design_revision") change.revision = value;
    if (kind === "workforce") change.available_workers = Number(value);
    if (kind === "material" || kind === "equipment") {
      change.resource_id = value;
      change.available = false;
    }
    if (kind === "predecessor") {
      change.predecessor_id = value;
      change.complete = false;
    }
    if (kind === "inspection") change.inspection_passed = false;
    onCreate({
      id: crypto.randomUUID(),
      project_id: project,
      work_package_id: wp.id,
      kind,
      title: `${kind.replaceAll("_", " ")} / ${wp.id}`,
      note,
      source: "local-demo-ui",
      change,
    });
  }
  return (
    <div className="modal-backdrop">
      <section
        ref={dialog}
        className="event-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="event-title"
      >
        <span className="eyebrow">NEW PROJECT OBSERVATION</span>
        <h2 id="event-title">Record an event</h2>
        <p>
          {wp.id} / {wp.name}
        </p>
        <label className="form-label">
          Event family
          <select
            value={kind}
            onChange={(e) => {
              const k = e.target.value as typeof kind;
              setKind(k);
              setValue(
                k === "workforce"
                  ? "1"
                  : k === "material"
                    ? (Object.keys(wp.materials ?? {})[0] ?? "")
                    : k === "equipment"
                      ? (Object.keys(wp.equipment ?? {})[0] ?? "")
                      : k === "predecessor"
                        ? (wp.predecessors?.[0] ?? "")
                        : "V17",
              );
            }}
          >
            <option value="design_revision">Design revision</option>
            <option value="workforce">Workforce shortage</option>
            <option value="predecessor">Incomplete predecessor</option>
            <option value="material">Material unavailable</option>
            <option value="equipment">Equipment unavailable</option>
            <option value="inspection">Inspection failed</option>
            <option value="external">External observation</option>
          </select>
        </label>
        {!["inspection", "external"].includes(kind) && (
          <label className="form-label">
            {kind === "design_revision"
              ? "New revision"
              : kind === "workforce"
                ? "Available workers"
                : "Resource / predecessor ID"}
            <input
              type={kind === "workforce" ? "number" : "text"}
              min={0}
              max={10000}
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
          </label>
        )}
        <label className="form-label">
          Source note (untrusted content)
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={4000}
          />
        </label>
        <div className="dialog-actions">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit}>Ingest & analyze</Button>
        </div>
        <small>
          Events change recorded facts. They do not grant agent permissions.
        </small>
      </section>
    </div>
  );
}
