import Image from "next/image";
import styles from "./under-construction.module.css";
import Frill from "./frill";
import { Card } from "@tremor/react";

export default function UnderConstruction() {
  return (
    <>
      <Frill />
      <main className="p-4 md:p-10 mx-auto max-w-7xl">
        <Card className="p-4 md:p-10 h-5/6 mx-auto max-w-7xl mt-6">
          <div className={styles.container}>
            <h2 className={styles.title}>Under construction 👷🏾‍♂️👷🏻‍♀️</h2>
            <h3>
              Visit our{" "}
              <a href="https://github.com/orgs/keephq/projects/1">Roadmap</a>{" "}
              and drop a ⭐️ and ⬆️
            </h3>
            <div className="mt-5">
              <Image src="/keep.png" alt="Keep" width={96} height={96} />
            </div>
          </div>
        </Card>
      </main>
    </>
  );
}
