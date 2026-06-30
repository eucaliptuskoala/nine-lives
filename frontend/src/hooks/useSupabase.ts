import { createElement, createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { createClient } from "@supabase/supabase-js";
import type { Session, User } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";

/**
 * Shared Supabase client. The frontend uses this client for AUTHENTICATION ONLY
 * (login, session management, and obtaining the JWT). All data reads/writes go
 * through the authenticated backend API — never directly against the database.
 */
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

/** Returns the shared Supabase client. */
export function useSupabase() {
  return supabase;
}

interface AuthContextValue {
  /** The currently authenticated user, or null when signed out. */
  user: User | null;
  /** The current Supabase session, or null when signed out. */
  session: Session | null;
  /** True until the initial session lookup has resolved. */
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

/**
 * Provides the current Supabase auth `session` and `user` to the app and keeps
 * them in sync via `supabase.auth.onAuthStateChange`. Wrap the app (or the
 * authenticated subtree) with this provider so the session is shared app-wide.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    // Seed state with any existing session on mount.
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session);
      setLoading(false);
    });

    // Track sign-in / sign-out / token-refresh events for the lifetime of the app.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setLoading(false);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  const value: AuthContextValue = {
    session,
    user: session?.user ?? null,
    loading,
  };

  return createElement(AuthContext.Provider, { value }, children);
}

/**
 * Returns the current auth `{ user, session, loading }`. Must be used within an
 * `AuthProvider`.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
