import { useCallback, useEffect, useRef } from "react";
import { useWebsocket } from "@/utils/hooks/usePusher";
import { useRevalidateMultiple } from "@/shared/lib/state-utils";

const PRESET_POLLING_INTERVAL = 5 * 1000; // Once per 5 seconds

export function usePresetPolling() {
  const { bind, unbind } = useWebsocket();
  const revalidateMultiple = useRevalidateMultiple();
  const lastPollTimeRef = useRef(0);

  const handleIncoming = useCallback(
    (presetNamesToUpdate: string[]) => {
      const currentTime = Date.now();
      const timeSinceLastPoll = currentTime - lastPollTimeRef.current;

      if (timeSinceLastPoll < PRESET_POLLING_INTERVAL) {
        console.log("usePresetPolling: Ignoring poll due to short interval");
        return;
      }

      console.log("usePresetPolling: Revalidating preset data");
      lastPollTimeRef.current = currentTime;
      revalidateMultiple(["/preset", "/preset?"], {
        isExact: true,
      });
    },
    [revalidateMultiple]
  );

  useEffect(() => {
    console.log(
      "usePresetPolling: Setting up event listener for 'poll-presets'"
    );
    bind("poll-presets", handleIncoming);
    return () => {
      console.log(
        "usePresetPolling: Cleaning up event listener for 'poll-presets'"
      );
      unbind("poll-presets", handleIncoming);
    };
  }, [bind, unbind, handleIncoming]);
}
