"use client";

import { Fragment, useState } from "react";
import { Button } from "@tremor/react";
import { CorrelationSidebar } from "./CorrelationSidebar";
import { PlaceholderSankey } from "./ui/PlaceholderSankey";
import { PlusIcon } from "@heroicons/react/20/solid";
import { EmptyStateCard } from "@/shared/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

export const CorrelationPlaceholder = () => {
  const { t } = useI18n();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const onCorrelationClick = () => {
    setIsSidebarOpen(true);
  };

  return (
    <Fragment>
      <EmptyStateCard
        noCard
        className="h-full"
        title={t("rules.correlation.messages.noCorrelations")}
        description={t("rules.correlation.messages.noCorrelationsDescription")}
      >
        <Button
          className="mb-10"
          color="orange"
          variant="primary"
          size="md"
          onClick={() => onCorrelationClick()}
          icon={PlusIcon}
        >
          {t("rules.correlation.addRule")}
        </Button>
        <PlaceholderSankey className="max-w-full" />
      </EmptyStateCard>
      <CorrelationSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(!isSidebarOpen)}
      />
    </Fragment>
  );
};
