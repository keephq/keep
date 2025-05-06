import { IncidentDto } from "@/entities/incidents/model";
import { Button } from "@tremor/react";
import { useState, useCallback } from "react";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { AuditEvent } from "@/entities/alerts/model";
import { useUsers } from "@/entities/users/model/useUsers";
import { IncidentCommentInput, extractTaggedUsers } from "./IncidentCommentInput";

/**
 * Component for adding comments to an incident with user mention capability
 */
export function IncidentActivityComment({
  incident,
  mutator,
}: {
  incident: IncidentDto;
  mutator: KeyedMutator<AuditEvent[]>;
}) {
  const [comment, setComment] = useState("");
  const [taggedUsers, setTaggedUsers] = useState<string[]>([]);
  
  const api = useApi();
  
  const { data: users = [] } = useUsers();
  const onSubmit = useCallback(async () => {
    try {
      const extractedTaggedUsers = extractTaggedUsers(comment);
      console.log('Extracted tagged users:', extractedTaggedUsers);
      
      await api.post(`/incidents/${incident.id}/comment`, {
        status: incident.status,
        comment,
        tagged_users: extractedTaggedUsers,
      });
      toast.success("Comment added!", { position: "top-right" });
      setComment("");
      setTaggedUsers([]);
      mutator();
    } catch (error) {
      showErrorToast(error, "Failed to add comment");
    }
  }, [api, incident.id, incident.status, comment, mutator]);

  return (
    <div className="relative border border-gray-300 rounded-md mb-4">
      <div className="flex flex-col p-2.5 gap-2.5">
        <div className="w-full">
          <IncidentCommentInput
            value={comment}
            onValueChange={setComment}
            users={users}
            placeholder="Add a comment..."
            className="comment-editor"
          />
        </div>

        <div className="flex justify-end mt-2">
          <Button
            color="orange"
            variant="secondary"
            disabled={!comment}
            onClick={onSubmit}
          >
            Comment
          </Button>
        </div>
      </div>
    </div>
  );
}
