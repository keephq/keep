"use client";

import React, { useEffect, useState } from "react";
// https://github.com/zenoamaro/react-quill/issues/292
const ReactQuill =
  typeof window === "object" ? require("react-quill") : () => false;
import "react-quill/dist/quill.snow.css";
import { Button } from "@tremor/react";
import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui/utils/showErrorToast";

interface AlertNoteModalProps {
  handleClose: () => void;
  alert: AlertDto | null;
}

const AlertNoteModal = ({ handleClose, alert }: AlertNoteModalProps) => {
  const api = useApi();
  const [noteContent, setNoteContent] = useState<string>("");

  useEffect(() => {
    if (alert) {
      setNoteContent(alert.note || "");
    }
  }, [alert]);

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
      const response = await api.post(`/alerts/enrich`, requestData);

      handleNoteClose();
    } catch (error) {
      showErrorToast(error, "Failed to save note");
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
