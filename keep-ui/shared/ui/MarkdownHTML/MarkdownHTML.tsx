// import Markdown from "react-markdown";
// import remarkGfm from "remark-gfm";
// import remarkRehype from "remark-rehype";
// import rehypeRaw from "rehype-raw";
// import rehypeSanitize from "rehype-sanitize";

// // Only this component should be used to render markdown or HTML,
// // it sanitizes the HTML and allows for the use of raw HTML.
// export const MarkdownHTML = ({ children }: { children: string }) => {
//   return (
//     <Markdown
//       remarkPlugins={[remarkGfm, remarkRehype]}
//       rehypePlugins={[rehypeRaw, rehypeSanitize]}
//     >
//       {children}
//     </Markdown>
//   );
// };

// mock implementation for now, testing the e2e tests
export const MarkdownHTML = ({ children }: { children: string }) => {
  return <div>{children}</div>;
};
