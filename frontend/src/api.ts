// Thin fetch wrapper: session-cookie auth + CSRF header on unsafe methods.

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

export class ApiError extends Error {
  status: number;
  data: any;
  constructor(status: number, data: any) {
    super(typeof data?.detail === "string" ? data.detail : `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const opts: RequestInit = { method, credentials: "same-origin", headers };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = getCookie("csrftoken");
    if (token) headers["X-CSRFToken"] = token;
  }

  const res = await fetch(`/api${path}`, opts);
  if (res.status === 204) return undefined as T;

  let data: any = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

export const api = {
  get: <T>(p: string) => request<T>("GET", p),
  post: <T>(p: string, b?: unknown) => request<T>("POST", p, b),
  put: <T>(p: string, b?: unknown) => request<T>("PUT", p, b),
  patch: <T>(p: string, b?: unknown) => request<T>("PATCH", p, b),
};

// ---- Types -------------------------------------------------------------- //

export interface Onboarding {
  llm_configured: boolean;
  linkedin_configured: boolean;
  has_campaign: boolean;
  complete: boolean;
}
export interface User {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
}
export interface Me {
  user: User;
  onboarding: Onboarding;
}
export interface Campaign {
  id: number;
  name: string;
  product_docs: string;
  campaign_objective: string;
  booking_link: string;
  seed_public_ids: string[];
  action_fraction: number;
  is_freemium: boolean;
  enabled: boolean;
  auto_send: boolean;
  connection_note_template: string;
  follow_up_template: string;
}
export interface LinkedInProfile {
  linkedin_username: string;
  linkedin_password_set?: boolean;
  active?: boolean;
  connect_daily_limit?: number;
  follow_up_daily_limit?: number;
  subscribe_newsletter?: boolean;
  connection_status: string;
  last_login_error?: string;
}
export interface LLMSettings {
  llm_provider: string;
  ai_model: string;
  llm_api_base: string;
  llm_api_key_set: boolean;
}
export interface QueueMessage {
  id: number;
  campaign: number;
  campaign_name: string;
  lead: number;
  lead_name: string;
  kind: string;
  status: string;
  body: string;
  created_at: string;
  sent_at: string | null;
}
export interface Deal {
  id: number;
  public_identifier: string;
  linkedin_url: string;
  campaign: number;
  campaign_name: string;
  state: string;
  outcome: string;
  reason: string;
  update_date: string;
}
export interface ChatMsg {
  id: number;
  content: string;
  is_outgoing: boolean;
  creation_date: string;
}
export interface Dashboard {
  campaigns: { id: number; name: string; enabled: boolean; auto_send: boolean }[];
  deals_by_state: Record<string, number>;
  tasks_by_status: Record<string, number>;
  actions_today: { connect: number; follow_up: number };
  daily_limits: { connect: number; follow_up: number };
  pending_approvals: number;
  linkedin_status: string;
  onboarding: Onboarding;
}
