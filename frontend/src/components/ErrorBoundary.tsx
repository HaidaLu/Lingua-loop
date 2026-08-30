import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

// Keeps a crash inside a third-party embed (e.g. the YouGlish widget) from taking
// the whole page down.
export default class ErrorBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.failed) {
      return this.props.fallback ?? <p className="muted">Something went wrong here.</p>;
    }
    return this.props.children;
  }
}
