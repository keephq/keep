import React, { FC } from "react";
import { MarkdownHTML } from "../MarkdownHTML/MarkdownHTML";

import { unified } from "unified";
import rehypeParse from "rehype-parse";
import rehypeSanitize from "rehype-sanitize";
import rehypeStringify from "rehype-stringify";
import clsx from "clsx";

const sanitizeHtml = (html: string) => {
  return unified()
    .use(rehypeParse, { fragment: true })
    .use(rehypeSanitize)
    .use(rehypeStringify)
    .processSync(html).value;
};

function FormattedHTMLContent({
  content,
  className,
}: {
  content: string;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "prose prose-slate dark:prose-invert max-w-none",
        "prose-headings:font-semibold",
        "prose-p:text-base prose-p:leading-7",
        "prose-ul:list-disc prose-ul:pl-6",
        "prose-ol:list-decimal prose-ol:pl-6",
        className
      )}
      // eslint-disable-next-line react/no-danger -- we sanitized the html
      dangerouslySetInnerHTML={{ __html: sanitizeHtml(content) }}
    />
  );
}

interface FormattedContentProps {
  content: string | null | undefined;
  format?: "markdown" | "html" | null;
  className?: string;
}

export const FormattedContent: FC<FormattedContentProps> = ({
  content,
  format,
  className,
}) => {
  if (!content) {
    return null;
  }

  if (format === "markdown") {
    return (
      <div
        className={clsx(
          "prose prose-slate dark:prose-invert max-w-none",
          "prose-headings:font-semibold",
          "prose-h1:text-3xl prose-h1:mb-4",
          "prose-h2:text-2xl prose-h2:mb-3",
          "prose-h3:text-xl prose-h3:mb-2",
          "prose-p:text-base prose-p:leading-7 prose-p:mb-4",
          "prose-ul:my-4 prose-ul:list-disc prose-ul:pl-6",
          "prose-ol:my-4 prose-ol:list-decimal prose-ol:pl-6",
          "prose-li:my-1",
          "prose-pre:bg-gray-100 dark:prose-pre:bg-gray-800 prose-pre:p-4 prose-pre:rounded-lg",
          "prose-code:text-sm prose-code:bg-gray-100 dark:prose-code:bg-gray-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded",
          "prose-a:text-blue-600 dark:prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline",
          className
        )}
      >
        <MarkdownHTML>{content}</MarkdownHTML>
      </div>
    );
  }

  if (format === "html") {
    return <FormattedHTMLContent content={content} className={className} />;
  }

  // Default to plain text with preserved whitespace
  return (
    <pre
      className={clsx(
        "whitespace-pre-wrap text-base text-gray-700 dark:text-gray-300",
        className
      )}
    >
      {content}
    </pre>
  );
};
