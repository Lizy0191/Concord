import { Component, type ReactNode } from "react";

/** A failed lazy viewer or WebGL render must not remove approval controls. */
export class ViewerBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <section className="loading-view" role="alert">
          <h2>This workspace view could not be loaded</h2>
          <p>
            The project inspector, approvals, and other views remain available.
          </p>
          <p>
            Switch to another view. Reload after checking the browser,
            connection, and viewer assets.
          </p>
        </section>
      );
    }
    return this.props.children;
  }
}
