import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCelState } from "../use-cel-state";
import { renderHook, act } from "@testing-library/react";

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
  useSearchParams: jest.fn(),
  usePathname: jest.fn(() => "/alerts/feed"),
}));
jest.useFakeTimers();

describe("useCelState", () => {
  let replaceMock: jest.Mock;
  beforeEach(() => {
    (useSearchParams as jest.Mock).mockReturnValue(new URLSearchParams());
    replaceMock = jest.fn();
    (useRouter as jest.Mock).mockReturnValue({
      replace: replaceMock,
    });
  });

  it("should initialize with defaultCel when no query param is present", () => {
    (useSearchParams as jest.Mock).mockReturnValue(new URLSearchParams({}));
    const { result } = renderHook(() =>
      useCelState({
        enableQueryParams: false,
        defaultCel: "name.contains('cpu')",
      })
    );

    expect(result.current[0]).toBe("name.contains('cpu')");
  });

  it("should initialize with query param value if present", () => {
    (useSearchParams as jest.Mock).mockReturnValue(
      new URLSearchParams({
        cel: "name.contains('cpu')",
      })
    );

    const { result } = renderHook(() =>
      useCelState({
        enableQueryParams: true,
        defaultCel: "name.contains('memory')",
      })
    );

    expect(result.current[0]).toBe("name.contains('cpu')");
  });

  it("should update query params when celState changes and enableQueryParams is true", () => {
    (useSearchParams as jest.Mock).mockReturnValue(
      new URLSearchParams({
        cel: "name.contains('cpu')",
      })
    );

    const { result } = renderHook(() =>
      useCelState({ enableQueryParams: true, defaultCel: "" })
    );

    act(() => {
      result.current[1]("name.contains('memory')");
    });

    act(() => {
      jest.advanceTimersByTime(500);
    });

    expect(replaceMock).toHaveBeenCalledWith(
      "/?cel=name.contains%28%27memory%27%29"
    );
  });

  it("should not update query params when enableQueryParams is false", () => {
    const { result } = renderHook(() =>
      useCelState({ enableQueryParams: false, defaultCel: "" })
    );

    act(() => {
      result.current[1]("name.contains('cpu')");
    });

    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("should remove cel query param when celState is reset to defaultCel", () => {
    (useSearchParams as jest.Mock).mockReturnValue(
      new URLSearchParams({
        cel: "name.contains('memory')",
      })
    );

    const { result } = renderHook(() =>
      useCelState({
        enableQueryParams: true,
        defaultCel: "name.contains('cpu')",
      })
    );

    act(() => {
      result.current[1]("name.contains('cpu')");
    });

    expect(replaceMock).toHaveBeenCalledWith("/");
  });

  it("should clean up cel query param when pathname changes", () => {
    (useSearchParams as jest.Mock).mockReturnValue(
      new URLSearchParams({
        cel: "name.contains('cpu')",
      })
    );

    (usePathname as jest.Mock).mockReturnValue("/new/pathname");

    const { result, unmount } = renderHook(() =>
      useCelState({ enableQueryParams: true, defaultCel: "" })
    );

    unmount();

    expect(replaceMock).toHaveBeenCalledWith("/");
  });
});
