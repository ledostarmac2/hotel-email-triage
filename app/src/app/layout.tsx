import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "ReplyRight",
  description: "AI-powered Outlook shared mailbox triage for reservation teams"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
