import { Title, Text } from "@tremor/react";

export function EmptyBuilderState() {
  return (
    <div className="flex flex-col h-full justify-center items-center">
      <Title>Please start by loading or creating a new workflow</Title>
      <Text>
        Load YAML or use the &quot;New&quot; button from the top right menu
      </Text>
    </div>
  );
}
