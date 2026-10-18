import { NextRequest, NextResponse } from "next/server";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const protocolId = body.protocol_id || "aave-v3";
    const amountUsd = Number(body.amount_usd) || 10000;
    const userId = body.user_id || "demo_trader";
    const tolerance = body.tolerance || "moderate";

    // Determine repository root directory
    let repoRoot = process.cwd();
    if (!fs.existsSync(path.join(repoRoot, "scripts", "assess_api.py"))) {
      repoRoot = path.resolve(process.cwd(), "..");
    }

    // Determine Python executable
    let pythonExe = process.env.PYTHON_BIN || process.env.PYTHON_PATH;
    if (!pythonExe) {
      if (process.platform === "win32") {
        const venvWin = path.join(repoRoot, ".venv", "Scripts", "python.exe");
        pythonExe = fs.existsSync(venvWin) ? venvWin : "python";
      } else {
        const venvPosix = path.join(repoRoot, ".venv", "bin", "python");
        pythonExe = fs.existsSync(venvPosix) ? venvPosix : "python3";
      }
    }

    const scriptPath = path.join(repoRoot, "scripts", "assess_api.py");

    const args = [
      scriptPath,
      "--protocol", protocolId,
      "--amount", String(amountUsd),
      "--user_id", userId,
      "--tolerance", tolerance,
    ];

    return new Promise<NextResponse>((resolve) => {
      let stdoutData = "";
      let stderrData = "";

      const child = spawn(pythonExe, args, {
        cwd: repoRoot,
        env: { ...process.env, PYTHONIOENCODING: "utf-8" },
      });

      child.stdout.on("data", (chunk) => {
        stdoutData += chunk.toString("utf-8");
      });

      child.stderr.on("data", (chunk) => {
        stderrData += chunk.toString("utf-8");
      });

      child.on("close", (code) => {
        if (code === 0) {
          try {
            // Find the last JSON line in stdout
            const lines = stdoutData.trim().split("\n");
            let jsonText = "";
            for (let i = lines.length - 1; i >= 0; i--) {
              const line = lines[i].trim();
              if (line.startsWith("{") && line.endsWith("}")) {
                jsonText = line;
                break;
              }
            }

            if (jsonText) {
              const parsed = JSON.parse(jsonText);
              return resolve(NextResponse.json(parsed));
            }
          } catch (err) {
            console.error("Failed to parse assess Python JSON output:", err, stdoutData);
          }
        }

        console.warn("Assess Python execution code:", code, stderrData);
        return resolve(
          NextResponse.json({
            success: false,
            error: stderrData || "Backend assess execution failed",
            fallback: true,
          }, { status: 500 })
        );
      });

      child.on("error", (err) => {
        console.error("Failed to spawn assess child process:", err);
        return resolve(
          NextResponse.json({
            success: false,
            error: err.message,
            fallback: true,
          }, { status: 500 })
        );
      });
    });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error?.message || "Internal server error" },
      { status: 500 }
    );
  }
}
