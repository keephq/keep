import { Preset, useSilencedPresets } from "@/entities/presets/model";
import { useMemo } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import useSWR from "swr";
import { AlertsQuery } from "@/entities/alerts/model";
// Using dynamic import to avoid hydration issues with react-player
import dynamic from "next/dynamic";
import clsx from "clsx";
const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });

interface PresetsNoiseProps {
  presets: Preset[];
}

export const PresetsNoise = ({ presets }: PresetsNoiseProps) => {
  const api = useApi();
  const { silencedPresetIds } = useSilencedPresets();
  
  const noisyPresets = useMemo(
    () => presets?.filter((preset) => preset.is_noisy && !silencedPresetIds.includes(preset.id)),
    [presets, silencedPresetIds]
  );

  const { data: shouldDoNoise } = useSWR(
    () =>
      api.isReady() && noisyPresets
        ? noisyPresets.map((noisyPreset) => noisyPreset.id)
        : null,
    async () => {
      let shouldDoNoise = false;

      // Iterate through noisy presets and find first that has an Alert that should trigger noise
      for (let noisyPreset of noisyPresets) {
        const noisyAlertsCelRules = [
          "status == 'firing' && deleted == false && dismissed == false",
          noisyPreset.options.find((opt) => opt.label == "CEL")?.value,
        ];
        const query: AlertsQuery = {
          cel: noisyAlertsCelRules.map((cel) => `(${cel})`).join(" && "),
          limit: 0,
          offset: 0,
        };

        const { count: matchingAlertsCount } = await api.post(
          "/alerts/query",
          query
        );
        shouldDoNoise = !!matchingAlertsCount;

        if (shouldDoNoise) {
          break;
        }
      }

      return shouldDoNoise;
    }
  );

  /* React Player for playing alert sound */
  return (
    <div
      data-testid="noisy-presets-audio-player"
      className={clsx("absolute -z-10", {
        playing: shouldDoNoise,
      })}
    >
      <ReactPlayer
        // TODO: cache the audio file fiercely
        url="/music/alert.mp3"
        playing={shouldDoNoise}
        volume={0.5}
        loop={true}
        width="0"
        height="0"
        playsinline
        className="absolute -z-10"
      />
    </div>
  );
};
