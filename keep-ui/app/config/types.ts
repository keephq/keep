export interface AWSTag {
  Key: string;
  Value: string;
}

export interface Config {
  aws: {
    tags: AWSTag[];
  };
  // ... other config properties
}
