export enum Severity {
    Critical = "critical",
    High = "high",
    Medium = "medium",
    Low = "low",
    Info = "info",
}

export interface Alert {
    id: string;
    name: string;
    status: string;
    lastReceived: Date;
    environment: string;
    isDuplicate?: boolean;
    service?: string;
    source?: string[];
    message?: string;
    description?: string;
    severity?: Severity;
}

export const AlertTableKeys: string[] = ['Severity', 'Status', 'Last Received', 'Duplicate', 'Environment', 'Service', 'Source', 'Message', 'Description']
