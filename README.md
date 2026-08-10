# OgrowNT — AI Front Desk

## About

Plataforma SaaS multi-tenant de "recepcionista digital" por WhatsApp: cada empresa
conecta o próprio número, configura seu negócio (nicho, serviços, horários) e o agente
de IA passa a agendar, confirmar, lembrar e responder clientes como um funcionário de
verdade. Vendida inicialmente para 5 nichos - hípicas, escolas de kite/watersports,
restaurantes, coffeeshops e hostels - todos rodando sobre o **mesmo core universal**
(reservas, conversas, IA, WhatsApp); o que muda por nicho é configuração, não código.

## Como funciona

- **Multi-tenant real**: cada usuário faz login (`User`) e tem um papel (`Role`:
  OWNER/ADMIN/STAFF) numa ou mais empresas (`Membership`) - nenhuma rota de negócio
  roda sem confirmar esse vínculo (isolamento por `businessId`).
- **Canal**: WhatsApp Business Platform (API Oficial da Meta / Cloud API) - grátis para
  conversas iniciadas pelo cliente, sem risco de banimento do número.
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
principal explicando seu papel (`auth/`, `booking/engine.ts`, `conversation/`, `ai/`,
`whatsapp/`, `reminders/`). O plano completo de arquitetura e as 10 fases do produto
estão documentados à parte (auditoria, schema alvo, roadmap) - este README cobre o que
já está implementado.

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
- `JWT_SECRET`: gere com `openssl rand -hex 32` (assina os tokens de login)
- `WHATSAPP_APP_SECRET` e `WHATSAPP_WEBHOOK_VERIFY_TOKEN`: ver seção "Conectando um número
  real de WhatsApp" abaixo (para rodar só localmente sem número real, qualquer valor serve)
- `ANTHROPIC_API_KEY`: sua chave da Anthropic (opcional em dev)

Depois:

```bash
npx prisma migrate dev   # cria as tabelas no banco
npm run dev               # sobe o servidor em http://localhost:3000
```

## Autenticação e multi-tenant

Não existe mais API key por empresa - cada empresa é criada e acessada por um usuário
logado (`User` → `Membership` com um `Role`: `OWNER`, `ADMIN` ou `STAFF`).

```bash
# Cria a conta, a empresa (com o nicho) e o dono (OWNER) num unico passo
curl -X POST http://localhost:3000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dono@example.com",
    "password": "senha-forte-123",
    "name": "Fulano",
    "businessName": "Sunset Horse Riding",
    "industry": "EQUESTRIAN"
  }'
# -> { "token": "...", "user": {...}, "business": {...} }

# Login (retorna um novo token)
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{ "email": "dono@example.com", "password": "senha-forte-123" }'

# Quem sou eu / quais empresas tenho acesso
curl http://localhost:3000/api/auth/me -H "Authorization: Bearer <token>"

# Empresas do usuario logado
curl http://localhost:3000/api/businesses -H "Authorization: Bearer <token>"

# Rotas de uma empresa especifica (servicos, horarios, reservas, conversas) -
# sempre exigem Membership naquele :businessId; escrita exige OWNER ou ADMIN
curl http://localhost:3000/api/businesses/<businessId>/services -H "Authorization: Bearer <token>"

# OWNER adiciona um colega (que ja tenha se cadastrado) com um papel
curl -X POST http://localhost:3000/api/businesses/<businessId>/members \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "email": "equipe@example.com", "role": "STAFF" }'
```

`industry` aceita: `EQUESTRIAN`, `KITE_SCHOOL`, `RESTAURANT`, `COFFEE_SHOP`, `HOSTEL`,
`OTHER`. `/api/auth/login` tem rate limit (10 tentativas / 15 min por IP).

Para montar um cenário de teste completo (empresa + dono logável + dados de
demonstração + WhatsApp em modo dry-run) num só comando:

```bash
npm run create-business -- --name "Barbearia do Ze" --industry OTHER \
  --owner-email dono@example.com --owner-password "senha-forte-123" --seed-demo
```

