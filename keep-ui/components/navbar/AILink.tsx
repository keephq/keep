"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { AIIcon, ExportIcon } from "components/icons";
import { useEffect, useState, useRef } from "react";

export const AILink = () => {
  const [text, setText] = useState("");
  const [animate, setAnimate] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [newText, setNewText] = useState("AI correlation");

  const onlyOnce = useRef(false);

  useEffect(() => {
    let index = 0;

    const interval = setInterval(() => {
      setText(newText.slice(0, index + 1));
      index++;

      if (index === newText.length) {
        clearInterval(interval);
      }
    }, 100);

    if (onlyOnce.current === false) {
      onlyOnce.current = true;
      const AICycle = setInterval(() => {
        setNewText("🤗 AI needs more data...");
        setAnimate(true);
        const intervalA = setInterval(() => {
          setAnimate(false);
        }, 2000);
      }, 60000);
    }

    return () => {
      clearInterval(interval);
    };
  }, [newText]);

  return (
    <LinkWithIcon
      href="/ai"
      icon={AIIcon}
      className={(animate && "animate-pulse") + ""}
    >
      <Subtitle>{text}</Subtitle>
    </LinkWithIcon>
  );
};
