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
- `CORS_ORIGINS`: origens do dashboard (`web/`) autorizadas a chamar a API pelo navegador,
  separadas por vírgula (ex: `http://localhost:3001` em dev)

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

## Agent Core (identidade, conhecimento e regras)

O "funcionário digital" de cada empresa tem três camadas independentes, montadas em
`src/ai/identity.ts` e consultadas por `src/ai/agent.ts` (e a saudação do fluxo guiado,
em `src/conversation/stateMachine.ts`):

- **Identidade** (`Agent`) - como ele fala: nome, tom (`FRIENDLY`/`PROFESSIONAL`/
  `CASUAL`/`PREMIUM`), formalidade, uso de emojis, saudação e instruções extras.
- **Conhecimento** (`KnowledgeEntry`) - o que ele sabe: FAQ, políticas, localização,
  regras, etc, por categoria. Consultado sob demanda pela IA via tool (`search_knowledge`)
  - nunca despejado inteiro no prompt, e a IA nunca inventa o que não está aqui.
- **Regras de negócio** (`BusinessRule`) - o que ele pode/não pode fazer (ex: "não
  aceitamos grupos maiores que 10 pessoas") - injetadas no prompt com prioridade sobre o
  tom de conversa.

```bash
# Configura a identidade do agente
curl -X PUT http://localhost:3000/api/businesses/<businessId>/agent \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "name": "Luna", "tone": "FRIENDLY", "formality": "CASUAL", "emojiUsage": "MEDIUM" }'
# valores aceitos: tone FRIENDLY|PROFESSIONAL|CASUAL|PREMIUM,
# formality FORMAL|NEUTRAL|CASUAL, emojiUsage NONE|LOW|MEDIUM|HIGH

# Adiciona conhecimento (a IA so usa o que estiver aqui - nunca inventa)
curl -X POST http://localhost:3000/api/businesses/<businessId>/knowledge \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "category": "POLICIES", "title": "Cancelamento",
        "content": "Cancelamentos devem ser feitos com 24h de antecedencia." }'
# categorias: COMPANY, SERVICES, PRICING, FAQ, POLICIES, LOCATION, RULES, DOCUMENTS

# Adiciona uma regra de negocio (guardrail consultado pela IA)
curl -X POST http://localhost:3000/api/businesses/<businessId>/rules \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "description": "Menores de 12 anos precisam estar acompanhados de um adulto." }'
```

Com `Luna`/`FRIENDLY`/`MEDIUM` configurados, o menu inicial do WhatsApp passa a começar
com "Olá! Eu sou Luna, assistente virtual da <empresa>. 😊" em vez do texto genérico -
e a mesma identidade guia o tom das respostas livres do agente de IA.

## Motor multilíngue

Cada mensagem de texto recebida tem o idioma detectado automaticamente
(`src/language/detect.ts`, restrito aos idiomas que a empresa suporta - melhora muito a
precisão em mensagens curtas de WhatsApp) e a resposta - tanto do fluxo guiado quanto da
IA - sai nesse idioma. O cliente pode trocar de idioma a qualquer momento simplesmente
escrevendo na outra língua; a preferência (`Customer.preferredLanguage`) é atualizada
automaticamente.

```bash
# Configura os idiomas e a moeda da empresa
curl -X PATCH http://localhost:3000/api/businesses/<businessId> \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "defaultLanguage": "pt", "supportedLanguages": ["pt", "en", "es"], "currency": "BRL" }'
```

- `defaultLanguage`/`supportedLanguages` aceitam: `pt`, `en`, `es`, `fr`, `de`, `it`, `nl`
  (códigos ISO 639-1). A detecção e as ferramentas de IA funcionam para todos; as
  strings do fluxo guiado (menus/botões) hoje têm tradução completa em `pt`/`en`/`es` -
  um idioma suportado sem tradução de UI ainda cai para o idioma padrão da empresa
  (nunca mistura idiomas nem mostra texto quebrado).
- `currency` aceita qualquer código ISO 4217 (`BRL`, `USD`, `EUR`, `GBP`...) - usado para
  formatar preços de serviço de forma nativa no idioma de cada conversa.
- Sem nenhuma configuração, o comportamento padrão é `pt`/`BRL` (compatível com o que já
  existia antes desta fase).

Teste rápido (mesmo fluxo, três idiomas): mande "Olá, vocês têm horário amanhã?",
"Hi, do you have availability tomorrow?" e "Hola, ¿tenéis disponibilidad para mañana?"
para o mesmo número - cada uma recebe o menu no idioma correspondente.

## Recursos, quantidade e campos de reserva customizados

O motor de reservas é universal: por padrão cada empresa usa uma única agenda
compartilhada (como nas fases anteriores). Quando um serviço precisa de um recurso
específico e limitado - cavalo, mesa, quarto, instrutor - configure `Resource` e ligue o
serviço a ele via `requiresResourceType`; o motor passa a só oferecer um horário se
houver pelo menos um recurso daquele tipo, com capacidade suficiente, livre naquele
intervalo (e reserva um automaticamente, com proteção contra concorrência).

```bash
# Cadastra 2 mesas (recurso "table") com capacidades diferentes
curl -X POST http://localhost:3000/api/businesses/<businessId>/resources \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "type": "table", "name": "Mesa 1", "capacity": 4 }'
curl -X POST http://localhost:3000/api/businesses/<businessId>/resources \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "type": "table", "name": "Mesa 2", "capacity": 2 }'

# Liga o servico "Mesa" ao tipo de recurso "table"
curl -X PATCH http://localhost:3000/api/businesses/<businessId>/services/<serviceId> \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "requiresResourceType": "table" }'

# Campo de reserva customizado (ex: nivel de experiencia na hipica)
curl -X POST http://localhost:3000/api/businesses/<businessId>/custom-fields \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{ "serviceId": "<serviceId ou omita para valer em todos>",
        "label": "Qual seu nivel de experiencia?", "fieldType": "SELECT",
        "options": ["iniciante", "intermediario", "avancado"], "required": true }'
```

- No **fluxo guiado**, um serviço com `requiresResourceType` passa a perguntar "Para
  quantas pessoas?" antes de mostrar horários (a disponibilidade já leva em conta a
  capacidade). Serviços sem recurso continuam exatamente como antes - sem esse passo.
