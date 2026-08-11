-- Muda os planos padrao (starter/pro) de BRL para EUR - mercado inicial de
-- cobranca do OgrowNT. Precos calibrados por pesquisa de concorrentes
-- (chatbots WhatsApp com IA e SaaS de agenda) - sem taxa de adesao, que
-- nao e comum na entrada desse mercado. So dados de referencia (tabela
-- Plan), nao afeta estrutura nem assinaturas existentes.
UPDATE "Plan" SET "currency" = 'EUR', "priceMonthly" = 39.00, "setupFee" = 0.00 WHERE "key" = 'starter';
UPDATE "Plan" SET "currency" = 'EUR', "priceMonthly" = 89.00, "setupFee" = 0.00 WHERE "key" = 'pro';
