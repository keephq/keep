"use client";

import { User } from "@/app/(keep)/settings/models";
import { useEffect, useRef, useState, useMemo } from "react";
import "react-quill-new/dist/quill.snow.css";
import "./quill-mention.css";
import dynamic from "next/dynamic";

// Add TypeScript declaration for the global Quill object
declare global {
  interface Window {
    Quill: any;
  }
}

/**
 * A function that extracts tagged user emails from Quill content
 * @param content HTML content from Quill editor
 * @returns Array of email addresses that were mentioned
 */
export function extractTaggedUsers(content: string): string[] {
  if (!content) return [];

  // Extract data-id attributes from mention spans
  const mentionRegex = /data-id="([^"]+)"/g;
  const matches = content.match(mentionRegex) || [];

  return matches
    .map(match => {
      const idMatch = match.match(/data-id="([^"]+)"/);
      return idMatch ? idMatch[1] : null;
    })
    .filter(Boolean) as string[];
}

// Import ReactQuill dynamically to avoid SSR issues
const ReactQuill = dynamic(
  () => {
    return new Promise((resolve) => {
      // First, dynamically import ReactQuill
      import("react-quill-new").then((ReactQuill) => {
        // Create a wrapper component that handles Quill initialization
        const QuillWithMentions = (props: any) => {
          const [quillLoaded, setQuillLoaded] = useState(false);
          const quillRef = useRef<any>(null);

          // Initialize Quill and mention module
          useEffect(() => {
            // Function to initialize Quill with mention module
            const initQuill = async () => {
              try {
                // Make Quill available globally
                if (typeof window !== 'undefined') {
                  // Set Quill on the window object
                  window.Quill = ReactQuill.default.Quill;

                  // Load CSS for mentions
                  if (!document.getElementById('quill-mention-css')) {
                    const link = document.createElement('link');
                    link.rel = 'stylesheet';
                    link.href = '/quill-mention.css';
                    link.id = 'quill-mention-css';
                    document.head.appendChild(link);
                  }

                  // Register the mention format
                  const Quill = ReactQuill.default.Quill;
                  const Embed = Quill.import('blots/embed');

                  // Register all formats that we'll use to prevent console errors
                  if (!Quill.imports['formats/bold']) {
                    const Bold = Quill.import('formats/bold');
                    Quill.register('formats/bold', Bold, true);
                  }

                  if (!Quill.imports['formats/italic']) {
                    const Italic = Quill.import('formats/italic');
                    Quill.register('formats/italic', Italic, true);
                  }

                  if (!Quill.imports['formats/underline']) {
                    const Underline = Quill.import('formats/underline');
                    Quill.register('formats/underline', Underline, true);
                  }

                  if (!Quill.imports['formats/link']) {
                    const Link = Quill.import('formats/link');
                    Quill.register('formats/link', Link, true);
                  }

                  // Define MentionBlot if not already defined
                  if (!Quill.imports['formats/mention']) {
                    class MentionBlot extends Embed {
                      static create(data: any) {
                        const node = super.create();

                        // Create a proper structure for the mention with blue styling
                        // First, add the @ symbol
                        const denotationChar = document.createElement('span');
                        denotationChar.className = 'ql-mention-denotation-char';
                        denotationChar.innerText = data.denotationChar;
                        denotationChar.style.color = '#0366d6';
                        denotationChar.style.fontWeight = '600';
                        denotationChar.style.marginRight = '1px';
                        node.appendChild(denotationChar);

                        // Then add the user name/value
                        const valueSpan = document.createElement('span');
                        valueSpan.className = 'ql-mention-value';
                        valueSpan.innerText = data.value;
                        valueSpan.style.color = '#0366d6';
                        valueSpan.style.fontWeight = '500';
                        node.appendChild(valueSpan);

                        // Apply styles to the mention node itself
                        node.style.backgroundColor = '#E8F4FE';
                        node.style.borderRadius = '4px';
                        node.style.padding = '0 2px';
                        node.style.color = '#0366d6';
                        node.style.marginRight = '2px';
                        node.style.display = 'inline-block';
                        node.style.whiteSpace = 'nowrap';

                        // Add important flag to ensure styles are applied
                        node.setAttribute('style', node.getAttribute('style') + ' !important');

                        // Store data attributes for later extraction
                        node.dataset.id = data.id;
                        node.dataset.value = data.value;
                        node.dataset.denotationChar = data.denotationChar;
                        if (data.email) {
                          node.dataset.email = data.email;
                        }

                        return node;
                      }

                      static value(node: HTMLElement) {
                        return {
                          id: node.dataset.id || '',
                          value: node.dataset.value || '',
                          denotationChar: node.dataset.denotationChar || '',
                          email: node.dataset.email || node.dataset.id || ''
                        };
                      }
                    }

                    MentionBlot.blotName = 'mention';
                    MentionBlot.tagName = 'span';
                    MentionBlot.className = 'mention';

                    Quill.register('formats/mention', MentionBlot);
                  }

                  // Now load the quill-mention script
                  await new Promise<void>((resolve) => {
                    if (!document.getElementById('quill-mention-script')) {
                      const script = document.createElement('script');
                      script.src = '/quill-mention.js';
                      script.id = 'quill-mention-script';
                      script.async = false; // Important: ensure script loads synchronously

                      script.onload = () => {
                        console.log('Quill mention script loaded successfully');
                        // Give a small delay to ensure everything is initialized
                        setTimeout(resolve, 100);
                      };

                      script.onerror = (e) => {
                        console.error('Failed to load quill-mention.js', e);
                        resolve();
                      };

                      document.body.appendChild(script);
                    } else {
                      // Script already exists, resolve after a small delay
                      setTimeout(resolve, 100);
                    }
                  });

                  // Mark as loaded
                  setQuillLoaded(true);
                }
              } catch (error) {
                console.error('Error initializing Quill:', error);
                // Still mark as loaded to avoid infinite loading
                setQuillLoaded(true);
              }
            };

            initQuill();
          }, [quillLoaded]);

          // Fix regenerationSnapshot issue when editor is available
          useEffect(() => {
            if (quillRef.current) {
              const editor = quillRef.current.getEditor();
              if (editor) {
                // @ts-ignore
                editor.regenerationSnapshot = { delta: null };
              }
            }
          }, [quillRef.current, quillLoaded]);

          // Show loading state while Quill is initializing
          if (!quillLoaded) {
            return (
              <div className="border border-gray-200 rounded-md p-3 min-h-[100px]">
                {props.placeholder || 'Loading editor...'}
              </div>
            );
          }

          // Render the actual ReactQuill component once everything is loaded
          return <ReactQuill.default ref={quillRef} {...props} />;
        };

        resolve(QuillWithMentions);
      });
    });
  },
  { ssr: false }
);

