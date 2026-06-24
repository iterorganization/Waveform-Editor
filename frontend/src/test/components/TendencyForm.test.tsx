import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TendencyForm } from "../../components/timeline/TendencyForm";
import type { TendencyData } from "../../types";

const CONSTANT: TendencyData = { type: "constant", duration: 10, value: 5.0 };
const LINEAR: TendencyData = { type: "linear", duration: 20, from: 0, to: 10 };


describe("TendencyForm — rendering", () => {
  it("renders nothing inside form when no tendencies", () => {
    const onChange = vi.fn();
    render(<TendencyForm tendencies={[]} onChange={onChange} />);
    expect(screen.getByText("+ Add tendency")).toBeInTheDocument();
  });

  it("renders one tendency item", () => {
    render(<TendencyForm tendencies={[CONSTANT]} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("constant")).toBeInTheDocument();
  });

  it("renders all fields for a constant tendency", () => {
    render(<TendencyForm tendencies={[CONSTANT]} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText("duration")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("value")).toBeInTheDocument();
  });

  it("renders correct fields for a linear tendency", () => {
    render(<TendencyForm tendencies={[LINEAR]} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText("from")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("to")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("duration")).toBeInTheDocument();
  });

  it("shows a remove button per tendency", () => {
    render(<TendencyForm tendencies={[CONSTANT, LINEAR]} onChange={vi.fn()} />);
    const removes = screen.getAllByTitle("Remove");
    expect(removes).toHaveLength(2);
  });
});


describe("TendencyForm — interactions", () => {
  it("calls onChange with new tendency on add click", () => {
    const onChange = vi.fn();
    render(<TendencyForm tendencies={[]} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ Add tendency"));
    expect(onChange).toHaveBeenCalledWith([{ type: "constant", duration: 10, value: 0 }]);
  });

  it("calls onChange with removed tendency on remove click", () => {
    const onChange = vi.fn();
    render(<TendencyForm tendencies={[CONSTANT, LINEAR]} onChange={onChange} />);
    const removes = screen.getAllByTitle("Remove");
    fireEvent.click(removes[0]);
    expect(onChange).toHaveBeenCalledWith([LINEAR]);
  });

  it("calls onChange with updated type on select change", async () => {
    const onChange = vi.fn();
    render(<TendencyForm tendencies={[CONSTANT]} onChange={onChange} />);
    const select = screen.getByDisplayValue("constant");
    await userEvent.selectOptions(select, "linear");
    expect(onChange).toHaveBeenCalledWith([{ type: "linear" }]);
  });

  it("calls onChange with numeric value on field change", () => {
    const onChange = vi.fn();
    render(<TendencyForm tendencies={[CONSTANT]} onChange={onChange} />);
    const valueInput = screen.getByPlaceholderText("value");
    fireEvent.change(valueInput, { target: { value: "42" } });
    expect(onChange).toHaveBeenCalledWith([{ ...CONSTANT, value: 42 }]);
  });

  it("type=number input passes empty string through as-is", () => {
    const onChange = vi.fn();
    render(<TendencyForm tendencies={[CONSTANT]} onChange={onChange} />);
    const durationInput = screen.getByPlaceholderText("duration");
    fireEvent.change(durationInput, { target: { value: "" } });
    const updated = onChange.mock.calls[0][0][0];
    // parseFloat("") is NaN, so update() keeps raw string "" rather than coercing to number
    expect(updated.duration).toBe("");
  });

  it("can add multiple tendencies", () => {
    let tendencies: TendencyData[] = [];
    const onChange = (updated: TendencyData[]) => { tendencies = updated; };
    const { rerender } = render(<TendencyForm tendencies={tendencies} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ Add tendency"));
    rerender(<TendencyForm tendencies={tendencies} onChange={onChange} />);
    fireEvent.click(screen.getByText("+ Add tendency"));
    expect(tendencies).toHaveLength(2);
  });
});


describe("TendencyForm — sine wave fields", () => {
  const SINE: TendencyData = {
    type: "sine-wave",
    duration: 100,
    base: 1.0,
    amplitude: 0.5,
    frequency: 1.0,
    phase: 0.0,
  };

  it("shows frequency and amplitude for sine-wave", () => {
    render(<TendencyForm tendencies={[SINE]} onChange={vi.fn()} />);
    expect(screen.getByPlaceholderText("frequency")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("amplitude")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("phase")).toBeInTheDocument();
  });
});
