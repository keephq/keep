import { User } from "@/app/(keep)/settings/models";
import { TextInput } from "@tremor/react";
import { useEffect, useRef, useState } from "react";
import { UserStatefulAvatar } from "@/entities/users/ui/UserStatefulAvatar";

interface MentionsInputProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  users: User[];
  onTagUser?: (email: string) => void;
}

export function MentionsInput({
  value,
  onValueChange,
  placeholder = "Add a new comment...",
  users,
  onTagUser,
}: MentionsInputProps) {
  const [inputValue, setInputValue] = useState(value);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionSearch, setMentionSearch] = useState("");
  const [cursorPosition, setCursorPosition] = useState(0);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const mentionsRef = useRef<HTMLDivElement>(null);

  // Filter users based on mention search
  const filteredUsers = users?.filter((user) => {
    const searchTerm = mentionSearch.toLowerCase();
    return (
      user.email.toLowerCase().includes(searchTerm) ||
      (user.name && user.name.toLowerCase().includes(searchTerm))
    );
  }) || [];

  // Handle input change
  const handleInputChange = (newValue: string) => {
    setInputValue(newValue);
    onValueChange(newValue);

    // Check if we're in a mention context
    const curPos = inputRef.current?.selectionStart || 0;
    setCursorPosition(curPos);

    // Find the last @ symbol before the cursor
    const textBeforeCursor = newValue.substring(0, curPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf("@");

    if (lastAtIndex !== -1) {
      // Check if there's a space between the @ and the cursor
      const textBetweenAtAndCursor = textBeforeCursor.substring(lastAtIndex + 1);
      const hasSpace = /\s/.test(textBetweenAtAndCursor);

      if (!hasSpace) {
        setMentionSearch(textBetweenAtAndCursor);
        setShowMentions(true);
        setSelectedIndex(0);
        return;
      }
    }

    setShowMentions(false);
    setSelectedIndex(0);
  };

  // Handle selecting a user from the mentions dropdown
  const selectUser = (user: User) => {
    const textBeforeCursor = inputValue.substring(0, cursorPosition);
    const lastAtIndex = textBeforeCursor.lastIndexOf("@");

    if (lastAtIndex !== -1) {
      // Use name if available, otherwise use email
      const displayText = user.name || user.email;

      // Replace the @mention text with the selected user
      // Format: @DisplayName <email@example.com>
      const newValue =
        inputValue.substring(0, lastAtIndex) +
        `@${displayText} <${user.email}> ` +
        inputValue.substring(cursorPosition);

      setInputValue(newValue);
      onValueChange(newValue);
      setShowMentions(false);

      // Notify parent component about the tagged user
      if (onTagUser) {
        onTagUser(user.email);
      }

      // Focus back on input
      if (inputRef.current) {
        inputRef.current.focus();
        // Set cursor position after the inserted mention
        const mentionLength = displayText.length + user.email.length + 5; // +5 for @ and <> and space
        const newCursorPos = lastAtIndex + mentionLength;
        setTimeout(() => {
          if (inputRef.current) {
            inputRef.current.selectionStart = newCursorPos;
            inputRef.current.selectionEnd = newCursorPos;
          }
        }, 0);
      }
    }
  };

  // Close mentions dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        mentionsRef.current &&
        !mentionsRef.current.contains(event.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setShowMentions(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Update local state when prop value changes
  useEffect(() => {
    setInputValue(value);
  }, [value]);

  return (
    <div className="relative w-full">
      <TextInput
        ref={inputRef}
        value={inputValue}
        onValueChange={handleInputChange}
        placeholder={placeholder}
        onFocus={() => {
          // Check if we should show mentions when focusing
          const curPos = inputRef.current?.selectionStart || 0;
          setCursorPosition(curPos);

          const textBeforeCursor = inputValue.substring(0, curPos);
          const lastAtIndex = textBeforeCursor.lastIndexOf("@");

          if (lastAtIndex !== -1) {
            const textBetweenAtAndCursor = textBeforeCursor.substring(lastAtIndex + 1);
            const hasSpace = /\s/.test(textBetweenAtAndCursor);

            if (!hasSpace) {
              setMentionSearch(textBetweenAtAndCursor);
              setShowMentions(true);
            }
          }
        }}
        onKeyDown={(e: { key: string; preventDefault: () => void; }) => {
          // Handle escape key to close mentions dropdown
          if (e.key === "Escape" && showMentions) {
            e.preventDefault();
            setShowMentions(false);
          }

          // Handle arrow keys for navigating mentions
          if (showMentions && filteredUsers.length > 0) {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setSelectedIndex((prevIndex: number) =>
                prevIndex < filteredUsers.length - 1 ? prevIndex + 1 : 0
              );
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setSelectedIndex((prevIndex: number) =>
                prevIndex > 0 ? prevIndex - 1 : filteredUsers.length - 1
              );
            } else if (e.key === "Enter") {
              e.preventDefault();
              selectUser(filteredUsers[selectedIndex]);
            }
          }
        }}
      />

      {showMentions && filteredUsers.length > 0 && (
        <div
          ref={mentionsRef}
          className="absolute z-10 mt-1 w-full max-h-60 overflow-auto bg-white border border-gray-200 rounded-md shadow-lg"
        >
          <ul className="py-1">
            {filteredUsers.map((user, index) => (
              <li
                key={user.email}
                className={`px-3 py-2 cursor-pointer flex items-center gap-2 ${
                  index === selectedIndex ? 'bg-blue-50' : 'hover:bg-gray-100'
                }`}
                onClick={() => selectUser(user)}
                onMouseEnter={() => setSelectedIndex(index)}
              >
                <UserStatefulAvatar email={user.email} size="xs" />
                <div className="flex flex-col">
                  <span className="font-medium">{user.name || user.email}</span>
                  {user.name && <span className="text-xs text-gray-500">{user.email}</span>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
