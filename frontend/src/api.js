// ATS Frontend — Pure JavaScript API Client
// Connects to Java Spring Boot 3 backend at localhost:8080
// Falls back to rich local demo state when backend is offline

const API_BASE = (
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_URL) ||
  window._ATS_API_URL ||
  "http://localhost:8080/api/v1"
).replace(/\/+$/, "");

let authToken = localStorage.getItem("ats_auth_token");

export function getAuthToken() {
  return authToken;
}
export function setAuthToken(t) {
  authToken = t;
  localStorage.setItem("ats_auth_token", t);
}
export function clearAuthToken() {
  authToken = null;
  localStorage.removeItem("ats_auth_token");
}

// ─── Status normalisation ────────────────────────────────────────────────────
// Maps Java backend SCREAMING_SNAKE_CASE → frontend camelCase / lowercase
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

// ─── Demo data (used as fallback when backend is offline) ───────────────────
const INITIAL_CLIENTS = [
  {
    id: "client-001",
    name: "Acme Corp",
    industry: "Enterprise Cloud & SaaS",
    contactName: "Johnathan Doe",
    contactEmail: "client@example.com",
    contactPhone: "+1 (555) 234-5678",
    address: "100 Technology Square, Suite 400, Cambridge, MA",
    website: "https://acmecorp.com",
    emailDomain: "acmecorp.com",
    isActive: true,
    candidateCount: 3,
    activeJobsCount: 4,
    createdAt: "2026-01-15T10:00:00Z",
  },
  {
    id: "client-002",
    name: "TechCorp Innovations",
    industry: "AI & Financial Technology",
    contactName: "Elena Rostova",
    contactEmail: "elena@techcorp.io",
    contactPhone: "+1 (555) 789-0123",
    address: "500 Market St, San Francisco, CA",
    website: "https://techcorp.io",
    emailDomain: "techcorp.io",
    isActive: true,
    candidateCount: 2,
    activeJobsCount: 3,
    createdAt: "2026-02-01T12:00:00Z",
  },
  {
    id: "client-003",
    name: "GlobalHealth Systems",
    industry: "Healthcare & MedTech",
    contactName: "Dr. Marcus Vance",
    contactEmail: "mvance@globalhealth.org",
    contactPhone: "+1 (555) 456-7890",
    address: "75 Binney Street, Boston, MA",
    website: "https://globalhealth.org",
    emailDomain: "globalhealth.org",
    isActive: true,
    candidateCount: 1,
    activeJobsCount: 2,
    createdAt: "2026-02-18T14:30:00Z",
  },
  {
    id: "client-004",
    name: "FinEdge Capital",
    industry: "Quantitative Trading & Banking",
    contactName: "Sophie Martin",
    contactEmail: "smartin@finedge.com",
    contactPhone: "+44 20 7123 4567",
    address: "25 Bank Street, Canary Wharf, London",
    website: "https://finedge.com",
    emailDomain: "finedge.com",
    isActive: true,
    candidateCount: 0,
    activeJobsCount: 5,
    createdAt: "2026-03-05T09:15:00Z",
  },
];

