"use client";

import React, { useEffect, useState } from "react";
// https://github.com/zenoamaro/react-quill/issues/292
const ReactQuill =
  typeof window === "object" ? require("react-quill") : () => false;
import "react-quill/dist/quill.snow.css";
import { Button } from "@tremor/react";
import { useApiUrl } from "utils/hooks/useConfig";
import { useSession } from "next-auth/react";
import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";

interface AlertNoteModalProps {
  handleClose: () => void;
  alert: AlertDto | null;
}

const AlertNoteModal = ({ handleClose, alert }: AlertNoteModalProps) => {
  const [noteContent, setNoteContent] = useState<string>("");

  useEffect(() => {
    if (alert) {
      setNoteContent(alert.note || "");
    }
  }, [alert]);
  // get the session
  const { data: session } = useSession();
  const apiUrl = useApiUrl();

  // if this modal should not be open, do nothing
  if (!alert) return null;

  const formats = [
    "header",
    "bold",
    "italic",
    "underline",
    "list",
    "bullet",
    "link",
    "align",
    "blockquote",
    "code-block",
    "color",
  ];

  const modules = {
    toolbar: [
      [{ header: "1" }, { header: "2" }],
      [{ list: "ordered" }, { list: "bullet" }],
      ["bold", "italic", "underline"],
      ["link"],
      [{ align: [] }],
      ["blockquote", "code-block"], // Add quote and code block options to the toolbar
      [{ color: [] }], // Add color option to the toolbar
    ],
  };

  const saveNote = async () => {
    try {
      // build the formData
      const requestData = {
        enrichments: {
          note: noteContent,
        },
        fingerprint: alert.fingerprint,
      };
      const response = await fetch(`${apiUrl}/alerts/enrich`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify(requestData),
      });

      if (response.ok) {
        // Handle success
        console.log("Note saved successfully");
        handleNoteClose();
      } else {
        // Handle error
        console.error("Failed to save note");
      }
    } catch (error) {
      // Handle unexpected error
      console.error("An unexpected error occurred");
    }
  };

  const isOpen = alert !== null;

  const handleNoteClose = () => {
    alert.note = noteContent;
    setNoteContent("");
    handleClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose}>
      {/* WYSIWYG editor */}
      <ReactQuill
        value={noteContent}
        onChange={(value: string) => setNoteContent(value)}
        theme="snow" // Use the Snow theme
        placeholder="Add your note here..."
        modules={modules}
        formats={formats} // Add formats
      />
      <div className="mt-4 flex justify-end">
        <Button // Use Tremor button for Save
          onClick={saveNote}
          color="orange"
          className="mr-2"
        >
          Save
        </Button>
        <Button // Use Tremor button for Cancel
          onClick={handleNoteClose}
          variant="secondary"
          color="orange"
        >
          Cancel
        </Button>
      </div>
    </Modal>
  );
};

export default AlertNoteModal;
