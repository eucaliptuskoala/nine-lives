import { useMediaQuery } from "@base-ui/react/unstable-use-media-query";

/**
 * Detects whether the client is a Touch_Device — a client whose primary
 * pointer input does not support hover, per the `(hover: none)` media query.
 *
 * @see design.md "useIsTouchDevice" — Requirements 2.3, 4.7
 */
export function useIsTouchDevice(): boolean {
  return useMediaQuery("(hover: none)", { defaultMatches: false, noSsr: true });
}
