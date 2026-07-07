import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import InfoIcon from "./InfoIcon";

describe("InfoIcon", () => {
  afterEach(() => {
    cleanup();
  });

  it("calls onToggle on click/tap", () => {
    const onToggle = vi.fn();
    render(
      <InfoIcon
        onToggle={onToggle}
        aria-controls="panel-1"
        label="Toggle info for Pounce"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Toggle info for Pounce" }));

    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("exposes the accessible label via aria-label", () => {
    render(
      <InfoIcon
        onToggle={vi.fn()}
        aria-controls="panel-2"
        label="Toggle info for Bite"
      />,
    );

    const icon = screen.getByRole("button", { name: "Toggle info for Bite" });
    expect(icon).toHaveAttribute("aria-label", "Toggle info for Bite");
  });

  it("sets aria-controls to match the panel id prop", () => {
    render(
      <InfoIcon
        onToggle={vi.fn()}
        aria-controls="panel-3"
        label="Toggle info for Claw"
      />,
    );

    const icon = screen.getByRole("button", { name: "Toggle info for Claw" });
    expect(icon).toHaveAttribute("aria-controls", "panel-3");
  });
});
