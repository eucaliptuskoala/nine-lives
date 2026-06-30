// @vitest-environment node
import { describe, it, expect, vi, beforeEach } from "vitest";

// Control the Supabase sign-out call.
const signOut = vi.fn();
vi.mock("../hooks/useSupabase", () => ({
  supabase: { auth: { signOut: () => signOut() } },
}));

import { signOutAndRedirect } from "./AppHeader";

describe("signOutAndRedirect", () => {
  beforeEach(() => {
    signOut.mockReset();
    signOut.mockResolvedValue({ error: null });
  });

  it("calls supabase.auth.signOut() before redirecting", async () => {
    const navigate = vi.fn();

    await signOutAndRedirect(navigate);

    expect(signOut).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith("/login", { replace: true });
  });

  it("waits for sign-out to resolve before navigating", async () => {
    const order: string[] = [];
    signOut.mockImplementation(async () => {
      order.push("signOut");
      return { error: null };
    });
    const navigate = vi.fn(() => {
      order.push("navigate");
    });

    await signOutAndRedirect(navigate);

    expect(order).toEqual(["signOut", "navigate"]);
  });
});
