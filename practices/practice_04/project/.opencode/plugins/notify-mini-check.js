import { spawn } from "node:child_process"
import { appendFile, mkdir } from "node:fs/promises"
import { join } from "node:path"

// OpenCode 1.18.34 calls this hook with the mutable tool result as output.
export default async ({ directory }) => ({
  "tool.execute.after": async (input, output) => {
    if (!["write", "edit", "apply_patch"].includes(input.tool) || !output) return
    const result = await new Promise((resolve) => {
      const child = spawn("sh", ["scripts/check.sh"], { cwd: directory })
      let stdout = ""
      let stderr = ""
      child.stdout.on("data", (data) => { stdout += data.toString() })
      child.stderr.on("data", (data) => { stderr += data.toString() })
      child.on("error", (error) => resolve({ exit_code: 127, stdout, stderr: stderr + error.message }))
      child.on("close", (code, signal) => resolve({ exit_code: code ?? 128, signal, stdout, stderr }))
    })
    const record = { event: "tool.execute.after", tool: input.tool,
      command: "sh scripts/check.sh", ...result }
    output.output = (output.output ?? "") + "\n\n[notify-mini-check hook]\n" + JSON.stringify(record, null, 2)
    await mkdir(join(directory, "evidence"), { recursive: true })
    await appendFile(join(directory, "evidence", "hook-events.jsonl"), JSON.stringify(record) + "\n")
  },
})
