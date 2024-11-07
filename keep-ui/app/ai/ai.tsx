"use client";
import { Card, List, ListItem, Title, Subtitle } from "@tremor/react";
import { useAIStats, usePollAILogs, useUpdateAISettings } from "utils/hooks/useAI";
import { useSession } from "next-auth/react";
import { useEffect, useState, useRef, FormEvent } from "react";
import { AILogs } from "./model";

export default function Ai() {
  const { data: aistats, isLoading } = useAIStats();
  const { data: session } = useSession();
  const [text, setText] = useState("");
  const [basicAlgorithmLog, setBasicAlgorithmLog] = useState("");

  const mutateAILogs = (logs: AILogs) => {
    setBasicAlgorithmLog(logs.log);
  };
  usePollAILogs(mutateAILogs);

  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <div className="flex justify-between items-center">
        <div>
          <Title>AI Correlation</Title>
          <Subtitle>
            Correlating alerts to incidents based on past alerts, incidents, and
            the other data.
          </Subtitle>
        </div>
      </div>
      <Card className="mt-10 p-4 md:p-10 mx-auto">
        <div>
          <div>
            <div className="grid grid-cols-2 gap-4 mt-6">
              {aistats?.algorithm_configs?.map((algorithm_config, index) => (
                <Card
                  key={index}
                  className="p-4 flex flex-col justify-between w-full border-white border-2"
                >
                  <h3 className="text-lg sm:text-xl font-semibold line-clamp-2">
                    {algorithm_config.algorithm.name}
                  </h3>
                  <p className="text-sm">
                    {algorithm_config.algorithm.description}
                    {/* {algorithm_config.settings} */}
                  </p>
                  {algorithm_config.settings.map(
                    (setting: any) => (
                      <div key={setting} className="mt-2">
                        {setting.name}
                        <p className="text-sm text-gray-500">{setting.description}</p>
                        {setting.type === "bool" ? (
                          <input
                            type="checkbox"
                            id={`checkbox-${index}`}
                            name={`checkbox-${index}`}
                            checked={setting.value}
                            onChange={(e) => {
                              const newValue = e.target.checked;
                              setting.value = newValue;
                              console.log(setting);
                              updateAISettings({
                                [algorithm_config.algorithm.name]: algorithm_config.settings,
                              });
                            }}
                            className="mt-2"
                          />
                        ) : null}
                        {setting.type === "float" ? (
                          <input
                            type="range"
                            id={`slider-${index}`}
                            name={`slider-${index}`}
                            min={setting.min}
                            max={setting.max}
                            value={setting.value}
                            onChange={(e) => {
                              const newValue = e.target.value;
                              setting.value = newValue;
                            }}
                            className="mt-2 w-full"
                          />
                        ) : null}
                      </div>
                    )
                  )}
                  <h4 className="text-md font-medium mt-4">Execution logs:</h4>
                  <pre className="text-sm bg-gray-100 p-2 rounded">
                    {algorithm_config.feedback_log
                      ? algorithm_config.feedback_log
                      : "Algorithm not executed yet."}
                  </pre>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </main>
  );
}
