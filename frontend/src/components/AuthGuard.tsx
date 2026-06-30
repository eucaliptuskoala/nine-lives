import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useSupabase";
import AppHeader from "./AppHeader";

/**
 * Wraps protected routes and ensures the user has a valid authenticated
 * session before rendering them.
 *
 * While the initial session lookup is in flight (`loading`), nothing is
 * rendered to avoid a flash of content or an incorrect redirect before the
 * session resolves. Once loading completes, unauthenticated users are
 * redirected to `/login`, preserving the originally requested path in
 * `location.state.from` so `LoginPage` can send them back after sign-in.
 *
 * Implements Requirement 25 (Authentication): verifies a valid auth token for
 * the Digitize, Battle, and Memorial pages (25.1–25.3) and redirects to the
 * login page when the session is missing or expired (25.4).
 */
function AuthGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // Wait for the session lookup to resolve before deciding what to render.
  if (loading) {
    return null;
  }

  // No authenticated session — send the user to login, remembering where they
  // were trying to go so they can be returned there afterwards.
  if (!user) {
    return (
      <Navigate to="/login" replace state={{ from: location.pathname }} />
    );
  }

  return (
    <>
      <AppHeader />
      {children}
    </>
  );
}

export default AuthGuard;
