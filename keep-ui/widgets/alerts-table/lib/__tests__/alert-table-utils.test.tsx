import { useState } from "react";
import { render, renderHook, screen, fireEvent } from "@testing-library/react";
import { ColumnDef, flexRender } from "@tanstack/react-table";
import { AlertDto } from "@/entities/alerts/model";
import { useAlertTableCols } from "../alert-table-utils";

jest.mock("@/utils/hooks/useLocalStorage", () => ({
  useLocalStorage: jest.fn((_key: string, initial: unknown) => [
    initial,
    jest.fn(),
  ]),
}));
jest.mock("@/utils/hooks/useProviders", () => ({
  useProviders: jest.fn(() => ({ data: undefined })),
}));
jest.mock("@/utils/hooks/useConfig", () => ({
  useConfig: jest.fn(() => ({ data: {} })),
}));
jest.mock("@/utils/hooks/useExpandedRows", () => ({
  useExpandedRows: jest.fn(() => ({ isRowExpanded: () => false })),
}));
jest.mock("@/entities/alerts/model/useAlertRowStyle", () => ({
  useAlertRowStyle: jest.fn(() => ["default"]),
}));
jest.mock("@/entities/alerts/model/useSeverityMapping", () => ({
  useSeverityMapping: jest.fn(() => ({ severityMapping: undefined })),
}));
jest.mock("@/features/alerts/alert-menu", () => ({
  AlertMenu: () => null,
}));

const getMenuColumn = (columns: ColumnDef<AlertDto>[]) =>
  columns.find((col) => col.id === "alertMenu")!;

describe("useAlertTableCols alertMenu column", () => {
  it("keeps the menu cell identity stable across re-renders", () => {
    const { result, rerender } = renderHook(() =>
      useAlertTableCols({
        presetName: "feed",
        isMenuDisplayed: true,
        // new function each render, like an inline arrow in a parent component
        setRunWorkflowModalAlert: () => {},
      })
    );

    const firstCell = getMenuColumn(result.current).cell;
    rerender();
    rerender();

    expect(getMenuColumn(result.current).cell).toBe(firstCell);
  });

  it("does not remount the menu (state survives) when columns are rebuilt", () => {
    const alert = { fingerprint: "fp-1" } as AlertDto;

    function StatefulMenu() {
      const [open, setOpen] = useState(false);
      return (
        <button onClick={() => setOpen(true)}>{open ? "open" : "closed"}</button>
      );
    }
    const MenuComponent = () => <StatefulMenu />;

    function Harness() {
      // forces the hook (and the columns array) to be rebuilt on every render
      const [, setTick] = useState(0);
      const columns = useAlertTableCols({
        presetName: "feed",
        isMenuDisplayed: true,
        MenuComponent,
      });
      const cell = getMenuColumn(columns).cell;
      return (
        <div>
          <button onClick={() => setTick((t) => t + 1)}>rerender</button>
          {flexRender(cell, { row: { original: alert } } as any)}
        </div>
      );
    }

    render(<Harness />);
    fireEvent.click(screen.getByText("closed"));
    expect(screen.getByText("open")).toBeTruthy();

    fireEvent.click(screen.getByText("rerender"));

    expect(screen.getByText("open")).toBeTruthy();
  });

  it("uses the latest props without changing the cell identity", () => {
    const first = jest.fn();
    const second = jest.fn();
    const { result, rerender } = renderHook(
      ({ cb }: { cb: () => void }) =>
        useAlertTableCols({
          presetName: "feed",
          isMenuDisplayed: true,
          MenuComponent: () => {
            cb();
            return null;
          },
        }),
      { initialProps: { cb: first } }
    );
    const cell = getMenuColumn(result.current).cell as (c: any) => unknown;

    rerender({ cb: second });
    cell({ row: { original: {} } });

    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });
});
