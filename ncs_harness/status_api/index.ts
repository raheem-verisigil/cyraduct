const GH = "https://api.github.com";
const HEADERS = {
  "Accept": "application/vnd.github+json",
  "X-GitHub-Api-Version": "2022-11-28",
  "User-Agent": "NCS-Evidence-Status/0.1"
};
let cached = null;
let cachedAt = 0;
const CACHE_MS = 60_000;

async function workflow(repo, workflow, branch) {
  const url = new URL(`${GH}/repos/${repo}/actions/workflows/${workflow}/runs`);
  url.searchParams.set("branch", branch);
  url.searchParams.set("per_page", "1");
  const response = await fetch(url, { headers: HEADERS, signal: AbortSignal.timeout(8000) });
  if (response.status === 404) return { state: "NOT_CONFIGURED", reason: "Workflow not found or repository access unavailable." };
  if (response.status === 403 || response.status === 429) return { state: "NOT_VERIFIED", reason: "GitHub API rate limit or access restriction." };
  if (!response.ok) return { state: "NOT_VERIFIED", reason: `GitHub returned HTTP ${response.status}.` };
  const data = await response.json();
  const run = data.workflow_runs?.[0];
  if (!run) return { state: "NO_RUNS", reason: "No workflow runs found for this branch." };
  return {
    state: run.status === "completed" ? (run.conclusion === "success" ? "PASS" : "FAIL") : "IN_PROGRESS",
    run_id: run.id,
    run_number: run.run_number,
    workflow_name: run.name,
    branch: run.head_branch,
    commit_sha: run.head_sha,
    event: run.event,
    created_at: run.created_at,
    updated_at: run.updated_at,
    html_url: run.html_url,
    conclusion: run.conclusion
  };
}

async function buildStatus() {
  const [ncs, cyraduct, verisigil] = await Promise.all([
    workflow("raheem-verisigil/cyraduct", "ncs-finance-guard.yml", "ncs/experiment-runner-v0.1"),
    workflow("raheem-verisigil/cyraduct", "tests.yml", "main"),
    workflow("raheem-verisigil/verisigil-api", "verisigil-ci.yml", "main")
  ]);
  return {
    schema: "ncs-live-evidence-status/0.1",
    generated_at: new Date().toISOString(),
    source: "GitHub Actions public workflow metadata",
    projects: {
      ncs: {
        name: "Native Conduct Standard",
        subject: "NCS selected Finance Guard harness on development branch",
        workflow: ncs,
        assurance_status: ncs.state === "PASS" ? "PASS" : ncs.state,
        limitation: "Selected synthetic harness only; not a live model-provider assessment or certification."
      },
      cyraduct: {
        name: "Cyraduct",
        subject: "Full product test workflow on main branch",
        workflow: cyraduct,
        assurance_status: cyraduct.state,
        limitation: "CI test status is not a production security certification."
      },
      verisigilai: {
        name: "VeriSigilAI / VCB",
        subject: "Legacy API workflow metadata only",
        workflow: verisigil,
        assurance_status: "NOT_VERIFIED",
        limitation: "The inspected workflow does not require the Node jurisdiction conformance runner; its workflow conclusion must not be presented as full VCB assurance. Legacy API and current VCB website artifact equivalence is unverified."
      }
    },
    deployment_status: "NOT_INCLUDED",
    certificate_status: "NOT_ISSUED",
    note: "Workflow status, deployment health, evidence assurance and certification are separate facts."
  };
}

Bun.serve({
  port: Number(Bun.env.PORT || 3000),
  async fetch(request) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Cache-Control": "no-store"
    };
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "GET") return Response.json({ error: "method_not_allowed" }, { status: 405, headers: cors });
    if (url.pathname === "/health") return Response.json({ status: "ok", service: "ncs-evidence-status-api", version: "0.1.0" }, { headers: cors });
    if (url.pathname !== "/v1/status") return Response.json({ error: "not_found", available: ["/health", "/v1/status"] }, { status: 404, headers: cors });
    try {
      if (!cached || Date.now() - cachedAt > CACHE_MS) {
        cached = await buildStatus();
        cachedAt = Date.now();
      }
      return Response.json(cached, { headers: { ...cors, "Cache-Control": "public, max-age=30" } });
    } catch (error) {
      return Response.json({
        schema: "ncs-live-evidence-status/0.1",
        generated_at: new Date().toISOString(),
        error: "status_source_unavailable",
        detail: error instanceof Error ? error.name : "UnknownError",
        projects: {},
        note: "No status should be inferred when the source cannot be reached."
      }, { status: 503, headers: cors });
    }
  }
});