- O **agente de IA** vê os `customFields` de cada serviço via `list_services` e sabe que
  precisa perguntar antes de reservar - as respostas vão para `Booking.metadata`.
  Perguntas abertas (texto livre) ficam a cargo da IA; o fluxo guiado por botões não
  coleta campos customizados.
- Toda chamada de ferramenta da IA é registrada em `ToolCallLog` (nome, parâmetros,
  sucesso) para observabilidade - sem guardar o conteúdo das mensagens.

## Arquitetura de canais (`ChannelAdapter`)

A camada de conversa/IA (`src/conversation/`, `src/ai/`) nunca fala diretamente com a
API do WhatsApp - ela só conhece a interface `ChannelAdapter` (`src/channels/types.ts`):
`sendText`, `sendList`, `sendButtons`, `sendTemplate`. `src/conversation/outbox.ts` é o
único lugar que chama um `ChannelAdapter`; todo o resto (fluxo guiado, agente de IA,
lembretes) passa por ele.

- **`WhatsAppAdapter`** (`src/channels/whatsapp.ts`): implementação real, usada em
  produção - reaproveita o cliente da Graph API já existente.
- **`InstagramAdapter`** (`src/channels/instagram.ts`): **stub honesto**, não uma
  simulação. Cada método lança `ChannelNotImplementedError` explicando que a integração
  com Instagram Direct ainda não foi construída. `POST/GET /webhooks/instagram` também
  respondem `501` de propósito - nada finge estar conectado.