const INITIAL_CANDIDATES = [
  {
    id: "cand-101",
    name: "Aman Ansari",
    email: "aman.ansari@techhub.io",
    phone: "+91 98765 43210",
    location: "Bangalore",
    skills: ["Java", "Spring Boot", "React", "PostgreSQL", "Docker"],
    experienceYears: 6,
    ctcCurrent: 2400000,
    ctcExpected: 3200000,
    currentStatus: "interview_scheduled",
    isBlacklisted: false,
    clientId: "client-001",
    clientName: "Acme Corp",
    selectedClientName: "Acme Corp",
    notes: "Strong backend with Spring Boot 3 & microservices.",
    resumeParsed: {
      summary:
        "Full-stack Software Engineer with 6+ years in distributed systems.",
      education: "B.Tech Computer Science, 2018",
      recentCompany: "Razorpay",
      recentRole: "Senior Backend Engineer",
      parsedText:
        "AMAN ANSARI\nSenior Backend Engineer | Bangalore, India\nSkills: Java 21, Spring Boot 3, PostgreSQL RLS, React, Docker",
    },
  },
  {
    id: "cand-102",
    name: "Sarah Jenkins",
    email: "sarah.jenkins@cloudmail.com",
    phone: "+44 20 7946 0912",
    location: "London",
    skills: ["Python", "FastAPI", "PostgreSQL", "Machine Learning", "NLP"],
    experienceYears: 5,
    ctcCurrent: 65000,
    ctcExpected: 80000,
    currentStatus: "screening",
    isBlacklisted: false,
    clientId: "client-002",
    clientName: "TechCorp Innovations",
    selectedClientName: "TechCorp Innovations",
    notes: "Parsed via email webhook. Skills extracted via PDF OCR.",
    resumeParsed: {
      summary: "NLP Engineer specialising in automated document parsing.",
      education: "M.Sc Data Science, University of Edinburgh",
      recentCompany: "TalentAI UK",
      recentRole: "NLP Data Engineer",
      parsedText:
        "SARAH JENKINS\nNLP Data Engineer | London\nSkills: Python, FastAPI, Tesseract OCR, PostgreSQL, Celery",
    },
  },
  {
    id: "cand-103",
    name: "David Chen",
    email: "david.chen@enterprise.dev",
    phone: "+1 415 555 0198",
    location: "San Francisco",
    skills: ["React", "JavaScript", "HTML", "CSS", "Node.js"],
    experienceYears: 7,
    ctcCurrent: 140000,
    ctcExpected: 165000,
    currentStatus: "selected",
    isBlacklisted: false,
    clientId: "client-001",
    clientName: "Acme Corp",
    selectedClientName: "Acme Corp",
    notes: "Client Acme Corp selected after Round 2 system design.",
    resumeParsed: {
      summary: "Senior Frontend Architect, React design systems & performance.",
      education: "B.S. Computer Engineering, UC Berkeley",
      recentCompany: "Stripe",
      recentRole: "Staff Frontend Engineer",
      parsedText:
        "DAVID CHEN\nStaff Frontend Engineer | San Francisco\nSkills: React, JavaScript ES2024, Vanilla CSS, Web Performance",
    },
  },
  {
    id: "cand-104",
    name: "Robert 'Bob' Smith",
    email: "rsmith.former@legacy.co",
    phone: "+1 202 555 0177",
    location: "New York",
    skills: ["Java", "Oracle", "Spring"],
    experienceYears: 9,
    ctcCurrent: 120000,
    ctcExpected: 135000,
    currentStatus: "left_company",
    isBlacklisted: true,
    clientId: "client-001",
    clientName: "Acme Corp",
    selectedClientName: "Acme Corp",
    notes: "LEFT COMPANY 2025-11-30. AUTO-BLACKLISTED by FSM trigger.",
    resumeParsed: {
      summary: "Former Acme Corp employee. Excluded from talent search.",
      education: "B.S. Information Systems",
      recentCompany: "Acme Corp (Left)",
      recentRole: "Java Developer",
      parsedText:
        "ROBERT SMITH (LEAVER) — Ineligible for re-engagement per HR policy.",
    },
  },
  {
    id: "cand-105",
    name: "Priya Sharma",
    email: "priya.sharma@innovate.in",
    phone: "+91 99887 76655",
    location: "Bangalore",
    skills: ["Python", "Django", "React", "PostgreSQL", "AWS"],
    experienceYears: 4,
    ctcCurrent: 1800000,
    ctcExpected: 2500000,
    currentStatus: "joined",
    isBlacklisted: false,
    clientId: "client-002",
    clientName: "TechCorp Innovations",
    selectedClientName: "TechCorp Innovations",
    notes:
      "Joined TechCorp Bangalore as Full Stack Dev. Onboarded successfully.",
    resumeParsed: {
      summary: "Full Stack Engineer with 4 years in fintech APIs & web apps.",
      education: "B.Tech Computer Science, NIT Karnataka",
      recentCompany: "TechCorp",
      recentRole: "Full Stack Developer",
      parsedText:
        "PRIYA SHARMA\nFull Stack Developer | Bangalore\nSkills: Python, Django, React, PostgreSQL, AWS",
    },
  },
  {
    id: "cand-106",
    name: "Michael Chang",
    email: "mchang@cloudops.net",
    phone: "+1 206 555 0144",
    location: "Seattle",
    skills: ["Kubernetes", "AWS", "Terraform", "Go", "Docker"],
    experienceYears: 8,
    ctcCurrent: 175000,
    ctcExpected: 205000,
    currentStatus: "active",
    isBlacklisted: false,
    clientId: "client-003",
    clientName: "GlobalHealth Systems",
    selectedClientName: "GlobalHealth Systems",
    notes: "Platform DevOps architect with HIPAA compliance experience.",
    resumeParsed: {
      summary: "Cloud Platform and Infrastructure Engineer.",
      education: "B.S. Software Engineering, University of Washington",
      recentCompany: "Nordstrom",
      recentRole: "Senior SRE Engineer",
      parsedText:
        "MICHAEL CHANG\nSenior SRE Engineer | Seattle\nSkills: Kubernetes, AWS, Terraform, Go, CI/CD",
    },
  },
];

