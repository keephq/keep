import "@testing-library/jest-dom";
import "@/shared/tests/next-auth-mock";

// Mocks
window.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

window.confirm = jest.fn();

jest.mock("react-code-blocks", () => ({
  CopyBlock: ({ text }: { text: string }) => null,
  a11yLight: {},
}));

jest.mock("@/shared/lib/hooks/useApi", () => ({
  useApi: jest.fn().mockReturnValue({
    request: jest.fn(),
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
    isReady: () => true,
  }),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
  usePathname: () => jest.fn(),
}));

// Mock useConfig hook
jest.mock("@/utils/hooks/useConfig", () => ({
  useConfig: jest.fn().mockReturnValue({
    data: {},
  }),
}));
