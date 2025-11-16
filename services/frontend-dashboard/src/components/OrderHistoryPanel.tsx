import type { OrderHistoryEntry } from "../api/types";
import { historyStatusLabel } from "./WorkflowTimeline";

export function OrderHistoryPanel({
  orderId,
  history,
  loading
}: {
  orderId: string | null;
  history: OrderHistoryEntry[];
  loading: boolean;
}) {
  const subtitle = !orderId
    ? "Выберите заказ"
    : loading
      ? "Загружаем историю..."
      : history.length
        ? `${history.length} статусов`
        : "История заказа пока пуста";

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>История заказа</h2>
          <p>{subtitle}</p>
        </div>
      </div>
      <ul className="history-list">
        {loading && (
          <li className="empty-state">
            <span>Загружаем историю...</span>
          </li>
        )}
        {!loading && orderId && !history.length && (
          <li className="empty-state">
            <span>История заказа пока пуста</span>
          </li>
        )}
        {!loading &&
          history.map((entry) => (
            <li key={entry.id}>
              <time>{new Date(entry.created_at).toLocaleString("ru-RU")}</time>
              <strong>{historyStatusLabel(entry.status)}</strong>
              {entry.reason && <span>{entry.reason}</span>}
            </li>
          ))}
      </ul>
    </section>
  );
}
