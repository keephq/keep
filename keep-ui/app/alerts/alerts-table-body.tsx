import {
  ArrowDownIcon,
  ArrowDownRightIcon,
  ArrowRightIcon,
  ArrowTopRightOnSquareIcon,
  ArrowUpIcon,
  ArrowUpRightIcon,
  Cog8ToothIcon,
  TicketIcon,
} from "@heroicons/react/24/outline";
import {
  TableBody,
  TableRow,
  TableCell,
  CategoryBar,
  Icon,
  Accordion,
  AccordionHeader,
  AccordionBody,
} from "@tremor/react";
import { Alert, AlertKnownKeys, Severity } from "./models";
import Image from "next/image";
import "./alerts-table-body.css";
import AlertMenu from "./alert-menu";
import { Workflow } from "app/workflows/models";
import { useRouter } from "next/navigation";
import PushPullBadge from "@/components/ui/push-pulled-badge/push-pulled-badge";
import moment from "moment";
import { Provider } from "app/providers/providers";

interface Props {
  data: Alert[];
  groupBy?: string;
  groupedByData?: { [key: string]: Alert[] };
  openModal?: (alert: Alert) => void;
  workflows?: Workflow[];
  providers?: Provider[];
  mutate?: () => void;
}

const getSeverity = (severity: Severity | undefined) => {
  let icon: any;
  let color: any;
  let severityText: string;
  switch (severity) {
    case "critical":
      icon = ArrowUpIcon;
      color = "red";
      severityText = Severity.Critical.toString();
      break;
    case "high":
      icon = ArrowUpRightIcon;
      color = "orange";
      severityText = Severity.High.toString();
      break;
    case "medium":
      color = "yellow";
      icon = ArrowRightIcon;
      severityText = Severity.Medium.toString();
      break;
    case "low":
      icon = ArrowDownRightIcon;
      color = "green";
      severityText = Severity.Low.toString();
      break;
    default:
      icon = ArrowDownIcon;
      color = "emerald";
      severityText = Severity.Info.toString();
      break;
  }
  return (
    <Icon
      //deltaType={deltaType as DeltaType}
      color={color}
      icon={icon}
      tooltip={severityText}
      size="sm"
      className="ml-2.5"
    ></Icon>
  );
};

