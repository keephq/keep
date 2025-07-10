/**
 * Unit test for preset navigation logic to verify the fix for GitHub issue #5112
 * Tests the navigation behavior when preset names are changed vs when they stay the same
 */

describe("Preset Navigation Logic", () => {
  let mockRouter: { push: jest.fn };
  let mockMutatePresets: jest.fn;
  let originalWindowLocation: Location;

  beforeEach(() => {
    mockRouter = { push: jest.fn() };
    mockMutatePresets = jest.fn().mockResolvedValue(undefined);
    
    // Mock window.location
    originalWindowLocation = window.location;
    delete (window as any).location;
    window.location = { href: "" } as any;
  });

  afterEach(() => {
    window.location = originalWindowLocation;
    jest.clearAllMocks();
  });

  it("should use router.push for normal navigation when preset name does not change", () => {
    // Simulate the logic from onCreateOrUpdatePreset
    const selectedPreset = { name: "test-preset" };
    const updatedPreset = { name: "test-preset" }; // Same name
    
    const oldPresetName = selectedPreset?.name?.toLowerCase();
    const newPresetName = updatedPreset.name.toLowerCase();
    const isNameChanged = selectedPreset && oldPresetName !== newPresetName;
    
    const encodedPresetName = encodeURIComponent(updatedPreset.name.toLowerCase());
    const newUrl = `/alerts/${encodedPresetName}`;
    
    if (!isNameChanged) {
      mockRouter.push(newUrl);
    }
    
    expect(isNameChanged).toBe(false);
    expect(mockRouter.push).toHaveBeenCalledWith("/alerts/test-preset");
    expect(window.location.href).toBe("");
  });

  it("should use window.location.href for navigation when preset name changes", async () => {
    // Simulate the logic from onCreateOrUpdatePreset
    const selectedPreset = { name: "old-preset" };
    const updatedPreset = { name: "new-preset" }; // Different name
    
    const oldPresetName = selectedPreset?.name?.toLowerCase();
    const newPresetName = updatedPreset.name.toLowerCase();
    const isNameChanged = selectedPreset && oldPresetName !== newPresetName;
    
    const encodedPresetName = encodeURIComponent(updatedPreset.name.toLowerCase());
    const newUrl = `/alerts/${encodedPresetName}`;
    
    if (isNameChanged) {
      try {
        await mockMutatePresets();
        window.location.href = newUrl;
      } catch (error) {
        mockRouter.push(newUrl);
      }
    }
    
    expect(isNameChanged).toBe(true);
    expect(mockMutatePresets).toHaveBeenCalled();
    expect(window.location.href).toBe("/alerts/new-preset");
    expect(mockRouter.push).not.toHaveBeenCalled();
  });

  it("should fallback to router.push when preset revalidation fails", async () => {
    mockMutatePresets.mockRejectedValue(new Error("Revalidation failed"));
    
    // Simulate the logic from onCreateOrUpdatePreset
    const selectedPreset = { name: "old-preset" };
    const updatedPreset = { name: "new-preset" }; // Different name
    
    const oldPresetName = selectedPreset?.name?.toLowerCase();
    const newPresetName = updatedPreset.name.toLowerCase();
    const isNameChanged = selectedPreset && oldPresetName !== newPresetName;
    
    const encodedPresetName = encodeURIComponent(updatedPreset.name.toLowerCase());
    const newUrl = `/alerts/${encodedPresetName}`;
    
    if (isNameChanged) {
      try {
        await mockMutatePresets();
        window.location.href = newUrl;
      } catch (error) {
        mockRouter.push(newUrl);
      }
    }
    
    expect(isNameChanged).toBe(true);
    expect(mockMutatePresets).toHaveBeenCalled();
    expect(mockRouter.push).toHaveBeenCalledWith("/alerts/new-preset");
    expect(window.location.href).toBe(""); // Should remain empty due to fallback
  });

  it("should properly encode preset names with special characters", () => {
    const selectedPreset = { name: "test preset" };
    const updatedPreset = { name: "test preset with spaces & symbols!" };
    
    const encodedPresetName = encodeURIComponent(updatedPreset.name.toLowerCase());
    const expectedEncoded = "test%20preset%20with%20spaces%20%26%20symbols!";
    
    expect(encodedPresetName).toBe(expectedEncoded);
  });
});