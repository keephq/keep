import { Preset } from "@/entities/presets/model/types";

/**
 * @param preset
 *
 * @deprecated preset tabs are removed, this function shouldn't be used anymore
 */
export function getTabsFromPreset(preset: Preset): any[] {
  const tabsOption = preset.options.find(
    (option) => option.label.toLowerCase() === "tabs"
  );
  return tabsOption && Array.isArray(tabsOption.value) ? tabsOption.value : [];
}
