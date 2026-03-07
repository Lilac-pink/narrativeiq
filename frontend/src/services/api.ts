import axios from "axios";
import { API_BASE } from "../config";
import { AnalysisResult, JobStatus } from "../types";

const client = axios.create({ baseURL: API_BASE });

// ── Auth token injection ──────────────────────────────────────
// Reads token from localStorage and adds to every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("narrativeiq_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Auth ──────────────────────────────────────────────────────

export async function register(payload: {
  name: string;
  email: string;
  password: string;
}): Promise<{ access_token: string; user_id: string; name: string; email: string }> {
  const { data } = await client.post("/api/auth/register", payload);
  return data;
}

export async function login(payload: {
  email: string;
  password: string;
}): Promise<{ access_token: string; user_id: string; name: string; email: string }> {
  const { data } = await client.post("/api/auth/login", payload);
  return data;
}

export async function getMe(): Promise<{ id: string; name: string; email: string }> {
  const { data } = await client.get("/api/auth/me");
  return data;
}

export function logout() {
  localStorage.removeItem("narrativeiq_token");
  localStorage.removeItem("narrativeiq_user");
}

export function isLoggedIn(): boolean {
  return !!localStorage.getItem("narrativeiq_token");
}

// ── Pipeline (anonymous — no DB save) ────────────────────────

export async function submitStory(payload: {
  series_title: string;
  story_description: string;   // frontend field name kept for compatibility
  num_episodes: number;
}): Promise<{ job_id: string }> {
  // FIX: map frontend field names → backend field names
  const { data } = await client.post("/api/analyse", {
    series_title: payload.series_title,
    story_idea: payload.story_description,      // ← renamed
    target_episodes: payload.num_episodes,      // ← renamed
  });
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await client.get(`/api/jobs/${jobId}`);
  return data;
}

export async function getJobResult(jobId: string): Promise<AnalysisResult> {
  const { data } = await client.get(`/api/jobs/${jobId}/result`);
  return data;
}

// ── Story (authenticated — saves to DB) ──────────────────────

export async function submitStoryAuth(payload: {
  series_title: string;
  story_description: string;
  num_episodes: number;
}): Promise<{ id: string; status: string }> {
  const { data } = await client.post("/api/story/analyse", {
    series_title: payload.series_title,
    story_idea: payload.story_description,
    target_episodes: payload.num_episodes,
  });
  return data;
}

export async function getStoryStatus(storyId: string): Promise<{ id: string; status: string }> {
  const { data } = await client.get(`/api/story/${storyId}`);
  return data;
}

export async function getStoryResult(storyId: string): Promise<AnalysisResult> {
  const { data } = await client.get(`/api/story/${storyId}/result`);
  return data;
}

export async function getStoryHistory(): Promise<Array<{
  id: string;
  series_title: string;
  status: string;
  episode_count: number;
  created_at: string;
}>> {
  const { data } = await client.get("/api/story/history");
  return data;
}

export async function deleteStory(storyId: string): Promise<void> {
  await client.delete(`/api/story/${storyId}`);
}

// ── Health ───────────────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  try {
    await client.get("/health");
    return true;
  } catch {
    return false;
  }
}
