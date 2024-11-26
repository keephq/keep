"use client";

import { Card, List, ListItem, Title, Subtitle } from "@tremor/react";
import { useAIStats, usePollAILogs } from "utils/hooks/useAI";
import { toast } from "react-toastify";
import { useEffect, useState, FormEvent } from "react";
import { AILogs } from "./model";
import { useApi } from "@/shared/lib/hooks/useApi";

export default function Ai() {
  const api = useApi();
  const { data: aistats } = useAIStats();
  const [text, setText] = useState("");
  const [basicAlgorithmLog, setBasicAlgorithmLog] = useState("");
  const [newText, setNewText] = useState("Mine incidents");
  const [animate, setAnimate] = useState(false);

  const mutateAILogs = (logs: AILogs) => {
    setBasicAlgorithmLog(logs.log);
  };
  usePollAILogs(mutateAILogs);

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

  const mineIncidents = async (e: FormEvent) => {
    e.preventDefault();
    setAnimate(true);
    setNewText("Mining 🚀🚀🚀 ...");
    try {
      const response = await api.post(`/incidents/mine`, {});
    } catch (error) {
      toast.error(
        "Failed to mine incidents, please contact us if this issue persists."
      );
    }

    setAnimate(false);
    setNewText("Mine incidents");
  };

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
          {aistats?.is_mining_enabled == false && (
            <div>
              <div className="prose-2xl">👋 You are almost there!</div>
              AI Correlation is coming soon. Make sure you have enough data
              collected to prepare.
              <div className="max-w-md mt-10 flex justify-items-start justify-start">
                <List>
                  <ListItem>
                    <span>
                      Connect an incident source to dump incidents, or create 10
                      incidents manually
                    </span>
                    <span>
                      {aistats?.incidents_count &&
                      aistats?.incidents_count >= 10 ? (
                        <div>✅</div>
                      ) : (
                        <div>⏳</div>
                      )}
                    </span>
                  </ListItem>
                  <ListItem>
                    <span>Collect 100 alerts</span>
                    <span>
                      {aistats?.alerts_count && aistats?.alerts_count >= 100 ? (
                        <div>✅</div>
                      ) : (
                        <div>⏳</div>
                      )}
                    </span>
                  </ListItem>
                  <ListItem>
                    <span>Collect alerts for more than 3 days</span>
                    <span>
                      {aistats?.first_alert_datetime &&
                      new Date(aistats.first_alert_datetime) <
                        new Date(Date.now() - 3 * 24 * 60 * 60 * 1000) ? (
                        <div>✅</div>
                      ) : (
                        <div>⏳</div>
                      )}
                    </span>
                  </ListItem>
                </List>
              </div>
            </div>
          )}
          {aistats?.is_mining_enabled && (
            <div>
              <div className="grid grid-cols-2 gap-4 mt-6">
                <Card
                  className={
                    "p-4 flex flex-col justify-between w-full border-white border-2"
                  }
                >
                  <h3 className="text-lg sm:text-xl font-semibold line-clamp-2">
                    {aistats?.algorithm_verbose_name}
                  </h3>
                  <p className="text-sm">
                    Basic algorithm combining algorithmical methods to correlate
                    alerts to incidents and Large Language Models to provide
                    incident summary.
                  </p>

                  <div className="mt-4">
                    <Subtitle>Log:</Subtitle>
                    {!basicAlgorithmLog && <p>No recent logs found.</p>}
                    {basicAlgorithmLog}
                  </div>

                  <button
                    className={
                      (animate && "animate-pulse") +
                      " w-full text-white mt-2 pt-2 pb-2 pr-2 rounded-xl transition-all duration-500 bg-gradient-to-tl from-amber-800 via-amber-600 to-amber-400 bg-size-200 bg-pos-0 hover:bg-pos-100"
                    }
                    onClick={mineIncidents}
                  >
                    <div className="flex flex-row p-2">
                      <div className="p-2">
                        {animate && (
                          <svg
                            className="animate-spin h-6 w-6 text-white"
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                            ></circle>
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                            ></path>
                          </svg>
                        )}
                        {!animate && (
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                            className="w-6 h-6"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5"
                            />
                          </svg>
                        )}
                      </div>
                      <div className="pt-2">{text}</div>
                    </div>
                  </button>
                </Card>
                <Card
                  className={"p-4 flex flex-col w-full border-white border-2"}
                >
                  <h3 className="text-lg sm:text-xl font-semibold line-clamp-2">
                    Summarization v0.1
                  </h3>
                  <p className="text-sm top-0">
                    Using LLMs to provide a human-readable incident summary.
                  </p>
                </Card>
              </div>
            </div>
          )}
        </div>
      </Card>
    </main>
  );
}
