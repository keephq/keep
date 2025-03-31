import {Preset} from "@/entities/presets/model/types";

export function getTabsFromPreset(preset: Preset): any[] {
  const tabsOption = preset.options.find(
    (option) => option.label.toLowerCase() === "tabs"
  );
  return tabsOption && Array.isArray(tabsOption.value) ? tabsOption.value : [];
}
