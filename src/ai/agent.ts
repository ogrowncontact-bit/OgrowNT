import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config";
import { prisma } from "../db";
import * as outbox from "../conversation/outbox";
import type { FlowContext } from "../conversation/types";
import { buildSystemPrompt, getAgent } from "./identity";
import { buildToolDefinitions, createToolExecutor } from "./tools";

// Camada de IA hibrida: cuida de qualquer mensagem em texto livre que nao
// bate com um passo esperado do fluxo guiado (perguntas, pedidos fora do
// padrao). Usa as mesmas ferramentas do motor de reservas via tool-use, para
// que a IA nunca invente horarios/precos e nunca crie um agendamento
// divergente do que o fluxo guiado permitiria. O prompt em si (identidade,
// regras) vem de src/ai/identity.ts - configuravel por empresa.

const MAX_TOOL_ITERATIONS = 6;
const HISTORY_MESSAGES = 12;

export async function runAiAgent(ctx: FlowContext): Promise<void> {
  if (!config.anthropic.apiKey) {
    console.warn("[ai] ANTHROPIC_API_KEY nao configurada - respondendo com fallback estatico.");
    await outbox.sendText(
      ctx,
      "Nao entendi bem sua mensagem. Digite qualquer coisa para ver o menu de opcoes, ou peca para falar com um atendente."
    );
    return;
  }

  const anthropic = new Anthropic({ apiKey: config.anthropic.apiKey });
  const agent = await getAgent(ctx.business.id);
  const systemPrompt = await buildSystemPrompt(ctx.business, agent);

  const history = await prisma.message.findMany({
    where: { conversationId: ctx.conversationId },
    orderBy: { createdAt: "desc" },
    take: HISTORY_MESSAGES,
  });
  history.reverse();

  const messages: Anthropic.MessageParam[] = history.map((m) => ({
    role: m.direction === "IN" ? "user" : "assistant",
    content: m.content,
  }));

  const tools = buildToolDefinitions();
  const executeTool = createToolExecutor(ctx);

  for (let iteration = 0; iteration < MAX_TOOL_ITERATIONS; iteration++) {
    const response = await anthropic.messages.create({
      model: config.anthropic.model,
      max_tokens: 1024,
      system: systemPrompt,
      tools,
      messages,
    });

    const toolUseBlocks = response.content.filter(
      (b): b is Anthropic.ToolUseBlock => b.type === "tool_use"
    );

    if (toolUseBlocks.length === 0) {
      const finalText = response.content
        .filter((b): b is Anthropic.TextBlock => b.type === "text")
        .map((b) => b.text)
        .join("\n")
        .trim();
      if (finalText) {
        await outbox.sendText(ctx, finalText);
      }
      return;
    }

    messages.push({ role: "assistant", content: response.content });

    const toolResults: Anthropic.ToolResultBlockParam[] = [];
    for (const block of toolUseBlocks) {
      const result = await executeTool(block.name, block.input as Record<string, unknown>);
      toolResults.push({ type: "tool_result", tool_use_id: block.id, content: result });
    }
    messages.push({ role: "user", content: toolResults });
  }

  await outbox.sendText(ctx, "Deixa eu chamar um atendente humano para te ajudar melhor com isso.");
  await prisma.conversation.update({ where: { id: ctx.conversationId }, data: { needsHuman: true } });
}