Isso prova que a arquitetura já comporta um canal novo sem tocar na lógica de
reservas/IA - quando o Instagram Messaging for implementado de verdade (fora do escopo
desta versão), basta trocar o stub por uma implementação real do mesmo contrato.

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

## Inbox (dashboard web, `web/`)

Aplicação Next.js separada (irmã do backend, não um monorepo) que consome a mesma API
REST autenticada por JWT - é a central de atendimento humano por cima da mesma conversa
que o bot usa.

```bash
cd web
npm install
cp .env.local.example .env.local   # ajuste NEXT_PUBLIC_API_BASE_URL se necessário
npm run dev                          # sobe em http://localhost:3001 (ou a próxima porta livre)
```

Fluxo:

1. Login (`/login`) com a mesma conta criada via `POST /api/auth/register` - o JWT fica
   em `localStorage` e é anexado como `Authorization: Bearer` em toda chamada.
2. Inbox (`/inbox`, 3 colunas):
   - **Conversas**: lista com filtro "precisam de atendimento" vs "todas" (polling a
     cada 6s).
   - **Conversa**: histórico completo (cliente/bot/atendente diferenciados por cor),
     caixa de resposta manual (grava como `sender: HUMAN`, passa pelo mesmo
     `ChannelAdapter`/`outbox.ts` do bot), botão para assumir a conversa (pausa o bot,
     `needsHuman: true`) ou devolvê-la (`resolve`).
   - **Detalhes**: dados do cliente, atribuição da conversa a um membro da equipe, e
     notas internas (nunca enviadas ao cliente).

Sem WebSocket: as atualizações usam polling simples (a cada 4-6s) - suficiente para uma
central de atendimento com poucos atendentes simultâneos, sem a complexidade de
infraestrutura em tempo real. Se um número de WhatsApp real não estiver conectado à
empresa, a resposta manual retorna `501` com uma mensagem clara em vez de fingir que foi
enviada (mesmo princípio dos stubs de canal, ver seção acima).

Novos endpoints no backend (`src/routes/inbox.routes.ts`, montados em
`/api/businesses/:businessId`):

| Rota | O que faz |
| --- | --- |
| `GET /conversations/:id` | Detalhe completo (mensagens, cliente, atribuição, notas) |
| `POST /conversations/:id/messages` | Resposta manual do atendente (`sender: HUMAN`) |
| `POST /conversations/:id/assign` | Atribui/desatribui a conversa a um membro da equipe |
| `POST /conversations/:id/handoff` | Marca `needsHuman: true` (pausa o bot) |
| `POST /conversations/:id/resolve` | Devolve a conversa ao bot (já existia) |
| `POST /conversations/:id/notes` | Adiciona uma nota interna |
| `GET /members` | Lista a equipe da empresa (para o seletor de atribuição) |

## Roadmap (o que ainda não está implementado)

A plataforma é construída em 10 fases sobre o mesmo core universal (nenhum nicho tem
código próprio - só configuração). Implementado até agora: **Fase 1 (Fundação)**
(autenticação, usuários, papéis, isolamento multi-tenant, seleção de nicho), **Fase 2
(Business Setup)** (template por nicho, onboarding, perfil da empresa), **Fase 3
(Agent Core)** (identidade/voz configurável, Knowledge Base, regras de negócio),
**Fase 4 (motor multilíngue)** (detecção automática de idioma, fluxo guiado e IA
totalmente traduzidos, formatação de data/moeda por locale), **Fase 5 (Tools)**
(`Resource` com capacidade, campos de reserva customizados, observabilidade de tools) e
**Fase 6 (Channels)** (`ChannelAdapter` formalizado, WhatsApp real + Instagram como stub
honesto preparado para a integração futura) e **Fase 7 (Inbox)** (dashboard Next.js
separado, assumir/devolver conversa, resposta manual, atribuição por membro da equipe,
notas internas).

| Fase | Conteúdo |
| --- | --- |
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
