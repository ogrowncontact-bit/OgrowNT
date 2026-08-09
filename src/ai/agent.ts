import Anthropic from "@anthropic-ai/sdk";
import { config } from "../config";
import { prisma } from "../db";
import * as outbox from "../conversation/outbox";
import type { FlowContext } from "../conversation/types";
import { buildToolDefinitions, createToolExecutor } from "./tools";

// Camada de IA hibrida: cuida de qualquer mensagem em texto livre que nao
// bate com um passo esperado do fluxo guiado (perguntas, pedidos fora do
// padrao). Usa as mesmas ferramentas do motor de reservas via tool-use, para
// que a IA nunca invente horarios/precos e nunca crie um agendamento
// divergente do que o fluxo guiado permitiria.

const MAX_TOOL_ITERATIONS = 6;
const HISTORY_MESSAGES = 12;

function buildSystemPrompt(ctx: FlowContext): string {
  return [
    `Voce e o atendente virtual da empresa "${ctx.business.name}", respondendo pelo WhatsApp como um funcionario de verdade.`,
    "Seja educado, direto e breve (estilo mensagem de WhatsApp, sem formalidade excessiva).",
    "NUNCA invente horarios, precos ou servicos - sempre use as ferramentas disponiveis para consultar dados reais antes de responder.",
    "So chame create_booking depois que o cliente disser claramente que quer aquele horario especifico.",
    "Se o cliente pedir para falar com uma pessoa, ou se voce nao tiver certeza de como ajudar, use a ferramenta request_human.",
    "Responda sempre no mesmo idioma que o cliente estiver usando.",
  ].join(" ");
}

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
      system: buildSystemPrompt(ctx),
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
