export const TIMEFRAME_UNITS_TO_SECONDS = {
  seconds: (amount: number) => amount,
  minutes: (amount: number) => 60 * amount,
  hours: (amount: number) => 3600 * amount,
  days: (amount: number) => 86400 * amount,
} as const;
