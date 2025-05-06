"use client";

import React, { useState, useCallback, useMemo, useEffect } from "react";
import dynamic from "next/dynamic";
import { User } from "@/app/(keep)/settings/models";

// Declare Quill on the window object since quill-mention expects it to be there
declare global {
  interface Window {
    Quill: any;
  }
}

// Import required styles
import "react-quill-new/dist/quill.snow.css";
import "./IncidentCommentInput.scss";

// Simple dynamic import for ReactQuill - we'll handle the mention module in useEffect
const ReactQuill = dynamic(() => import("react-quill-new"), {
  ssr: false,
  loading: () => <div className="h-24 w-full rounded-md border border-gray-300 bg-gray-50 animate-pulse"></div>
});

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
  placeholder = "Add a comment...",
  className = "",
}: IncidentCommentInputProps) {
  const [mentionModuleReady, setMentionModuleReady] = useState(false);

  useEffect(() => {
    /**
     *
     * We load quill-mention via script injection rather than standard imports
     * to ensure proper loading sequence in Next.js. This approach guarantees that:
     * 1) Quill initializes before the mention module attempts to register,
     * 2) registration happens client-side only,
     * 3) we can observe when the module is fully ready before rendering the editor.
     * 
     * Standard imports were throwing "Cannot resolve module 'quill-mention'" error.
     * 
     * TODO: Ensure standard imports work.
     */
    async function loadQuillMentionModule() {
      if (typeof window !== 'undefined') {
        try {
          const cssId = 'quill-mention-css';
          if (!document.getElementById(cssId)) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = '/quill-mention.css';
            link.id = cssId;
            document.head.appendChild(link);
          }

          // Ensure Quill is available globally
          const ReactQuillModule = await import('react-quill-new');
          window.Quill = ReactQuillModule.default.Quill;

          // Register the mention format with Quill
          const Quill = window.Quill;

          if (!Quill.imports['formats/mention']) {
            const Embed = Quill.import('blots/embed');

            class MentionBlot extends Embed {
              static create(data: { id: string; value: string; denotationChar: string }) {
                const node = super.create();
                node.innerHTML = data.value;
                node.dataset.id = data.id;
                node.dataset.value = data.value;
                node.dataset.denotationChar = data.denotationChar;
                return node;
              }

              static value(node: HTMLElement) {
                return {
                  id: node.dataset.id || '',
                  value: node.dataset.value || '',
                  denotationChar: node.dataset.denotationChar || ''
                };
              }
            }

            MentionBlot.blotName = 'mention';
            MentionBlot.tagName = 'span';
            MentionBlot.className = 'mention';

            Quill.register('formats/mention', MentionBlot);
          }

          // Load the quill-mention module script
          const scriptId = 'quill-mention-script';
          if (!document.getElementById(scriptId)) {
            await new Promise<void>((resolve) => {
              const script = document.createElement('script');
              script.src = '/quill-mention.js';
              script.id = scriptId;
              script.async = false;
              script.onload = () => {
                setTimeout(() => {
                  setMentionModuleReady(true);
                  resolve();
                }, 100);
              };
              script.onerror = (e) => {
                console.error('Error loading QuillMention script:', e);
                resolve();
              };
              document.body.appendChild(script);
            });
          } else {
            await new Promise<void>(resolve => setTimeout(() => {
              setMentionModuleReady(true);
              resolve();
            }, 100));
          }
        } catch (error) {
          console.error('Error setting up quill-mention:', error);
        }
      }
    }

    loadQuillMentionModule();
  }, []);


  const [taggedUsers, setTaggedUsers] = useState<string[]>([]);

  const mentionUsers = useMemo(() => {
    return users.map((user) => ({
      id: user.email || "",
      value: user.name || user.email || ""
    }));
  }, [users]);

  const quillModules = useMemo(() => ({
    toolbar: false,
    mention: {
      allowedChars: /^[A-Za-z0-9\s]*$/,
      mentionDenotationChars: ["@"],
      fixMentionsToQuill: false,  // Important - allows the dropdown to position correctly
      defaultMenuOrientation: 'bottom',
      blotName: 'mention',
      mentionContainerClass: 'mention-container',
      mentionListClass: 'mention-list',
      listItemClass: 'mention-item',
      showDenotationChar: true,
      source: function (searchTerm: string, renderList: (values: any[], searchTerm: string) => void) {
        const filteredUsers = mentionUsers.filter(user =>
          user.value.toLowerCase().includes(searchTerm.toLowerCase()) ||
          user.id.toLowerCase().includes(searchTerm.toLowerCase())
        );

        if (filteredUsers.length === 0) {
          renderList([{ id: 'test', value: 'Test User' }], searchTerm);
        } else {
          renderList(filteredUsers, searchTerm);
        }
      },
      onSelect: (item: { id: string, value: string }, insertItem: (item: any) => void) => {
        insertItem(item);
      },
      positioningStrategy: 'fixed',
      renderLoading: () => document.createTextNode('Loading...'),
      spaceAfterInsert: true
    },
  }), [mentionUsers, taggedUsers]);

  const quillFormats = ["mention"];

  const handleChange = useCallback(
    (content: string) => {
      onValueChange(content);
    },
    [onValueChange]
  );

  return (
    <>
      <div className={`quill-editor-container ${className}`} style={{
        width: '100%',
        border: '1px solid #ccc',
        borderRadius: '4px',
        marginBottom: '0',
        position: 'relative'
      }}>
        {/* Only render ReactQuill when mention module is ready */}
        {mentionModuleReady ? (
          <ReactQuill
            key="quill-editor"
            value={value}
            onChange={handleChange}
            modules={quillModules}
            formats={quillFormats}
            placeholder={placeholder}
            theme="snow"
            className="quill-editor"
          />
        ) : (
          <div className="loading-editor" style={{
            padding: '20px',
            textAlign: 'center',
            color: '#666',
            backgroundColor: '#f9f9f9',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <span>Initializing rich text editor...</span>
          </div>
        )}
      </div>

      {/* All styles now imported from IncidentCommentInput.scss */}
    </>
  );
}

/**
 * Helper hook for components that need to access mentioned users
 * @returns A useState tuple for tracking tagged users
 */
export function useTaggedUsers() {
  return useState<string[]>([]);
}

/**
 * Extracts tagged user IDs from Quill editor content
 * This is called when a comment is submitted to get the final list of mentions
 * 
 * @param content - HTML content from the Quill editor
 * @returns Array of user IDs that were mentioned in the content
 */
export function extractTaggedUsers(content: string): string[] {
  const mentionRegex = /data-id="([^"]+)"/g;
  const matches = content.match(mentionRegex) || [];

  return matches
    .map(match => {
      const idMatch = match.match(/data-id="([^"]+)"/);
      return idMatch ? idMatch[1] : null;
    })
    .filter(Boolean) as string[];
}
