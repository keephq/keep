import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { AlertTableThemeSelection } from "../AlertTableThemeSelection";
import { useAlertTableTheme } from "@/entities/alerts/model";
import { predefinedThemes } from "../AlertTableThemeSelection";

// Mock the useAlertTableTheme hook - use the exact path that matches the import
jest.mock("@/entities/alerts/model", () => ({
  useAlertTableTheme: jest.fn(),
}));

// Get all theme names and their indices
const themeEntries = Object.entries(predefinedThemes);

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

  themeEntries.forEach(([themeName, theme], index) => {
    it(`should apply ${themeName} theme correctly`, () => {
      // Render component once
      render(<AlertTableThemeSelection onClose={mockOnClose} />);

      // Get the tab list and apply button
      const tabList = screen.getByTestId("theme-tab-list");
      const applyButton = screen.getByTestId("apply-theme-button");

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
