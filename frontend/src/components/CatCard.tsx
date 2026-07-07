import { memo, useEffect, useRef } from "react";
import { motion, useAnimationControls } from "framer-motion";
import type { Class } from "../types/game";
import HealthBar from "./HealthBar";
import ManaBar from "./ManaBar";
import { Card } from "@/components/ui/8bit/card";
import type {
  AbilityInfoFields,
  EnemyAbilityListEntry,
  EnemyStatFields,
  PlayerStatFields,
} from "@/lib/battleInfo";
import { useInfoDisclosure } from "@/hooks/useInfoDisclosure";
import { useIsTouchDevice } from "@/hooks/useIsTouchDevice";
import StatInfoPanel from "./StatInfoPanel";
import AbilityInfoPanel from "./AbilityInfoPanel";
import InfoIcon from "./InfoIcon";

interface CatCardProps {
  name: string;
  avatarUrl?: string;
  classType: Class;
  hp: number;
  maxHp: number;
  mana: number;
  maxMana: number;
  isDefending?: boolean;
  shield?: number;
  flip?: boolean;
  /** Requirements 3.1/5.1: enables the avatar Stat_Info_Panel trigger when provided. */
  statPanel?: PlayerStatFields | EnemyStatFields;
  /** Overrides the Stat_Info_Panel's title; defaults to `name`. */
  statPanelTitle?: string;
  /** Requirement 5: enables the Pinned mechanic on the avatar's Stat_Info_Panel. Default false. */
  pinnable?: boolean;
  /** Requirement 4.1/4.2: enables the Enemy_Ability_List when provided (enemy only). */
  abilityList?: EnemyAbilityListEntry[];
  /** Requirement 4.3: keyed by ability id, sourced via `getEnemyAbilityInfoFields`. */
  abilityFieldsById?: Record<string, AbilityInfoFields>;
}

/** `PlayerStatFields` has `dmg`/`lore`; `EnemyStatFields` does not. */
function isPlayerStatFields(
  fields: PlayerStatFields | EnemyStatFields
): fields is PlayerStatFields {
  return "dmg" in fields;
}

/**
 * Requirement 3.1 (player) / 5.1 (enemy): builds the Stat_Info_Panel `rows`
 * in the exact requirement-specified field order.
 */
function buildStatRows(
  fields: PlayerStatFields | EnemyStatFields
): Array<{ label: string; value: string | number }> {
  if (isPlayerStatFields(fields)) {
    return [
      { label: "Damage", value: fields.dmg },
      { label: "Defence", value: fields.defence },
      { label: "Speed", value: fields.spd },
      { label: "Max HP", value: fields.maxHp },
      { label: "Max Mana", value: fields.maxMana },
      { label: "Breed", value: fields.breed },
      { label: "Lore", value: fields.lore },
    ];
  }
  return [
    { label: "Breed", value: fields.breed },
    { label: "Attack", value: fields.atk },
    { label: "Defence", value: fields.defence },
    { label: "Speed", value: fields.spd },
    { label: "Max HP", value: fields.maxHp },
    { label: "Max Mana", value: fields.maxMana },
  ];
}

const classColors: Record<Class, string> = {
  STRENGTH: "text-class-strength",
  AGILITY: "text-class-agility",
  INTELLIGENCE: "text-class-intelligence",
};

interface EnemyAbilityListItemProps {
  entry: EnemyAbilityListEntry;
  fields?: AbilityInfoFields;
}

/**
 * Renders a single Enemy_Ability_List entry plus its hover/focus-driven
 * Ability_Info_Panel and (touch only) Info_Icon.
 *
 * Extracted from the `abilityList.map()` loop so `useInfoDisclosure` and
 * `useIsTouchDevice` can be called once per entry without violating the
 * rules of hooks (Requirements 4, 6). Not pinnable — only the avatar's
 * Stat_Info_Panel supports pinning per the design.
 */
function EnemyAbilityListItem({ entry, fields }: EnemyAbilityListItemProps) {
  const isTouchDevice = useIsTouchDevice();
  const disclosure = useInfoDisclosure({ hoverOutGraceMs: 150 });

  return (
    <li className="relative">
      <span
        tabIndex={0}
        role="button"
        aria-label={`${entry.name} info`}
        className="inline-flex items-center gap-1 text-xs text-text-secondary"
        {...disclosure.triggerProps}
      >
        {entry.name}
        {isTouchDevice && (
          <InfoIcon
            onToggle={disclosure.toggleTouch}
            aria-controls={disclosure.panelId}
            label={`Toggle info for ${entry.name}`}
          />
        )}
      </span>
      {fields && disclosure.isOpen && (
        <AbilityInfoPanel
          id={disclosure.panelId}
          name={entry.name}
          fields={fields}
        />
      )}
    </li>
  );
}

