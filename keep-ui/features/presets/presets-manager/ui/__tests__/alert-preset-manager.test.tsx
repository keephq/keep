import { render, screen, fireEvent } from "@testing-library/react";
import { AlertPresetManager } from "../alert-preset-manager";
import { Table } from "@tanstack/react-table";
import { AlertDto } from "@/entities/alerts/model";

// Mock the dependencies
jest.mock("@/entities/presets/model/usePresets", () => ({
  usePresets: () => ({ dynamicPresets: [] }),
}));

jest.mock("@/entities/alerts/model", () => ({
  useAlerts: () => ({
    useErrorAlerts: () => ({ data: [] }),
  }),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
  }),
}));

describe("AlertPresetManager", () => {
  const mockTable = {} as Table<AlertDto>;
  const mockToggleAll = jest.fn();
  const mockAreAllGroupsExpanded = jest.fn();
  
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should not show collapse/expand button when grouping is not active", () => {
    render(
      <AlertPresetManager
        presetName="test-preset"
        table={mockTable}
        isGroupingActive={false}
        onToggleAllGroups={mockToggleAll}
        areAllGroupsExpanded={mockAreAllGroupsExpanded}
      />
    );

    expect(screen.queryByText("Collapse All")).not.toBeInTheDocument();
    expect(screen.queryByText("Expand All")).not.toBeInTheDocument();
  });

  it("should show Collapse All button when grouping is active and all groups are expanded", () => {
    mockAreAllGroupsExpanded.mockReturnValue(true);

    render(
      <AlertPresetManager
        presetName="test-preset"
        table={mockTable}
        isGroupingActive={true}
        onToggleAllGroups={mockToggleAll}
        areAllGroupsExpanded={mockAreAllGroupsExpanded}
      />
    );

    const button = screen.getByText("Collapse All");
    expect(button).toBeInTheDocument();
  });

  it("should show Expand All button when grouping is active and not all groups are expanded", () => {
    mockAreAllGroupsExpanded.mockReturnValue(false);

    render(
      <AlertPresetManager
        presetName="test-preset"
        table={mockTable}
        isGroupingActive={true}
        onToggleAllGroups={mockToggleAll}
        areAllGroupsExpanded={mockAreAllGroupsExpanded}
      />
    );

    const button = screen.getByText("Expand All");
    expect(button).toBeInTheDocument();
  });

  it("should call onToggleAllGroups when button is clicked", () => {
    mockAreAllGroupsExpanded.mockReturnValue(true);

    render(
      <AlertPresetManager
        presetName="test-preset"
        table={mockTable}
        isGroupingActive={true}
        onToggleAllGroups={mockToggleAll}
        areAllGroupsExpanded={mockAreAllGroupsExpanded}
      />
    );

    const button = screen.getByText("Collapse All");
    fireEvent.click(button);

    expect(mockToggleAll).toHaveBeenCalledTimes(1);
  });

  it("should always show Test alerts button", () => {
    render(
      <AlertPresetManager
        presetName="test-preset"
        table={mockTable}
      />
    );

    // The test alerts button is rendered, check by its color and variant
    const buttons = screen.getAllByRole("button");
    const testButton = buttons.find(button => 
      button.className.includes("border-orange-500") && 
      button.className.includes("text-orange-500")
    );
    expect(testButton).toBeInTheDocument();
  });

  it("should maintain button order and spacing", () => {
    mockAreAllGroupsExpanded.mockReturnValue(true);

    render(
      <AlertPresetManager
        presetName="test-preset"
        table={mockTable}
        isGroupingActive={true}
        onToggleAllGroups={mockToggleAll}
        areAllGroupsExpanded={mockAreAllGroupsExpanded}
      />
    );

    const buttons = screen.getAllByRole("button");
    
    // Should have at least the collapse button and test alerts button
    expect(buttons.length).toBeGreaterThanOrEqual(2);
    
    // Check that buttons have consistent styling
    buttons.forEach(button => {
      expect(button.className).toContain("ml-2"); // margin-left spacing
    });
  });


});