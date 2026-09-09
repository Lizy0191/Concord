import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";
import { SemanticRetrieval } from "./SemanticRetrieval";

const mocks = vi.hoisted(() => ({ semanticSearch: vi.fn() }));
vi.mock("../api/client", () => ({
  api: {
    documents: async () => [
      { id: "first", filename: "First source" },
      { id: "second", filename: "Second source" },
    ],
    semanticSearch: mocks.semanticSearch,
  },
}));
beforeEach(() => vi.clearAllMocks());

function setup() {
  const cache = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={cache}>
      <SemanticRetrieval
        project="harbor-east"
        enabled
        perform={async (fn) => {
          await fn();
        }}
        onRun={() => {}}
      />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByText("Derived vector retrieval / PostgreSQL"));
}

it("changing source or query clears the previous disclosure consent", async () => {
  setup();
  await screen.findByRole("option", { name: "First source" });
  const consent = screen.getByRole("checkbox");
  fireEvent.click(consent);
  fireEvent.change(screen.getByLabelText("Document to index"), {
    target: { value: "second" },
  });
  expect(consent).not.toBeChecked();
  fireEvent.click(consent);
  fireEvent.change(screen.getByLabelText("Semantic query"), {
    target: { value: "different text" },
  });
  expect(consent).not.toBeChecked();
});

it("a late result for an old source cannot appear under the new source", async () => {
  let finish!: (value: unknown[]) => void;
  mocks.semanticSearch.mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  setup();
  await screen.findByRole("option", { name: "First source" });
  fireEvent.change(screen.getByLabelText("Semantic query"), {
    target: { value: "duct evidence" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Search vectors" }));
  await waitFor(() => expect(mocks.semanticSearch).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText("Document to index"), {
    target: { value: "second" },
  });
  await act(async () =>
    finish([
      {
        chunk_id: "old",
        text: "OLD SOURCE RESULT",
        score: 0.9,
        model: "test",
        model_version: "v1",
        source_hash: "123456789012",
        test_only: true,
      },
    ]),
  );
  expect(screen.queryByText("OLD SOURCE RESULT")).toBeNull();
});
