import "@testing-library/jest-dom";

window.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

jest.mock("react-code-blocks", () => ({
  CopyBlock: ({ text }: { text: string }) => null,
  a11yLight: {},
}));
