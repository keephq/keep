import { ReactNode } from "react";
import { AlertDto } from "@/entities/alerts/model";
import { Badge } from "@tremor/react";
import { FieldHeader } from "@/shared/ui";
import { DynamicImageProviderIcon } from "@/components/ui";
import { FormattedContent } from "@/shared/ui/FormattedContent/FormattedContent";
import { Link } from "@/components/ui";
import { Button } from "@tremor/react";
import { ClipboardDocumentIcon } from "@heroicons/react/24/outline";
import { QuestionMarkCircleIcon } from "@heroicons/react/20/solid";
import { Tooltip } from "@/shared/ui";

/**
 * Get a nested value from an object using dot notation path
 * Supports paths like "labels.alertname" or "annotations.description"
 * Also supports array indices like "incident_dto.0.assignee"
 */
function getNestedValue(obj: any, path: string): any {
  if (!obj || !path) return undefined;

  const keys = path.split(".");
  let value = obj;

  for (const key of keys) {
    if (value === null || value === undefined) {
      return undefined;
    }

    // Handle array index access
    const arrayMatch = key.match(/^(\w+)\[(\d+)\]$/);
    if (arrayMatch) {
      const [, arrayKey, index] = arrayMatch;
      value = value[arrayKey]?.[parseInt(index, 10)];
    } else {
      value = value[key];
    }
  }

  return value;
}

/**
 * Format a field name for display (convert snake_case or camelCase to Title Case)
 */
function formatFieldName(fieldPath: string): string {
  // Take the last part of the path for the label
  const parts = fieldPath.split(".");
  const lastPart = parts[parts.length - 1];

  // Convert snake_case or camelCase to spaces
  return lastPart
    .replace(/([A-Z])/g, " $1")
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase())
    .trim();
}

export type AlertSidebarFieldName =
  | "service"
  | "source"
  | "description"
  | "message"
  | "fingerprint"
  | "url"
  | "incidents"
  | "timeline"
  | "relatedServices";

export interface AlertSidebarFieldRendererProps {
  alert: AlertDto;
  providerName?: string;
  config?: any;
  handleCopyFingerprint?: (fingerprint: string) => void;
  handleCopyUrl?: (url: string | undefined) => void;
}

export interface AlertSidebarFieldConfig {
  name: AlertSidebarFieldName;
  shouldRender: (alert: AlertDto) => boolean;
  render: (props: AlertSidebarFieldRendererProps) => ReactNode;
}

export const alertSidebarFieldsConfig: Record<
  AlertSidebarFieldName,
  AlertSidebarFieldConfig
