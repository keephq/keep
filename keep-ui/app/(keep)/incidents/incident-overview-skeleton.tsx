import Skeleton from "react-loading-skeleton";
import { FieldHeader } from "@/shared/ui";
import { useTranslations } from "next-intl";

export function IncidentOverviewSkeleton() {
  const t = useTranslations("incidents");

  return (
    <div className="flex gap-6 items-start w-full pb-4 text-tremor-default">
      <div className="basis-2/3 grow">
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="max-w-2xl">
            <FieldHeader>{t("labels.summary")}</FieldHeader>
            <Skeleton count={3} />
          </div>
          <div className="flex flex-col gap-2">
            <FieldHeader>{t("labels.involvedServices")}</FieldHeader>
            <div className="flex flex-wrap gap-1">
              <Skeleton width={80} />
              <Skeleton width={100} />
              <Skeleton width={90} />
            </div>
          </div>
          <div>
            <Skeleton count={2} />
          </div>
          <div>
            <Skeleton count={2} />
          </div>
        </div>
      </div>
      <div className="pr-10 grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="xl:col-span-2">
          <FieldHeader>{t("status.title")}</FieldHeader>
          <Skeleton height={38} />
        </div>
        <div>
          <FieldHeader>{t("labels.lastSeenAt")}</FieldHeader>
          <Skeleton />
        </div>
        <div>
          <FieldHeader>{t("labels.startedAt")}</FieldHeader>
          <Skeleton />
        </div>
        <div>
          <FieldHeader>{t("labels.assignee")}</FieldHeader>
          <Skeleton />
        </div>
        <div>
          <FieldHeader>{t("labels.groupedBy")}</FieldHeader>
          <Skeleton />
        </div>
      </div>
    </div>
  );
}
