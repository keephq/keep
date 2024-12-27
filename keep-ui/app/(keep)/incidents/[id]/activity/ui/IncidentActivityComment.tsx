import { IncidentDto } from "@/entities/incidents/model";
import { AuditEvent } from "@/utils/hooks/useAlerts";
import { TextInput, Button } from "@tremor/react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";

export function IncidentActivityComment({
  incident,
  mutator,
}: {
  incident: IncidentDto;
  mutator: KeyedMutator<AuditEvent[]>;
}) {
  const [comment, setComment] = useState("");
  const api = useApi();

  const onSubmit = useCallback(async () => {
    try {
      const response = await api.post(`/incidents/${incident.id}/comment`, {
        status: incident.status,
        comment,
      });
      toast.success("Comment added!", { position: "top-right" });
      setComment("");
      mutator();
    } catch (error) {
      showErrorToast(error, "Failed to add comment");
    }
  }, [api, incident.id, incident.status, comment, mutator]);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (
        event.key === "Enter" &&
        (event.metaKey || event.ctrlKey) &&
        comment
      ) {
        onSubmit();
      }
    },
    [onSubmit, comment]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [comment, handleKeyDown]);

  return (
    <div className="flex h-full w-full relative items-center">
      <TextInput
        value={comment}
        onValueChange={setComment}
        placeholder="Add a new comment..."
      />
      <Button
        color="orange"
        variant="secondary"
        className="ml-2.5"
        disabled={!comment}
        onClick={onSubmit}
      >
        Comment
      </Button>
    </div>
  );
}