export function AlertsTableBody({
  data,
  groupBy,
  groupedByData,
  openModal,
  workflows,
  providers,
  mutate,
}: Props) {
  const router = useRouter();
  const getAlertLastReceieved = (alert: Alert) => {
    let lastReceived = "unknown";
    if (alert.lastReceived) {
      lastReceived = alert.lastReceived.toString();
      try {
        lastReceived = moment(alert.lastReceived).fromNow();
      } catch {}
    }
    return lastReceived;
  };

  const handleWorkflowClick = (workflows: Workflow[]) => {
    if (workflows.length === 1) {
      router.push(`workflows/${workflows[0].id}`);
    } else {
      router.push("workflows");
    }
  };

  return (
    <TableBody>
      {data
        .sort((a, b) => b.lastReceived.getTime() - a.lastReceived.getTime())
        .map((alert) => {
          const extraPayloadNoKnownKeys = Object.keys(alert)
            .filter((key) => !AlertKnownKeys.includes(key))
            .reduce((obj, key) => {
              return {
                ...obj,
                [key]: (alert as any)[key],
              };
            }, {});
          const extraIsEmpty =
            Object.keys(extraPayloadNoKnownKeys).length === 0;
          const ticketUrl = (alert as any)["ticket_url"];
          const relevantWorkflows =
            workflows?.filter((workflow) => {
              const alertTrigger = workflow.triggers.find(
                (trigger) => trigger.type === "alert"
              );

              const workflowIsRelevant = alertTrigger?.filters?.every(
                (filter) => {
                  if (filter.key === "source") {
                    return alert.source?.includes(filter.value);
                  }
                  return (
                    (alert as any)[filter.key] === filter.value ||
                    (extraPayloadNoKnownKeys as any)[filter.key] ===
                      filter.value
                  );
                }
              );
              return workflowIsRelevant;
            }) ?? [];
          return (
            <TableRow key={alert.id}>
              {
                <TableCell className="pb-9">
                  <AlertMenu
                    alert={alert}
                    canOpenHistory={!groupedByData![(alert as any)[groupBy!]]}
                    openHistory={() => openModal!(alert)}
                    provider={providers?.find(
                      (p) => p.type === alert.source![0]
                    )}
                    mutate={mutate}
                  />
                </TableCell>
              }
              <TableCell>{getSeverity(alert.severity)}</TableCell>
              <TableCell className="max-w-[340px]">
                <div className="flex items-center justify-between">
                  <div className="truncate" title={alert.name}>
                    {alert.name}{" "}
                  </div>
                  <div>
                    {(alert.url ?? alert.generatorURL) && (
                      <a href={alert.url || alert.generatorURL} target="_blank">
                        <Icon
                          icon={ArrowTopRightOnSquareIcon}
                          tooltip="Open Original Alert"
                          color="gray"
                          variant="solid"
                          size="xs"
                          className="ml-1"
                        />
                      </a>
                    )}
                    {ticketUrl && (
                      <a href={ticketUrl} target="_blank">
                        <Icon
                          icon={TicketIcon}
                          tooltip="Ticket Assigned"
                          size="xs"
                          color="gray"
                          className="ml-1"
                          variant="solid"
                        />
                      </a>
                    )}
                    {relevantWorkflows?.length > 0 && (
                      <Icon
                        icon={Cog8ToothIcon}
                        size="xs"
                        color={`${
                          relevantWorkflows.every(
                            (wf) => wf.last_execution_status === "success"
                          )
                            ? "green"
                            : relevantWorkflows.some(
                                (wf) => wf.last_execution_status === "error"
                              )
                            ? "red"
                            : relevantWorkflows.some(
                                (wf) =>
                                  wf.last_execution_status ===
                                  "providers_not_configured"
                              )
                            ? "amber"
                            : "gray"
                        }`}
                        tooltip={`${
                          relevantWorkflows.every(
                            (wf) => wf.last_execution_status === "success"
                          )
                            ? "All workflows executed successfully"
                            : relevantWorkflows.some(
                                (wf) => wf.last_execution_status === "error"
                              )
                            ? "Some workflows failed to execute"
                            : relevantWorkflows.some(
                                (wf) =>
                                  wf.last_execution_status ===
                                  "providers_not_configured"
                              )
                            ? "Some workflows are not configured"
                            : "Workflows have yet to execute"
                        }`}
                        onClick={() => handleWorkflowClick(relevantWorkflows)}
                        className="ml-1 cursor-pointer"
                        variant="solid"
                      />
                    )}
                  </div>
                </div>
              </TableCell>
              <TableCell className="max-w-[340px]">
                <div className="truncate">{alert.description}</div>
              </TableCell>
              <TableCell>
                <PushPullBadge pushed={alert.pushed} />
              </TableCell>
              <TableCell>{alert.status}</TableCell>
              <TableCell>{getAlertLastReceieved(alert)}</TableCell>
              <TableCell>
                {alert.source?.map((source, index) => {
                  return (
                    <Image
                      className={`inline-block ${index == 0 ? "" : "-ml-2"}`}
                      key={source}
                      alt={source}
                      height={24}
                      width={24}
                      title={source}
                      src={`/icons/${source}-icon.png`}
                    />
                  );
                })}
              </TableCell>

              <TableCell>
                <CategoryBar
                  values={[40, 30, 20, 10]}
                  colors={["emerald", "yellow", "orange", "rose"]}
                  markerValue={alert.fatigueMeter ?? 0}
                  tooltip={alert.fatigueMeter?.toString() ?? "0"}
                  className="w-48"
                />
              </TableCell>
              {/* <TableCell>List of workflows refs</TableCell> */}
              <TableCell className="w-96">
                {extraIsEmpty ? null : (
                  <Accordion>
                    <AccordionHeader className="w-96">
                      Extra Payload
                    </AccordionHeader>
                    <AccordionBody>
                      <pre className="w-80 overflow-y-scroll">
                        {JSON.stringify(extraPayloadNoKnownKeys, null, 2)}
                      </pre>
                    </AccordionBody>
                  </Accordion>
                )}
              </TableCell>
            </TableRow>
          );
        })}
    </TableBody>
  );
}
