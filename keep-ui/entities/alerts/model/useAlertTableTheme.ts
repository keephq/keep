import { severityMapping } from "@/entities/alerts/model/index";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";

export function useAlertTableTheme() {
  const [theme, setTheme] = useLocalStorage(
    "alert-table-theme",
    Object.values(severityMapping).reduce<{ [key: string]: string }>(
      (acc, severity) => {
        acc[severity] = "bg-white";
        return acc;
      },
      {}
    )
  );

  return { theme, setTheme };
}
