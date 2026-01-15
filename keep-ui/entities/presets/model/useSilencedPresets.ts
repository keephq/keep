import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { useCallback } from "react";

const SILENCED_PRESETS_KEY = "silencedPresets";

export function useSilencedPresets() {
  const [silencedPresetIds, setSilencedPresetIds] = useLocalStorage<string[]>(
    SILENCED_PRESETS_KEY,
    []
  );

  const isPresetSilenced = useCallback(
    (presetId: string) => {
      return silencedPresetIds.includes(presetId);
    },
    [silencedPresetIds]
  );

  const togglePresetSilence = useCallback(
    (presetId: string) => {
      setSilencedPresetIds((prev) => {
        if (prev.includes(presetId)) {
          return prev.filter((id) => id !== presetId);
        } else {
          return [...prev, presetId];
        }
      });
    },
    [setSilencedPresetIds]
  );

  return {
    silencedPresetIds,
    isPresetSilenced,
    togglePresetSilence,
  };
}

