"use client";
import { useI18n } from "@/i18n/hooks/useI18n";
// Only import this component via dynamic(); react-quill and quill-mention are not SSR friendly

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { User } from "@/app/(keep)/settings/models";
import ReactQuill, { Quill } from "react-quill-new";
import { Mention, MentionBlot } from "quill-mention";
import "react-quill-new/dist/quill.snow.css";
import "./IncidentCommentInput.scss";
import clsx from "clsx";

/**
 * Props for the IncidentCommentInput component
 */
interface IncidentCommentInputProps {
  value: string;
  onValueChange: (value: string) => void;
  users: User[];
  placeholder?: string;
  className?: string;
}

/**
 * A comment input component with user mention functionality
 */
export function IncidentCommentInput({
  value,
  onValueChange,
  users,
  placeholder,
  className = "",
}: IncidentCommentInputProps) {
  const { t } = useI18n();
  const [isReady, setIsReady] = useState(false);

  // Use i18n for default placeholder
  const commentPlaceholder = placeholder || t("incidents.messages.addCommentPlaceholder");

  const usersRef = useRef(users);

  // Update ref when users change, to ensure the latest users are used in the suggestUsers function
  useEffect(() => {
    usersRef.current = users;
  }, [users]);

  useEffect(() => {
    Quill.register({
      "blots/mention": MentionBlot,
      "modules/mention": Mention,
    });
    setIsReady(true);
  }, []);

  const suggestUsers = async (searchTerm: string) => {
    // TODO: Implement API call to search for users?
    return usersRef.current
      .filter(
        (user) =>
          user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          user.email.toLowerCase().includes(searchTerm.toLowerCase())
      )
      .map((user) => ({
        id: user.email || "",
        value: user.name || user.email || "",
      }));
  };

  const quillModules = useMemo(
    () => ({
      toolbar: false,
      mention: {
        allowedChars: /^[\p{L}\p{N}\s]*$/u,
        mentionDenotationChars: ["@"],
        fixMentionsToQuill: false, // Important - allows the dropdown to position correctly
        defaultMenuOrientation: "bottom",
        blotName: "mention",
        mentionContainerClass: "mention-container",
        mentionListClass: "mention-list",
        listItemClass: "mention-item",
        showDenotationChar: true,
        source: async function (
          searchTerm: string,
          renderList: (values: any[], searchTerm: string) => void
        ) {
          const filteredUsers = await suggestUsers(searchTerm);

          if (filteredUsers.length === 0) {
            renderList([], searchTerm);
          } else {
            renderList(filteredUsers, searchTerm);
          }
        },
        onSelect: (
          item: { id: string; value: string },
          insertItem: (item: { id: string; value: string }) => void
        ) => {
          insertItem(item);
        },
        positioningStrategy: "fixed",
        renderLoading: () => document.createTextNode(t("common.actions.loading")),
        spaceAfterInsert: true,
      },
    }),
    // Empty array to initialize only once, since changing quillModules will re-initialize the component and it's broken
    []
  );

  const quillFormats = ["mention"];

  const handleChange = useCallback(
    (content: string) => {
      onValueChange(content);
    },
    [onValueChange]
  );

  if (!isReady) {
    return null;
  }

  return (
    <ReactQuill
      key="incident-comment-input"
      value={value}
      onChange={handleChange}
      modules={quillModules}
      formats={quillFormats}
      placeholder={commentPlaceholder}
      theme="snow"
      className={clsx("incident-comment-input", className)}
    />
  );
}
