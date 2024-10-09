export interface ContentDto {
  id: string;
  content: string;
  link: string;
  encoding: string | null;
  file_name: string;
}
export interface RunbookDto {
  id: number;
  title: string;
  contents: ContentDto[];
  provider_type: string;
  provider_id: string;
  repo_id: string;
  file_path: string;
}

export type RunbookResponse = {
  runbooks: RunbookDto[];
  total_count: number;
};
