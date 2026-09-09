import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type DTO } from "../api/client";
import { Button } from "../components/ui/button";

export function SemanticRetrieval({
  project,
  enabled,
  perform,
  onRun,
}: {
  project: string;
  enabled: boolean;
  perform: (fn: () => Promise<unknown>) => Promise<void>;
  onRun: (id: string) => void;
}) {
  const documents = useQuery({
    queryKey: ["documents", project],
    queryFn: () => api.documents(project),
  });
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [consent, setConsent] = useState(false);
  const [matches, setMatches] = useState<DTO<"SemanticMatch">[]>([]);
  const [searched, setSearched] = useState(false);
  const searchVersion = useRef(0);
  function changeSelection() {
    searchVersion.current += 1;
    setConsent(false);
    setMatches([]);
    setSearched(false);
  }
  async function search() {
    const version = ++searchVersion.current;
    const found = await api.semanticSearch(project, query, documentId, consent);
    if (version === searchVersion.current) {
      setMatches(found);
      setSearched(true);
    }
  }
  const documentId = selected || documents.data?.[0]?.id || "";
  return (
    <details className="operation-form">
      <summary>Derived vector retrieval / PostgreSQL</summary>
      <p>
        Structured and local text search remain the default. Index only a
        selected document (up to 128 chunks). Test-token embeddings are labeled
        and are not a language model.
      </p>
      <select
        aria-label="Document to index"
        value={documentId}
        onChange={(event) => {
          changeSelection();
          setSelected(event.target.value);
        }}
      >
        {documents.data?.map((doc) => (
          <option value={doc.id} key={doc.id}>
            {doc.filename}
          </option>
        ))}
      </select>
      <label className="consent">
        <input
          type="checkbox"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
        />
        For a real cloud embedding provider, I consent to sending selected
        minimized text and my query.
      </label>
      <Button
        variant="secondary"
        disabled={!enabled || !documentId}
        onClick={() =>
          void perform(async () => {
            const run = await api.indexDocument(project, documentId, consent);
            onRun(run.id);
          })
        }
      >
        Index selected document
      </Button>
      <div className="semantic-query">
        <input
          aria-label="Semantic query"
          value={query}
          onChange={(event) => {
            changeSelection();
            setQuery(event.target.value);
          }}
          placeholder="Find related document evidence"
        />
        <Button
          disabled={!enabled || !query.trim()}
          onClick={() => void perform(search)}
        >
          Search vectors
        </Button>
      </div>
      {!enabled && (
        <small>
          Requires the server extra, PostgreSQL with pgvector,
          CCA_VECTOR_ENABLED, and the optional vector migration.
        </small>
      )}
      {searched && matches.length === 0 && (
        <p>
          No matching indexed evidence. Confirm that indexing completed for the
          selected source/model revision.
        </p>
      )}
      {matches.map((match) => (
        <article className="document-chunk" key={match.chunk_id}>
          <strong>
            {match.test_only ? "TEST-ONLY VECTOR" : "SEMANTIC MATCH"} / score{" "}
            {match.score.toFixed(3)}
          </strong>
          <p>{match.text}</p>
          <small>
            Page {match.page ?? "?"} / {match.model}@{match.model_version} / SHA{" "}
            {match.source_hash.slice(0, 12)}
          </small>
        </article>
      ))}
    </details>
  );
}
