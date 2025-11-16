import { Check, Circle, X } from "lucide-react";
import type { WorkflowRun } from "../api/types";

type TimelineStep = {
  key: string;
  activeLabel: string;
  doneLabel?: string;
  failureOnly?: boolean;
};

const baseSteps: TimelineStep[] = [
  { key: "accepted", activeLabel: "Запрос принят" },
  {
    key: "order_creating",
    activeLabel: "Заказ создаётся",
    doneLabel: "Заказ создан"
  },
  {
    key: "invoice_generating",
    activeLabel: "Счёт формируется",
    doneLabel: "Счёт готов"
  },
  { key: "awaiting_payment", activeLabel: "Ожидается оплата" },
  { key: "payment_requested", activeLabel: "Оплата запрошена" },
  { key: "payment_processing", activeLabel: "Оплата обрабатывается" },
  {
    key: "payment_failed",
    activeLabel: "Оплата не прошла",
    failureOnly: true
  },
  {
    key: "receipt_generating",
    activeLabel: "Чек формируется",
    doneLabel: "Чек готов"
  },
  {
    key: "notification_sending",
    activeLabel: "Уведомление отправляется",
    doneLabel: "Уведомление отправлено"
  },
  { key: "completed", activeLabel: "Workflow завершён" },
  { key: "failed", activeLabel: "Workflow завершился с ошибкой" }
];

export function statusLabel(status?: string | null): string {
  const labels: Record<string, string> = {
    accepted: "Запрос принят",
    order_creating: "Заказ создаётся",
    invoice_generating: "Счёт формируется",
    awaiting_payment: "Ожидается оплата",
    payment_requested: "Оплата запрошена",
    payment_processing: "Оплата обрабатывается",
    payment_failed: "Оплата не прошла",
    receipt_generating: "Чек формируется",
    notification_sending: "Уведомление отправляется",
    notification_failed: "Уведомление не отправлено",
    completed: "Workflow завершён",
    failed: "Workflow завершился с ошибкой",
    created: "Заказ создан",
    invoice_generated: "Счёт сформирован",
    payment_completed: "Оплата прошла",
    receipt_generated: "Чек готов",
    notification_sent: "Уведомление отправлено"
  };
  return status ? labels[status] || status : "Нет активного workflow";
}

export function historyStatusLabel(status?: string | null): string {
  const labels: Record<string, string> = {
    created: "Заказ создан",
    invoice_generated: "Счёт сформирован",
    payment_completed: "Оплата прошла",
    payment_failed: "Оплата не прошла",
    receipt_generated: "Чек готов",
    notification_sent: "Уведомление отправлено"
  };
  return status ? labels[status] || statusLabel(status) : "Нет статуса";
}

export function orderListStatusLabel(
  orderStatus: string,
  workflow?: WorkflowRun | null
): string {
  if (workflow?.status === "completed") return "Заказ завершён";
  if (workflow?.status === "failed") return "Workflow завершился с ошибкой";
  if (workflow?.failure_code) return "Оплата не прошла";
  if (workflow?.status === "awaiting_payment") return "Ожидается оплата";
  if (orderStatus === "notification_sent") return "Заказ завершён";
  if (orderStatus === "receipt_generated") return "Чек готов";
  if (orderStatus === "payment_completed") return "Оплата прошла";
  if (orderStatus === "payment_failed") return "Оплата не прошла";
  if (orderStatus === "invoice_generated") return "Счёт сформирован";
  return historyStatusLabel(orderStatus);
}

export function failureLabel(failureCode?: string | null): string {
  if (failureCode === "INSUFFICIENT_FUNDS") {
    return "Причина: недостаточно средств";
  }
  if (failureCode === "PROVIDER_UNAVAILABLE") {
    return "Платёжный провайдер временно недоступен";
  }
  if (failureCode === "SUSPECTED_FRAUD") return "Оплата отклонена";
  return failureCode ? `Failure code: ${failureCode}` : "";
}

function shouldShowFailureStep(workflow: WorkflowRun | null): boolean {
  return Boolean(
    workflow?.failure_code ||
      workflow?.failed_step === "payment" ||
      workflow?.current_step === "payment_failed"
  );
}

function timelineSteps(workflow: WorkflowRun | null): TimelineStep[] {
  const includeFailure = shouldShowFailureStep(workflow);
  return baseSteps.filter((step) => !step.failureOnly || includeFailure);
}

function stepLabel(step: TimelineStep, done: boolean): string {
  return done && step.doneLabel ? step.doneLabel : step.activeLabel;
}

export function WorkflowTimeline({ workflow }: { workflow: WorkflowRun | null }) {
  const current = workflow?.current_step || workflow?.status || "";
  const steps = timelineSteps(workflow);
  const stepIndex = new Map(steps.map((step, index) => [step.key, index]));
  const currentIndex = stepIndex.get(current) ?? -1;
  const terminalFailed = workflow?.status === "failed";

  return (
    <section className="panel timeline-panel">
      <div className="panel-header">
        <div>
          <h2>Workflow status</h2>
          <p>{statusLabel(workflow?.status)}</p>
        </div>
      </div>
      <ol className="timeline">
        {steps.map((step, index) => {
          const active =
            step.key === current || (terminalFailed && step.key === "failed");
          const done = !terminalFailed && currentIndex > index;
          return (
            <li className={active ? "active" : done ? "done" : ""} key={step.key}>
              <span className="timeline-icon">
                {terminalFailed && step.key === "failed" ? (
                  <X size={14} />
                ) : done ? (
                  <Check size={14} />
                ) : (
                  <Circle size={14} />
                )}
              </span>
              <span>{stepLabel(step, done)}</span>
            </li>
          );
        })}
      </ol>
      {workflow?.failure_code && (
        <div className="failure-box">
          <strong>{failureLabel(workflow.failure_code)}</strong>
          <span>Failure code: {workflow.failure_code}</span>
          {workflow.last_error && <small>{workflow.last_error}</small>}
        </div>
      )}
    </section>
  );
}
