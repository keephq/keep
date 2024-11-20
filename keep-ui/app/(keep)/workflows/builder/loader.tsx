import { Title, Text } from "@tremor/react";

export default function Loader() {
  return (
    <div className="flex flex-col h-full justify-center items-center">
      <Title>Please start by loading or creating a new alert</Title>
      <Text>You can use the `Load` or `+` button from the top right menu</Text>
    </div>
  );
}
