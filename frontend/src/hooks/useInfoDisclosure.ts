/**
 * Shared hover/focus/touch/pin disclosure state machine backing Requirements
 * 2, 3, 4, 5, and 6 of the battle-info-tooltips feature.
 *
 * This module exports the standalone, React-decoupled `DisclosureState`/
 * `Action` types and the pure `reduce`/`isOpen` functions so they can be
 * exercised directly by property-based tests, as well as the
 * `useInfoDisclosure(options)` React hook that wraps this reducer with
 * React state for use by triggers/panels.
 */

import { useCallback, useEffect, useId, useReducer, useRef } from "react";
import type { KeyboardEvent } from "react";

export type DisclosureState = {
  hovering: boolean;
  focused: boolean;
  touchOpen: boolean;
  pinned: boolean;
};

/**
 * `isOpen` is always the disjunction of the four flags — this single line
 * of logic is the entire shared contract that Requirements 2.1/2.2,
 * 3.1/3.2, 4.3, 5.1/5.2, and 6.1/6.2 all reduce to.
 */
export function isOpen(s: DisclosureState): boolean {
  return s.pinned || s.hovering || s.focused || s.touchOpen;
}

export type Action =
  | { type: "HOVER_ENTER" }
  | { type: "HOVER_LEAVE_CONFIRMED" } // dispatched immediately, or after the grace timer
  | { type: "FOCUS_IN" }
  | { type: "FOCUS_OUT" }
  | { type: "TOUCH_TOGGLE" }
  | { type: "PIN" }
  | { type: "UNPIN_AND_CLOSE" };

export function reduce(s: DisclosureState, a: Action): DisclosureState {
  switch (a.type) {
    case "HOVER_ENTER":
      return { ...s, hovering: true };
    case "HOVER_LEAVE_CONFIRMED":
      return { ...s, hovering: false };
    case "FOCUS_IN":
      return { ...s, focused: true };
    case "FOCUS_OUT":
      return { ...s, focused: false };
    case "TOUCH_TOGGLE":
      return { ...s, touchOpen: !s.touchOpen };
    case "PIN":
      return { ...s, pinned: true };
    case "UNPIN_AND_CLOSE":
      return { pinned: false, hovering: false, focused: false, touchOpen: false };
  }
}

const INITIAL_STATE: DisclosureState = {
  hovering: false,
  focused: false,
  touchOpen: false,
  pinned: false,
};

export interface UseInfoDisclosureOptions {
  /** Enables the Pinned mechanic (Requirement 5). Default: false. */
  pinnable?: boolean;
  /** Grace window (ms) after a pointer leaves before the panel actually
   *  closes; a re-entry within the window cancels the close. Used only by
   *  the Enemy_Ability_List (Requirement 4.4/4.5). Default: 0. */
  hoverOutGraceMs?: number;
  /** When true, all triggers are no-ops (Requirement 2.9 — disabled ability
   *  buttons must not change visibility). Default: false. */
  disabled?: boolean;
}

export interface UseInfoDisclosureResult {
  /** True iff the panel should be visible right now. */
  isOpen: boolean;
  /** True iff the panel is in the Pinned state (Requirement 5). */
  isPinned: boolean;
  /** Spread onto the trigger element (button/avatar/list entry). */
  triggerProps: {
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    onFocus: () => void;
    onBlur: () => void;
    onKeyDown: (e: KeyboardEvent) => void; // Enter/Space -> pin, when pinnable
    "aria-describedby": string | undefined; // only set once panelId is known & open
  };
  /** Call from an Info_Icon or a touch-tap on the trigger itself. */
  toggleTouch: () => void;
  /** Call from a click on the trigger itself when `pinnable`, e.g. a
   *  non-Touch_Device click on an already-open trigger (Requirement 5.3). */
  pin: () => void;
  /** Call from the Pinned panel's close control. */
  unpinAndClose: () => void;
  /** Stable id to assign to the panel element and reference via
   *  `aria-describedby` (Requirement 6.3). */
  panelId: string;
}

/**
 * Wraps the standalone `reduce`/`isOpen` state machine with React state,
 * plus the two pieces of behavior that need real timers/DOM wiring:
 * a hover-out grace window and a `disabled` short-circuit.
 *
 * @see design.md "useInfoDisclosure" — Requirements 2.9, 4.4, 4.5, 4.6, 5.3,
 * 5.4, 5.6, 6.3, 6.4
 */
export function useInfoDisclosure(
  options?: UseInfoDisclosureOptions,
): UseInfoDisclosureResult {
  const { pinnable = false, hoverOutGraceMs = 0, disabled = false } = options ?? {};

  const [state, dispatch] = useReducer(reduce, INITIAL_STATE);
  const leaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const panelId = useId();

  // Clear any pending grace-window timeout on unmount so it never fires
  // (and dispatches) after the component is gone.
  useEffect(() => {
    return () => {
      if (leaveTimeoutRef.current !== null) {
        clearTimeout(leaveTimeoutRef.current);
      }
    };
  }, []);

  const clearPendingLeave = useCallback(() => {
    if (leaveTimeoutRef.current !== null) {
      clearTimeout(leaveTimeoutRef.current);
      leaveTimeoutRef.current = null;
    }
  }, []);

  const handleMouseEnter = useCallback(() => {
    if (disabled) return;
    clearPendingLeave();
    dispatch({ type: "HOVER_ENTER" });
  }, [disabled, clearPendingLeave]);

  const handleMouseLeave = useCallback(() => {
    if (disabled) return;
    if (hoverOutGraceMs > 0) {
      clearPendingLeave();
      leaveTimeoutRef.current = setTimeout(() => {
        leaveTimeoutRef.current = null;
        dispatch({ type: "HOVER_LEAVE_CONFIRMED" });
      }, hoverOutGraceMs);
    } else {
      dispatch({ type: "HOVER_LEAVE_CONFIRMED" });
    }
  }, [disabled, hoverOutGraceMs, clearPendingLeave]);

  const handleFocus = useCallback(() => {
    if (disabled) return;
    dispatch({ type: "FOCUS_IN" });
  }, [disabled]);

  const handleBlur = useCallback(() => {
    if (disabled) return;
    dispatch({ type: "FOCUS_OUT" });
  }, [disabled]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (disabled || !pinnable) return;
      if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
        dispatch({ type: "PIN" });
      }
    },
    [disabled, pinnable],
  );

  const toggleTouch = useCallback(() => {
    if (disabled) return;
    dispatch({ type: "TOUCH_TOGGLE" });
  }, [disabled]);

  const pin = useCallback(() => {
    if (disabled || !pinnable) return;
    dispatch({ type: "PIN" });
  }, [disabled, pinnable]);

  const unpinAndClose = useCallback(() => {
    if (disabled) return;
    clearPendingLeave();
    dispatch({ type: "UNPIN_AND_CLOSE" });
  }, [disabled, clearPendingLeave]);

  const open = isOpen(state);

  return {
    isOpen: open,
    isPinned: state.pinned,
    triggerProps: {
      onMouseEnter: handleMouseEnter,
      onMouseLeave: handleMouseLeave,
      onFocus: handleFocus,
      onBlur: handleBlur,
      onKeyDown: handleKeyDown,
      "aria-describedby": open ? panelId : undefined,
    },
    toggleTouch,
    pin,
    unpinAndClose,
    panelId,
  };
}
