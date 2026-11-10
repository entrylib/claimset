// Written by `claimset init`: the claimset guard for opencode (lab record §4.5). Before a tool runs, the guard
// reads the call and refuses one that would modify the lab record other than through `claimset lab`.
import { spawnSync } from "node:child_process"

const GUARD = {guard}

export const ClaimsetGuard = async ({ directory }) => ({
  "tool.execute.before": async (input, output) => {
    const call = JSON.stringify({ tool: input.tool, args: output.args, cwd: directory })
    const r = spawnSync(GUARD, { shell: true, input: call, cwd: directory, encoding: "utf8" })
    if (r.status === 2) throw new Error((r.stderr || "claimset guard: blocked").trim())
  },
})
