"use client";

import { Badge, Subtitle } from "@tremor/react";
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
      <div className="flex justify-between items-center w-full">
        <Subtitle className="text-xs text-gray-900 font-medium">
          {text}
        </Subtitle>
        <div className="flex items-center">
          <Badge color="orange" size="xs" className="ml-2 mr-2">
            Soon
          </Badge>
        </div>
      </div>
    </LinkWithIcon>
  );
};