function CatCard({
  name,
  avatarUrl,
  classType,
  hp,
  maxHp,
  mana,
  maxMana,
  isDefending,
  shield,
  flip,
  statPanel,
  statPanelTitle,
  pinnable = false,
  abilityList,
  abilityFieldsById,
}: CatCardProps) {
  // React to HP changes with a short shake + flash so taking damage (or being
  // healed) reads clearly. Purely presentational — no effect on data flow.
  const controls = useAnimationControls();
  const prevHp = useRef(hp);

  // Requirements 3/5/6: the avatar becomes a Stat_Info_Panel trigger only
  // when `statPanel` is provided — omitting it keeps the avatar exactly as
  // before (no interactivity change).
  const statDisclosure = useInfoDisclosure({ pinnable });
  const isTouchDevice = useIsTouchDevice();

  // Requirements 3.3/5.3/5.7: on a Touch_Device, tapping the avatar toggles
  // the panel open/closed (same as any other touch trigger); on a
  // non-Touch_Device, clicking the avatar while its panel is already open
  // pins it instead (Enter/Space already pins via `triggerProps.onKeyDown`).
  const handleAvatarClick = () => {
    if (isTouchDevice) {
      statDisclosure.toggleTouch();
    } else if (pinnable && statDisclosure.isOpen) {
      statDisclosure.pin();
    }
  };

  useEffect(() => {
    const prev = prevHp.current;
    if (hp < prev) {
      controls.start({
        x: [0, -8, 8, -6, 6, -3, 0],
        filter: [
          "brightness(1)",
          "brightness(1.9)",
          "brightness(1)",
        ],
        transition: { duration: 0.45 },
      });
    } else if (hp > prev) {
      controls.start({
        filter: [
          "brightness(1)",
          "brightness(1.4) sepia(0.4) hue-rotate(60deg)",
          "brightness(1)",
        ],
        transition: { duration: 0.5 },
      });
    }
    prevHp.current = hp;
  }, [hp, controls]);

  return (
    <motion.div animate={controls}>
      <Card
        font="normal"
        className="bg-panel/60 border-border-ui text-text-primary overflow-visible"
      >
        <div
          className={`flex items-center gap-4 p-4 ${
            flip ? "flex-row-reverse" : ""
          }`}
        >
          <div className="relative shrink-0">
            <div
              className="w-20 h-20 rounded-full bg-elevated flex items-center justify-center text-3xl shrink-0 border-2 border-border-ui overflow-hidden"
              {...(statPanel
                ? {
                    tabIndex: 0,
                    role: "button",
                    "aria-label": `${name} stats`,
                    ...statDisclosure.triggerProps,
                    onClick: handleAvatarClick,
                  }
                : !avatarUrl
                  ? { role: "img", "aria-label": `${name} avatar` }
                  : {})}
            >
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt={`${name} avatar`}
                  className="w-full h-full object-cover"
                />
              ) : (
                <span aria-hidden="true">{"\uD83D\uDC31"}</span>
              )}
            </div>
            {statPanel && statDisclosure.isOpen && (
              <div className="absolute z-10 top-full mt-1 left-0 min-w-max">
                <StatInfoPanel
                  id={statDisclosure.panelId}
                  title={statPanelTitle ?? name}
                  rows={buildStatRows(statPanel)}
                  isPinned={statDisclosure.isPinned}
                  onClose={statDisclosure.unpinAndClose}
                />
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className={`flex items-center gap-2 mb-1 ${
                flip ? "justify-end" : ""
              }`}
            >
              <span className="font-semibold text-text-primary truncate">{name}</span>
              <span className={`text-xs font-medium ${classColors[classType]}`}>
                {classType}
              </span>
            </div>
            <div className="space-y-1.5">
              <HealthBar current={hp} max={maxHp} />
              <ManaBar current={mana} max={maxMana} />
            </div>
            <div className={`flex gap-2 mt-1 ${flip ? "justify-end" : ""}`}>
              {isDefending && (
                <span className="text-xs text-defend font-medium">
                  {"\uD83D\uDEE1\uFE0F"} Defending
                </span>
              )}
              {shield !== undefined && shield > 0 && (
                <span className="text-xs text-shield font-medium">
                  {"\uD83D\uDEE1\uFE0F"} Shield {shield}
                </span>
              )}
            </div>
            {abilityList && abilityList.length > 0 && (
              <ul
                className={`flex flex-wrap gap-x-2 gap-y-1 mt-1.5 ${
                  flip ? "justify-end" : ""
                }`}
              >
                {abilityList.map((entry) => (
                  <EnemyAbilityListItem
                    key={entry.id}
                    entry={entry}
                    fields={abilityFieldsById?.[entry.id]}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

export default memo(CatCard);
