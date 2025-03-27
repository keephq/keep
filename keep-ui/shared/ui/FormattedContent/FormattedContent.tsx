import React, { FC } from "react";
import ReactMarkdown from "react-markdown";

interface FormattedContentProps {
  content: string | null | undefined;
  format?: "markdown" | "html" | null;
}

export const FormattedContent: FC<FormattedContentProps> = ({
  content,
  format,
}) => {
  if (!content) {
    return null;
  }

  if (format === "markdown") {
    return (
      <div
        className="prose prose-slate dark:prose-invert max-w-none
        prose-headings:font-semibold
        prose-h1:text-3xl prose-h1:mb-4
        prose-h2:text-2xl prose-h2:mb-3
        prose-h3:text-xl prose-h3:mb-2
        prose-p:text-base prose-p:leading-7 prose-p:mb-4
        prose-ul:my-4 prose-ul:list-disc prose-ul:pl-6
        prose-ol:my-4 prose-ol:list-decimal prose-ol:pl-6
        prose-li:my-1
        prose-pre:bg-gray-100 dark:prose-pre:bg-gray-800 prose-pre:p-4 prose-pre:rounded-lg
        prose-code:text-sm prose-code:bg-gray-100 dark:prose-code:bg-gray-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded
        prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline"
      >
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    );
  }

  if (format === "html") {
    return (
      <div
        className="prose prose-slate dark:prose-invert max-w-none
          prose-headings:font-semibold
          prose-p:text-base prose-p:leading-7
          prose-ul:list-disc prose-ul:pl-6
          prose-ol:list-decimal prose-ol:pl-6"
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  }

  // Default to plain text with preserved whitespace
  return (
    <pre className="whitespace-pre-wrap text-base text-gray-700 dark:text-gray-300">
      {content}
    </pre>
  );
};
