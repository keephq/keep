export const metadata = {
  title: "Keep",
  description: "The open-source alert management and AIOps platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
