import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act, cleanup } from "@testing-library/react";
import fc from "fast-check";

import { reduce, isOpen, useInfoDisclosure } from "./useInfoDisclosure";
import type { DisclosureState, Action } from "./useInfoDisclosure";

const INITIAL_STATE: DisclosureState = {
  hovering: false,
  focused: false,
  touchOpen: false,
  pinned: false,
};

/** Reusable arbitrary generating any single `Action` from the disclosure state machine. */
const actionArb: fc.Arbitrary<Action> = fc.constantFrom<Action>(
  { type: "HOVER_ENTER" },
  { type: "HOVER_LEAVE_CONFIRMED" },
  { type: "FOCUS_IN" },
  { type: "FOCUS_OUT" },
  { type: "TOUCH_TOGGLE" },
  { type: "PIN" },
  { type: "UNPIN_AND_CLOSE" },
);

/** Reusable arbitrary generating a sequence of `Action`s. */
const actionSequenceArb: fc.Arbitrary<Action[]> = fc.array(actionArb, { minLength: 0, maxLength: 50 });

describe("useInfoDisclosure reducer", () => {
  // Feature: battle-info-tooltips, Property 3: Disclosure visibility is exactly hovering-or-focused-or-touchOpen-or-pinned
  // Validates: Requirements 2.1, 2.2, 3.1, 3.2, 3.3, 4.3, 5.1, 5.2, 5.5, 5.7, 6.1, 6.2
  it("isOpen always equals pinned || hovering || focused || touchOpen after every action in any sequence", () => {
    fc.assert(
      fc.property(actionSequenceArb, (actions) => {
        let state = INITIAL_STATE;

        for (const action of actions) {
          state = reduce(state, action);

          const expectedOpen = state.pinned || state.hovering || state.focused || state.touchOpen;
          expect(isOpen(state)).toBe(expectedOpen);

          // Once pinned, isOpen must remain true regardless of subsequent
          // HOVER_LEAVE_CONFIRMED/FOCUS_OUT effects on the other flags.
          if (state.pinned) {
            expect(isOpen(state)).toBe(true);
          }
        }
      }),
      { numRuns: 100 },
    );
  });
});

/** Reusable arbitrary generating any `DisclosureState` with all four flags arbitrary. */
const disclosureStateArb: fc.Arbitrary<DisclosureState> = fc.record({
  hovering: fc.boolean(),
  focused: fc.boolean(),
  touchOpen: fc.boolean(),
  pinned: fc.boolean(),
});

describe("useInfoDisclosure reducer - TOUCH_TOGGLE", () => {
  // Feature: battle-info-tooltips, Property 4: Touch toggle is self-inverse
  // Validates: Requirements 2.4, 3.3, 4.8, 5.7
  it("a single TOUCH_TOGGLE always flips touchOpen and leaves the other flags unchanged", () => {
    fc.assert(
      fc.property(disclosureStateArb, (state) => {
        const toggled = reduce(state, { type: "TOUCH_TOGGLE" });

        expect(toggled.touchOpen).toBe(!state.touchOpen);
        expect(toggled.hovering).toBe(state.hovering);
        expect(toggled.focused).toBe(state.focused);
        expect(toggled.pinned).toBe(state.pinned);
      }),
      { numRuns: 100 },
    );
  });

  // Feature: battle-info-tooltips, Property 4: Touch toggle is self-inverse
  // Validates: Requirements 2.4, 3.3, 4.8, 5.7
  it("two consecutive TOUCH_TOGGLE actions with nothing in between return touchOpen to its original value", () => {
    fc.assert(
      fc.property(disclosureStateArb, (state) => {
        const toggledOnce = reduce(state, { type: "TOUCH_TOGGLE" });
        const toggledTwice = reduce(toggledOnce, { type: "TOUCH_TOGGLE" });

        expect(toggledTwice.touchOpen).toBe(state.touchOpen);
        expect(toggledTwice.hovering).toBe(state.hovering);
        expect(toggledTwice.focused).toBe(state.focused);
        expect(toggledTwice.pinned).toBe(state.pinned);
      }),
      { numRuns: 100 },
    );
  });
});

describe("useInfoDisclosure - hover-out grace window", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  // Feature: battle-info-tooltips, Property 5: Hover-out grace window
  // Validates: Requirements 4.4, 4.5, 4.6
  //
  // numRuns is intentionally lower than the suite's usual 100 (rather than
  // fast-check's default) because each run renders a real hook via RTL and
  // steps fake timers, which is far more expensive per-iteration than the
  // pure-function properties above; 30 runs still covers the gap/graceMs
  // input space well given the small number of interesting boundary cases
  // (gap < grace, gap == grace, gap > grace).
  it("never observes a closed panel for a sub-grace-window gap, and reliably closes+reopens for a gap >= grace", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 500 }), // hoverOutGraceMs
        fc.integer({ min: 0, max: 1000 }), // leave/re-entry gap in ms
        (hoverOutGraceMs, gap) => {
          vi.useFakeTimers();
          try {
            const { result, unmount } = renderHook(() =>
              useInfoDisclosure({ hoverOutGraceMs }),
            );

            // Open via hover.
            act(() => {
              result.current.triggerProps.onMouseEnter();
            });
            expect(result.current.isOpen).toBe(true);

            // Leave — schedules the grace-window timeout rather than
            // closing immediately.
            act(() => {
              result.current.triggerProps.onMouseLeave();
            });

            if (gap < hoverOutGraceMs) {
              // Advance only partway through the grace window: the panel
              // must never be observed closed during the gap.
              act(() => {
                vi.advanceTimersByTime(gap);
              });
              expect(result.current.isOpen).toBe(true);

              // Re-entry within the window cancels the pending close
              // entirely — still open, and remains open after the
              // original timeout would have fired.
              act(() => {
                result.current.triggerProps.onMouseEnter();
              });
              expect(result.current.isOpen).toBe(true);

              act(() => {
                vi.advanceTimersByTime(hoverOutGraceMs);
              });
              expect(result.current.isOpen).toBe(true);
            } else {
              // Advance past (or exactly to) the grace window: the
              // originally-scheduled close must fire.
              act(() => {
                vi.advanceTimersByTime(gap);
              });
              expect(result.current.isOpen).toBe(false);

              // Re-entry after the window is a fresh hover.
              act(() => {
                result.current.triggerProps.onMouseEnter();
              });
              expect(result.current.isOpen).toBe(true);
            }

            unmount();
          } finally {
            vi.useRealTimers();
          }
        },
      ),
      { numRuns: 30 },
    );
  });
});

