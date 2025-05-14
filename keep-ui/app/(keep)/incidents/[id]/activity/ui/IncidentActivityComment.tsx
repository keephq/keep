import { IncidentDto } from "@/entities/incidents/model";
import { Button } from "@tremor/react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { AuditEvent } from "@/entities/alerts/model";
import { CommentInput, extractTaggedUsers } from "./CommentInput";
import { useUsers } from "@/entities/users/model/useUsers";

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
  const { data: users = [], isLoading: usersLoading } = useUsers();

  const onSubmit = useCallback(async () => {
    try {
      // Extract tagged users from the comment content
      const extractedTaggedUsers = extractTaggedUsers(comment);

      // Combine with manually tracked tagged users
      const allTaggedUsers = [...new Set([...taggedUsers, ...extractedTaggedUsers])];

      await api.post(`/incidents/${incident.id}/comment`, {
        status: incident.status,
        comment,
        tagged_users: allTaggedUsers,
      });

      toast.success("Comment added!", { position: "top-right" });
      setComment("");
      setTaggedUsers([]);
      mutator();
    } catch (error) {
      showErrorToast(error, "Failed to add comment");
    }
  }, [api, incident.id, incident.status, comment, taggedUsers, mutator]);

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
    <div className="flex flex-col h-full w-full relative">
      <div className="w-full mb-3">
        <CommentInput
          value={comment}
          onValueChange={setComment}
          placeholder="Add a new comment... Type @ to mention users"
          users={users}
          onTagUser={(email) => {
            if (!taggedUsers.includes(email)) {
              setTaggedUsers([...taggedUsers, email]);
            }
          }}
        />
      </div>
      <div className="flex justify-end">
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
  );
}