> = {
  service: {
    name: "service",
    shouldRender: (alert) => !!alert.service,
    render: ({ alert }) => (
      <p>
        <FieldHeader>Service</FieldHeader>
        <Badge size="sm" color="gray">
          {alert.service}
        </Badge>
      </p>
    ),
  },
  source: {
    name: "source",
    shouldRender: (alert) => !!alert.source && alert.source.length > 0,
    render: ({ alert, providerName }) => (
      <p>
        <FieldHeader>Source</FieldHeader>
        <DynamicImageProviderIcon
          src={`/icons/${alert.source![0]}-icon.png`}
          alt={alert.source![0]}
          providerType={alert.source![0]}
          width={24}
          height={24}
          className="inline-block w-6 h-6 mr-2"
        />
        <span>{providerName}</span>
      </p>
    ),
  },
  description: {
    name: "description",
    shouldRender: (alert) => !!alert.description,
    render: ({ alert }) => (
      <p>
        <FieldHeader>Description</FieldHeader>
        <FormattedContent
          content={alert.description}
          format={alert.description_format}
        />
      </p>
    ),
  },
  message: {
    name: "message",
    shouldRender: (alert) => !!alert.message,
    render: ({ alert }) => (
      <p>
        <FieldHeader>Message</FieldHeader>
        <span className="break-words">{alert.message}</span>
      </p>
    ),
  },
  fingerprint: {
    name: "fingerprint",
    shouldRender: () => true,
    render: ({ alert, config, handleCopyFingerprint }) => (
      <p>
        <FieldHeader className="flex items-center gap-1">
          Fingerprint
          <Tooltip
            content={
              <>
                Fingerprints are unique identifiers associated with alert
                instances in Keep. Each provider declares the fields fingerprints
                are calculated based on.{" "}
                <Link
                  href={`${
                    config?.KEEP_DOCS_URL || "https://docs.keephq.dev"
                  }/overview/fingerprints`}
                  className="text-white"
                >
                  Read more about it here.
                </Link>
              </>
            }
            className="z-[100]"
          >
            <QuestionMarkCircleIcon className="w-4 h-4" />
          </Tooltip>
        </FieldHeader>
        <div className="flex items-center gap-2">
          <span className="truncate max-w-[calc(100%-40px)] inline-block">
            {alert.fingerprint}
          </span>
          {handleCopyFingerprint && (
            <Button
              icon={ClipboardDocumentIcon}
              size="xs"
              color="orange"
              variant="light"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleCopyFingerprint(alert.fingerprint);
              }}
              tooltip="Copy fingerprint"
            />
          )}
        </div>
      </p>
    ),
  },
  url: {
    name: "url",
    shouldRender: (alert) => !!alert.url,
    render: ({ alert, handleCopyUrl }) => (
      <p>
        <FieldHeader>URL</FieldHeader>
        <div className="flex items-center gap-2">
          <Link
            href={alert.url!}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline truncate max-w-[calc(100%-40px)] inline-block"
          >
            {alert.url}
          </Link>
          {handleCopyUrl && (
            <Button
              icon={ClipboardDocumentIcon}
              size="xs"
              color="orange"
              variant="light"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                handleCopyUrl(alert.url);
              }}
              tooltip="Copy URL"
            />
          )}
        </div>
      </p>
    ),
  },
  incidents: {
    name: "incidents",
    shouldRender: (alert) => !!alert.incident_dto,
    render: () => null, // This is rendered separately in the component
  },
  timeline: {
    name: "timeline",
    shouldRender: () => true,
    render: () => null, // This is rendered separately in the component
  },
  relatedServices: {
    name: "relatedServices",
    shouldRender: () => true,
    render: () => null, // This is rendered separately in the component
  },
};

export function getEnabledFields(
  configuredFields: string[]
): AlertSidebarFieldName[] {
  return configuredFields.filter((field) =>
    Object.keys(alertSidebarFieldsConfig).includes(field)
  ) as AlertSidebarFieldName[];
}

/**
 * Get all custom fields that are not in the predefined field list
 */
export function getCustomFields(configuredFields: string[]): string[] {
  return configuredFields.filter(
    (field) => !Object.keys(alertSidebarFieldsConfig).includes(field)
  );
}

/**
 * Render a custom field from the alert object using dot notation path
 */
export function renderCustomField(
  alert: AlertDto,
  fieldPath: string
): ReactNode | null {
  const value = getNestedValue(alert as any, fieldPath);

  if (value === undefined || value === null || value === "") {
    return null;
  }

  const displayName = formatFieldName(fieldPath);

  // Format the value based on its type
  let displayValue: ReactNode;

  if (typeof value === "string") {
    // Check if it's a URL
    if (value.startsWith("http://") || value.startsWith("https://")) {
      displayValue = (
        <Link
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:underline break-all"
        >
          {value}
        </Link>
      );
    } else {
      displayValue = <span className="break-words">{value}</span>;
    }
  } else if (typeof value === "number" || typeof value === "boolean") {
    displayValue = <span>{String(value)}</span>;
  } else if (Array.isArray(value)) {
    // Display arrays as comma-separated values or badges
    displayValue = (
      <div className="flex flex-wrap gap-1">
        {value.map((item, index) => (
          <Badge key={index} size="sm" color="gray">
            {typeof item === "object" ? JSON.stringify(item) : String(item)}
          </Badge>
        ))}
      </div>
    );
  } else if (typeof value === "object") {
    // Display objects as formatted JSON
    displayValue = (
      <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-40">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  } else {
    displayValue = <span>{String(value)}</span>;
  }

  return (
    <p>
      <FieldHeader>{displayName}</FieldHeader>
      {displayValue}
    </p>
  );
}

