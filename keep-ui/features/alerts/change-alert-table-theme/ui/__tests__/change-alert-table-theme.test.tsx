import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { AlertTableThemeSelection } from "../AlertTableThemeSelection";
import { useAlertTableTheme } from "@/entities/alerts/model/useAlertTableTheme";
import { predefinedThemes } from "../AlertTableThemeSelection";

// Mock the useAlertTableTheme hook
jest.mock("@/entities/alerts/model/useAlertTableTheme");

describe("AlertTableThemeSelection", () => {
  const mockSetTheme = jest.fn();
  const mockOnClose = jest.fn();

  beforeEach(() => {
    // Reset all mocks before each test
    jest.clearAllMocks();
    // Setup default mock implementation
    (useAlertTableTheme as jest.Mock).mockReturnValue({
      theme: {},
      setTheme: mockSetTheme,
    });
  });

  it("should apply correct theme when selecting different tabs and clicking apply", () => {
    // Render component once
    render(<AlertTableThemeSelection onClose={mockOnClose} />);

    // Get the tab list and apply button
    const tabList = screen.getByTestId("theme-tab-list");
    const applyButton = screen.getByTestId("apply-theme-button");

    // Get all theme names and their indices
    const themeEntries = Object.entries(predefinedThemes);

    themeEntries.forEach(([themeName, theme], index) => {
      // Click the corresponding tab
      const tabs = tabList.querySelectorAll("button");
      fireEvent.click(tabs[index]);

      // Click apply button
      fireEvent.click(applyButton);

      // Verify the correct theme was set
      expect(mockSetTheme).toHaveBeenCalledWith(theme);

      // Verify onClose was called
      expect(mockOnClose).toHaveBeenCalled();

      // Clean up mocks for next iteration
      jest.clearAllMocks();
    });
  });
});
