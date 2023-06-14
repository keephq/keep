import Image from 'next/image';

export default function Loading() {
  return (
    <main className="flex items-center justify-center min-h-screen">
      <Image src='/keep_loading_new.gif' alt="loading" width={200} height={200}/>
    </main>
  );
}
