interface TraceSpan {
  children_ids: string[];
  duration: number;
  end: number;
  name: string;
  parent_id: string;
  resource: string;
  service: string;
  start: number;
  type: string;
  status: string;
  inferred_entity?: {
    entity: string;
    entity_key: string;
  };
  meta?: { [key: string]: string };
}

interface TraceData {
  root_id: string;
  spans: {
    [key: string]: TraceSpan;
  };
}

export type { TraceData, TraceSpan };
