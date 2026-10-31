// ATS Frontend — Pure JavaScript API Client
// Connects to Java Spring Boot 3 backend at localhost:8080 (or relative /api/v1 via Nginx)
// Strictly authoritative: no local mock data fallback, real errors are surfaced.

const API_BASE = (
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_URL) ||
  (typeof window !== "undefined" && window._ATS_API_URL) ||
  (typeof window !== "undefined" && !["5173", "5174", "5175"].includes(window.location.port) ? "/api/v1" : "http://localhost:8080/api/v1")
).replace(/\/+$/, "");

let authToken = typeof window !== "undefined" ? localStorage.getItem("ats_auth_token") : null;

export function getAuthToken() {
  return authToken;
}
export function setAuthToken(t) {
  authToken = t;
  if (typeof window !== "undefined") {
    if (t) {
      localStorage.setItem("ats_auth_token", t);
    } else {
      localStorage.removeItem("ats_auth_token");
    }
  }
}
export function clearAuthToken() {
  authToken = null;
  if (typeof window !== "undefined") {
    localStorage.removeItem("ats_auth_token");
  }
}

export class ApiError extends Error {
  constructor(message, status = 500, data = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

// ─── Status normalisation ────────────────────────────────────────────────────
const BACKEND_CANDIDATE_STATUS = {
  ACTIVE: "active",
  POOL: "pool",
  INTERVIEW_SCHEDULED: "interview_scheduled",
  SELECTED: "selected",
  JOINED: "joined",
  REJECTED: "rejected",
  LEFT_COMPANY: "left_company",
  INACTIVE: "inactive",
};
const BACKEND_APPLICATION_STATUS = {
  RECEIVED: "received",
  SCREENING: "screening",
  SHORTLISTED: "shortlisted",
  HR_INTERVIEW: "hr_interview",
  TECHNICAL_INTERVIEW: "technical_interview",
  CLIENT_INTERVIEW: "client_interview",
  OFFER_EXTENDED: "offer_extended",
  OFFER_ACCEPTED: "offer_accepted",
  HIRED: "hired",
  REJECTED: "rejected",
  WITHDRAWN: "withdrawn",
  ON_HOLD: "on_hold",
};
const FRONTEND_TO_BACKEND_STATUS = {
  active: "ACTIVE",
  pool: "POOL",
  interview_scheduled: "INTERVIEW_SCHEDULED",
  selected: "SELECTED",
  joined: "JOINED",
  rejected: "REJECTED",
  left_company: "LEFT_COMPANY",
  hired: "HIRED",
  withdrawn: "WITHDRAWN",
};

// ─── HTTP helper ─────────────────────────────────────────────────────────────
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint.startsWith("/") ? endpoint : "/" + endpoint}`;
  const headers = {
    ...(!(options.body instanceof FormData) && {
      "Content-Type": "application/json",
    }),
    ...(authToken && { Authorization: `Bearer ${authToken}` }),
    ...options.headers,
  };

  let res;
  try {
    res = await fetch(url, { ...options, headers });
  } catch (err) {
    console.error(`[API Network Error] ${options.method || "GET"} ${endpoint}:`, err);
    throw new ApiError(`Network error: backend service unreachable (${err.message})`, 0);
  }

  if (res.status === 401) {
    clearAuthToken();
    if (typeof window !== "undefined") {
      localStorage.removeItem("user");
      window.dispatchEvent(new CustomEvent("ats:unauthorized"));
    }
    throw new ApiError("Session expired or unauthorized. Please sign in again.", 401);
  }

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      errorDetail = errJson.message || errJson.error || JSON.stringify(errJson);
    } catch {
      const errText = await res.text().catch(() => "");
      if (errText) errorDetail = errText;
    }
    console.warn(`[API] ${options.method || "GET"} ${endpoint} → ${res.status}:`, errorDetail);
    throw new ApiError(errorDetail, res.status);
  }

  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// ─── Spring Data Page<T> unwrapper ──────────────────────────────────────────
function unwrapList(response) {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (response.content !== undefined) return response.content;
  if (response.items !== undefined) return response.items;
  if (response.data !== undefined) return response.data;
  return [];
}

// ─── Candidate transformer (Java backend → frontend shape) ───────────────────
function transformCandidate(c) {
  if (!c || typeof c !== "object") return c;

  let skills = [];
  if (Array.isArray(c.skills)) {
    skills = c.skills;
  } else if (c.skills && typeof c.skills === "object" && Array.isArray(c.skills.skills)) {
    skills = c.skills.skills;
  }

  const status = BACKEND_CANDIDATE_STATUS[c.status] || c.status || "active";

  return {
    id: c.id,
    name: c.name,
    email: c.email || "",
    phone: c.phone || "",
    location: c.location || "",
    company: c.company || "",
    clientId: c.client_id || c.clientId || "",
    clientName: c.selected_client_name || c.selectedClientName || c.clientName || (c.client ? c.client.name : ""),
    selectedClientName: c.selected_client_name || c.selectedClientName || c.clientName || "",
    skills,
    experienceYears: c.total_experience_years || c.experienceYears || 0,
    ctcCurrent: c.ctc_current || c.ctcCurrent || 0,
    ctcExpected: c.ctc_expected || c.ctcExpected || 0,
    noticePeriodDays: c.notice_period_days || c.noticePeriodDays || 0,
    currentStatus: status,
    isBlacklisted: Boolean(c.is_blacklisted || c.isBlacklisted),
    isDirectInterview: Boolean(c.is_direct_interview || c.isDirectInterview),
    resumeUrl: c.resume_url || c.resumeUrl || "",
    resumeFilePath: c.resume_file_path || c.resumeFilePath || "",
    keySkill: c.key_skill || c.keySkill || "",
    remark: c.remark || "",
    source: c.source || "MANUAL",
    linkedinUrl: c.linkedin_url || c.linkedinUrl || "",
    assignedUserId: c.assigned_user_id || c.assignedUserId || "",
    notes: c.notes || "",
    createdAt: c.created_at || c.createdAt || new Date().toISOString(),
    updatedAt: c.updated_at || c.updatedAt || new Date().toISOString(),
    resumeParsed: c.resumeParsed || null,
  };
}

// ─── Client transformer ──────────────────────────────────────────────────────
function transformClient(c) {
  if (!c || typeof c !== "object") return c;
  return {
    id: c.id,
    name: c.name,
    industry: c.industry || "Enterprise Software",
    contactName: c.contact_name || c.contactName || "",
    contactEmail: c.contact_email || c.contactEmail || "",
    contactPhone: c.contact_phone || c.contactPhone || "",
    address: c.address || "",
    website: c.website || "",
    emailDomain: c.email_domain || c.emailDomain || "",
    isActive: c.is_active !== undefined ? c.is_active : (c.isActive !== undefined ? c.isActive : true),
    candidateCount: c.candidate_count !== undefined ? c.candidate_count : (c.candidateCount || 0),
    activeJobsCount: c.active_jobs_count !== undefined ? c.active_jobs_count : (c.activeJobsCount || 0),
    createdAt: c.created_at || c.createdAt || new Date().toISOString(),
    updatedAt: c.updated_at || c.updatedAt || new Date().toISOString(),
  };
}

// ─── Application transformer ─────────────────────────────────────────────────
function transformApplication(a) {
  if (!a) return a;
  return {
    id: a.id,
    candidateId: a.candidate_id || a.candidateId,
    jobId: a.job_id || a.jobId,
    jobTitle: a.job_title || a.jobTitle || "Unknown Position",
    status: BACKEND_APPLICATION_STATUS[a.status] || a.status || "received",
    flaggedForReview: Boolean(a.flagged_for_review || a.flaggedForReview),
    flagReason: a.flag_reason || a.flagReason || "",
    notes: a.notes || "",
    source: a.source || "MANUAL",
    hrInterviewAcknowledged: Boolean(a.hr_interview_acknowledged),
    applicationDate: a.application_date || a.applicationDate || a.created_at,
    createdAt: a.created_at || a.createdAt,
    candidate: a.candidate ? transformCandidate(a.candidate) : null,
  };
}

// ─── Auth API ─────────────────────────────────────────────────────────────────
export const authApi = {
  async login(email, password) {
    const res = await request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    const token = res?.access_token || res?.token;
    if (token) {
      setAuthToken(token);
      return { success: true, user: res };
    }
    throw new ApiError("Authentication failed: No token received from server", 401);
  },

  async me() {
    const res = await request("/auth/me");
    if (!res) return null;
    return {
      id: res.id,
      email: res.email,
      name: res.full_name || res.name || res.email,
      role: (res.role || "client_user").toUpperCase(),
      clientId: res.client_id,
    };
  },

  logout() {
    clearAuthToken();
  },
};

// ─── Main API object ─────────────────────────────────────────────────────────
export const api = {
  // ── Auth ────────────────────────────────────────────────────────────────
  async login(email, password) {
    const res = await request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });

    const token = res?.token || res?.access_token;
    if (token) {
      setAuthToken(token);
      return {
        token: token,
        userId: res.userId || res.user_id || res.id,
        email: res.email || email,
        role: (res.role || "").toUpperCase(),
      };
    }
    throw new ApiError("Invalid email or password", 401);
  },

  async logout() {
    clearAuthToken();
    return { success: true };
  },

  // ── Candidates ──────────────────────────────────────────────────────────
  async getCandidates(filters = {}) {
    const params = new URLSearchParams();
    if (filters.search) params.set("search", filters.search);
    if (filters.location) params.set("location", filters.location);
    if (filters.skill) params.set("skill", filters.skill);
    if (filters.status) {
      params.set("status", FRONTEND_TO_BACKEND_STATUS[filters.status] || filters.status);
    }
    params.set("size", String(filters.size || 50));
    params.set("page", String(filters.page || 0));

    const remote = await request(`/candidates?${params}`);
    const list = unwrapList(remote);
    return list.map(transformCandidate).filter((c) => {
      if (filters.excludeLeavers !== false && c.isBlacklisted) return false;
      return true;
    });
  },

  async getCandidate(id) {
    const res = await request(`/candidates/${id}`);
    return res ? transformCandidate(res) : null;
  },

  async addCandidate(data) {
    const body = {
      name: data.name,
      email: data.email,
      phone: data.phone,
      location: data.location,
      company: data.company,
      key_skill: data.keySkill || data.key_skill || "",
      skills: Array.isArray(data.skills)
        ? data.skills
        : (data.skills || "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
      ctc_current: Number(data.ctcCurrent || data.ctc_current || 0),
      ctc_expected: Number(data.ctcExpected || data.ctc_expected || 0),
      total_experience_years: Number(data.experienceYears || data.total_experience_years || 0),
      notice_period_days: Number(data.noticePeriodDays || data.notice_period_days || 0),
      source: data.source || "MANUAL",
      linkedin_url: data.linkedinUrl || data.linkedin_url || "",
      remark: data.remark || "",
      client_id: data.clientId || data.client_id || null,
      selected_client_name: data.clientName || data.selectedClientName || data.selected_client_name || "",
    };

    const res = await request("/candidates", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return transformCandidate(res);
  },

  async updateCandidate(id, updateData) {
    const body = {};
    if (updateData.name !== undefined) body.name = updateData.name;
    if (updateData.email !== undefined) body.email = updateData.email;
    if (updateData.phone !== undefined) body.phone = updateData.phone;
    if (updateData.location !== undefined) body.location = updateData.location;
    if (updateData.company !== undefined) body.company = updateData.company;
    if (updateData.keySkill !== undefined) body.key_skill = updateData.keySkill;
    if (updateData.skills !== undefined) body.skills = updateData.skills;
    if (updateData.ctcCurrent !== undefined) body.ctc_current = updateData.ctcCurrent;
    if (updateData.ctcExpected !== undefined) body.ctc_expected = updateData.ctcExpected;
    if (updateData.experienceYears !== undefined) body.total_experience_years = updateData.experienceYears;
    if (updateData.noticePeriodDays !== undefined) body.notice_period_days = updateData.noticePeriodDays;
    if (updateData.remark !== undefined) body.remark = updateData.remark;
    if (updateData.linkedinUrl !== undefined) body.linkedin_url = updateData.linkedinUrl;
    if (updateData.clientId !== undefined) body.client_id = updateData.clientId;
    if (updateData.clientName !== undefined || updateData.selectedClientName !== undefined) {
      body.selected_client_name = updateData.clientName || updateData.selectedClientName;
    }

    const res = await request(`/candidates/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    return transformCandidate(res);
  },

  async deleteCandidate(id) {
    await request(`/candidates/${id}`, { method: "DELETE" });
    return true;
  },

  // ── FSM Status Transition ───────────────────────────────────────────────
  async transitionStatus(candidateId, newStatus, extraData = {}) {
    const backendStatus =
      FRONTEND_TO_BACKEND_STATUS[newStatus] || newStatus.toUpperCase();

    const appRes = await request(`/candidates/${candidateId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: backendStatus, ...extraData }),
    });
    return transformCandidate(appRes);
  },

  // ── Applications ────────────────────────────────────────────────────────
  async getApplications(filters = {}) {
    const params = new URLSearchParams();
    if (filters.candidateId) params.set("candidateId", filters.candidateId);
    if (filters.status) {
      params.set("status", FRONTEND_TO_BACKEND_STATUS[filters.status] || filters.status);
    }
    params.set("size", String(filters.size || 50));
    params.set("page", String(filters.page || 0));

    const res = await request(`/applications?${params}`);
    const list = unwrapList(res);
    return list.map(transformApplication);
  },

  async createApplication(data) {
    const body = {
      candidate_id: data.candidateId,
      job_id: data.jobId || null,
      job_title: data.jobTitle || null,
      source: data.source || "MANUAL",
      notes: data.notes || null,
    };
    const res = await request("/applications", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return transformApplication(res);
  },

  async transitionApplicationStatus(applicationId, newStatus) {
    const backendStatus =
      FRONTEND_TO_BACKEND_STATUS[newStatus] || newStatus.toUpperCase();
    const res = await request(`/applications/${applicationId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: backendStatus }),
    });
    return transformApplication(res);
  },

  // ── Jobs ────────────────────────────────────────────────────────────────
  async getJobs(filters = {}) {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status.toUpperCase());
    params.set("size", String(filters.size || 50));
    params.set("page", String(filters.page || 0));
    const res = await request(`/jobs?${params}`);
    return unwrapList(res);
  },

  async getVacantJobs() {
    const res = await request("/jobs/vacant");
    return unwrapList(res);
  },

  async createJob(data) {
    const newJob = {
      title: data.title,
      company_name: data.companyName || data.company_name || "Enterprise ATS",
      client_id: data.clientId || data.client_id || null,
      requirements: data.requirements || "",
      department: data.department || "Engineering",
      location: data.location || "Remote",
      employment_type: data.employmentType || "FULL_TIME",
      openings_count: Number(data.openingsCount || 1),
      experience_required: Number(data.experienceRequired || 0),
      salary_lpa: Number(data.salaryLpa || 0),
      status: "OPEN",
    };

    const res = await request("/jobs", {
      method: "POST",
      body: JSON.stringify(newJob),
    });
    return res;
  },

  // ── Resume Upload & Ingestion ──────────────────────────────────────────
  async uploadResume(file, clientId = null) {
    const formData = new FormData();
    formData.append("file", file);
    if (clientId) formData.append("clientId", clientId);

    const res = await request("/candidates/upload-resume", {
      method: "POST",
      body: formData,
    });
    return transformCandidate(res);
  },

  async bulkUploadResumes(files, clientId = null) {
    const formData = new FormData();
    for (const f of files) {
      formData.append("files", f);
    }
    if (clientId) formData.append("clientId", clientId);

    const res = await request("/candidates/bulk-upload", {
      method: "POST",
      body: formData,
    });
    if (res && res.candidates) {
      res.candidates = res.candidates.map(transformCandidate);
    }
    return res;
  },

  // ── Email Ingestion Pipeline ────────────────────────────────────────────
  async pollEmailInbox() {
    return await request("/email/poll", { method: "POST" });
  },

  async getEmailStatus() {
    return await request("/email/status");
  },

  // ── Check Duplicates ────────────────────────────────────────────────────
  async checkDuplicates(name, email, phone) {
    const res = await request("/candidates/check-duplicates", {
      method: "POST",
      body: JSON.stringify({ name, email, phone }),
    });
    return Array.isArray(res) ? res : [];
  },

  // ── Activity Logs ───────────────────────────────────────────────────────
  async getActivityLogs(page = 0, size = 50) {
    const res = await request(`/activity-logs?page=${page}&size=${size}`);
    return unwrapList(res);
  },

  // ── Clients ─────────────────────────────────────────────────────────────
  async getClients() {
    const res = await request("/clients");
    const list = unwrapList(res);
    return list.map(transformClient);
  },

  async getClient(id) {
    const res = await request(`/clients/${id}`);
    return res && res.id ? transformClient(res) : null;
  },

  async createClient(data) {
    const body = {
      name: data.name,
      industry: data.industry || "Enterprise Software",
      contact_name: data.contactName || data.contact_name || "",
      contact_email: data.contactEmail || data.contact_email || "",
      contact_phone: data.contactPhone || data.contact_phone || "",
      address: data.address || "",
      website: data.website || "",
      email_domain: data.emailDomain || data.email_domain || "",
      is_active: data.isActive !== undefined ? data.isActive : true,
    };
    const res = await request("/clients", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return transformClient(res);
  },

  async updateClient(id, data) {
    const body = {
      name: data.name,
      industry: data.industry,
      contact_name: data.contactName || data.contact_name,
      contact_email: data.contactEmail || data.contact_email,
      contact_phone: data.contactPhone || data.contact_phone,
      address: data.address,
      website: data.website,
      email_domain: data.emailDomain || data.email_domain,
      is_active: data.isActive,
    };
    const res = await request(`/clients/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    return transformClient(res);
  },

  async deleteClient(id) {
    await request(`/clients/${id}`, { method: "DELETE" });
    return true;
  },

  async inviteClientUser(clientId) {
    return await request(`/clients/${clientId}/invite`, { method: "POST" });
  },

  async assignCandidateToClient(candidateId, clientId, clientName, notes = "") {
    const body = {
      client_id: clientId,
      selected_client_name: clientName,
      status: "ACTIVE",
      remark: notes ? `Assigned to ${clientName}: ${notes}` : `Assigned to ${clientName}`,
    };
    const res = await request(`/candidates/${candidateId}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    return transformCandidate(res);
  },
};
