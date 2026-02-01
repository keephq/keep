import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { DEFAULT_ROW_STYLE } from "./constants";

export type RowStyle = "relaxed" | "default";

export const useAlertRowStyle = () => {
  const [rowStyle, setRowStyle] = useLocalStorage<RowStyle>(
    "alert-table-row-style",
    DEFAULT_ROW_STYLE
  );

  return [rowStyle, setRowStyle] as const;
};
