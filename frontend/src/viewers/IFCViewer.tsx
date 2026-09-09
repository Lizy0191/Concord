import { Button } from "../components/ui/button";
import { useIFCViewer } from "./useIFCViewer";

/** All SDK objects stay inside this lazy boundary, never in server/domain DTOs. */
export default function IFCViewer({
  file,
  impacted,
  onSelected,
}: {
  file: File;
  impacted: readonly string[];
  onSelected: (id: string) => void;
}) {
  const { container, ready, message, error, properties, busy, act } =
    useIFCViewer(file, impacted, onSelected);
  return (
    <div className="bim-stage" ref={container} aria-label="IFC model viewer">
      <div className="viewer-actions">
        <Button
          disabled={!ready || busy}
          size="sm"
          variant="secondary"
          onClick={() => void act("focus")}
        >
          Focus
        </Button>
        <Button
          disabled={!ready || busy}
          size="sm"
          variant="secondary"
          onClick={() => void act("isolate")}
        >
          Isolate
        </Button>
        <Button
          disabled={!ready || busy}
          size="sm"
          variant="secondary"
          onClick={() => void act("showAll")}
        >
          Show all
        </Button>
      </div>
      <div className="viewer-message" role={error ? "alert" : "status"}>
        {error
          ? `3D viewer unavailable: ${error}. Structured BIM remains usable.`
          : message}
        {properties && (
          <details>
            <summary>Selected element properties</summary>
            <pre>{properties}</pre>
          </details>
        )}
      </div>
    </div>
  );
}
