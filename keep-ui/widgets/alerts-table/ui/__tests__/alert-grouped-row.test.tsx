import { render, screen, fireEvent } from "@testing-library/react";
import { GroupedRow } from "../alert-grouped-row";
import { Table, Row } from "@tanstack/react-table";
import { AlertDto } from "@/entities/alerts/model";

describe("GroupedRow", () => {
  const mockTable = {} as Table<AlertDto>;
  const mockTheme = { critical: "bg-red-100", warning: "bg-yellow-100" };
  const mockOnRowClick = jest.fn();
  const mockOnToggleExpanded = jest.fn();
  const mockOnGroupInitialized = jest.fn();

  const createMockRow = (isGrouped: boolean, groupValue: string = "Test Group") => ({
    id: "group-1",
    getIsGrouped: () => isGrouped,
    groupingColumnId: "status",
    getValue: (columnId: string) => groupValue,
    original: {
      fingerprint: "alert-1",
      name: "Test Alert",
      status: "firing",
    } as AlertDto,
    subRows: [
      {
        id: "alert-1",
        original: {
          fingerprint: "alert-1",
          name: "Test Alert 1",
        } as AlertDto,
        getVisibleCells: () => [],
      },
      {
        id: "alert-2",
        original: {
          fingerprint: "alert-2",
          name: "Test Alert 2",
        } as AlertDto,
        getVisibleCells: () => [],
      },
    ],
    getVisibleCells: () => [],
  } as unknown as Row<AlertDto>);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should render grouped row with correct group value and count", () => {
    const mockRow = createMockRow(true, "Firing");

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme={mockTheme}
        onRowClick={mockOnRowClick}
        lastViewedAlert={null}
        rowStyle="default"
        isExpanded={true}
        onToggleExpanded={mockOnToggleExpanded}
      />
    );

    expect(screen.getByText("Firing")).toBeInTheDocument();
    expect(screen.getByText("(2 alerts)")).toBeInTheDocument();
  });

  it("should show collapsed state when isExpanded is false", () => {
    const mockRow = createMockRow(true);

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme={mockTheme}
        onRowClick={mockOnRowClick}
        lastViewedAlert={null}
        rowStyle="default"
        isExpanded={false}
        onToggleExpanded={mockOnToggleExpanded}
      />
    );

    // Check chevron rotation class
    const chevron = screen.getByTestId("chevron-icon").parentElement;
    expect(chevron?.className).toContain("-rotate-90");
    
    // Sub rows should not be rendered
    expect(screen.queryByText("Test Alert 1")).not.toBeInTheDocument();
    expect(screen.queryByText("Test Alert 2")).not.toBeInTheDocument();
  });

  it("should call onToggleExpanded when group header is clicked", () => {
    const mockRow = createMockRow(true);

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme={mockTheme}
        onRowClick={mockOnRowClick}
        lastViewedAlert={null}
        rowStyle="default"
        isExpanded={true}
        onToggleExpanded={mockOnToggleExpanded}
      />
    );

    const groupHeader = screen.getByText("Test Group").closest("td");
    fireEvent.click(groupHeader!);

    expect(mockOnToggleExpanded).toHaveBeenCalledWith("group-1");
  });

  it("should initialize group on mount", () => {
    const mockRow = createMockRow(true);

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme={mockTheme}
        onRowClick={mockOnRowClick}
        lastViewedAlert={null}
        rowStyle="default"
        isExpanded={true}
        onToggleExpanded={mockOnToggleExpanded}
        onGroupInitialized={mockOnGroupInitialized}
      />
    );

    expect(mockOnGroupInitialized).toHaveBeenCalledWith("group-1");
  });

  it("should render non-grouped row normally", () => {
    const mockRow = createMockRow(false);

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme={mockTheme}
        onRowClick={mockOnRowClick}
        lastViewedAlert={null}
        rowStyle="default"
      />
    );

    // Should render as a regular row, not a group
    expect(screen.queryByText("(2 alerts)")).not.toBeInTheDocument();
  });

  it("should handle incident grouping with special formatting", () => {
    const mockRow = {
      ...createMockRow(true),
      groupingColumnId: "incident",
      getValue: () => "incident-123",
      original: {
        ...createMockRow(true).original,
        incident_dto: [
          {
            user_generated_name: "Production Outage",
            ai_generated_name: "Database Connection Issues",
          },
        ],
      },
    } as unknown as Row<AlertDto>;

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme={mockTheme}
        onRowClick={mockOnRowClick}
        lastViewedAlert={null}
        rowStyle="default"
        isExpanded={true}
      />
    );

    expect(screen.getByText("Production Outage")).toBeInTheDocument();
  });
});