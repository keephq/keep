import { IncidentDto } from "@/entities/incidents/model";
import { AuditEvent } from "@/utils/hooks/useAlerts";
import { useApiUrl } from "@/utils/hooks/useConfig";
import { TextInput, Button } from "@tremor/react";
import { useSession } from "next-auth/react";
import { useState, useCallback, useEffect } from "react";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";

export function IncidentActivityComment({
  incident,
  mutator,
}: {
  incident: IncidentDto;
  mutator: KeyedMutator<AuditEvent[]>;
}) {
  const [comment, setComment] = useState("");
  const apiUrl = useApiUrl();
  const { data: session } = useSession();

  const onSubmit = useCallback(async () => {
    const response = await fetch(`${apiUrl}/incidents/${incident.id}/comment`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status: incident.status,
        comment: comment,
      }),
    });
    if (response.ok) {
      toast.success("Comment added!", { position: "top-right" });
      setComment("");
      mutator();
    } else {
      toast.error("Failed to add comment", { position: "top-right" });
    }
  }, [
    apiUrl,
    incident.id,
    incident.status,
    comment,
    session?.accessToken,
    mutator,
  ]);

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
