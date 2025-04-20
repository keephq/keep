"use client";

import { Editor, EditorProps, loader } from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";

interface MonacoCelProps extends EditorProps {
  onMonacoLoaded?: (monacoInstance: typeof import("monaco-editor")) => void;
  onMonacoLoadFailure?: (error: Error) => void;
}

export function MonacoCelCDN(props: MonacoCelProps) {
  const [isLoaded, setIsLoaded] = useState(false);
  const onMonacoLoadedRef = useRef<MonacoCelProps["onMonacoLoaded"] | null>(
    null
  );
  onMonacoLoadedRef.current = props.onMonacoLoaded;
  const onMonacoLoadFailureRef = useRef<
    MonacoCelProps["onMonacoLoadFailure"] | null
  >();
  onMonacoLoadFailureRef.current = props.onMonacoLoadFailure;
  useEffect(() => {
    console.log("Ihor MonacoCelTurbopack created");
  }, []);

  useEffect(() => {
    loader
      .init()
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
