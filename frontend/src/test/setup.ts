import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock react-plotly.js — requires canvas which jsdom doesn't support
vi.mock("react-plotly.js", () => ({
  default: vi.fn(() => null),
}));

// Mock Monaco editor — loads worker scripts incompatible with jsdom
vi.mock("@monaco-editor/react", () => ({
  default: vi.fn(({ value, onChange }: { value: string; onChange?: (v: string | undefined) => void }) => {
    return null;
  }),
}));