let localCandidates = [...INITIAL_CANDIDATES];
const savedCandidates = localStorage.getItem("ats_candidates_db");
if (savedCandidates) {
  try {
    localCandidates = JSON.parse(savedCandidates);
  } catch {
    /* keep defaults */
  }
}
function persistCandidates() {
  localStorage.setItem("ats_candidates_db", JSON.stringify(localCandidates));
}

let localClients = [...INITIAL_CLIENTS];
const savedClients = localStorage.getItem("ats_clients_db");
if (savedClients) {
  try {
    localClients = JSON.parse(savedClients);
  } catch {
    /* keep defaults */
  }
}
function persistClients() {
  localStorage.setItem("ats_clients_db", JSON.stringify(localClients));
}

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

  try {
    const res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
      clearAuthToken();
      window.location.href = "/login";
      return null;
    }
    if (!res.ok) {
      const err = await res.text().catch(() => `HTTP ${res.status}`);
      console.warn(
        `[API] ${options.method || "GET"} ${endpoint} → ${res.status}:`,
        err,
      );
      return null;
    }

    const text = await res.text();
    if (!text) return {};
    return JSON.parse(text);
  } catch (err) {
    console.info(`[API Offline] ${endpoint} — using local data:`, err.message);
    return null;
  }
}

// ─── Spring Data Page<T> unwrapper ──────────────────────────────────────────
// Spring returns: { content: [], totalElements, totalPages, size, number }
// Python returned: plain array or { items: [], total, page }
function unwrapList(response) {
  if (!response) return null;
  if (Array.isArray(response)) return response;
  if (response.content !== undefined) return response.content; // Spring Page<T>
  if (response.items !== undefined) return response.items;
  if (response.data !== undefined) return response.data;
  return [];
}

