// create-pr-helper: Create GitHub Pull Requests via Edge Function
// POST /create-pr-helper
// Body: { repo_owner, repo_name, head_branch, base_branch, title, body }
//
// Requires GITHUB_TOKEN environment variable with repo access.

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { Octokit } from "npm:@octokit/rest@19.0.7";
import { handleCorsOptions, jsonResponse, errorResponse } from "../_shared/cors.ts";

interface CreatePRRequest {
  repo_owner: string;
  repo_name: string;
  head_branch: string;
  base_branch: string;
  title: string;
  body?: string;
}

serve(async (req: Request): Promise<Response> => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return handleCorsOptions();
  }

  // Only allow POST requests
  if (req.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  try {
    const githubToken = Deno.env.get("GITHUB_TOKEN");
    if (!githubToken) {
      console.error("[create-pr-helper] GITHUB_TOKEN not configured");
      return errorResponse("GITHUB_TOKEN not configured", 500);
    }

    const body: CreatePRRequest = await req.json();
    const { repo_owner, repo_name, head_branch, base_branch, title, body: prBody } = body;

    // Validate required fields
    if (!repo_owner || !repo_name || !head_branch || !base_branch || !title) {
      return errorResponse(
        "Missing required fields: repo_owner, repo_name, head_branch, base_branch, title",
        400
      );
    }

    const octokit = new Octokit({ auth: githubToken });

    const { data: pr } = await octokit.pulls.create({
      owner: repo_owner,
      repo: repo_name,
      head: head_branch,
      base: base_branch,
      title,
      body: prBody || "",
    });

    console.log(`[create-pr-helper] Created PR #${pr.number}: ${pr.html_url}`);

    return jsonResponse({
      success: true,
      pr_number: pr.number,
      pr_url: pr.html_url,
      state: pr.state,
    });
  } catch (err) {
    console.error("[create-pr-helper] Error:", err);

    // Handle GitHub API errors
    if (err.status === 422) {
      return errorResponse(
        `GitHub API error: ${err.message || "Validation failed"}`,
        422
      );
    }

    return errorResponse(
      `Failed to create PR: ${err instanceof Error ? err.message : String(err)}`,
      500
    );
  }
});
