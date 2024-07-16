"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Ai } from "components/icons";
import { useEffect, useState, useRef } from "react";

export const AILink = () => {
  const [text, setText] = useState("");
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
    <LinkWithIcon href="/ai" icon={Ai} className="w-full">
      <div className="flex justify-between items-center w-full">
        <Subtitle className="text-xs text-gray-900 font-medium">
          {text}
        </Subtitle>
      </div>
    </LinkWithIcon>
  );
};
