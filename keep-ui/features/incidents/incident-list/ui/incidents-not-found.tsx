"use client";

import { Button } from "@tremor/react";
import { EmptyStateCard } from "@/shared/ui/EmptyState/EmptyStateCard";
import { MdFlashOn } from "react-icons/md";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

interface Props {
  onClearFilters: () => void;
}

export const IncidentsNotFoundForFiltersPlaceholder = ({
  onClearFilters,
}: Props) => {
  const t = useTranslations("incidents");
  return (
    <EmptyStateCard
      icon={MdFlashOn}
      title={t("noIncidentsMatchingFilter")}
      description={t("clearFiltersDesc")}
    >
      <Button onClick={() => onClearFilters()}>{t("clearFilters")}</Button>
    </EmptyStateCard>
  );
};

export const IncidentsNotFoundPlaceholder = () => {
  const t = useTranslations("incidents");
  const router = useRouter();
  return (
    <EmptyStateCard
      icon={MdFlashOn}
      title={t("noIncidentsFound")}
      description={t("noActiveIncidents")}
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
          {t("correlateManually")}
        </Button>
        <Button
          color="orange"
          variant="primary"
          size="md"
          onClick={() => {
            router.push(`/alerts/feed?createIncidentsFromLastAlerts=50`);
          }}
        >
          {t("tryAiCorrelation")}
        </Button>
      </div>
    </EmptyStateCard>
  );
};
