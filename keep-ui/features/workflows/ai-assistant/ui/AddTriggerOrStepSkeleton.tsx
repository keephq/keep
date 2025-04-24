import Skeleton from "react-loading-skeleton";

export const AddTriggerOrStepSkeleton = () => {
  return (
    <div className="flex flex-col gap-2">
      <div className="h-4 w-full">
        <Skeleton />
      </div>
      <div className="h-4 w-1/2">
        <Skeleton />
      </div>
      <div className="h-12 max-w-[250px] w-full rounded-md">
        <Skeleton className="w-full h-full" />
      </div>
    </div>
  );
};
