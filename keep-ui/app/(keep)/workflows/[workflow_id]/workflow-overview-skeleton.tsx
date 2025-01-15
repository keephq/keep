import Skeleton from "react-loading-skeleton";

export function WorkflowOverviewSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <div>
          <Skeleton className="h-24" />
        </div>
        <div>
          <Skeleton className="h-24" />
        </div>
        <div>
          <Skeleton className="h-24" />
        </div>
        <div>
          <Skeleton className="h-24" />
        </div>
        <div>
          <Skeleton className="h-24" />
        </div>
      </div>
      <div className="flex flex-col gap-4">
        <Skeleton className="h-32" />
      </div>
    </div>
  );
}
