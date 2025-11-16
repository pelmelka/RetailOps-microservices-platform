import { RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, createIdempotencyKey } from "./api/client";
import type {
  AuthUser,
  CatalogItem,
  Order,
  OrderHistoryEntry,
  PaymentScenario,
  WorkflowRun
} from "./api/types";
import { AuthPanel } from "./components/AuthPanel";
import { CatalogPanel } from "./components/CatalogPanel";
import { DebugTracePanel } from "./components/DebugTracePanel";
import { DocumentsPanel } from "./components/DocumentsPanel";
import { OrderHistoryPanel } from "./components/OrderHistoryPanel";
import { PaymentSimulationPanel } from "./components/PaymentSimulationPanel";
import {
  WorkflowTimeline,
  orderListStatusLabel,
  statusLabel
} from "./components/WorkflowTimeline";

const tokenStorageKey = "mwp-dashboard-token";
const workflowStorageKey = "mwp-dashboard-workflow-id";
const selectedOrderStorageKey = "mwp-dashboard-selected-order-id";
const activeStatuses = new Set([
  "accepted",
  "order_creating",
  "invoice_generating",
  "payment_requested",
  "payment_processing",
  "receipt_generating",
  "notification_sending"
]);

const moneyFormatter = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB"
});

export function App() {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(tokenStorageKey)
  );
  const [user, setUser] = useState<AuthUser | null>(null);
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedItemId, setSelectedItemId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(() =>
    localStorage.getItem(selectedOrderStorageKey)
  );
  const [workflowId, setWorkflowId] = useState<string | null>(() =>
    localStorage.getItem(workflowStorageKey)
  );
  const [workflow, setWorkflow] = useState<WorkflowRun | null>(null);
  const [historyByOrderId, setHistoryByOrderId] = useState<
    Record<string, OrderHistoryEntry[]>
  >({});
  const [historyLoadingOrderId, setHistoryLoadingOrderId] = useState<string | null>(
    null
  );
  const [paymentScenario, setPaymentScenario] =
    useState<PaymentScenario>("success");
  const [pollRevision, setPollRevision] = useState(0);
  const [selectionRevision, setSelectionRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const selectedItem = useMemo(
    () => catalog.find((item) => item.id === selectedItemId) || null,
    [catalog, selectedItemId]
  );

  const selectedOrder = useMemo(
    () => orders.find((order) => order.id === selectedOrderId) || null,
    [orders, selectedOrderId]
  );

  const currentItem = useMemo(() => {
    const itemId = selectedOrder?.catalog_item_id || selectedItemId;
    return catalog.find((item) => item.id === itemId) || null;
  }, [catalog, selectedOrder?.catalog_item_id, selectedItemId]);

  const selectedWorkflow = useMemo(() => {
    if (!workflow) return null;
    if (!selectedOrderId) return workflow;
    return workflow.order_id === selectedOrderId ? workflow : null;
  }, [workflow, selectedOrderId]);

  const selectedHistory = selectedOrderId
    ? historyByOrderId[selectedOrderId] || []
    : [];
  const historyLoading = Boolean(
    selectedOrderId && historyLoadingOrderId === selectedOrderId
  );
  const currentQuantity = selectedOrder?.quantity || quantity;
  const currentTotalKopecks =
    selectedOrder?.total_kopecks ??
    (currentItem ? currentItem.price_kopecks * quantity : null);

  useEffect(() => {
    loadCatalog();
  }, []);

  useEffect(() => {
    if (!token) return;
    api.me(token).then(setUser).catch(() => logout());
    loadOrders(token);
  }, [token]);

  useEffect(() => {
    if (!catalog.length || selectedItemId) return;
    setSelectedItemId(catalog[0].id);
  }, [catalog, selectedItemId]);

  useEffect(() => {
    if (!token || !selectedOrderId) return;
    const activeToken = token;
    const activeOrderId = selectedOrderId;
    const currentWorkflowMatches = workflow?.order_id === activeOrderId;
    let cancelled = false;

    async function loadSelectedOrderContext() {
      setHistoryLoadingOrderId(activeOrderId);
      if (!currentWorkflowMatches) {
        setWorkflow(null);
        setWorkflowId(null);
        localStorage.removeItem(workflowStorageKey);
      }

      const workflowPromise: Promise<WorkflowRun> = currentWorkflowMatches && workflow
        ? Promise.resolve(workflow)
        : api.workflowByOrder(activeToken, activeOrderId);

      const [workflowResult, historyResult] = await Promise.allSettled([
        workflowPromise,
        api.history(activeToken, activeOrderId)
      ]);
      if (cancelled) return;

      if (workflowResult.status === "fulfilled") {
        setWorkflow(workflowResult.value);
        setWorkflowId(workflowResult.value.id);
        localStorage.setItem(workflowStorageKey, workflowResult.value.id);
      } else {
        setWorkflow(null);
        setWorkflowId(null);
        localStorage.removeItem(workflowStorageKey);
      }

      setHistoryByOrderId((previous) => ({
        ...previous,
        [activeOrderId]:
          historyResult.status === "fulfilled" ? historyResult.value.history : []
      }));
      setHistoryLoadingOrderId((current) =>
        current === activeOrderId ? null : current
      );
    }

    loadSelectedOrderContext();
    return () => {
      cancelled = true;
    };
  }, [token, selectedOrderId, selectionRevision]);

  useEffect(() => {
    if (!token || !workflowId) return;
    const activeToken = token;
    const activeWorkflowId = workflowId;
    let cancelled = false;
    let timer: number | undefined;

    async function poll() {
      try {
        const next = await api.workflow(activeToken, activeWorkflowId);
        if (cancelled) return;
        setWorkflow(next);
        if (next.order_id) {
          setSelectedOrderId(next.order_id);
          localStorage.setItem(selectedOrderStorageKey, next.order_id);
          await Promise.all([
            loadHistory(activeToken, next.order_id),
            loadOrders(activeToken)
          ]);
        }
        if (!cancelled && activeStatuses.has(next.status)) {
          timer = window.setTimeout(poll, 1500);
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(
            error instanceof Error ? error.message : "Workflow недоступен"
          );
        }
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [token, workflowId, pollRevision]);

  async function loadCatalog() {
    try {
      const response = await api.catalog();
      setCatalog(response.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Каталог недоступен");
    }
  }

  async function loadOrders(activeToken = token) {
    if (!activeToken) return;
    try {
      const response = await api.orders(activeToken);
      setOrders(response.orders);
    } catch {
      setOrders([]);
    }
  }

  async function loadHistory(activeToken: string, orderId: string) {
    setHistoryLoadingOrderId(orderId);
    try {
      const response = await api.history(activeToken, orderId);
      setHistoryByOrderId((previous) => ({
        ...previous,
        [orderId]: response.history
      }));
    } catch {
      setHistoryByOrderId((previous) => ({ ...previous, [orderId]: [] }));
    } finally {
      setHistoryLoadingOrderId((current) => (current === orderId ? null : current));
    }
  }

  async function refreshCurrentContext() {
    if (!token) return;
    if (selectedOrderId) {
      setSelectionRevision((revision) => revision + 1);
      return;
    }
    if (!workflowId) return;
    const next = await api.workflow(token, workflowId);
    setWorkflow(next);
    if (next.order_id) {
      setSelectedOrderId(next.order_id);
      localStorage.setItem(selectedOrderStorageKey, next.order_id);
      await Promise.all([loadHistory(token, next.order_id), loadOrders(token)]);
    }
  }

  function handleLogin(nextToken: string, nextUser: AuthUser) {
    setToken(nextToken);
    setUser(nextUser);
    localStorage.setItem(tokenStorageKey, nextToken);
  }

  function logout() {
    setToken(null);
    setUser(null);
    setWorkflow(null);
    setWorkflowId(null);
    setSelectedOrderId(null);
    setHistoryByOrderId({});
    setHistoryLoadingOrderId(null);
    localStorage.removeItem(tokenStorageKey);
    localStorage.removeItem(workflowStorageKey);
    localStorage.removeItem(selectedOrderStorageKey);
  }

  async function createOrder() {
    if (!token || !selectedItemId) return;
    setBusy(true);
    setMessage("");
    try {
      const accepted = await api.createOrder(
        token,
        { catalog_item_id: selectedItemId, quantity },
        createIdempotencyKey("dashboard-order")
      );
      setWorkflowId(accepted.workflow_id);
      setWorkflow(null);
      setSelectedOrderId(accepted.order_id || null);
      setHistoryLoadingOrderId(null);
      localStorage.setItem(workflowStorageKey, accepted.workflow_id);
      if (accepted.order_id) {
        localStorage.setItem(selectedOrderStorageKey, accepted.order_id);
      } else {
        localStorage.removeItem(selectedOrderStorageKey);
      }
      setPollRevision((revision) => revision + 1);
      setMessage(`Workflow принят в обработку: ${accepted.workflow_id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Заказ не создан");
    } finally {
      setBusy(false);
    }
  }

  async function requestPayment() {
    if (!token || !selectedWorkflow?.order_id) return;
    setBusy(true);
    setMessage("");
    try {
      await api.requestPayment(
        token,
        selectedWorkflow.order_id,
        paymentScenario,
        createIdempotencyKey("dashboard-payment")
      );
      setMessage("Запрос оплаты принят");
      setWorkflowId(selectedWorkflow.id);
      localStorage.setItem(workflowStorageKey, selectedWorkflow.id);
      setPollRevision((revision) => revision + 1);
      const next = await api.workflow(token, selectedWorkflow.id);
      setWorkflow(next);
      if (next.order_id) {
        setSelectedOrderId(next.order_id);
        localStorage.setItem(selectedOrderStorageKey, next.order_id);
        await Promise.all([loadHistory(token, next.order_id), loadOrders(token)]);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Оплата не запущена");
    } finally {
      setBusy(false);
    }
  }

  async function downloadDocument(documentId: string, kind: "invoice" | "receipt") {
    if (!token || !selectedWorkflow?.order_id) return;
    setBusy(true);
    setMessage("");
    try {
      const blob = await api.downloadDocument(
        token,
        selectedWorkflow.order_id,
        documentId
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${kind}-${selectedWorkflow.order_id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Документ не скачан");
    } finally {
      setBusy(false);
    }
  }

  function openOrder(order: Order) {
    setSelectedOrderId(order.id);
    localStorage.setItem(selectedOrderStorageKey, order.id);
    setSelectionRevision((revision) => revision + 1);
    setMessage(
      `Открыт заказ ${order.id}. Workflow можно продолжить из текущего экрана.`
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>Панель async workflow</h1>
          <p>
            {selectedWorkflow
              ? `${statusLabel(selectedWorkflow.status)} · workflow_id: ${selectedWorkflow.id}`
              : selectedOrderId
                ? `Заказ ${selectedOrderId}`
                : "Создайте заказ и дождитесь статуса awaiting_payment"}
          </p>
        </div>
        <button
          className="icon-button"
          type="button"
          onClick={refreshCurrentContext}
          title="Обновить workflow"
        >
          <RefreshCw size={18} />
        </button>
      </header>

      <AuthPanel token={token} user={user} onLogin={handleLogin} onLogout={logout} />

      <div className="dashboard-grid">
        <div className="main-column">
          <CatalogPanel
            items={catalog}
            selectedItemId={selectedItemId}
            quantity={quantity}
            busy={busy}
            disabled={!token}
            onRefresh={loadCatalog}
            onSelectItem={setSelectedItemId}
            onQuantityChange={setQuantity}
            onCreateOrder={createOrder}
          />
          <WorkflowTimeline workflow={selectedWorkflow} />
          <DocumentsPanel
            workflow={selectedWorkflow}
            busy={busy}
            onDownload={downloadDocument}
          />
          <PaymentSimulationPanel
            workflow={selectedWorkflow}
            scenario={paymentScenario}
            busy={busy}
            onScenarioChange={setPaymentScenario}
            onPay={requestPayment}
          />
        </div>

        <aside className="side-column">
          <section className="panel">
            <div className="panel-header">
              <div>
                <h2>Текущий заказ</h2>
                <p>
                  {currentItem
                    ? currentItem.name
                    : selectedOrder?.catalog_item_id || "Товар не выбран"}
                </p>
              </div>
            </div>
            <dl className="summary-grid">
              <div>
                <dt>Количество</dt>
                <dd>{currentQuantity}</dd>
              </div>
              <div>
                <dt>Сумма</dt>
                <dd>
                  {currentTotalKopecks === null
                    ? "-"
                    : moneyFormatter.format(currentTotalKopecks / 100)}
                </dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>
                  {selectedOrder
                    ? orderListStatusLabel(selectedOrder.status, selectedWorkflow)
                    : statusLabel(selectedWorkflow?.status)}
                </dd>
              </div>
            </dl>
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <h2>Мои заказы</h2>
                <p>{orders.length ? `${orders.length} заказов` : "Список пуст"}</p>
              </div>
            </div>
            <ul className="orders-list">
              {orders.map((order) => (
                <li key={order.id}>
                  <button
                    className={selectedOrderId === order.id ? "selected" : ""}
                    type="button"
                    aria-pressed={selectedOrderId === order.id}
                    onClick={() => openOrder(order)}
                  >
                    <strong>{order.id}</strong>
                    <span>
                      {orderListStatusLabel(
                        order.status,
                        selectedWorkflow?.order_id === order.id
                          ? selectedWorkflow
                          : null
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <OrderHistoryPanel
            orderId={selectedOrderId}
            history={selectedHistory}
            loading={historyLoading}
          />
          <DebugTracePanel workflow={selectedWorkflow} />
        </aside>
      </div>

      {message && <div className="toast">{message}</div>}
    </main>
  );
}
