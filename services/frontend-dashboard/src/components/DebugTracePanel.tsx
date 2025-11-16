import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import type { WorkflowRun } from "../api/types";

export function DebugTracePanel({ workflow }: { workflow: WorkflowRun | null }) {
  const [open, setOpen] = useState(false);
  const rows = workflow
    ? [
        ["workflow_id", workflow.id],
        ["correlation_id", workflow.correlation_id],
        ["order_id", workflow.order_id],
        ["status", workflow.status],
        ["current_step", workflow.current_step],
        ["invoice_document_id", workflow.invoice_document_id],
        ["receipt_document_id", workflow.receipt_document_id],
        ["payment_id", workflow.payment_id],
        ["notification_id", workflow.notification_id],
        ["failure_code", workflow.failure_code],
        ["last_error", workflow.last_error]
      ]
    : [];

  return (
    <section className="panel debug-panel">
      <button className="debug-toggle" type="button" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
        Debug / technical trace
      </button>
      {open && (
        <dl className="debug-grid">
          {rows.map(([key, value]) => (
            <div key={key || ""}>
              <dt>{key}</dt>
              <dd>{value || "-"}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
