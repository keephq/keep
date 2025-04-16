// "use client";

// import { KeepLoader } from "../KeepLoader/KeepLoader";
// import { useState } from "react";
// import { ErrorComponent } from "../ErrorComponent/ErrorComponent";
// import { setupCustomCellanguage } from "./cel-support";
// import { MonacoCel } from "./monaco-cel-base.turbopack";
// import { editor } from "monaco-editor";

// const Loader = <KeepLoader loadingText="Loading Code Editor ..." />;

// interface MonacoCelProps {
//   className: string;
// }

// export function MonacoCelEditor(props: MonacoCelProps) {
//   const [error, setError] = useState<Error | null>(null);
//   const [editor, setEditor] = useState<editor.IStandaloneCodeEditor | null>(
//     null
//   );

//   function monacoLoadedCallback(
//     monacoInstance: typeof import("monaco-editor")
//   ) {
//     setupCustomCellanguage(monacoInstance);
//   }

//   const handleEditorDidMount = (
//     editor: editor.IStandaloneCodeEditor,
//     monaco: typeof import("monaco-editor")
//   ) => {
//     setEditor(editor);
//   };

//   if (error) {
//     return (
//       <ErrorComponent
//         error={error}
//         defaultMessage={`Error loading Monaco Editor from CDN`}
//         description="Check your internet connection and try again"
//       />
//     );
//   }

//   return (
//     <MonacoCel
//       onMonacoLoaded={monacoLoadedCallback}
//       onMonacoLoadFailure={setError}
//       onMount={handleEditorDidMount}
//       className={props.className}
//       language="cel"
//       defaultLanguage="cel"
//       theme="cel-dark"
//       loading={Loader}
//       wrapperProps={{
//         style: {
//           backgroundColor: "transparent", // ✅ wrapper transparency
//         },
//       }}
//       options={{
//         readOnly: false,
//         minimap: { enabled: false },
//         scrollBeyondLastLine: false,
//         fontSize: 12,
//         lineNumbers: "off",
//         folding: false,
//         wordWrap: "off",
//       }}
//     />
//   );
// }
