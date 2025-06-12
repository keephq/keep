import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { GroupedRow } from "@/widgets/alerts-table/ui/alert-grouped-row";
import { Table, Row, Column } from "@tanstack/react-table";
import { AlertDto, Status, Severity } from "@/entities/alerts/model/types";

describe("GroupedRow", () => {
  const createMockAlert = (fingerprint: string, name: string): AlertDto => ({
    id: `alert-${fingerprint}`,
    fingerprint,
    name,
    description: "Test description",
    severity: Severity.Warning,
    status: Status.Firing,
    source: ["test-source"],
    lastReceived: new Date(),
    environment: "test",
    url: "https://example.com",
    pushed: true,
    assignee: undefined,
    dismissed: false,
    deleted: false,
    event_id: `event-${fingerprint}`,
    enriched_fields: [],
    ticket_url: "",
  });

  const createMockRow = (isGrouped: boolean, groupingValue?: string): Row<AlertDto> => ({
    id: "test-row",
    index: 0,
    original: createMockAlert("123", "Test alert"),
    depth: 0,
    subRows: isGrouped ? [
      { id: "sub-1", original: createMockAlert("456", "Test alert 1"), getVisibleCells: () => [] } as any,
      { id: "sub-2", original: createMockAlert("789", "Test alert 2"), getVisibleCells: () => [] } as any,
    ] : [],
    getIsGrouped: () => isGrouped,
    groupingColumnId: "status",
    getValue: (columnId: string) => groupingValue || "Test Group",
    renderValue: () => null,
    getCanExpand: () => isGrouped,
    getIsExpanded: () => false,
    getToggleExpandedHandler: () => () => {},
    getContext: () => ({} as any),
    getVisibleCells: () => [], 
  } as any);

  const mockTable = {
    getVisibleLeafColumns: () => [],
    getState: () => ({
      columnPinning: {
        left: [],
        right: []
      }
    })
  } as any;

  const mockTheme = {
    critical: "bg-red-100",
    warning: "bg-yellow-100",
    info: "bg-blue-100"
  };

  it("should show collapsed state when isExpanded is false", () => {
    const mockRow = createMockRow(true, "Test Group");
    const onToggleExpanded = jest.fn();

    const { container } = render(
      <table>
        <tbody>
          <GroupedRow
            row={mockRow}
            table={mockTable}
            theme={mockTheme}
            lastViewedAlert={null}
            rowStyle="default"
            isExpanded={false}
            onToggleExpanded={onToggleExpanded}
          />
        </tbody>
      </table>
    );

    // Check chevron rotation class - look for SVG element by class
    const svg = container.querySelector('svg');
    expect(svg?.className.baseVal).toContain("-rotate-90");
    
    // Sub rows should not be rendered
    expect(screen.queryByText("Test alert 1")).not.toBeInTheDocument();
    expect(screen.queryByText("Test alert 2")).not.toBeInTheDocument();
  });

  it("should show expanded state when isExpanded is true", () => {
    const mockRow = createMockRow(true, "Test Group");
    const onToggleExpanded = jest.fn();

    const { container } = render(
      <table>
        <tbody>
          <GroupedRow
            row={mockRow}
            table={mockTable}
            theme={mockTheme}
            lastViewedAlert={null}
            rowStyle="default"
            isExpanded={true}
            onToggleExpanded={onToggleExpanded}
          />
        </tbody>
      </table>
    );

    // Check chevron is not rotated
    const svg = container.querySelector('svg');
    expect(svg?.className.baseVal).not.toContain("-rotate-90");
  });

  it("should format incident grouping correctly", () => {
    const mockRow = {
      ...createMockRow(true, '{"name": "incident-123"}'),
      groupingColumnId: "incident",
      original: {
        ...createMockAlert("123", "Test alert"),
        incident_dto: [{
          user_generated_name: "Production Outage",
          ai_generated_name: "Database Connection Issues"
        }]
      }
    } as any;
    
    const onToggleExpanded = jest.fn();

    render(
      <table>
        <tbody>
          <GroupedRow
            row={mockRow}
            table={mockTable}
            theme={mockTheme}
            lastViewedAlert={null}
            rowStyle="default"
            isExpanded={true}
            onToggleExpanded={onToggleExpanded}
          />
        </tbody>
      </table>
    );

    // Check if incident name is displayed
    expect(screen.getByText("Production Outage")).toBeInTheDocument();
  });

  it("should toggle expansion when clicked", () => {
    const mockRow = createMockRow(true, "Test Group");
    const onToggleExpanded = jest.fn();

    render(
      <table>
        <tbody>
          <GroupedRow
            row={mockRow}
            table={mockTable}
            theme={mockTheme}
            lastViewedAlert={null}
            rowStyle="default"
            isExpanded={false}
            onToggleExpanded={onToggleExpanded}
          />
        </tbody>
      </table>
    );

    // Click on the group header cell
    const groupHeader = screen.getByText("Test Group").closest("td");
    fireEvent.click(groupHeader!);

    // Check if toggleGroup was called with the correct group key
    expect(onToggleExpanded).toHaveBeenCalledWith("test-row");
  });
});