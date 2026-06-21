"use client";

import { Editor, EditorProps, loader } from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";

interface MonacoCelProps extends EditorProps {
  onMonacoLoaded?: (monacoInstance: typeof import("monaco-editor")) => void;
  onMonacoLoadFailure?: (error: Error) => void;
}

// Monaco Editor - imported as an npm package instead of loading from the
// CDN to support air-gapped environments.
// https://github.com/suren-atoyan/monaco-react?tab=readme-ov-file#use-monaco-editor-as-an-npm-package
//
// The dynamic import is started at module evaluation (not inside useEffect) so
// that it does not interfere with React's render cycle.  A typeof-window guard
// makes it SSR-safe without causing "window is not defined" crashes.
const monacoConfigPromise: Promise<void> | null =
  typeof window !== "undefined"
    ? import("monaco-editor").then((monaco) => {
        loader.config({ monaco });
      })
    : null;

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
    (monacoConfigPromise ?? Promise.resolve())
      .then(() => loader.init())
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
