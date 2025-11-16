import { Download } from "lucide-react";
import type { WorkflowRun } from "../api/types";

type Props = {
  workflow: WorkflowRun | null;
  busy: boolean;
  onDownload: (documentId: string, kind: "invoice" | "receipt") => void;
};

export function DocumentsPanel({ workflow, busy, onDownload }: Props) {
  const orderId = workflow?.order_id;
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Документы</h2>
          <p>{orderId ? `order_id: ${orderId}` : "Заказ ещё создаётся"}</p>
        </div>
      </div>
      <div className="document-grid">
        <div className="document-row">
          <span>Счёт</span>
          <strong>{workflow?.invoice_document_id ? "Счёт готов" : "Формируется"}</strong>
          <button
            className="secondary-button"
            type="button"
            disabled={!workflow?.invoice_document_id || !orderId || busy}
            onClick={() => workflow?.invoice_document_id && onDownload(workflow.invoice_document_id, "invoice")}
          >
            <Download size={18} />
            Скачать invoice PDF
          </button>
        </div>
        <div className="document-row">
          <span>Чек</span>
          <strong>{workflow?.receipt_document_id ? "Чек готов" : "Ожидает оплату"}</strong>
          <button
            className="secondary-button"
            type="button"
            disabled={!workflow?.receipt_document_id || !orderId || busy}
            onClick={() => workflow?.receipt_document_id && onDownload(workflow.receipt_document_id, "receipt")}
          >
            <Download size={18} />
            Скачать receipt PDF
          </button>
        </div>
      </div>
      {workflow?.notification_id && (
        <p className="status-note success">Уведомление отправлено</p>
      )}
      {workflow?.status === "notification_failed" && (
        <p className="status-note danger">Уведомление не отправлено</p>
      )}
    </section>
  );
}
