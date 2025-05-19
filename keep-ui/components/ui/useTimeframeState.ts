import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  AbsoluteTimeFrame,
  AllTimeFrame,
  areTimeframesEqual,
  RelativeTimeFrame,
  TimeFrameV2,
} from "./DateRangePickerV2";

const defaultOptions = {
  enableQueryParams: false,
  defaultTimeframe: {
    type: "all-time",
    isPaused: false,
  } as AllTimeFrame,
};

function getTimeframeInitialState(defaultTimeframe: TimeFrameV2): TimeFrameV2 {
  const searchParams = new URLSearchParams(window.location.search);
  const type = searchParams.get("timeFrameType");

  if (!type) {
    return defaultTimeframe;
  }

  switch (type) {
    case "absolute": {
      const startDate = Number.parseInt(
        searchParams.get("startDate") as string
      );
      const endDate = Number.parseInt(searchParams.get("endDate") as string);

      if (!startDate || !endDate) {
        break;
      }

      return {
        type: "absolute",
        start: new Date(startDate),
        end: new Date(endDate),
      } as AbsoluteTimeFrame;
    }

    case "relative": {
      const deltaMs = Number.parseInt(searchParams.get("deltaMs") as string);

      if (!deltaMs) {
        break;
      }

      const isPaused = searchParams.get("isPaused") === "true";

      return {
        type: "relative",
        deltaMs,
        isPaused,
      } as RelativeTimeFrame;
    }

    case "all-time": {
      return {
        type: "all-time",
        isPaused: searchParams.get("isPaused") === "true",
      } as AllTimeFrame;
    }
  }

  return defaultTimeframe;
}

function deleteTimeframeParams(searchParams: URLSearchParams) {
  ["timeFrameType", "startDate", "endDate", "deltaMs", "isPaused"].forEach(
    (timeframePropName) => searchParams.delete(timeframePropName)
  );
}

export function useTimeframeState({
  enableQueryParams,
  defaultTimeframe,
}: typeof defaultOptions) {
  const defaultTimeframeRef = useRef<TimeFrameV2>();
  defaultTimeframeRef.current =
    defaultTimeframe || defaultOptions.defaultTimeframe;

  const pathname = usePathname();
  const [timeframeState, setTimeframeState] = useState<TimeFrameV2 | null>(
    () => {
      return getTimeframeInitialState(defaultTimeframe);
    }
  );

  useEffect(() => {
    return () => {
      const newParams = new URLSearchParams(window.location.search);
      deleteTimeframeParams(newParams);
      const queryString = newParams.toString();
      window.history.replaceState(
        null,
        "",
        window.location.pathname + (queryString ? `?${queryString}` : "")
      );
    };
  }, [pathname]);

  useEffect(() => {
    if (!enableQueryParams || !timeframeState) return;

    const params = new URLSearchParams(window.location.search);
    deleteTimeframeParams(params);

    if (
      timeframeState &&
      !areTimeframesEqual(
        timeframeState,
        defaultTimeframeRef.current as TimeFrameV2
      )
    ) {
      switch (timeframeState.type) {
        case "absolute":
          params.set("timeFrameType", "absolute");
          params.set("startDate", String(timeframeState.start.getTime()));
          params.set("endDate", String(timeframeState.end.getTime()));
          break;

        case "relative":
          params.set("timeFrameType", "relative");
          params.set("deltaMs", String(timeframeState.deltaMs));
          params.set("isPaused", String(timeframeState.isPaused));
          break;

        case "all-time":
          params.set("timeFrameType", "all-time");
          params.set("isPaused", String(timeframeState.isPaused));
          break;
      }
    }
    const queryString = params.toString();

    window.history.replaceState(
      null,
      "",
      window.location.pathname + (queryString ? `?${queryString}` : "")
    );
  }, [timeframeState, enableQueryParams]);

  return [timeframeState, setTimeframeState] as const;
}
