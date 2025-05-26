import { Tooltip } from "@/shared/ui";
import { InformationCircleIcon } from "@heroicons/react/24/outline";
import { Switch, Text } from "@tremor/react";

interface PresetControlsProps {
  isPrivate: boolean;
  setIsPrivate: (value: boolean) => void;
  isNoisy: boolean;
  setIsNoisy: (value: boolean) => void;
  counterShowsFiringOnly: boolean;
  setCounterShowsFiringOnly: (value: boolean) => void;
}

export const PresetControls: React.FC<PresetControlsProps> = ({
  isPrivate,
  setIsPrivate,
  isNoisy,
  setIsNoisy,
  counterShowsFiringOnly,
  setCounterShowsFiringOnly,
}) => {
  return (
    <div className="mt-4">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <Switch
            id="private"
            checked={isPrivate}
            onChange={() => setIsPrivate(!isPrivate)}
            color="orange"
          />
          <label htmlFor="private" className="text-sm text-gray-500">
            <Text>Private</Text>
          </label>
          <Tooltip
            content={<>Private presets are only visible to you</>}
            className="z-60"
          >
            <InformationCircleIcon className="w-4 h-4" />
          </Tooltip>
        </div>

        <div className="flex items-center gap-2">
          <Switch
            id="noisy"
            checked={isNoisy}
            onChange={() => setIsNoisy(!isNoisy)}
            color="orange"
          />
          <label htmlFor="noisy" className="text-sm text-gray-500">
            <Text>Noisy</Text>
          </label>
          <Tooltip
            content={
              <>Noisy presets will trigger sound for every matching event</>
            }
            className="z-60"
          >
            <InformationCircleIcon className="w-4 h-4" />
          </Tooltip>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            data-testid="counter-shows-firing-only-switch"
            id="counterShowsFiringOnly"
            checked={counterShowsFiringOnly}
            onChange={() => setCounterShowsFiringOnly(!counterShowsFiringOnly)}
            color="orange"
          />
          <label
            htmlFor="counterShowsFiringOnly"
            className="text-sm text-gray-500"
          >
            <Text>Firing alerts counter mode</Text>
          </label>
          <Tooltip
            content={
              <>
                Indicates whether the counter in the navbar shows only firing
                alerts or all matching alerts for this preset
              </>
            }
            className="z-60"
          >
            <InformationCircleIcon className="w-4 h-4" />
          </Tooltip>
        </div>
      </div>
    </div>
  );
};
