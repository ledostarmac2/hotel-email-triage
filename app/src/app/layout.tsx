import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Waldorf Reservations Triage",
  description: "AI-powered Outlook shared mailbox triage for Waldorf Astoria New York Reservations"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