interface CommentInputProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  users: User[];
  onTagUser?: (email: string) => void;
}

export function CommentInput({
  value,
  onValueChange,
  placeholder = "Add a new comment...",
  users,
  onTagUser,
}: CommentInputProps) {
  const [isClient, setIsClient] = useState(false);
  const quillRef = useRef<any>(null);
  const [taggedEmails, setTaggedEmails] = useState<string[]>([]);
  // Use internal state to avoid issues with the external value
  const [internalValue, setInternalValue] = useState(value || '');

  // Set isClient to true on component mount
  useEffect(() => {
    setIsClient(true);
  }, []);

  // Sync internal value with external value
  useEffect(() => {
    if (value !== internalValue) {
      setInternalValue(value || '');
    }
  }, [value]);

  // Handle value changes
  const handleChange = (newValue: string) => {
    setInternalValue(newValue);
    onValueChange(newValue);
  };

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
  const mentionSources = useMemo(() => users.map(user => ({
    id: user.email || '',
    value: user.name || user.email || '',
    email: user.email || '',
    // Add avatar URL if available (using picture property from User type)
    avatar: user.picture || null,
  })), [users]);

  // Quill modules configuration - using useMemo to avoid recreating on each render
  const modules = useMemo(() => {
    // Define toolbar handlers to ensure they work properly
    const toolbarHandlers = {
      bold: function() {},
      italic: function() {},
      underline: function() {},
      link: function() {}
    };

    // Basic toolbar configuration with proper format
    const toolbarOptions = {
      toolbar: {
        container: [
          ['bold', 'italic', 'underline'],
          ['link']
        ],
        handlers: toolbarHandlers
      }
    };

    // Only add mention module if we have users
    if (users && users.length > 0) {
      return {
        ...toolbarOptions,
        mention: {
          allowedChars: /^[A-Za-z\s0-9._-]*$/,
          mentionDenotationChars: ["@"],
          spaceAfterInsert: true,
          showDenotationChar: true,
          blotName: 'mention',
          dataAttributes: ['id', 'value', 'denotationChar', 'email'],
          mentionContainerClass: 'mention-container',
          mentionListClass: 'mention-list',
          listItemClass: 'mention-item',
          positioningStrategy: 'fixed',
          defaultMenuOrientation: 'bottom',
          fixMentionsToQuill: false,  // Important - allows the dropdown to position correctly
          // Show a hint when typing @ to make it more obvious
          renderLoading: () => {
            return document.createTextNode('Type to search users...');
          },
          source: function(searchTerm: string, renderList: Function, mentionChar: string) {
            // Return all users if search term is empty
            if (searchTerm.length === 0) {
              renderList(mentionSources, searchTerm);
              return;
            }

            // Filter users based on search term
            const searchTermLower = searchTerm.toLowerCase();
            const matches = mentionSources.filter(source =>
              source.value.toLowerCase().includes(searchTermLower) ||
              source.email.toLowerCase().includes(searchTermLower)
            );

            // Always show at least one result if we have users
            if (matches.length === 0 && mentionSources.length > 0) {
              renderList([mentionSources[0]], searchTerm);
            } else {
              renderList(matches, searchTerm);
            }
          },
          // Custom rendering for mention items in the dropdown with improved styling
          renderItem: function(item: any) {
            return `
              <div class="mention-item-content" style="display: flex; align-items: center; padding: 8px 0;">
                <div class="mention-item-avatar" style="width: 28px; height: 28px; border-radius: 50%; margin-right: 10px; background-color: #E8F4FE; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #0366d6; overflow: hidden;">
                  ${item.avatar
                    ? `<img src="${item.avatar}" alt="${item.value}" width="28" height="28" style="border-radius: 50%; object-fit: cover;" />`
                    : `<span style="font-size: 14px;">${item.value.charAt(0).toUpperCase()}</span>`}
                </div>
                <div class="mention-item-info" style="display: flex; flex-direction: column;">
                  <div class="mention-item-name" style="font-weight: 500; font-size: 14px;">${item.value}</div>
                  <div class="mention-item-email" style="font-size: 12px; color: #666;">${item.email}</div>
                </div>
              </div>
            `;
          },
          // Handle mention selection
          onSelect: function(item: any, insertItem: Function) {
            // Add the email to the list of tagged emails
            setTaggedEmails(prev => [...prev, item.id]);
            insertItem(item);
          }
        }
      };
    }

    // Return basic toolbar if no users
    return toolbarOptions;
  }, [mentionSources, users]);

  // Quill formats - only include formats that are actually registered
  const formats = useMemo(() => [
    'bold', 'italic', 'underline',
    'link', 'mention'
    // Remove 'bullet' to fix the console error
  ], []);

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
    <div className="w-full quill-wrapper">
      <ReactQuill
        ref={quillRef}
        value={internalValue}
        onChange={handleChange}
        modules={modules}
        formats={formats}
        placeholder={placeholder}
        theme="snow"
        style={quillStyle}
      />
    </div>
  );
}