Sem `--phone-number-id`/`--access-token`, o bot roda em **modo dry-run**: em vez de
enviar mensagens reais pelo WhatsApp, ele só loga no console o que enviaria - dá para
testar o fluxo inteiro (webhook -> conversa -> reserva no banco) sem gastar nada nem
precisar de um número real.

## Business Setup (onboarding por nicho)

Cada `industry` tem um template (`src/templates/registry.ts`) com serviços sugeridos e
campos específicos do nicho - o mesmo core (banco, motor de reservas, rotas) atende
todos; o que muda é só esse template.

```bash
# Template do nicho da empresa + checklist de configuracao
curl http://localhost:3000/api/businesses/<businessId>/onboarding -H "Authorization: Bearer <token>"

# Cria servicos de exemplo + horario padrao (seg-sab 09:00-18:00) de uma vez -
# so preenche o que ainda estiver vazio, seguro de chamar mais de uma vez
curl -X POST http://localhost:3000/api/businesses/<businessId>/onboarding/quick-start \
  -H "Authorization: Bearer <token>"

# Edita o perfil da empresa (dados gerais + campos do nicho em "metadata")
curl -X PATCH http://localhost:3000/api/businesses/<businessId> \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "description": "Passeios a cavalo para todos os niveis, num haras familiar.",
    "address": "Estrada Rural km 4, Sao Roque - SP",
    "phone": "+55 11 99999-0000",
    "metadata": { "arrivalInstructions": "Portao azul, seguir placas ate o estacionamento." }
  }'

# Servicos tambem aceitam "metadata" com campos do nicho (ver o template)
curl -X POST http://localhost:3000/api/businesses/<businessId>/services \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "name": "Passeio a cavalo", "durationMinutes": 60, "price": 80,
        "metadata": { "experienceLevel": "iniciante", "minAge": 8 } }'
```

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

## Roadmap (o que ainda não está implementado)

A plataforma é construída em 10 fases sobre o mesmo core universal (nenhum nicho tem
código próprio - só configuração). Implementado até agora: **Fase 1 (Fundação)** -
autenticação, usuários, papéis, isolamento multi-tenant, seleção de nicho - e **Fase 2
(Business Setup)** - template por nicho, checklist de onboarding, quick-start e perfil
da empresa - por cima do motor de reservas/WhatsApp/IA da rodada anterior.

| Fase | Conteúdo |
| --- | --- |
| 3. Agent Core | Identidade/voz do agente configurável, Knowledge Base, regras de negócio |
| 4. Conversation Engine | Detecção automática de idioma, contexto entre mensagens |
| 5. Tools | `Resource` (cavalo/mesa/quarto/instrutor), campos de reserva customizados |
| 6. Channels | Formalizar adaptador de canal e adicionar Instagram Direct (premium) |
| 7. Inbox | Central de atendimento (assumir conversa, notas, handoff humano na prática) |
| 8. Dashboard | Métricas (taxa de resolução por IA, reservas, etc.) |
| 9. Automations | Confirmação/lembrete/follow-up configuráveis |
| 10. Billing | Planos, setup fee + primeiro mês grátis |

Outras coisas fora do escopo atual: **conexão self-service do WhatsApp** (Embedded
Signup - hoje é manual, ver seção acima) e **múltiplos recursos/profissionais por
empresa** (por enquanto uma única agenda compartilhada; entra na Fase 5 com `Resource`).

## Scripts

| Comando | O que faz |
| --- | --- |
| `npm run dev` | Sobe o servidor em modo desenvolvimento (recarrega ao salvar) |
| `npm run build` / `npm start` | Compila e roda em produção |
| `npm run typecheck` | Checa tipos sem gerar arquivos |
| `npm run db:migrate` | Aplica migrações do Prisma (dev) |
| `npm run db:deploy` | Aplica migrações do Prisma (produção) |
| `npm run create-business` | Cadastra empresa/dono/dados de teste via CLI (ops, ver seção de autenticação) |
