import { IncidentDto } from "@/entities/incidents/model";
import { TextInput, Button } from "@tremor/react";
import { useState, useCallback, useEffect, useRef } from "react";
import { toast } from "react-toastify";
import { KeyedMutator } from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { AuditEvent } from "@/entities/alerts/model";
import { UserMention } from "@/entities/incidents/ui/UserMention";
import { UserDto } from "@/types/users";

interface MentionState {
  isActive: boolean;
  startPosition: number;
  searchText: string;
  position: { top: number; left: number };
}

export function IncidentActivityComment({
  incident,
  mutator,
}: {
  incident: IncidentDto;
  mutator: KeyedMutator<AuditEvent[]>;
}) {
  const [comment, setComment] = useState("");
  const [mentionState, setMentionState] = useState<MentionState>({
    isActive: false,
    startPosition: 0,
    searchText: "",
    position: { top: 0, left: 0 },
  });
  const inputRef = useRef<HTMLInputElement>(null);
  const api = useApi();

  const handleUserMention = useCallback((user: UserDto) => {
    const beforeMention = comment.slice(0, mentionState.startPosition - 1);
    const afterMention = comment.slice(mentionState.startPosition + mentionState.searchText.length);
    const newComment = `${beforeMention}@${user.email}${afterMention}`;
    setComment(newComment);
    setMentionState((prev: MentionState) => ({ ...prev, isActive: false, searchText: "" }));
    inputRef.current?.focus();
  }, [comment, mentionState]);

  const handleInputChange = useCallback((value: string) => {
    setComment(value);
    
    // Handle @ mentions
    const cursorPosition = inputRef.current?.selectionStart || 0;
    const textBeforeCursor = value.slice(0, cursorPosition);
    const lastAtSymbol = textBeforeCursor.lastIndexOf("@");
    
    if (lastAtSymbol !== -1 && lastAtSymbol === textBeforeCursor.length - 1) {
      // Start of mention
      const rect = inputRef.current?.getBoundingClientRect();
      setMentionState({
        isActive: true,
        startPosition: cursorPosition,
        searchText: "",
        position: {
          top: (rect?.bottom || 0) + window.scrollY + 5,
          left: (rect?.left || 0) + window.scrollX,
        },
      });
    } else if (mentionState.isActive) {
      // Update mention search
      const searchText = textBeforeCursor.slice(mentionState.startPosition);
      if (searchText.match(/^[a-zA-Z0-9@._-]*$/)) {
        setMentionState((prev: MentionState) => ({ ...prev, searchText }));
      } else {
        setMentionState((prev: MentionState) => ({ ...prev, isActive: false }));
      }
    }
  }, [mentionState]);

  const onSubmit = useCallback(async () => {
    try {
      // Extract mentioned users from the comment
      const matches = comment.matchAll(/@([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/g);
      const mentionedUsers = Array.from(matches).map(match => match[1]);

      await api.post(`/incidents/${incident.id}/comment`, {
        status: incident.status,
        comment,
        mentioned_users: mentionedUsers,
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
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey) && comment) {
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
        ref={inputRef}
        value={comment}
        onValueChange={handleInputChange}
        placeholder="Add a new comment... Use @ to mention users"
      />
      {mentionState.isActive && (
        <UserMention
          searchText={mentionState.searchText}
          position={mentionState.position}
          onSelect={handleUserMention}
          onClose={() => setMentionState((prev: MentionState) => ({ ...prev, isActive: false }))}
        />
      )}
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
