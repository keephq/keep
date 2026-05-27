"use client";

import { Editor, EditorProps, loader } from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";

interface MonacoCelProps extends EditorProps {
  onMonacoLoaded?: (monacoInstance: typeof import("monaco-editor")) => void;
  onMonacoLoadFailure?: (error: Error) => void;
}

export function MonacoCelBase(props: MonacoCelProps) {
  const [isLoaded, setIsLoaded] = useState(false);
  const onMonacoLoadedRef = useRef<MonacoCelProps["onMonacoLoaded"] | null>(
    null
  );
  onMonacoLoadedRef.current = props.onMonacoLoaded;
  const onMonacoLoadFailureRef = useRef<
    MonacoCelProps["onMonacoLoadFailure"] | null
  >(null);
  onMonacoLoadFailureRef.current = props.onMonacoLoadFailure;

  useEffect(() => {
    // Monaco Editor - imported as an npm package instead of loading from the
    // CDN to support air-gapped environments.
    // https://github.com/suren-atoyan/monaco-react?tab=readme-ov-file#use-monaco-editor-as-an-npm-package
    import("monaco-editor")
      .then((monaco) => {
        loader.config({ monaco });
        return loader.init();
      })
      .then((monacoInstance) => {
        onMonacoLoadedRef.current?.(monacoInstance);
        setIsLoaded(true);
      })
      .catch((error: Error) => {
        onMonacoLoadFailureRef.current?.(error);
      });
  }, []);

  if (!isLoaded) {
    return null;
  }

  return <Editor {...props} />;
}
