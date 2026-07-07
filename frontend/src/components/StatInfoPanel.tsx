import { cn } from "@/lib/utils";

interface StatInfoPanelProps {
  id: string;
  title: string; // e.g. cat name or enemy name
  rows: Array<{ label: string; value: string | number }>;
  isPinned?: boolean;
  onClose?: () => void; // rendered as a close control iff isPinned
  className?: string;
}

// Presentational tooltip-style panel shared by the player Stat_Info_Panel
// (Requirement 3) and the enemy Stat_Info_Panel (Requirement 5). Renders
// `rows` in the exact order passed in — the caller (CatCard) is responsible
// for field ordering per the requirement-specified field lists. The close
// control (Requirement 5.10) is only ever rendered when `isPinned` is true,
// so non-pinnable panels (e.g. the player's own stat panel) never show one.
function StatInfoPanel({
  id,
  title,
  rows,
  isPinned,
  onClose,
  className,
}: StatInfoPanelProps) {
  return (
    <div
      id={id}
      role="tooltip"
      className={cn(
        "bg-panel border-2 border-border-ui text-text-primary text-xs p-3 rounded-none shadow-lg",
        className
      )}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="font-semibold text-text-primary">{title}</span>
        {isPinned && (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-text-secondary hover:text-text-primary leading-none px-1"
          >
            {"\u2715"}
          </button>
        )}
      </div>
      <dl className="space-y-0.5">
        {rows.map((row) => (
          <div key={row.label} className="flex justify-between gap-3">
            <dt className="text-text-secondary">{row.label}</dt>
            <dd className="font-medium">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default StatInfoPanel;
