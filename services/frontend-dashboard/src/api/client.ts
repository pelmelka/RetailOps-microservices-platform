import type {
  AuthUser,
  CatalogItem,
  LoginResponse,
  Order,
  OrderHistoryEntry,
  PaymentScenario,
  WorkflowAccepted,
  WorkflowRun
} from "./types";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

type RequestOptions = {
  token?: string | null;
  idempotencyKey?: string;
  body?: unknown;
};

async function apiFetch<T>(
  path: string,
  method: string = "GET",
  options: RequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }
  if (options.idempotencyKey) {
    headers["Idempotency-Key"] = options.idempotencyKey;
  }
  const response = await fetch(`${configuredBaseUrl}${path}`, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message =
      data?.error?.message ||
      data?.detail ||
      `HTTP ${response.status}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data as T;
}

export function createIdempotencyKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export const api = {
  register(body: {
    username: string;
    email: string;
    display_name?: string;
    password: string;
  }) {
    return apiFetch<AuthUser>("/api/auth/register", "POST", { body });
  },

  login(body: { username: string; password: string }) {
    return apiFetch<LoginResponse>("/api/auth/login", "POST", { body });
  },

  me(token: string) {
    return apiFetch<AuthUser>("/api/auth/me", "GET", { token });
  },

  catalog() {
    return apiFetch<{ items: CatalogItem[] }>("/api/catalog/items");
  },

  orders(token: string) {
    return apiFetch<{ orders: Order[] }>("/api/orders", "GET", { token });
  },

  createOrder(
    token: string,
    body: { catalog_item_id: string; quantity: number },
    idempotencyKey: string
  ) {
    return apiFetch<WorkflowAccepted>("/api/orders", "POST", {
      token,
      idempotencyKey,
      body
    });
  },

  workflow(token: string, workflowId: string) {
    return apiFetch<WorkflowRun>(`/api/workflows/${workflowId}`, "GET", { token });
  },

  workflowByOrder(token: string, orderId: string) {
    return apiFetch<WorkflowRun>(`/api/orders/${orderId}/workflow`, "GET", {
      token
    });
  },

  history(token: string, orderId: string) {
    return apiFetch<{ history: OrderHistoryEntry[] }>(
      `/api/orders/${orderId}/history`,
      "GET",
      { token }
    );
  },

  requestPayment(
    token: string,
    orderId: string,
    paymentScenario: PaymentScenario,
    idempotencyKey: string
  ) {
    return apiFetch<WorkflowAccepted>(`/api/orders/${orderId}/payments`, "POST", {
      token,
      idempotencyKey,
      body: { payment_scenario: paymentScenario }
    });
  },

  async downloadDocument(token: string, orderId: string, documentId: string) {
    const response = await fetch(
      `${configuredBaseUrl}/api/orders/${orderId}/documents/${documentId}/download`,
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );
    if (!response.ok) {
      throw new Error(`PDF download failed: HTTP ${response.status}`);
    }
    return response.blob();
  }
};
