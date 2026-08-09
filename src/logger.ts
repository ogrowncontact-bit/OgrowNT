// Logger estruturado minimo (sem dependencia nova). Nao e observabilidade
// completa - so o suficiente para auditar eventos sensiveis (auth, tool-use,
// erros) com timestamp e formato consistente (JSON, uma linha por evento).

type LogLevel = "info" | "warn" | "error";

function write(level: LogLevel, event: string, meta: Record<string, unknown> = {}): void {
  const line = JSON.stringify({ timestamp: new Date().toISOString(), level, event, ...meta });
  if (level === "error") {
    console.error(line);
  } else if (level === "warn") {
    console.warn(line);
  } else {
    console.log(line);
  }
}

export const logger = {
  info: (event: string, meta?: Record<string, unknown>) => write("info", event, meta),
  warn: (event: string, meta?: Record<string, unknown>) => write("warn", event, meta),
  error: (event: string, meta?: Record<string, unknown>) => write("error", event, meta),
};
