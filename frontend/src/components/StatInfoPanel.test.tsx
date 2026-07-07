import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import StatInfoPanel from "./StatInfoPanel";

const rows = [
  { label: "HP", value: 80 },
  { label: "ATK", value: "12" },
  { label: "DEF", value: 5 },
];

describe("StatInfoPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the title and all rows in the order passed in", () => {
    render(<StatInfoPanel id="panel-1" title="Sir Pounce" rows={rows} />);

    expect(screen.getByText("Sir Pounce")).toBeInTheDocument();

    const labels = screen.getAllByRole("term").map((el) => el.textContent);
    const values = screen.getAllByRole("definition").map((el) => el.textContent);

    expect(labels).toEqual(["HP", "ATK", "DEF"]);
    expect(values).toEqual(["80", "12", "5"]);
  });

  it("does not render a close control when isPinned is omitted", () => {
    render(<StatInfoPanel id="panel-1" title="Sir Pounce" rows={rows} />);

    expect(screen.queryByRole("button", { name: /close/i })).toBeNull();
  });

  it("does not render a close control when isPinned is false", () => {
    render(
      <StatInfoPanel id="panel-1" title="Sir Pounce" rows={rows} isPinned={false} />,
    );

    expect(screen.queryByRole("button", { name: /close/i })).toBeNull();
  });

  it("renders a close control when isPinned is true and calls onClose when activated", () => {
    const onClose = vi.fn();
    render(
      <StatInfoPanel
        id="panel-1"
        title="Sir Pounce"
        rows={rows}
        isPinned
        onClose={onClose}
      />,
    );

    const closeButton = screen.getByRole("button", { name: /close/i });
    expect(closeButton).toBeInTheDocument();

    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("applies the id prop to the root element", () => {
    render(<StatInfoPanel id="panel-1" title="Sir Pounce" rows={rows} />);

    expect(screen.getByRole("tooltip")).toHaveAttribute("id", "panel-1");
  });
});
