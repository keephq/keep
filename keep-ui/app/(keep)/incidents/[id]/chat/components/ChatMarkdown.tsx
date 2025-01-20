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
  p({ children }) {
    return <p className="mb-2">{children}</p>;
  },
  a({ children, ...props }) {
    return (
      <a
        className="text-blue-600 underline"
        {...props}
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    );
  },
  code({ inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || "");
    const language = match ? match[1] : "";
    const content = String(children).replace(/\n$/, "");

    if (content === "▍") {
      return <span className="animate-pulse mt-1">▍</span>;
    }

    if (inline) {
      return (
        <code className="bg-gray-100 rounded px-1 py-0.5" {...props}>
          {content}
        </code>
      );
    }

    return (
      <div className="my-2">
        <SyntaxHighlighter
          style={atomDark}
          language={language}
          PreTag="div"
          {...props}
        >
          {content}
        </SyntaxHighlighter>
      </div>
    );
  },
  ul({ children }) {
    return <ul className="list-disc pl-6 mb-2">{children}</ul>;
  },
  ol({ children }) {
    return <ol className="list-decimal pl-6 mb-2">{children}</ol>;
  },
  li({ children }) {
    return <li className="mb-1">{children}</li>;
  },
  h1({ children }) {
    return <h1 className="text-2xl font-bold mb-3">{children}</h1>;
  },
  h2({ children }) {
    return <h2 className="text-xl font-bold mb-2">{children}</h2>;
  },
  h3({ children }) {
    return <h3 className="text-lg font-bold mb-2">{children}</h3>;
  },
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
        remarkPlugins={[remarkGfm, remarkMath]}
      >
        {children}
      </MemoizedReactMarkdown>
    </div>
  );
}
