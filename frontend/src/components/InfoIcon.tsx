interface InfoIconProps {
  /** Calls `useInfoDisclosure().toggleTouch` on activation. */
  onToggle: () => void;
  /** Id of the panel this icon controls (matches `useInfoDisclosure().panelId`). */
  "aria-controls": string;
  /** Accessible name, e.g. "Toggle info for Pounce". */
  label: string;
}

/**
 * Small "ⓘ" tap target rendered only on a Touch_Device (the parent decides
 * this via `useIsTouchDevice()`). Always a sibling of its associated trigger
 * element (e.g. an ability button or an avatar) — never nested inside it —
 * so a single tap can only ever land on one DOM element.
 *
 * Rendered as a native `<button>` so click and keyboard activation (Enter/
 * Space) and the accessible `button` role all come for free.
 */
function InfoIcon({ onToggle, "aria-controls": ariaControls, label }: InfoIconProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-controls={ariaControls}
      aria-label={label}
      className="inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-text-secondary/20 text-[11px] leading-none text-text-primary hover:bg-text-secondary/30"
    >
      {"\u24D8"}
    </button>
  );
}

export default InfoIcon;
