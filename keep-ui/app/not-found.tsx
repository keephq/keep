import Image from 'next/image';
import styles from './not-found.module.css';

export default function NotFound() {
  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Under construction 👷🏾‍♂️👷🏻‍♀️</h2>
      <h3>Visit our <a href="https://github.com/orgs/keephq/projects/1">Roadmap</a> and drop a ⭐️ and ⬆️</h3>
      <div className={styles.image}>
        <Image src="/keep.svg" alt="Keep" width={150} height={150} />
      </div>
    </div>
  );
}
