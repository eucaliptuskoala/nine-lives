import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";

// Import via the "@/" alias to also verify alias resolution under vitest.
import { Button } from "@/components/ui/8bit/button";

afterEach(() => cleanup());

describe("8bitcn Button", () => {
  it("renders its children as an accessible button", () => {
    render(<Button>Attack</Button>);
    expect(
      screen.getByRole("button", { name: "Attack" })
    ).toBeInTheDocument();
  });

  it("applies the retro pixel font class by default", () => {
    render(<Button>Retro</Button>);
    expect(screen.getByRole("button", { name: "Retro" })).toHaveClass("retro");
  });

  it("omits the retro font class when font='normal'", () => {
    render(<Button font="normal">Plain</Button>);
    expect(
      screen.getByRole("button", { name: "Plain" })
    ).not.toHaveClass("retro");
  });

  it("forwards disabled state to the underlying button", () => {
    render(<Button disabled>Nope</Button>);
    expect(screen.getByRole("button", { name: "Nope" })).toBeDisabled();
  });
});
