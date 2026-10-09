// A little person drawn entirely in HTML/CSS (no images, no SVG).
// Everyone wears Yale navy/blue; each role adds its own props.
import type { CSSProperties } from "react";
import type { Role } from "../types";
import type { AgentStatus } from "../teamState";

type Who = Role | "human";

const LOOK: Record<Who, { skin: string; hair: string }> = {
  boss: { skin: "#e0ac69", hair: "#8e8e8e" },
  inventory: { skin: "#8d5524", hair: "#1f140c" },
  accounting: { skin: "#f1c27d", hair: "#6b3e1f" },
  facilities: { skin: "#c68642", hair: "#2b1a0f" },
  customer_service: { skin: "#ffdbac", hair: "#b5651d" },
  human: { skin: "#f1c27d", hair: "#4a2c17" },
};

export function AgentFigure({ who, status = "idle", size = 1 }: { who: Who; status?: AgentStatus; size?: number }) {
  const { skin, hair } = LOOK[who];
  return (
    <div
      className={`fig fig-${who} fig-${status}`}
      style={{ "--skin": skin, "--hair": hair, "--s": size } as CSSProperties}
      aria-hidden="true"
    >
      <div className="fig-inner">
        <div className="fig-shadow" />
        <div className="fig-leg fig-leg-l" />
        <div className="fig-leg fig-leg-r" />
        <div className="fig-arm fig-arm-l" />
        <div className="fig-arm fig-arm-r" />
        <div className="fig-body">
          <span className="fig-y">Y</span>
        </div>
        <div className="fig-neck" />
        <div className="fig-head">
          <div className="fig-eye fig-eye-l" />
          <div className="fig-eye fig-eye-r" />
          <div className="fig-mouth" />
        </div>
        <div className="fig-hair" />

        {who === "boss" && (<><div className="acc-shirt" /><div className="acc-tie" /><div className="acc-pocket" /></>)}
        {who === "inventory" && (<><div className="acc-cap"><span>Y</span></div><div className="acc-brim" /><div className="acc-strings" /><div className="acc-box" /></>)}
        {who === "accounting" && (<><div className="acc-visor" /><div className="acc-glasses" /><div className="acc-collar" /><div className="acc-calc" /></>)}
        {who === "facilities" && (<><div className="acc-hardhat"><span>Y</span></div><div className="acc-hatbrim" /><div className="acc-belt" /><div className="acc-pouch" /><div className="acc-wrench" /></>)}
        {who === "customer_service" && (<><div className="acc-headband" /><div className="acc-ear" /><div className="acc-mic" /><div className="acc-polo" /><div className="acc-tag">HI!</div></>)}
        {who === "human" && (<><div className="acc-hood" /><div className="acc-yale">YALE</div></>)}

        {status === "done" && <div className="fig-badge">✓</div>}
        {status === "failed" && <div className="fig-badge fig-badge-bad">!</div>}
      </div>
    </div>
  );
}
