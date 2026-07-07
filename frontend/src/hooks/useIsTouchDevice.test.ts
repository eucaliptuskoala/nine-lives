import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act, cleanup } from "@testing-library/react";

import { useIsTouchDevice } from "./useIsTouchDevice";

/**
 * A minimal mock of the `MediaQueryList` returned by `window.matchMedia`,
 * supporting exactly the surface `useMediaQuery` relies on: `matches` and
 * `addEventListener`/`removeEventListener` for the `"change"` event.
 */
class MockMediaQueryList {
  matches: boolean;
  media: string;
  private listeners = new Set<(event: { matches: boolean }) => void>();

  constructor(media: string, matches: boolean) {
    this.media = media;
    this.matches = matches;
  }

  addEventListener = vi.fn((type: string, listener: (event: { matches: boolean }) => void) => {
    if (type === "change") this.listeners.add(listener);
  });

  removeEventListener = vi.fn((type: string, listener: (event: { matches: boolean }) => void) => {
    if (type === "change") this.listeners.delete(listener);
  });

  /** Simulates the browser firing a `"change"` event after the query result flips. */
  simulateChange(matches: boolean) {
    this.matches = matches;
    for (const listener of this.listeners) {
      listener({ matches });
    }
  }
}

function stubMatchMedia(initialMatches: boolean) {
  const mql = new MockMediaQueryList("(hover: none)", initialMatches);
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue(mql),
  );
  return mql;
}

describe("useIsTouchDevice", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("returns false when the (hover: none) media query does not match", () => {
    stubMatchMedia(false);

    const { result } = renderHook(() => useIsTouchDevice());

    expect(result.current).toBe(false);
  });

  it("returns true when the (hover: none) media query matches", () => {
    stubMatchMedia(true);

    const { result } = renderHook(() => useIsTouchDevice());

    expect(result.current).toBe(true);
  });

  it("re-evaluates when the media query result changes", () => {
    const mql = stubMatchMedia(false);

    const { result } = renderHook(() => useIsTouchDevice());

    expect(result.current).toBe(false);

    act(() => {
      mql.simulateChange(true);
    });

    expect(result.current).toBe(true);

    act(() => {
      mql.simulateChange(false);
    });

    expect(result.current).toBe(false);
  });
});