// ─── Candidate transformer (Java backend → frontend shape) ───────────────────
function transformCandidate(c) {
  if (!c || typeof c !== "object") return c;

  // Extract skills from Java JSONB: stored as List<String> in Spring
  let skills = [];
  if (Array.isArray(c.skills)) {
    skills = c.skills;
  } else if (
    c.skills &&
    typeof c.skills === "object" &&
    Array.isArray(c.skills.skills)
  ) {
    skills = c.skills.skills; // legacy Python wrapper
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
    // Keep legacy resumeParsed if available (demo/local)
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
    if (res && res.access_token) {
      setAuthToken(res.access_token);
      return { success: true, user: res };
    }
    return { success: false, error: "Invalid email or password" };
  },

  async me() {
    const res = await request("/auth/me");
    if (!res) return null;
    return {
      id: res.id,
      email: res.email,
      name: res.full_name || res.name || res.email,
      role: (res.role || "client_user").toLowerCase(),
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

    if (res && res.token) {
      setAuthToken(res.token);
      return {
        token: res.token,
        userId: res.userId,
        email: res.email,
        role: res.role,
      };
    }

    // Fallback for demo/development (when backend is offline)
    // Check against demo credentials
    const demoUsers = {
      "admin@example.com": {
        password: "admin123",
        role: "ADMIN",
        userId: "user-1",
      },
      "client@example.com": {
        password: "client123",
        role: "CLIENT",
        userId: "user-2",
      },
    };

    const demoUser = demoUsers[email];
    if (demoUser && demoUser.password === password) {
      const demoToken = btoa(`${email}:${Date.now()}`);
      setAuthToken(demoToken);
      return {
        token: demoToken,
        userId: demoUser.userId,
        email: email,
        role: demoUser.role,
      };
    }

    throw new Error("Invalid email or password");
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
    if (filters.status)
      params.set(
        "status",
        FRONTEND_TO_BACKEND_STATUS[filters.status] || filters.status,
      );
    params.set("size", String(filters.size || 50));
    params.set("page", String(filters.page || 0));

    const remote = await request(`/candidates?${params}`);
    const list = unwrapList(remote);

    if (list) {
      return list.map(transformCandidate).filter((c) => {
        // Enforce leaver exclusion from HR view
        if (filters.excludeLeavers !== false && c.isBlacklisted) return false;
        return true;
      });
    }

    // Local fallback
    return localCandidates.filter((c) => {
      if (filters.excludeLeavers !== false && c.isBlacklisted) return false;
      if (filters.search) {
        const q = filters.search.toLowerCase();
        if (
          !c.name.toLowerCase().includes(q) &&
          !c.email.toLowerCase().includes(q) &&
          !c.skills.some((s) => s.toLowerCase().includes(q))
        )
          return false;
      }
      if (filters.location && filters.location !== "All") {
        if (!c.location.toLowerCase().includes(filters.location.toLowerCase()))
          return false;
      }
      if (filters.skill && filters.skill !== "All") {
        if (
          !c.skills.some((s) => s.toLowerCase() === filters.skill.toLowerCase())
        )
          return false;
      }
      return true;
    });
  },

  async getCandidate(id) {
    const res = await request(`/candidates/${id}`);
    return res
      ? transformCandidate(res)
      : localCandidates.find((c) => c.id === id) || null;
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
      total_experience_years: Number(
        data.experienceYears || data.total_experience_years || 0,
      ),
      notice_period_days: Number(
        data.noticePeriodDays || data.notice_period_days || 0,
      ),
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
    if (res) return transformCandidate(res);

    // Local fallback
    const newCand = {
      id: `cand-${Date.now().toString().slice(-5)}`,
      currentStatus: "pool",
      isBlacklisted: false,
      clientId: body.client_id,
      clientName: body.selected_client_name,
      selectedClientName: body.selected_client_name,
      ...data,
      skills: body.skills,
    };
    localCandidates.unshift(newCand);
    persistCandidates();
    return newCand;
  },

  async updateCandidate(id, updateData) {
    // Convert frontend field names → backend snake_case
    const body = {};
    if (updateData.name !== undefined) body.name = updateData.name;
    if (updateData.email !== undefined) body.email = updateData.email;
    if (updateData.phone !== undefined) body.phone = updateData.phone;
    if (updateData.location !== undefined) body.location = updateData.location;
    if (updateData.company !== undefined) body.company = updateData.company;
    if (updateData.keySkill !== undefined) body.key_skill = updateData.keySkill;
    if (updateData.skills !== undefined) body.skills = updateData.skills;
    if (updateData.ctcCurrent !== undefined)
      body.ctc_current = updateData.ctcCurrent;
    if (updateData.ctcExpected !== undefined)
      body.ctc_expected = updateData.ctcExpected;
    if (updateData.experienceYears !== undefined)
      body.total_experience_years = updateData.experienceYears;
    if (updateData.noticePeriodDays !== undefined)
      body.notice_period_days = updateData.noticePeriodDays;
    if (updateData.remark !== undefined) body.remark = updateData.remark;
    if (updateData.linkedinUrl !== undefined)
      body.linkedin_url = updateData.linkedinUrl;
    if (updateData.clientId !== undefined)
      body.client_id = updateData.clientId;
    if (updateData.clientName !== undefined || updateData.selectedClientName !== undefined)
      body.selected_client_name = updateData.clientName || updateData.selectedClientName;

    const res = await request(`/candidates/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    if (res) return transformCandidate(res);

    // Local fallback
    const idx = localCandidates.findIndex((c) => c.id === id);
    if (idx !== -1) {
      localCandidates[idx] = { ...localCandidates[idx], ...updateData };
      persistCandidates();
      return localCandidates[idx];
    }
    return null;
  },

  async deleteCandidate(id) {
    await request(`/candidates/${id}`, { method: "DELETE" });
    localCandidates = localCandidates.filter((c) => c.id !== id);
    persistCandidates();
  },

  // ── FSM Status Transition ───────────────────────────────────────────────
  async transitionStatus(candidateId, newStatus, extraData = {}) {
    const backendStatus =
      FRONTEND_TO_BACKEND_STATUS[newStatus] || newStatus.toUpperCase();

    // Try Applications FSM endpoint first (if candidateId maps to an application)
    const appRes = await request(`/candidates/${candidateId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: backendStatus }),
    });

    if (!appRes) {
      // Local fallback
      const idx = localCandidates.findIndex((c) => c.id === candidateId);
      if (idx !== -1) {
        localCandidates[idx].currentStatus = newStatus;
        if (newStatus === "left_company") {
          localCandidates[idx].isBlacklisted = true;
          localCandidates[idx].notes =
            `[AUTO-BLACKLISTED] Left ${extraData.exitDate || new Date().toISOString().slice(0, 10)}`;
        }
        persistCandidates();
        return localCandidates[idx];
      }
    }

    return appRes ? transformCandidate(appRes) : null;
  },

  // ── Applications ────────────────────────────────────────────────────────
  async getApplications(filters = {}) {
    const params = new URLSearchParams();
    if (filters.candidateId) params.set("candidateId", filters.candidateId);
    if (filters.status)
      params.set(
        "status",
        FRONTEND_TO_BACKEND_STATUS[filters.status] || filters.status,
      );
    params.set("size", String(filters.size || 50));
    params.set("page", String(filters.page || 0));

    const res = await request(`/applications?${params}`);
    const list = unwrapList(res);
    return list ? list.map(transformApplication) : [];
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
    return res ? transformApplication(res) : null;
  },

  async transitionApplicationStatus(applicationId, newStatus) {
    const backendStatus =
      FRONTEND_TO_BACKEND_STATUS[newStatus] || newStatus.toUpperCase();
    const res = await request(`/applications/${applicationId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status: backendStatus }),
    });
    return res ? transformApplication(res) : null;
  },

  // ── Jobs ────────────────────────────────────────────────────────────────
  async getJobs(filters = {}) {
    const params = new URLSearchParams();
    if (filters.status) params.set("status", filters.status.toUpperCase());
    params.set("size", String(filters.size || 50));
    params.set("page", String(filters.page || 0));
    const res = await request(`/jobs?${params}`);
    const list = unwrapList(res);
    return list || [];
  },

  async getVacantJobs() {
    const res = await request("/jobs/vacant");
    return Array.isArray(res) ? res : [];
  },

  async createJob(data) {
    const body = {
      title: data.title,
      company_name: data.companyName || data.company_name,
      requirements: data.requirements || "",
      department: data.department || "",
      location: data.location || "",
      employment_type: data.employmentType || "FULL_TIME",
      openings_count: Number(data.openingsCount || 1),
      experience_required: Number(data.experienceRequired || 0),
      salary_lpa: Number(data.salaryLpa || 0),
      status: "OPEN",
      vacant: true,
    };
    return await request("/jobs", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  // ── Resume Upload ───────────────────────────────────────────────────────
  async uploadResume(file) {
    const formData = new FormData();
    formData.append("file", file);
    const res = await request("/candidates/upload-resume", {
      method: "POST",
      body: formData,
    });
    return res ? transformCandidate(res) : null;
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
    return unwrapList(res) || [];
  },

  // ── Clients ─────────────────────────────────────────────────────────────
  async getClients() {
    const res = await request("/clients");
    const list = unwrapList(res);
    if (list && list.length > 0) {
      return list.map(transformClient);
    }
    // Update local client candidate counts dynamically
    return localClients.map((client) => {
      const assignedCount = localCandidates.filter(
        (c) => c.clientId === client.id || c.clientName === client.name || c.selectedClientName === client.name
      ).length;
      return { ...client, candidateCount: assignedCount };
    });
  },

  async getClient(id) {
    const res = await request(`/clients/${id}`);
    if (res && res.id) return transformClient(res);
    return localClients.find((c) => c.id === id) || null;
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
    let client = res ? transformClient(res) : null;
    if (!client) {
      client = {
        id: `client-${Date.now().toString().slice(-4)}`,
        name: data.name,
        industry: data.industry || "Enterprise Software",
        contactName: data.contactName || "",
        contactEmail: data.contactEmail || "",
        contactPhone: data.contactPhone || "",
        address: data.address || "",
        website: data.website || "",
        emailDomain: data.emailDomain || "",
        isActive: true,
        candidateCount: 0,
        activeJobsCount: 0,
        createdAt: new Date().toISOString(),
      };
    }
    localClients = [client, ...localClients];
    persistClients();
    return client;
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
    const updated = res ? transformClient(res) : { ...data, id };
    const idx = localClients.findIndex((c) => c.id === id);
    if (idx !== -1) {
      localClients[idx] = { ...localClients[idx], ...updated };
      persistClients();
    }
    return updated;
  },

  async deleteClient(id) {
    await request(`/clients/${id}`, { method: "DELETE" });
    localClients = localClients.filter((c) => c.id !== id);
    persistClients();
    return true;
  },

  async inviteClientUser(clientId) {
    const res = await request(`/clients/${clientId}/invite`, { method: "POST" });
    if (res && res.invite_link) return res;
    const client = localClients.find((c) => c.id === clientId);
    return {
      client_id: clientId,
      client_name: client?.name || "Client",
      invite_link: `http://localhost:5173/client/login?inviteToken=inv_${Date.now()}&clientId=${clientId}`,
      message: `Setup invitation link generated for ${client?.name || "Client"} admin user.`,
    };
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

    const idx = localCandidates.findIndex((c) => c.id === candidateId);
    let updated;
    if (idx !== -1) {
      localCandidates[idx] = {
        ...localCandidates[idx],
        clientId,
        selectedClientName: clientName,
        clientName,
        currentStatus: "submitted",
        notes: notes || localCandidates[idx].notes,
      };
      persistCandidates();
      updated = localCandidates[idx];
    } else if (res) {
      updated = transformCandidate(res);
    }
    return updated;
  },

  // ── Utility ─────────────────────────────────────────────────────────────
  resetDemoData() {
    localCandidates = [...INITIAL_CANDIDATES];
    persistCandidates();
    localClients = [...INITIAL_CLIENTS];
    persistClients();
    return localCandidates;
  },
};
