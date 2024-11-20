"use client";

import { useRules } from "utils/hooks/useRules";
import { CorrelationPlaceholder } from "./CorrelationPlaceholder";
import { CorrelationTable } from "./CorrelationTable";
import Loading from "@/app/(keep)/loading";

export const Client = () => {
  const { data: rules = [], isLoading } = useRules();

  if (isLoading) {
    return <Loading />;
  }

  if (rules.length === 0) {
    return <CorrelationPlaceholder />;
  }

  return <CorrelationTable rules={rules} />;
};
