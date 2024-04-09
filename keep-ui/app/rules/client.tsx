"use client";

import { useRules } from "utils/hooks/useRules";
import { CorrelationPlaceholder } from "./CorrelationPlaceholder";
import { CorrelationTable } from "./CorrelationTable";

export const Client = () => {
  const { data: rules = [] } = useRules();

  if (rules.length === 0) {
    return <CorrelationPlaceholder />;
  }

  return <CorrelationTable rules={rules} />;
};
