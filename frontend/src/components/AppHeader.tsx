import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import type { NavigateFunction } from "react-router-dom";
import { supabase } from "../hooks/useSupabase";

/**
 * Signs the user out and redirects to the login page.
 *
 * Calls `supabase.auth.signOut()` — which triggers the app's
 * `onAuthStateChange` listener (see `AuthProvider`) to clear the session/user
 * state, causing `AuthGuard` to treat the user as unauthenticated. The explicit
 * `navigate("/login")` provides an immediate redirect rather than waiting for
 * the listener-driven re-render.
 *
 * Implements Requirement 25.4 (redirect to login when the session ends).
 */
export async function signOutAndRedirect(navigate: NavigateFunction): Promise<void> {
  await supabase.auth.signOut();
  navigate("/login", { replace: true });
}

/**
 * Shared header shown on authenticated pages. Provides a sign-out control.
 *
 * Rendered inside `AuthGuard`, so it appears on the Digitize, Battle, and
 * Memorial pages but never on the unguarded `/login` page.
 */
function AppHeader() {
  const navigate = useNavigate();

  const handleSignOut = useCallback(() => {
    void signOutAndRedirect(navigate);
  }, [navigate]);

  return (
    <header className="fixed top-0 right-0 z-50 p-3">
      <button
        type="button"
        onClick={handleSignOut}
        className="rounded-md bg-gray-800/80 px-3 py-1.5 text-sm font-medium text-white shadow-sm backdrop-blur-sm transition-colors hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-400"
      >
        Sign out
      </button>
    </header>
  );
}

export default AppHeader;
