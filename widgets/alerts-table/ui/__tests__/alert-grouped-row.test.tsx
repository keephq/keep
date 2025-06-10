import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { GroupedRow } from "../alert-grouped-row";
import { Table, Row, Column } from "@tanstack/react-table";
import { AlertDto } from "@/entities/alerts/model";

describe("GroupedRow", () => {
  const createMockAlert = (fingerprint: string, name: string): AlertDto => ({
    fingerprint,
    name,
    description: "Test description",
    severity: 3,
    status: "Firing",
    source: ["test-source"],
    lastReceived: new Date().toISOString(),
    firingStartTime: new Date().toISOString(),
    url: "https://example.com",
    pushed: true,
    assignee: null,
    dismissed: false,
    event_id: `event-${fingerprint}`,
    apiKeyRef: "test-api-key",
    providerId: "test-provider",
    providerType: "test",
    note: null,
    startedAt: new Date().toISOString(),
    isNoisy: false,
    enriched_fields: [],
    generatorURL: null,
  });

  const createMockRow = (isGrouped: boolean, groupingValue?: string): Row<AlertDto> => ({
    id: "test-row",
    index: 0,
    original: createMockAlert("123", "Test alert"),
    depth: 0,
    subRows: isGrouped ? [
      { id: "sub-1", original: createMockAlert("456", "Test alert 1") } as any,
      { id: "sub-2", original: createMockAlert("789", "Test alert 2") } as any,
    ] : [],
    getIsGrouped: () => isGrouped,
    getGroupingValue: () => groupingValue || "Test Group",
    getValue: () => null,
    renderValue: () => null,
    getCanExpand: () => isGrouped,
    getIsExpanded: () => false,
    getToggleExpandedHandler: () => () => {},
    getContext: () => ({} as any),
  } as any);

  const mockTable = {
    getVisibleLeafColumns: () => [],
  } as any;

  it("should show collapsed state when isExpanded is false", () => {
    const mockRow = createMockRow(true, "Firing");
    const mockExpansionState = {
      expandedGroups: new Set<string>(),
      toggleGroup: jest.fn(),
      setExpandedGroups: jest.fn(),
      areAllGroupsExpanded: jest.fn(),
      areAllGroupsCollapsed: jest.fn(),
      toggleAll: jest.fn(),
    };

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme="dark"
        presetName="test-preset"
        groupExpansionState={mockExpansionState}
      />
    );

    // Check chevron rotation class - look for SVG element
    const svg = screen.getByRole("img", { hidden: true });
    expect(svg.className).toContain("-rotate-90");
    
    // Sub rows should not be rendered
    expect(screen.queryByText("Test alert 1")).not.toBeInTheDocument();
    expect(screen.queryByText("Test alert 2")).not.toBeInTheDocument();
  });

  it("should show expanded state when isExpanded is true", () => {
    const mockRow = createMockRow(true, "Firing");
    const mockExpansionState = {
      expandedGroups: new Set<string>(["Test Group"]),
      toggleGroup: jest.fn(),
      setExpandedGroups: jest.fn(),
      areAllGroupsExpanded: jest.fn(),
      areAllGroupsCollapsed: jest.fn(),
      toggleAll: jest.fn(),
    };

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme="dark"
        presetName="test-preset"
        groupExpansionState={mockExpansionState}
      />
    );

    // Check chevron is not rotated
    const svg = screen.getByRole("img", { hidden: true });
    expect(svg.className).not.toContain("-rotate-90");
  });

  it("should format incident grouping correctly", () => {
    const mockRow = createMockRow(true, '{"name": "incident-123"}');
    const mockExpansionState = {
      expandedGroups: new Set<string>(),
      toggleGroup: jest.fn(),
      setExpandedGroups: jest.fn(),
      areAllGroupsExpanded: jest.fn(),
      areAllGroupsCollapsed: jest.fn(),
      toggleAll: jest.fn(),
    };

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme="light"
        presetName="test-preset"
        groupExpansionState={mockExpansionState}
      />
    );

    // Check if incident name is displayed
    expect(screen.getByText("Grouped by: incident-123")).toBeInTheDocument();
  });

  it("should toggle expansion when clicked", () => {
    const mockRow = createMockRow(true, "Firing");
    const mockExpansionState = {
      expandedGroups: new Set<string>(),
      toggleGroup: jest.fn(),
      setExpandedGroups: jest.fn(),
      areAllGroupsExpanded: jest.fn(),
      areAllGroupsCollapsed: jest.fn(),
      toggleAll: jest.fn(),
    };

    render(
      <GroupedRow
        row={mockRow}
        table={mockTable}
        theme="dark"
        presetName="test-preset"
        groupExpansionState={mockExpansionState}
      />
    );

    // Click on the row
    const row = screen.getByRole("row");
    fireEvent.click(row);

    // Check if toggleGroup was called with the correct group key
    expect(mockExpansionState.toggleGroup).toHaveBeenCalledWith("Test Group");
  });
});