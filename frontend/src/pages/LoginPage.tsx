import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/8bit/button";
import { Input } from "@/components/ui/8bit/input";
import { supabase, useAuth } from "../hooks/useSupabase";

type AuthMode = "signin" | "signup";

/** Shape of the location state set by AuthGuard when redirecting here. */
interface LocationState {
  from?: string;
}

/**
 * Public login / sign-up page. On success redirects to the page the user
 * originally tried to reach (via location.state.from), defaulting to `/`.
 */
function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, loading: authLoading } = useAuth();

  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const redirectTo = (location.state as LocationState | null)?.from ?? "/";

  useEffect(() => {
    if (!authLoading && user) {
      navigate(redirectTo, { replace: true });
    }
  }, [authLoading, user, navigate, redirectTo]);

  function toggleMode() {
    setMode((prev) => (prev === "signin" ? "signup" : "signin"));
    setError(null);
    setInfo(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setInfo(null);
    setSubmitting(true);

    try {
      if (mode === "signup") {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email,
          password,
        });
        if (signUpError) {
          setError(signUpError.message);
          return;
        }
        if (data.user && !data.session) {
          setInfo(
            "Check your email to confirm your account, then sign in.",
          );
          setMode("signin");
          return;
        }
      } else {
        const { error: signInError } =
          await supabase.auth.signInWithPassword({ email, password });
        if (signInError) {
          setError(signInError.message);
          return;
        }
        // Successful sign-in triggers the auth listener redirect above.
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const isSignup = mode === "signup";

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-6 px-4">
      <div className="w-full max-w-sm flex flex-col gap-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="retro text-2xl font-bold">Nine Lives</h1>
          <p className="text-text-secondary">
            {isSignup ? "Create an account to get started." : "Sign in to continue."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <label className="flex flex-col gap-2 text-sm font-medium">
            Email
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              font="normal"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm font-medium">
            Password
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={isSignup ? "new-password" : "current-password"}
              font="normal"
            />
          </label>

          {error && (
            <p role="alert" className="text-sm text-hp">
              {error}
            </p>
          )}
          {info && (
            <p role="status" className="text-sm text-ability">
              {info}
            </p>
          )}

          <Button
            type="submit"
            disabled={submitting}
            className="mt-2 h-auto bg-accent hover:bg-accent/90 px-4 py-2 text-[10px] text-app"
          >
            {submitting
              ? isSignup
                ? "Creating account..."
                : "Signing in..."
              : isSignup
                ? "Sign up"
                : "Sign in"}
          </Button>
        </form>

        <p className="text-center text-sm text-text-secondary">
          {isSignup ? "Already have an account?" : "Don't have an account?"}{" "}
          <Button
            type="button"
            variant="link"
            onClick={toggleMode}
            className="h-auto p-0 align-baseline font-medium text-accent hover:text-accent/80 hover:underline"
          >
            {isSignup ? "Sign in" : "Sign up"}
          </Button>
        </p>
      </div>
    </div>
  );
}

export default LoginPage;
