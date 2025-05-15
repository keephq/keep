import {
  ReadonlyURLSearchParams,
  usePathname,
  useSearchParams,
} from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  AbsoluteTimeFrame,
  AllTimeFrame,
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

function getTimeframeInitialState(
  searchParams: ReadonlyURLSearchParams,
  defaultTimeframe: TimeFrameV2
): TimeFrameV2 {
  const type = searchParams.get("timeFrameType");

  if (type === "absolute") {
    const startDate = Number.parseInt(searchParams.get("startDate") as string);
    const endDate = Number.parseInt(searchParams.get("endDate") as string);

    if (startDate && endDate) {
      return {
        type: "absolute",
        start: new Date(startDate),
        end: new Date(endDate),
      } as AbsoluteTimeFrame;
    }
  }

  if (type === "relative") {
    const deltaMs = Number.parseInt(searchParams.get("deltaMs") as string);

    if (deltaMs) {
      const isPaused = searchParams.get("isPaused") === "true";

      return {
        type: "relative",
        deltaMs,
        isPaused,
      } as RelativeTimeFrame;
    }
  }

  if (type === "all-time") {
    return {
      type: "all-time",
      isPaused: searchParams.get("isPaused") === "true",
    } as AllTimeFrame;
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
  if (!defaultTimeframe) {
    defaultTimeframe = defaultOptions.defaultTimeframe;
  }

  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const [timeframeState, setTimeframeState] = useState<TimeFrameV2 | null>(
    () => {
      return getTimeframeInitialState(
        searchParams,
        defaultOptions.defaultTimeframe
      );
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
        window.location.pathname + queryString ? `?${queryString}` : ""
      );
    };
  }, [pathname]);

  useEffect(() => {
    if (!enableQueryParams) return;

    const params = new URLSearchParams(window.location.search);

    deleteTimeframeParams(params);

    if (timeframeState) {
      if (timeframeState.type === "absolute") {
        params.set("timeFrameType", "absolute");
        params.set("startDate", String(timeframeState.start.getTime()));
        params.set("endDate", String(timeframeState.end.getTime()));
      }

      if (timeframeState.type === "relative") {
        params.set("timeFrameType", "relative");
        params.set("deltaMs", String(timeframeState.deltaMs));
        params.set("isPaused", String(timeframeState.isPaused));
      }
      if (timeframeState.type === "all-time") {
        params.set("timeFrameType", "all-time");
        params.set("isPaused", String(timeframeState.isPaused));
      }
    }
    const queryString = params.toString();

    window.history.replaceState(
      null,
      "",
      window.location.pathname + queryString ? `?${queryString}` : ""
    );
  }, [timeframeState, enableQueryParams]);

  return [timeframeState, setTimeframeState] as const;
}
