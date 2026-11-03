import type { Metadata } from "next";
import "./generated.css";

export const metadata: Metadata = {
  title: "FINN | Investment Intelligence",
  description: "Portfolio signals and primary-source management guidance research.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
