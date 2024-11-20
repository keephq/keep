import React, { useRef, useState } from "react";
import { useApiUrl } from "utils/hooks/useConfig";
import { useSession } from "next-auth/react";

const FileUpload: React.FC = () => {
  const apiUrl = useApiUrl();
  const { data: session } = useSession();
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const onDrop = async (files: any) => {
    const formData = new FormData();
    formData.append("file", files[0]);

    try {
      const response = await fetch(`${apiUrl}/workflows`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: formData,
      });

      if (response.ok) {
        setError(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
        window.location.reload();
      } else {
        const errorMessage = await response.text();
        setError(errorMessage);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    } catch (error) {
      setError("An error occurred during file upload");
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  return (
    <div className="absolute top-0 left-0 mt-4 ml-4">
      <label className="cursor-pointer flex items-center">
        <span className="text-gray-500 mr-2">Click to upload a workflow</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className="w-6 h-6 inline-block"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            onDrop(e.target.files);
          }}
        />
      </label>
      {error && (
        <p className="text-red-500 mt-4">
          Failed to upload the file: {error}
          <br></br>Please try again with another file.
        </p>
      )}
    </div>
  );
};

export default FileUpload;
