import { RefreshCw } from "lucide-react";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const latestEmails = await prisma.emailMessage.findMany({
    orderBy: { receivedDateTime: "desc" },
    take: 30,
    include: {
      classifications: {
        orderBy: { createdAt: "desc" },
        take: 1
      }
    }
  });

  const latestClassifications = latestEmails.flatMap((email) => email.classifications);
  const critical = latestClassifications.filter((item) => item.priority === "CRITICAL").length;
  const high = latestClassifications.filter((item) => item.priority === "HIGH").length;
  const payments = latestClassifications.filter((item) => item.category === "PAYMENT_NEEDED_CCA_SERTIFI").length;
  const vip = latestClassifications.filter((item) => item.category === "VIP_OWNER_CELEBRITY").length;
  const complaints = latestClassifications.filter((item) => item.category === "GUEST_COMPLAINT").length;

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <strong>ReplyRight</strong>
          <span>Reservations@waldorfastoria.com</span>
        </div>
        <form action="/api/sync/unread" method="post">
          <button className="button" type="submit">
            <RefreshCw size={15} aria-hidden="true" /> Sync unread
          </button>
        </form>
      </header>

      <section className="content">
        <div className="summary-grid">
          <SummaryCard label="Unread Queue" value={latestEmails.length} />
          <SummaryCard label="Critical" value={critical} />
          <SummaryCard label="High" value={high} />
          <SummaryCard label="Payment Pending" value={payments} />
          <SummaryCard label="VIP Guests" value={vip} />
          <SummaryCard label="Complaints" value={complaints} />
        </div>

        <div className="toolbar">
          <h1>Active Queue</h1>
          <button className="button secondary" type="button">Filters</button>
        </div>

        <section className="panel">
          <div className="panel-header">
            <h2>Latest classifications</h2>
            <span className="muted">Dry-run mode is controlled by TRIAGE_DRY_RUN</span>
          </div>

          {latestEmails.length === 0 ? (
            <div className="empty">No synced messages yet. Configure Microsoft Graph, then sync unread mail.</div>
          ) : (
            <table className="queue">
              <thead>
                <tr>
                  <th>Message</th>
                  <th>Sender</th>
                  <th>Priority</th>
                  <th>Category</th>
                  <th>Deadline</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {latestEmails.map((email) => {
                  const classification = email.classifications[0];
                  return (
                    <tr key={email.id}>
                      <td>
                        <div className="subject">{email.subject || "(No subject)"}</div>
                        <div className="muted">{email.receivedDateTime.toLocaleString()}</div>
                      </td>
                      <td>
                        <div>{email.senderName || email.senderEmail}</div>
                        <div className="muted">{email.senderEmail}</div>
                      </td>
                      <td>
                        {classification ? (
                          <span className={`badge ${classification.priority.toLowerCase()}`}>
                            {formatEnum(classification.priority)}
                          </span>
                        ) : (
                          <span className="muted">Pending</span>
                        )}
                      </td>
                      <td>{classification ? formatEnum(classification.category) : "Pending"}</td>
                      <td>{classification?.recommendedDeadline ?? ""}</td>
                      <td>{classification?.reason ?? ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      </section>
    </main>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatEnum(value: string) {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
