# OgrowNT

## About

Assistente de WhatsApp para agendamentos - um "funcionario virtual" que qualquer
empresa pode conectar ao proprio numero de WhatsApp para agendar horarios, confirmar
reservas, avisar clientes e responder duvidas automaticamente. Feito para ser facil de
plugar no site (widget) e no atendimento de qualquer empresa, sem precisar reescrever
nada do sistema existente dela.

## Como funciona

- **Canal**: WhatsApp Business Platform (API Oficial da Meta / Cloud API) - grátis para
  conversas iniciadas pelo cliente, sem risco de banimento do número.
- **Arquitetura**: SaaS multi-empresa - um único sistema, cada empresa conecta seu
  próprio número e configura seus serviços/horários.
- **Conversa hibrida**:
  - Um **fluxo guiado por botões/listas** cuida do caminho principal (agendar, ver, cancelar,
    remarcar) - rápido, previsível, sem erro.
  - Um **agente de IA (Claude)** responde perguntas livres e casos fora do fluxo, usando as
    mesmas funções do motor de reservas via tool-use - nunca inventa horário, preço ou
    serviço, e nunca cria uma reserva com regras diferentes do fluxo guiado.
- **Lembretes automáticos**: um worker interno varre os agendamentos confirmados e envia
  lembretes de WhatsApp (24h e 2h antes, por padrão).
- **Widget para o site**: um `<script>` estático que qualquer empresa cola no próprio site
  para abrir uma conversa de WhatsApp com um clique.

Veja `src/` para a estrutura do código; cada pasta tem um comentário no topo do arquivo
principal explicando seu papel (`booking/engine.ts`, `conversation/`, `ai/`, `whatsapp/`,
`reminders/`).

## Pré-requisitos

- Node.js 20+
- PostgreSQL 14+ (local ou hospedado)
- Uma conta no [Meta for Developers](https://developers.facebook.com) para criar o app do
  WhatsApp Business Platform (grátis)
- Uma chave de API da [Anthropic](https://console.anthropic.com) para o agente de IA
  (opcional para rodar o fluxo guiado; sem ela, mensagens em texto livre recebem uma
  resposta padrão pedindo para usar o menu)

## Setup local

```bash
npm install
cp .env.example .env
```

Preencha o `.env`:

- `DATABASE_URL`: string de conexão do Postgres
- `MASTER_ENCRYPTION_KEY`: gere com `openssl rand -hex 32` (usada para criptografar os
  tokens de acesso do WhatsApp de cada empresa no banco)
- `WHATSAPP_APP_SECRET` e `WHATSAPP_WEBHOOK_VERIFY_TOKEN`: ver seção "Conectando um número
  real de WhatsApp" abaixo (para rodar só localmente sem número real, qualquer valor serve)
- `ANTHROPIC_API_KEY`: sua chave da Anthropic (opcional em dev)

Depois:

```bash
npx prisma migrate dev   # cria as tabelas no banco
npm run create-business -- --name "Barbearia do Ze" --slug barbearia-ze --seed-demo
npm run dev               # sobe o servidor em http://localhost:3000
```

O comando `create-business` imprime a `apiKey` da empresa criada - use-a como
`Authorization: Bearer <apiKey>` para chamar a API `/api/*` (listar/editar serviços,
horários, agendamentos e conversas). Sem `--phone-number-id`/`--access-token`, o bot roda
em **modo dry-run**: em vez de enviar mensagens reais pelo WhatsApp, ele só loga no console
o que enviaria - dá para testar o fluxo inteiro (webhook -> conversa -> reserva no banco)
sem gastar nada nem precisar de um número real.

## Conectando um número real de WhatsApp

1. Crie um app em [developers.facebook.com](https://developers.facebook.com) do tipo
   "Business" e adicione o produto **WhatsApp**.
2. No painel do produto WhatsApp você recebe, de graça, um número de teste e um
   `phone_number_id` - use-os para testar antes de conectar o número real da empresa.
3. Em **App Settings > Basic**, copie o **App Secret** para `WHATSAPP_APP_SECRET`.
4. Escolha um valor qualquer (uma senha aleatória) para `WHATSAPP_WEBHOOK_VERIFY_TOKEN` e
   salve no `.env`.
5. Suba o servidor publicamente (ex: `ngrok http 3000` em dev) e configure o webhook no
   painel da Meta apontando para `https://SEU-DOMINIO/webhooks/whatsapp`, usando o mesmo
   verify token do passo 4. Inscreva-se no campo `messages`.
6. Gere um token de acesso permanente (via um usuário de sistema no Business Manager) e
   rode `npm run create-business` com `--phone-number-id`, `--waba-id` e `--access-token`
   para essa empresa (ou crie um endpoint/telinha de conexão depois, no dashboard).
7. Para lembretes automáticos (mensagens enviadas pela empresa fora da janela de 24h),
   crie e aprove um template de mensagem chamado `appointment_reminder` (ou configure outro
   nome via `WHATSAPP_REMINDER_TEMPLATE_NAME`) no Business Manager.

## Embedando o widget no site da empresa

```html
<script
  src="https://SEU-DOMINIO/widget/chat-widget.js"
  data-phone="5511999999999"
  data-message="Ola! Quero agendar um horario."
  data-color="#25D366"
  data-position="right"
  defer
></script>
```

Sem dependências, funciona em qualquer site - abre uma conversa de WhatsApp já com uma
mensagem pré-preenchida.

## Fora do escopo desta fase (arquitetado para, mas ainda não implementado)

- **Instagram Direct**: a Graph API da Meta cobre WhatsApp e Instagram Messaging com um
  formato de webhook parecido; a camada de canal foi pensada para permitir adicionar um
  adaptador de Instagram sem tocar no motor de reservas nem na IA.
- **Dashboard visual**: por enquanto a configuração é via CLI (`npm run create-business`) e
  API REST (`/api/*`). Um painel web fica para uma próxima fase.
- **Conexão self-service (Embedded Signup)**: hoje conectar o número é um passo manual
  (seção acima). Um fluxo de "conectar em 1 clique" é evolução futura.
- **Múltiplos profissionais/recursos por empresa**: a Fase 1 usa uma única agenda
  compartilhada por empresa.

## Scripts

| Comando | O que faz |
| --- | --- |
| `npm run dev` | Sobe o servidor em modo desenvolvimento (recarrega ao salvar) |
| `npm run build` / `npm start` | Compila e roda em produção |
| `npm run typecheck` | Checa tipos sem gerar arquivos |
| `npm run db:migrate` | Aplica migrações do Prisma (dev) |
| `npm run db:deploy` | Aplica migrações do Prisma (produção) |
| `npm run create-business` | Cadastra uma nova empresa (tenant) |
