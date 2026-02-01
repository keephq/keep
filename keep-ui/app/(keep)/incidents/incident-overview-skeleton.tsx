import Skeleton from "react-loading-skeleton";
import { FieldHeader } from "@/shared/ui";

export function IncidentOverviewSkeleton() {
  return (
    <div className="flex gap-6 items-start w-full pb-4 text-tremor-default">
      <div className="basis-2/3 grow">
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="max-w-2xl">
            <FieldHeader>Summary</FieldHeader>
            <Skeleton count={3} />
          </div>
          <div className="flex flex-col gap-2">
            <FieldHeader>Involved services</FieldHeader>
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
          <FieldHeader>Status</FieldHeader>
          <Skeleton height={38} />
        </div>
        <div>
          <FieldHeader>Last Incident Activity</FieldHeader>
          <Skeleton />
        </div>
        <div>
          <FieldHeader>Started at</FieldHeader>
          <Skeleton />
        </div>
        <div>
          <FieldHeader>Assignee</FieldHeader>
          <Skeleton />
        </div>
        <div>
          <FieldHeader>Group by value</FieldHeader>
          <Skeleton />
        </div>
      </div>
    </div>
  );
}
