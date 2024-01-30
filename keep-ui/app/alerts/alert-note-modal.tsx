'use client';

import React, { useContext, useState } from 'react';
const ReactQuill = typeof window === 'object' ? require('react-quill') : () => false;
import 'react-quill/dist/quill.snow.css';
import { Button } from '@tremor/react';
import { getApiURL } from '../../utils/apiUrl';
import { useSession } from 'next-auth/react';
import { useModal } from './modal-context';

interface AlertNoteModalProps {
  isOpenKey: string;
  initialContent: string;
  alertFingerprint: string;
}

const AlertNoteModal: React.FC<AlertNoteModalProps> = ({
    isOpenKey,
    initialContent,
    alertFingerprint
  }) => {
    const [noteContent, setNoteContent] = useState<string>(initialContent);
    const { modals, closeModal } = useModal();
    const isOpen = modals[isOpenKey];

    const handleClose = () => {
        closeModal(isOpenKey);
      };
    // get the session
    const { data: session } = useSession();

    const formats = [
      'header',
      'bold',
      'italic',
      'underline',
      'list',
      'bullet',
      'link',
      'align',
      'blockquote', // Add quote format
      'code-block', // Add code block format
      'color', // Add color format
    ];

    const modules = {
      toolbar: [
        [{ header: '1' }, { header: '2' }, { font: [] }],
        [{ list: 'ordered' }, { list: 'bullet' }],
        ['bold', 'italic', 'underline'],
        ['link'],
        [{ align: [] }],
        ['blockquote', 'code-block'], // Add quote and code block options to the toolbar
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
          fingerprint: alertFingerprint,
        };
        const response = await fetch(`${getApiURL()}/alerts/enrich`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${session?.accessToken}`,
          },
          body: JSON.stringify(requestData),
        });

        if (response.ok) {
          // Handle success
          console.log('Note saved successfully');
          handleClose(); // Close the modal on success
        } else {
          // Handle error
          console.error('Failed to save note');
        }
      } catch (error) {
        // Handle unexpected error
        console.error('An unexpected error occurred');
      }
    };

    return (
      <div className={`fixed inset-0 z-10 ${isOpen ? 'block' : 'hidden'}`}>
        <div className="flex items-center justify-center bg-black bg-opacity-30 inset-0 absolute">
          <div className="bg-white p-6 rounded-lg" style={{ width: '600px' }}> {/* Increase the width */}
            <div className="text-lg font-semibold mb-4">Add/Edit Note</div>
            {/* WYSIWYG editor */}
            <ReactQuill
              value={noteContent}
              onChange={(value) => setNoteContent(value)}
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
                onClick={handleClose}
                variant="secondary"
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  export default AlertNoteModal;
