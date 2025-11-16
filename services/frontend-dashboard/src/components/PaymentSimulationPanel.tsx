import { CreditCard } from "lucide-react";
import type { PaymentScenario, WorkflowRun } from "../api/types";

const scenarios: Array<{ value: PaymentScenario; label: string }> = [
  { value: "success", label: "Успешная оплата" },
  { value: "insufficient_funds", label: "Недостаточно средств" },
  { value: "provider_unavailable", label: "Провайдер временно недоступен" },
  { value: "suspected_fraud", label: "Подозрение на fraud" }
];

type Props = {
  workflow: WorkflowRun | null;
  scenario: PaymentScenario;
  busy: boolean;
  onScenarioChange: (scenario: PaymentScenario) => void;
  onPay: () => void;
};

function canPay(workflow: WorkflowRun | null): boolean {
  if (!workflow?.order_id) return false;
  if (workflow.status === "completed" || workflow.status === "failed") return false;
  if (workflow.status === "awaiting_payment") return true;
  return workflow.current_step === "payment_failed";
}

export function PaymentSimulationPanel({
  workflow,
  scenario,
  busy,
  onScenarioChange,
  onPay
}: Props) {
  if (workflow?.status === "completed") {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Оплата</h2>
            <p>Оплата уже завершена, повторный запуск недоступен.</p>
          </div>
        </div>
        {workflow.payment_id && (
          <p className="status-note success">payment_id: {workflow.payment_id}</p>
        )}
      </section>
    );
  }

  if (workflow?.status === "failed" && workflow.failure_code === "SUSPECTED_FRAUD") {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Оплата</h2>
            <p>Оплата отклонена, повторный запуск недоступен.</p>
          </div>
        </div>
        <p className="status-note danger">Failure code: SUSPECTED_FRAUD</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Оплата</h2>
          <p>Local payment simulation — локальный сценарий оплаты для проверки workflow.</p>
        </div>
      </div>
      <div className="segmented">
        {scenarios.map((item) => (
          <button
            className={scenario === item.value ? "selected" : ""}
            key={item.value}
            type="button"
            onClick={() => onScenarioChange(item.value)}
            disabled={!canPay(workflow) || busy}
          >
            {item.label}
          </button>
        ))}
      </div>
      <button
        className="primary-button"
        type="button"
        onClick={onPay}
        disabled={!canPay(workflow) || busy}
      >
        <CreditCard size={18} />
        Запустить оплату
      </button>
      {workflow?.failure_code === "SUSPECTED_FRAUD" && (
        <p className="status-note danger">Повторная оплата скрыта: workflow заблокирован.</p>
      )}
    </section>
  );
}
