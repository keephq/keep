import { WorkflowSteps } from "../workflows-templates";
import { WorkflowTemplate } from "@/shared/api/workflows";
import { Button, Card } from "@tremor/react";
import { useRouter } from "next/navigation";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";

export const WorkflowTemplateCard: React.FC<{ template: WorkflowTemplate }> = ({
  template,
}) => {
  const router = useRouter();
  const handlePreview = (template: WorkflowTemplate) => {
    localStorage.setItem("preview_workflow", JSON.stringify(template));
    router.push(`/workflows/preview/${template.workflow_raw_id}`);
  };
  const getNameFromId = (id: string) => {
    if (!id) {
      return "";
    }
    return id.split("-").join(" ");
  };
  return (
    <Card
      className="p-4 flex flex-col justify-between w-full border-2 border-transparent hover:border-orange-400 gap-2"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        handlePreview(template);
      }}
    >
      <div className="min-h-36">
        {template && <WorkflowSteps workflow={template.workflow} />}
        {!template && <Skeleton className="h-4 w-16 mb-2" />}
        <h3 className="text-lg sm:text-xl font-semibold line-clamp-2">
          {template && getNameFromId(template.workflow.id)}
          {!template && <Skeleton className="h-4 w-28 mb-2" />}
        </h3>
        <p className="mt-2 text-sm sm:text-base line-clamp-3">
          {template && template.workflow.description}
          {!template && <Skeleton className="h-16 w-full mb-2" />}
        </p>
      </div>
      <div>
        {template && (
          <Button
            variant="secondary"
            //   disabled={!!(loadingId && loadingId !== workflow.id)}
            //   loading={loadingId === workflow.id}
          >
            Preview
          </Button>
        )}
      </div>
    </Card>
  );
};