/** The set of trigger calls exercised against a disabled `useInfoDisclosure`
 *  instance: hover in/out, focus in/out, pin attempts via Enter/Space on
 *  `onKeyDown`, the touch toggle, and the pinned-panel close control. */
type TriggerCall =
  | "mouseEnter"
  | "mouseLeave"
  | "focus"
  | "blur"
  | "keyDownEnter"
  | "keyDownSpace"
  | "toggleTouch"
  | "unpinAndClose";

const triggerCallArb: fc.Arbitrary<TriggerCall> = fc.constantFrom<TriggerCall>(
  "mouseEnter",
  "mouseLeave",
  "focus",
  "blur",
  "keyDownEnter",
  "keyDownSpace",
  "toggleTouch",
  "unpinAndClose",
);

const triggerCallSequenceArb: fc.Arbitrary<TriggerCall[]> = fc.array(triggerCallArb, {
  minLength: 0,
  maxLength: 50,
});

describe("useInfoDisclosure - disabled no-op", () => {
  afterEach(() => {
    cleanup();
  });

  // Feature: battle-info-tooltips, Property 11: A disabled disclosure is a total no-op
  // Validates: Requirements 2.9
  //
  // numRuns is intentionally lower than the suite's usual 100 (rather than
  // fast-check's default) for the same reason as the hover-out grace window
  // property above: each run renders a real hook via RTL, which is more
  // expensive per-iteration than the pure-function properties; 30 runs
  // still covers the trigger-call sequence space well given there are only
  // 8 distinct call types and no timer-dependent branching to explore.
  it("isOpen and isPinned remain false after every trigger call in any sequence, even with pinnable: true", () => {
    fc.assert(
      fc.property(triggerCallSequenceArb, (calls) => {
        const { result, unmount } = renderHook(() =>
          useInfoDisclosure({ disabled: true, pinnable: true }),
        );

        try {
          // The hook exposes no ability-submission callback itself — that
          // wiring lives one layer up in the consuming component — so the
          // "no ability-submission callback invoked" half of Property 11
          // reduces, at this hook's boundary, to isOpen/isPinned never
          // changing away from their initial false values regardless of
          // what the disabled trigger handlers are called with.
          expect(result.current.isOpen).toBe(false);
          expect(result.current.isPinned).toBe(false);

          for (const call of calls) {
            act(() => {
              switch (call) {
                case "mouseEnter":
                  result.current.triggerProps.onMouseEnter();
                  break;
                case "mouseLeave":
                  result.current.triggerProps.onMouseLeave();
                  break;
                case "focus":
                  result.current.triggerProps.onFocus();
                  break;
                case "blur":
                  result.current.triggerProps.onBlur();
                  break;
                case "keyDownEnter":
                  result.current.triggerProps.onKeyDown({
                    key: "Enter",
                  } as unknown as Parameters<
                    typeof result.current.triggerProps.onKeyDown
                  >[0]);
                  break;
                case "keyDownSpace":
                  result.current.triggerProps.onKeyDown({
                    key: " ",
                  } as unknown as Parameters<
                    typeof result.current.triggerProps.onKeyDown
                  >[0]);
                  break;
                case "toggleTouch":
                  result.current.toggleTouch();
                  break;
                case "unpinAndClose":
                  result.current.unpinAndClose();
                  break;
              }
            });

            expect(result.current.isOpen).toBe(false);
            expect(result.current.isPinned).toBe(false);
          }
        } finally {
          unmount();
        }
      }),
      { numRuns: 30 },
    );
  });
});

describe("useInfoDisclosure reducer - PIN", () => {
  // Feature: battle-info-tooltips, Property 12: Pinning always opens and marks pinned, from any reachable state
  // Validates: Requirements 5.3, 5.4, 6.4
  it("dispatching PIN always results in pinned === true and isOpen === true, regardless of prior state", () => {
    fc.assert(
      fc.property(disclosureStateArb, (state) => {
        const result = reduce(state, { type: "PIN" });

        expect(result.pinned).toBe(true);
        expect(isOpen(result)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });
});

describe("useInfoDisclosure reducer - UNPIN_AND_CLOSE", () => {
  // Feature: battle-info-tooltips, Property 13: Unpin-and-close always fully resets, from any reachable state
  // Validates: Requirements 5.6
  it("dispatching UNPIN_AND_CLOSE always resets all four flags to false and isOpen to false, regardless of prior state", () => {
    fc.assert(
      fc.property(disclosureStateArb, (state) => {
        const result = reduce(state, { type: "UNPIN_AND_CLOSE" });

        expect(result.pinned).toBe(false);
        expect(result.hovering).toBe(false);
        expect(result.focused).toBe(false);
        expect(result.touchOpen).toBe(false);
        expect(isOpen(result)).toBe(false);
      }),
      { numRuns: 100 },
    );
  });
});
