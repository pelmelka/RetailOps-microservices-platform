export type AuthUser = {
  user_id: string;
  username: string;
  email: string;
  display_name?: string | null;
  is_active?: boolean;
};

export type LoginResponse = AuthUser & {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type CatalogItem = {
  id: string;
  sku: string;
  name: string;
  description: string;
  price_kopecks: number;
  currency: "RUB";
};

export type Order = {
  id: string;
  user_id: string;
  catalog_item_id: string;
  status: string;
  quantity: number;
  unit_price_kopecks: number;
  total_kopecks: number;
  currency: string;
  created_at: string;
  updated_at: string;
};

export type OrderHistoryEntry = {
  id: string;
  order_id: string;
  status: string;
  reason?: string | null;
  created_at: string;
};

export type PaymentScenario =
  | "success"
  | "insufficient_funds"
  | "provider_unavailable"
  | "suspected_fraud";

export type WorkflowRun = {
  id: string;
  workflow_type: string;
  user_id: string;
  user_email?: string | null;
  order_id?: string | null;
  status: string;
  current_step?: string | null;
  failed_step?: string | null;
  failure_code?: string | null;
  last_error?: string | null;
  correlation_id: string;
  idempotency_key?: string | null;
  invoice_document_id?: string | null;
  receipt_document_id?: string | null;
  payment_id?: string | null;
  notification_id?: string | null;
  payment_scenario?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type WorkflowAccepted = {
  workflow_id: string;
  status: string;
  correlation_id: string;
  order_id?: string | null;
};

export type ApiError = {
  error?: {
    code: string;
    message: string;
    correlation_id?: string | null;
  };
  detail?: unknown;
};
