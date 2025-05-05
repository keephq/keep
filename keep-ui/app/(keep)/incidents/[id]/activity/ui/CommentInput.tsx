import { User } from "@/entities/users/model/types";
import dynamic from "next/dynamic";
import "react-quill-new/dist/quill.snow.css";
import { useCallback, useMemo } from "react";

const ReactQuill = dynamic(() => import("react-quill-new"), { ssr: false });

interface CommentInputProps {
  value: string;
  onValueChange: (value: string) => void;
  users: User[];
  placeholder?: string;
}

export function CommentInput({
  value,
  onValueChange,
  users,
  placeholder = "Add a new comment... Use @ to mention users",
}: CommentInputProps) {
  const commentSuggestions = useMemo(() => {
    return users.map((user) => ({
      id: user.email,
      value: user.name || user.email,
    }));
  }, [users]);

  const modules = useMemo(
    () => ({
      toolbar: [
        ["bold", "italic", "underline"],
        [{ list: "ordered" }, { list: "bullet" }],
        ["link"],
      ],
      mention: {
        allowedChars: /^[A-Za-z\sÅÄÖåäö]*$/,
        mentionDenotationChars: ["@"],
        source: function (searchTerm: string, renderList: Function) {
          const matches = commentSuggestions.filter((item) =>
            item.value.toLowerCase().includes(searchTerm.toLowerCase())
          );
          renderList(matches, searchTerm);
        },
        renderItem: function (item: any) {
          return `${item.value} <${item.id}>`;
        },
      },
    }),
    [commentSuggestions]
  );

  const formats = ["bold", "italic", "underline", "list", "bullet", "link", "mention"];

  const handleChange = useCallback(
    (content: string) => {
      onValueChange(content);
    },
    [onValueChange]
  );

  return (
    <div className="w-full">
      <ReactQuill
        theme="snow"
        value={value}
        onChange={handleChange}
        modules={modules}
        formats={formats}
        placeholder={placeholder}
        className="border border-tremor-border rounded-tremor-default shadow-tremor-input"
      />
    </div>
  );
}