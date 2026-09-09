import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "./App";
import { initializeConnection } from "./api/client";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 1000, retry: 1, refetchOnWindowFocus: false },
  },
});
const root = ReactDOM.createRoot(document.getElementById("root")!);
root.render(<div className="startup">Starting the local workspace...</div>);
initializeConnection()
  .then(() =>
    root.render(
      <React.StrictMode>
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      </React.StrictMode>,
    ),
  )
  .catch((error) =>
    root.render(
      <div className="startup">
        <h1>Backend startup failed</h1>
        <p role="alert">{String(error)}</p>
        <p>Check the desktop sidecar build or start the Web API.</p>
      </div>,
    ),
  );
