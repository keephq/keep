// ThemeSelection.test.tsx
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ThemeSelection } from "./ThemeSelection";
import { AlertTableServerSide } from "./alert-table-server-side";
import "@testing-library/jest-dom";

// Mock the useLocalStorage hook
jest.mock("@/utils/hooks/useLocalStorage", () => ({
  useLocalStorage: jest.fn((key, initialValue) => {
    // For testing purposes, we'll use React's useState instead
    const [value, setValue] = React.useState(initialValue);
    return [value, setValue];
  }),
}));

// Create a minimal mock for the AlertDto type
const mockAlerts = [
  {
    id: "1",
    fingerprint: "fp1",
    severity: "critical",
    name: "Test Alert",
    description: "Test description",
    source: ["datadog"],
    status: "firing",
    lastReceived: new Date().toISOString(),
  },
];

describe("Theme Selection Component", () => {
  it("should apply theme when selected and Apply Theme button is clicked", async () => {
    // Setup the component test
    const handleThemeChange = jest.fn();

    // Render the ThemeSelection component
    const { getByText } = render(
      <ThemeSelection onThemeChange={handleThemeChange} />
    );

    // Click on the "Keep" theme tab
    fireEvent.click(screen.getByText("Keep"));

    // Click the Apply Theme button
    fireEvent.click(screen.getByText("Apply theme"));

    // Verify the onThemeChange was called with the correct theme
    expect(handleThemeChange).toHaveBeenCalledWith({
      critical: "bg-orange-400",
      high: "bg-orange-300",
      warning: "bg-orange-200",
      low: "bg-orange-100",
      info: "bg-orange-50",
    });
  });

  // This test will check the integration between components
  it("should change row background colors when theme is applied", async () => {
    // Create a test container where we'll render our components
    const container = document.createElement("div");
    document.body.appendChild(container);

    // Prepare test data and mocks
    const mockTable = {
      getState: jest.fn(() => ({
        columnPinning: { left: [], right: [] },
      })),
      // Add any other required mock methods
    };

    // We'll need to render the AlertTableServerSide component with some alerts
    // and a working theme setting mechanism

    // First, render the Settings component that includes ThemeSelection
    const { rerender } = render(
      <AlertTableServerSide
        refreshToken="test-token"
        alerts={mockAlerts}
        alertsTotalCount={1}
        columns={[]}
        initialFacets={[]}
        presetName="test"
      />,
      { container }
    );

    // Find the rendered table rows
    const beforeRows = container.querySelectorAll("tr");

    // Now, let's simulate changing the theme
    // First, find the settings button and click it
    // Note: You might need to adjust these selectors based on your actual component structure
    const settingsButton = container.querySelector('button[icon="FiSettings"]');
    if (settingsButton) {
      fireEvent.click(settingsButton);
    }

    // Find the theme tab and click it
    const themeTab = screen.getByText("Theme");
    fireEvent.click(themeTab);

    // Select the "Keep" theme
    const keepThemeTab = screen.getByText("Keep");
    fireEvent.click(keepThemeTab);

    // Click Apply Theme
    const applyButton = screen.getByText("Apply theme");
    fireEvent.click(applyButton);

    // Wait for the UI to update
    await waitFor(() => {
      const afterRows = container.querySelectorAll("tr");

      // Check that at least one row has the expected theme class
      // The critical severity should have bg-orange-400
      const criticalRow = Array.from(afterRows).find(
        (row) =>
          row.classList.contains("bg-orange-400") ||
          row.querySelector(".bg-orange-400")
      );

      expect(criticalRow).toBeTruthy();
    });

    // Clean up
    document.body.removeChild(container);
  });
});
