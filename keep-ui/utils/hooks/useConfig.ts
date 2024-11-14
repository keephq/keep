import { ConfigContext } from "@/app/config-provider";
import { useContext } from "react";

export const useConfig = () => {
  const context = useContext(ConfigContext);

  if (context === undefined) {
    throw new Error("useConfig must be used within a ConfigProvider");
  }

  return {
    data: context,
  };
};

export const useApiUrl = () => {
  const { data: config } = useConfig();

  if (config?.API_URL_CLIENT) {
    return config.API_URL_CLIENT;
  }

  // can't access the API directly
  return "/backend";
};
