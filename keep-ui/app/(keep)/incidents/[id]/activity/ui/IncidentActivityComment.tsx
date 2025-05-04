import { IncidentDto } from "@/entities/incidents/model";
import { Button } from "@tremor/react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { AuditEvent } from "@/entities/alerts/model";
import { MentionsInput } from "./MentionsInput";
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
      await api.post(`/incidents/${incident.id}/comment`, {
        status: incident.status,
        comment,
        tagged_users: taggedUsers,
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
    <div className="flex h-full w-full relative items-center">
      <MentionsInput
        value={comment}
        onValueChange={setComment}
        placeholder="Add a new comment... Use @ to mention users"
        users={users}
        onTagUser={(email) => {
          if (!taggedUsers.includes(email)) {
            setTaggedUsers([...taggedUsers, email]);
          }
        }}
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
