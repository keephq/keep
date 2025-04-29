"use server";

import path from "path";
import fs from "fs";

const baseExamples = path.join(process.cwd(), "../examples/workflows");

export async function saveFile(filename: string, yamlString: string) {
  fs.writeFileSync(path.join(baseExamples, filename), yamlString);
}
