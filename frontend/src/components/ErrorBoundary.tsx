import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional custom fallback rendered when a child throws. */
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/**
 * React error boundary. Catches render/lifecycle errors thrown by any child in
 * the tree and shows a friendly, dark-theme fallback instead of a blank screen.
 *
 * Usage: wrap each routed page so a crash in one page is contained and offers
 * recovery (reload the app or return home).
 */
class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    // Render the fallback UI on the next render.
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log for diagnostics; a real app might forward this to an error service.
    console.error("ErrorBoundary caught an error:", error, info.componentStack);
  }

  private handleReload = () => {
    window.location.reload();
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (this.props.fallback !== undefined) {
      return this.props.fallback;
    }

    return (
      <div
        role="alert"
        className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white px-6 text-center gap-4"
      >
        <h1 className="text-2xl font-bold">Something went wrong</h1>
        <p className="max-w-md text-gray-400">
          An unexpected error occurred. You can reload the app to try again, or
          head back home.
        </p>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={this.handleReload}
            className="rounded-md bg-indigo-600 px-4 py-2 font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          >
            Reload
          </button>
          <a
            href="/"
            className="rounded-md border border-gray-600 px-4 py-2 font-medium text-gray-200 transition-colors hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-gray-400"
          >
            Go home
          </a>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
