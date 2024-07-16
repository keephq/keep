"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { RiSparkling2Line } from "react-icons/ri";

import { useEffect, useState } from "react";

export const AILink = () => {
  const [text, setText] = useState("");
  const [newText, setNewText] = useState("AI correlation");


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
    <LinkWithIcon href="/ai" icon={RiSparkling2Line} className="w-full">
      <div className="flex justify-between items-center w-full">
        <Subtitle>
          {text}
        </Subtitle>
      </div>
    </LinkWithIcon>
  );
};
