import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useBIMSource } from "./useBIMSource";
import { Button } from "../components/ui/button";
const IFCViewer = lazy(() => import("./IFCViewer"));

export default function BIMWorkspace({
  project,
  impacted,
}: {
  project: string;
  impacted: readonly string[];
}) {
  const elements = useQuery({
    queryKey: ["bim", project],
    queryFn: () => api.bim(project),
  });
  const {
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
  } = useBIMSource(project);
  const item = elements.data?.find((e) => e.id === selected);
  return (
    <section className="bim-workspace">
      <div className="viewer-toolbar">
        <strong>BIM WORKSPACE</strong>
        <span>
          {file
            ? "That Open Engine / local IFC"
            : "Structured BIM / no geometry engine required"}
        </span>
        <label className="import-button">
          Open IFC locally
          <input
            aria-label="Local IFC file"
            type="file"
            accept=".ifc"
            disabled={busy}
            onChange={(event) => {
              chooseFile(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
        </label>
        <Button
          size="sm"
          variant="secondary"
          disabled={busy}
          onClick={() => void openImported()}
        >
          Open project IFC
        </Button>
        {file && (
          <Button
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => void importSource()}
          >
            {busy ? "Working..." : "Import to project"}
          </Button>
        )}
        {file && (
          <Button
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => {
              setFile(null);
              setSelected("");
            }}
          >
            Structured
          </Button>
        )}
      </div>
      {(error || imported.error) && (
        <div className="alert" role="alert">
          {error || imported.error?.message}
        </div>
      )}
      {(notice || imported.data) && (
        <div className="viewer-message" role="status">
          {notice} {imported.data && `Import ${imported.data.status}.`}
        </div>
      )}
      {imported.data?.error && (
        <div className="alert" role="alert">
          {imported.data.error}
        </div>
      )}
      {file ? (
        <Suspense
          fallback={
            <div className="loading-view">
              Loading the local IFC renderer...
            </div>
          }
        >
          <IFCViewer file={file} impacted={impacted} onSelected={setSelected} />
        </Suspense>
      ) : (
        <div className="bim-stage">
          <div className="bim-element-list">
            {elements.data?.map((element) => (
              <button
                key={element.id}
                className={`bim-element ${impacted.includes(element.id) ? "impacted" : ""} ${element.id === selected ? "selected" : ""}`}
                onClick={() => setSelected(element.id)}
              >
                <strong>{element.name}</strong>
                <small>
                  {element.type} / {element.storey ?? "Unassigned storey"}
                </small>
                <small>{element.id}</small>
                <small>
                  {impacted.includes(element.id)
                    ? "Impacted by current analysis"
                    : "No current impact"}
                </small>
              </button>
            ))}
          </div>
          {elements.error && (
            <div className="alert">{elements.error.message}</div>
          )}
          {item && (
            <div className="bim-properties">
              <h3>{item.name} / properties</h3>
              <pre>{JSON.stringify(item, null, 2)}</pre>
            </div>
          )}
          <div className="viewer-message">
            This structured relationship view is not a 3D model. Open an IFC
            file to use the separately loaded geometry viewer. Opening a file
            stays in this browser. Import to project explicitly sends it to the
            configured backend.
          </div>
        </div>
      )}
    </section>
  );
}
