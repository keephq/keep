"use client";

import { Button } from "@tremor/react";
import { EmptyStateCard } from "@/shared/ui/EmptyState/EmptyStateCard";
import { MdFlashOn } from "react-icons/md";
import { useRouter } from "next/navigation";
import { useI18n } from "@/i18n/hooks/useI18n";

interface Props {
  onClearFilters: () => void;
}

export const IncidentsNotFoundForFiltersPlaceholder = ({
  onClearFilters,
}: Props) => {
  const { t } = useI18n();
  return (
    <EmptyStateCard
      icon={MdFlashOn}
      title={t("incidents.notFound.noIncidentsMatchingFilter")}
      description={t("incidents.notFound.clearFiltersToSeeAll")}
    >
      <Button onClick={() => onClearFilters()}>{t("common.actions.clear")}</Button>
    </EmptyStateCard>
  );
};

export const IncidentsNotFoundPlaceholder = () => {
  const router = useRouter();
  const { t } = useI18n();
  return (
    <EmptyStateCard
      icon={MdFlashOn}
      title={t("incidents.notFound.noIncidentsFound")}
      description={t("incidents.notFound.noActiveIncidents")}
    >
      <div className="flex gap-2">
        <Button
          color="orange"
          variant="secondary"
          size="md"
          onClick={() => {
            router.push(`/alerts/feed`);
          }}
        >
          {t("incidents.notFound.correlateManually")}
        </Button>
        <Button
          color="orange"
          variant="primary"
          size="md"
          onClick={() => {
            router.push(`/alerts/feed?createIncidentsFromLastAlerts=50`);
          }}
        >
          {t("incidents.notFound.tryAICorrelation")}
        </Button>
      </div>
    </EmptyStateCard>
  );
};
