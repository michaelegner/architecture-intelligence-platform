// Run 3, stage 1 (comparison record, "Follow-up"): arm B's initial-context step only, exactly as the
// patched simulator runs it (same prompt builder, flags and init gate), against a local AIP built
// from this branch. Usage: SIM=<patched simulator> tsx probe.mts <fixture.yaml> <synthetic repo> <out dir>
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const sim = process.env.SIM!;
const { parse } = createRequire(`${sim}/package.json`)("yaml");
const [fixturePath, repo, out] = process.argv.slice(2);
const { invokeClaude } = await import(`${sim}/src/claude.ts`);
const { checkArmInit } = await import(`${sim}/src/runner.ts`);
const { createWorktree } = await import(`${sim}/src/worktree.ts`);
const prompts = await import(`${sim}/src/prompts.ts`);

const fx = parse(fs.readFileSync(fixturePath, "utf-8"));
const dir = path.dirname(path.resolve(fixturePath));
const arms = {
  ...fx.arms,
  settings: path.resolve(dir, fx.arms.settings),
  contextEnhanced: { ...fx.arms.contextEnhanced, mcpConfig: path.resolve(dir, "arm-unblocked-aip-local.mcp.json") },
};
const wt = createWorktree(repo, "probe", fx.branch ?? "main", true);
fs.mkdirSync(out, { recursive: true });
const started = new Date().toISOString();
const result = await invokeClaude({
  prompt: prompts.buildContextCollectionPrompt(fx.task.trim(), fx.contextInstructions ?? ""),
  appendSystemPrompt: prompts.buildContextCollectionSystemSuffix(),
  cwd: wt.path,
  model: fx.contextModel ?? fx.model,
  dangerouslySkipPermissions: true,
  timeoutMs: 600_000,
  verbose: true,
  tag: "probe:gather",
  mcpConfig: arms.contextEnhanced.mcpConfig,
  settings: arms.settings,
  effort: arms.effort,
  disallowedTools: ["Edit", "Write", "NotebookEdit", "Agent", ...arms.disallowedTools],
  checkInit: (init: Record<string, unknown>) => checkArmInit(arms, "contextEnhanced", "task", init),
});
const transcript = path.join(os.homedir(), ".claude", "projects", fs.realpathSync(wt.path).replace(/\//g, "-"), `${result.sessionId}.jsonl`);
if (fs.existsSync(transcript)) fs.copyFileSync(transcript, path.join(out, "probe-transcript.jsonl"));
fs.writeFileSync(path.join(out, "probe-result.json"), JSON.stringify({ started, finished: new Date().toISOString(), clone: wt.path, ...result }, null, 2));
console.log(`cost $${result.costUsd}, turns ${result.numTurns}, transcript ${fs.existsSync(transcript) ? "copied" : "NOT FOUND " + transcript}`);
