"use client";

import { User } from "@/app/(keep)/settings/models";
import { useEffect, useRef, useState } from "react";
import "react-quill-new/dist/quill.snow.css";
import "quill-mention/dist/quill.mention.css";
import dynamic from "next/dynamic";

// Import ReactQuill dynamically to avoid SSR issues
const ReactQuill = dynamic(() => import("react-quill-new"), { ssr: false });

interface QuillMentionsInputProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  users: User[];
  onTagUser?: (email: string) => void;
}

export function QuillMentionsInput({
  value,
  onValueChange,
  placeholder = "Add a new comment...",
  users,
  onTagUser,
}: QuillMentionsInputProps) {
  const [isClient, setIsClient] = useState(false);
  const quillRef = useRef<any>(null);
  const [taggedEmails, setTaggedEmails] = useState<string[]>([]);

  // Set isClient to true on component mount
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Track tagged users and notify parent component
  useEffect(() => {
    if (taggedEmails.length > 0 && onTagUser) {
      taggedEmails.forEach(email => {
        onTagUser(email);
      });
      // Reset the tagged emails after notifying
      setTaggedEmails([]);
    }
  }, [taggedEmails, onTagUser]);

  // Convert users to the format expected by quill-mention
  const mentionSources = users.map(user => ({
    id: user.email,
    value: user.name || user.email,
    email: user.email,
    // Add avatar URL if available
    avatar: user.avatar_url || null,
  }));

  // Quill modules configuration
  const modules = {
    toolbar: [
      ['bold', 'italic', 'underline'],
      [{ 'list': 'ordered' }, { 'list': 'bullet' }],
      ['link'],
    ],
    mention: {
      allowedChars: /^[A-Za-z\s0-9._-]*$/,
      mentionDenotationChars: ["@"],
      source: function(searchTerm: string, renderList: Function) {
        const matches = [];
        
        // Return all users if search term is empty
        if (searchTerm.length === 0) {
          renderList(mentionSources);
          return;
        }
        
        // Filter users based on search term
        const searchTermLower = searchTerm.toLowerCase();
        for (let i = 0; i < mentionSources.length; i++) {
          const source = mentionSources[i];
          if (
            source.value.toLowerCase().includes(searchTermLower) ||
            source.email.toLowerCase().includes(searchTermLower)
          ) {
            matches.push(source);
          }
        }
        
        renderList(matches, searchTerm);
      },
      // Custom rendering for mention items in the dropdown
      renderItem: function(item: any) {
        return `
          <div class="flex items-center p-2">
            <div class="flex-shrink-0 mr-2">
              ${item.avatar 
                ? `<img src="${item.avatar}" class="h-6 w-6 rounded-full" />` 
                : `<div class="h-6 w-6 rounded-full bg-gray-200 flex items-center justify-center text-xs">
                    ${item.value.charAt(0).toUpperCase()}
                  </div>`
              }
            </div>
            <div>
              <div class="font-medium">${item.value}</div>
              <div class="text-xs text-gray-500">${item.email}</div>
            </div>
          </div>
        `;
      },
      // Handle mention selection
      onSelect: function(item: any, insertItem: Function) {
        // Add the email to the list of tagged emails
        setTaggedEmails(prev => [...prev, item.email]);
        insertItem(item);
      }
    }
  };

  // Quill formats
  const formats = [
    'bold', 'italic', 'underline',
    'list', 'bullet',
    'link', 'mention'
  ];

  // Custom styles for the Quill editor
  const quillStyle = {
    border: '1px solid #e2e8f0',
    borderRadius: '0.375rem',
    minHeight: '100px',
  };

  // Only render ReactQuill on the client
  if (!isClient) {
    return <div className="border border-gray-200 rounded-md p-3 min-h-[100px]">{placeholder}</div>;
  }

  return (
    <div className="w-full">
      <ReactQuill
        ref={quillRef}
        value={value}
        onChange={onValueChange}
        modules={modules}
        formats={formats}
        placeholder={placeholder}
        theme="snow"
        style={quillStyle}
      />
    </div>
  );
}
