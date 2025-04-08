"use client";

import React, { useEffect, useState } from "react";
import "react-quill-new/dist/quill.snow.css";
import { Button } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import Modal from "@/components/ui/Modal";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import dynamic from "next/dynamic";

const ReactQuill = dynamic(() => import("react-quill-new"), { ssr: false });

interface AlertNoteModalProps {
  handleClose: () => void;
  alert: AlertDto | null;
  readOnly?: boolean;
}

export const AlertNoteModal = ({
  handleClose,
  alert,
  readOnly = false,
}: AlertNoteModalProps) => {
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
        note: noteContent,
        fingerprint: alert.fingerprint,
      };
      await api.post(`/alerts/enrich/note`, requestData);

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
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      beforeTitle={alert?.name}
      title="Add Note"
    >
      <div className="mt-4 border border-gray-200 rounded-lg overflow-hidden">
        {/* WYSIWYG editor */}
        <ReactQuill
          value={noteContent}
          onChange={(value: string) => setNoteContent(value)}
          theme="snow" // Use the Snow theme
          placeholder="Add your note here..."
          modules={readOnly ? { toolbar: [] } : modules}
          readOnly={readOnly}
          formats={formats} // Add formats
        />
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <Button // Use Tremor button for Cancel
          onClick={handleNoteClose}
          variant="secondary"
          color="orange"
        >
          {readOnly ? "Close" : "Cancel"}
        </Button>
        {!readOnly && (
          <Button // Use Tremor button for Save
            onClick={saveNote}
            color="orange"
          >
            Save
          </Button>
        )}
      </div>
    </Modal>
  );
};
