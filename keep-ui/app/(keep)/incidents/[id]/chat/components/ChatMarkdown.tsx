import { FC, memo } from "react";
import ReactMarkdown, { Options, Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { atomDark } from "react-syntax-highlighter/dist/cjs/styles/prism";

const MemoizedReactMarkdown: FC<Options> = memo(
  ReactMarkdown,
  (prevProps, nextProps) =>
    prevProps.children === nextProps.children &&
    prevProps.className === nextProps.className
);

interface MarkdownProps {
  children: string;
}
const components: Components = {
  // Renders paragraphs of text with bottom margin
  // Used for standard text blocks in markdown
  p({ children }) {
    return <p>{children}</p>;
  },

  // Renders hyperlinks that open in new tab
  // Used when markdown contains [text](url) syntax
  a({ children, href }) {
    return (
      <a
        className="text-blue-600 underline"
        href={href}
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    );
  },

  // Renders code blocks and inline code
  // Used for both inline `code` and fenced code blocks ```code```
  // Supports syntax highlighting for fenced code blocks with language specified
  code({ inline, className, children, ...props }: any) {
    const match = /language-(\w+)/.exec(className || "");
    const language = match ? match[1] : "";
    const content = String(children).replace(/\n$/, "");

    // Special case for cursor placeholder
    if (content === "▍") {
      return <span className="animate-pulse mt-1">▍</span>;
    }

    // Inline code rendering
    if (inline) {
      return (
        <code className="bg-gray-100 rounded px-1 py-0.5" {...props}>
          {content}
        </code>
      );
    }

    // Code block rendering with syntax highlighting
    return (
      <div className="my-2">
        <SyntaxHighlighter
          style={atomDark as { [key: string]: React.CSSProperties }}
          language={language}
          PreTag="div"
          {...props}
        >
          {content}
        </SyntaxHighlighter>
      </div>
    );
  },

  // Renders unordered lists with bullet points
  // Used when markdown contains * or - list items
  ul({ children }) {
    return <ul className="list-disc pl-6 my-0">{children}</ul>;
  },

  // Renders ordered lists with numbers
  // Used when markdown contains 1. 2. 3. list items
  ol({ children }) {
    return <ol className="list-decimal pl-6 my-0">{children}</ol>;
  },

  // Renders list items within ul/ol
  // Used for each item in a list
  li({ children }) {
    return <li className="my-0">{children}</li>;
  },

  // Renders heading level 1
  // Used when markdown contains # Heading
  h1({ children }) {
    return <h1 className="text-2xl font-bold mb-3">{children}</h1>;
  },

  // Renders heading level 2
  // Used when markdown contains ## Heading
  h2({ children }) {
    return <h2 className="text-xl font-bold mb-2">{children}</h2>;
  },

  // Renders heading level 3
  // Used when markdown contains ### Heading
  h3({ children }) {
    return <h3 className="text-lg font-bold mb-2">{children}</h3>;
  },

  // Renders blockquotes
  // Used when markdown contains > quoted text
  blockquote({ children }) {
    return (
      <blockquote className="border-l-4 border-gray-200 pl-4 my-2 italic">
        {children}
      </blockquote>
    );
  },
};

export function ChatMarkdown({ children }: MarkdownProps) {
  return (
    <div className="prose prose-sm max-w-none">
      <MemoizedReactMarkdown
        components={components}
        remarkPlugins={[remarkGfm as any, remarkMath as any]}
      >
        {children}
      </MemoizedReactMarkdown>
    </div>
  );
}
