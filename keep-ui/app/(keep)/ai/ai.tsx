"use client";
import { Card, List, ListItem, Title, Subtitle } from "@tremor/react";
import { useAIStats, usePollAILogs, UseAIActions } from "utils/hooks/useAI";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useApiUrl } from "utils/hooks/useConfig";
import { toast } from "react-toastify";
import { useEffect, useState, useRef, FormEvent } from "react";
import { AILogs } from "./model";
import Image from "next/image";

export default function Ai() {
  const { data: aistats, isLoading, refetch: refetchAIStats } = useAIStats();
  const { updateAISettings } = UseAIActions();

  useEffect(() => {
    const interval = setInterval(() => {
      refetchAIStats();
    }, 5000);

    return () => clearInterval(interval);
  }, [refetchAIStats]);

  return (
    <main className="p-4 md:p-10 mx-auto max-w-full">
      <div className="flex justify-between items-center">
        <div>
          <Title>AI Plugins</Title>
          <Subtitle>
            External AI engines can be plugged in and configured here.
          </Subtitle>
        </div>
      </div>
      <Card className="mt-10 p-4 md:p-10 mx-auto">
        <div>
          <div>
            <div className="grid grid-cols-1 gap-4">
              {isLoading ? (
                <p>Loading algorithms and their settings...</p>
              ) : null}
              {aistats?.algorithm_configs?.length === 0 && (
                <div className="flex flex-row">
                  <Image
                  src="/keep_sleeping.png"
                  alt="AI"
                  width={300}
                  height={300}
                  className="mr-4 rounded-lg"
                  />
                  <div>
                  <Title>No AI plugged in to your environment.</Title>
                  <p className="pt-2">
                    AI plugins can seamlessly correlate, enrich, and summarize
                    your alerts and incidents by leveraging the complete
                    context within Keep. This includes detailed information
                    like topology, runbooks, and other valuable data, allowing
                    you to gain deeper insights and respond more effectively.
                  </p>
                  <p className="pt-2">
                    Plus, AI plugins can even run in air-gapped environments. You can train models on-premises using your own data, so there is no need to share anything with third-party providers like OpenAI—keeping your data secure and private.
                  </p>
                  <p className="pt-2">
                    <a
                    href="https://www.keephq.dev/meet-keep"
                    className="text-orange-500 underline"
                    >
                    Talk to us to get access!
                    </a>
                  </p>
                  </div>
                </div>
              )}
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
                  </p>
                  <div className="flex flex-row">
                    <Card className="m-2 mt-4 p-2">
                      {algorithm_config.settings.map((setting: any) => (
                        <div key={setting} className="mt-2">
                          {setting.name}
                          <p className="text-sm text-gray-500">
                            {setting.description}
                          </p>
                          {setting.type === "bool" ? (
                            <input
                              type="checkbox"
                              id={`checkbox-${index}`}
                              name={`checkbox-${index}`}
                              checked={setting.value}
                              onChange={(e) => {
                                const newValue = e.target.checked;
                                setting.value = newValue;
                                algorithm_config.settings_proposed_by_algorithm =
                                  null;
                                updateAISettings(
                                  algorithm_config.algorithm_id,
                                  algorithm_config
                                );
                                refetchAIStats();
                              }}
                              className="mt-2 bg-orange-500 accent-orange-500"
                            />
                          ) : null}
                          {setting.type === "float" ? (
                            <div>
                              <p>Value: {setting.value}</p>
                              <input
                                type="range"
                                className="bg-orange-500 accent-orange-500"
                                step={(setting.max - setting.min) / 100}
                                min={setting.min}
                                max={setting.max}
                                // value={setting.value}
                                onChange={(e) => {
                                  const newValue = parseFloat(e.target.value);
                                  setting.value = newValue;
                                  algorithm_config.settings_proposed_by_algorithm =
                                    null;
                                  updateAISettings(
                                    algorithm_config.algorithm_id,
                                    algorithm_config
                                  );
                                  refetchAIStats();
                                }}
                              />
                            </div>
                          ) : null}
                          {setting.type === "int" ? (
                            <div>
                              <p>Value: {setting.value}</p>
                              <input
                                type="range"
                                className="bg-orange-500 accent-orange-500"
                                step={1}
                                min={setting.min}
                                max={setting.max}
                                // value={setting.value}
                                onChange={(e) => {
                                  const newValue = parseFloat(e.target.value);
                                  setting.value = newValue;
                                  algorithm_config.settings_proposed_by_algorithm =
                                    null;
                                  updateAISettings(
                                    algorithm_config.algorithm_id,
                                    algorithm_config
                                  );
                                  refetchAIStats();
                                }}
                              />
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </Card>

                    {algorithm_config.settings_proposed_by_algorithm &&
                      JSON.stringify(algorithm_config.settings) !==
                        JSON.stringify(
                          algorithm_config.settings_proposed_by_algorithm
                        ) && (
                        <Card className="m-2 mt-4 p-2">
                          <Title>The new settings proposal</Title>
                          <p className="text-sm">
                            The last time the model was trained and used for
                            inference, it suggested a configuration update.
                            However, please note that a configuration update
                            might not be very effective if the data quantity or
                            quality is low. For more details, please refer to
                            the logs below.
                          </p>
                          {algorithm_config.settings_proposed_by_algorithm.map(
                            (proposed_setting: any, idx: number) => (
                              <div key={idx} className="mt-2">
                                <p className="text-sm">
                                  {proposed_setting.name}:{" "}
                                  {String(proposed_setting.value)}
                                </p>
                              </div>
                            )
                          )}
                          <button
                            className="mt-2 p-2 bg-orange-500 text-white rounded"
                            onClick={() => {
                              algorithm_config.settings =
                                algorithm_config.settings_proposed_by_algorithm;
                              algorithm_config.settings_proposed_by_algorithm =
                                null;
                              updateAISettings(
                                algorithm_config.algorithm_id,
                                algorithm_config
                              );
                              refetchAIStats();
                              toast.success("Settings updated successfully!");
                            }}
                          >
                            Apply proposed settings
                          </button>
                        </Card>
                      )}
                  </div>
                  <h4 className="text-md font-medium mt-4">Execution logs:</h4>
                  <pre className="text-sm bg-gray-100 p-2 rounded break-words whitespace-pre-wrap">
                    {algorithm_config.feedback_logs
                      ? algorithm_config.feedback_logs
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
