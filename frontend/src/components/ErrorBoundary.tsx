import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/8bit/button";

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
        className="flex flex-col items-center justify-center min-h-screen bg-app text-text-primary px-6 text-center gap-4"
      >
        <h1 className="text-2xl font-bold">Something went wrong</h1>
        <p className="max-w-md text-text-secondary">
          An unexpected error occurred. You can reload the app to try again, or
          head back home.
        </p>
        <div className="flex items-center gap-4">
          <Button
            type="button"
            onClick={this.handleReload}
            className="h-auto bg-accent hover:bg-accent/90 px-4 py-2 text-app"
          >
            Reload
          </Button>
          <Link
            to="/"
            className="rounded-none border-4 border-foreground px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-panel focus:outline-none focus:ring-2 focus:ring-accent"
          >
            Go home
          </Link>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
