import { User } from "@/app/(keep)/settings/models";
import { useEffect, useRef, useState } from "react";
import { TextInput } from "@tremor/react";

interface MentionsInputProps {
  value: string;
  onValueChange: (value: string) => void;
  users: User[];
  placeholder?: string;
}

interface SuggestionState {
  isOpen: boolean;
  query: string;
  index: number;
  startPosition: number;
}

export function MentionsInput({
  value,
  onValueChange,
  users,
  placeholder,
}: MentionsInputProps) {
  const [suggestion, setSuggestion] = useState<SuggestionState>({
    isOpen: false,
    query: "",
    index: 0,
    startPosition: 0,
  });

  const inputRef = useRef<HTMLInputElement>(null);

  const filteredUsers = users.filter((user) =>
    (user.name?.toLowerCase() || user.email.toLowerCase()).includes(
      suggestion.query.toLowerCase()
    )
  );

  const insertMention = (user: User) => {
    const before = value.slice(0, suggestion.startPosition);
    const after = value.slice(inputRef.current?.selectionStart || 0);
    const mention = `@${user.email} `;
    onValueChange(before + mention + after);
    setSuggestion({ isOpen: false, query: "", index: 0, startPosition: 0 });
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (!suggestion.isOpen) return;

    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setSuggestion((prev) => ({
          ...prev,
          index: (prev.index + 1) % filteredUsers.length,
        }));
        break;
      case "ArrowUp":
        event.preventDefault();
        setSuggestion((prev) => ({
          ...prev,
          index:
            prev.index - 1 < 0 ? filteredUsers.length - 1 : prev.index - 1,
        }));
        break;
      case "Enter":
        event.preventDefault();
        if (filteredUsers[suggestion.index]) {
          insertMention(filteredUsers[suggestion.index]);
        }
        break;
      case "Escape":
        setSuggestion({ isOpen: false, query: "", index: 0, startPosition: 0 });
        break;
    }
  };

  const handleInput = (newValue: string) => {
    onValueChange(newValue);

    const cursorPosition = inputRef.current?.selectionStart || 0;
    const textBeforeCursor = newValue.slice(0, cursorPosition);
    const matches = textBeforeCursor.match(/@([\w\s]*)$/);

    if (matches) {
      setSuggestion({
        isOpen: true,
        query: matches[1],
        index: 0,
        startPosition: cursorPosition - matches[1].length - 1,
      });
    } else {
      setSuggestion({ isOpen: false, query: "", index: 0, startPosition: 0 });
    }
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        suggestion.isOpen &&
        inputRef.current &&
        !inputRef.current.contains(event.target as Node)
      ) {
        setSuggestion({ isOpen: false, query: "", index: 0, startPosition: 0 });
      }
    };

    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, [suggestion.isOpen]);

  return (
    <div className="relative w-full">
      <TextInput
        ref={inputRef}
        value={value}
        onValueChange={handleInput}
        placeholder={placeholder}
        onKeyDown={handleKeyDown}
      />
      {suggestion.isOpen && filteredUsers.length > 0 && (
        <div className="absolute z-10 w-64 mt-1 bg-white rounded-md shadow-lg border border-gray-200">
          <ul className="py-1">
            {filteredUsers.map((user, index) => (
              <li
                key={user.email}
                className={`px-3 py-2 cursor-pointer hover:bg-gray-100 ${suggestion.index === index ? "bg-gray-100" : ""}`}
                onClick={() => insertMention(user)}
              >
                <div className="flex items-center">
                  {user.picture && (
                    <img
                      src={user.picture}
                      alt={user.name}
                      className="w-6 h-6 rounded-full mr-2"
                    />
                  )}
                  <div>
                    <div className="font-medium">{user.name || user.email}</div>
                    {user.name && (
                      <div className="text-sm text-gray-500">{user.email}</div>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}