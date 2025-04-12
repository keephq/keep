import { useUsers } from "@/entities/users/model/useUsers";
import { useCallback, useEffect, useRef, useState } from "react";
import { UserDto } from "@/entities/users/model";

interface UserMentionProps {
  onSelect: (user: UserDto) => void;
  onClose: () => void;
  searchText: string;
  position: { top: number; left: number };
}

export function UserMention({ onSelect, onClose, searchText, position }: UserMentionProps) {
  const { data: users = [] } = useUsers();
  const [filteredUsers, setFilteredUsers] = useState<UserDto[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const filtered = users.filter(user => 
      (user.name?.toLowerCase().includes(searchText.toLowerCase()) || 
      user.email?.toLowerCase().includes(searchText.toLowerCase()))
    );
    setFilteredUsers(filtered);
    setSelectedIndex(0);
  }, [searchText, users]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex(prev => (prev + 1) % filteredUsers.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex(prev => (prev - 1 + filteredUsers.length) % filteredUsers.length);
    } else if (e.key === "Enter" && filteredUsers.length > 0) {
      e.preventDefault();
      onSelect(filteredUsers[selectedIndex]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  }, [filteredUsers, selectedIndex, onSelect, onClose]);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (filteredUsers.length === 0) return null;

  return (
    <div
      ref={menuRef}
      className="absolute z-50 bg-white rounded-md shadow-lg border border-gray-200 max-h-48 overflow-y-auto"
      style={{ top: position.top, left: position.left }}
    >
      {filteredUsers.map((user, index) => (
        <div
          key={user.email}
          className={`px-4 py-2 cursor-pointer hover:bg-gray-100 ${
            index === selectedIndex ? "bg-gray-100" : ""
          }`}
          onClick={() => onSelect(user)}
        >
          <div className="flex items-center gap-2">
            <span className="font-medium">{user.name || user.email}</span>
            {user.name && <span className="text-sm text-gray-500">{user.email}</span>}
          </div>
        </div>
      ))}
    </div>
  );
} 