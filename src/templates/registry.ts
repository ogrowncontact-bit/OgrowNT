import { BusinessIndustry } from "@prisma/client";

// Templates por nicho: NAO mudam o core (mesmo booking engine, mesma IA, mesmo
// schema) - so descrevem que servicos sugerir no "quick start" e quais campos
// especificos fazem sentido em Service.metadata / Business.metadata. Sao
// dados descritivos (usados pela API de onboarding e, futuramente, pelo
// dashboard) - nao validam nem bloqueiam nada no motor de reservas.

export type OnboardingFieldType = "text" | "textarea" | "number" | "boolean" | "select";

export interface OnboardingField {
  key: string;
  label: string;
  type: OnboardingFieldType;
  options?: string[]; // usado quando type = "select"
  required: boolean;
}

export interface DefaultService {
  name: string;
  durationMinutes: number;
}

export interface IndustryTemplate {
  industry: BusinessIndustry;
  label: string;
  description: string;
  defaultServices: DefaultService[];
  serviceFields: OnboardingField[];
  businessFields: OnboardingField[];
}

const EQUESTRIAN: IndustryTemplate = {
  industry: "EQUESTRIAN",
  label: "Hípica / Centro Equestre",
  description: "Passeios a cavalo, aulas de equitação e experiências para grupos.",
  defaultServices: [
    { name: "Passeio a cavalo", durationMinutes: 60 },
    { name: "Aula de equitação (iniciantes)", durationMinutes: 60 },
    { name: "Aula particular", durationMinutes: 60 },
  ],
  serviceFields: [
    { key: "experienceLevel", label: "Nível exigido", type: "select", options: ["iniciante", "intermediario", "avancado"], required: false },
    { key: "minAge", label: "Idade mínima", type: "number", required: false },
    { key: "maxWeightKg", label: "Peso máximo (kg)", type: "number", required: false },
    { key: "helmetProvided", label: "Capacete fornecido", type: "boolean", required: false },
  ],
  businessFields: [
    { key: "arrivalInstructions", label: "Instruções de chegada", type: "textarea", required: false },
    { key: "safetyInfo", label: "Informações de segurança", type: "textarea", required: false },
    { key: "recommendedAttire", label: "Roupa recomendada", type: "text", required: false },
  ],
};

const KITE_SCHOOL: IndustryTemplate = {
  industry: "KITE_SCHOOL",
  label: "Escola de Kite / Watersports",
  description: "Aulas de kitesurf e esportes aquáticos, aluguel de equipamento.",
  defaultServices: [
    { name: "Aula de kitesurf (iniciantes)", durationMinutes: 120 },
    { name: "Aula particular", durationMinutes: 90 },
    { name: "Aluguel de equipamento", durationMinutes: 240 },
  ],
  serviceFields: [
    { key: "skillLevel", label: "Nível", type: "select", options: ["beginner", "intermediate", "advanced"], required: false },
    { key: "minAge", label: "Idade mínima", type: "number", required: false },
    { key: "equipmentIncluded", label: "Equipamento incluído", type: "boolean", required: false },
  ],
  businessFields: [
    { key: "arrivalInstructions", label: "Instruções de chegada", type: "textarea", required: false },
    { key: "equipmentProvided", label: "Equipamentos fornecidos pela escola", type: "text", required: false },
  ],
};

const RESTAURANT: IndustryTemplate = {
  industry: "RESTAURANT",
  label: "Restaurante",
  description: "Reservas de mesa, eventos e experiências gastronômicas.",
  defaultServices: [{ name: "Mesa", durationMinutes: 90 }],
  serviceFields: [
    { key: "maxPartySize", label: "Tamanho máximo do grupo", type: "number", required: false },
    { key: "highchairAvailable", label: "Cadeira infantil disponível", type: "boolean", required: false },
    { key: "dietaryOptions", label: "Opções alimentares (ex: vegetariano, vegano)", type: "text", required: false },
  ],
  businessFields: [
    { key: "cuisineType", label: "Tipo de cozinha", type: "text", required: false },
    { key: "parkingAvailable", label: "Estacionamento disponível", type: "boolean", required: false },
    { key: "averageTableTimeMinutes", label: "Tempo médio de mesa (min)", type: "number", required: false },
  ],
};

const COFFEE_SHOP: IndustryTemplate = {
  industry: "COFFEE_SHOP",
  label: "Coffeeshop / Café",
  description: "Mesas, cardápio, workshops e ambiente para trabalhar.",
  defaultServices: [{ name: "Mesa", durationMinutes: 60 }],
  serviceFields: [
    { key: "maxPartySize", label: "Tamanho máximo do grupo", type: "number", required: false },
    { key: "dietaryOptions", label: "Opções alimentares", type: "text", required: false },
  ],
  businessFields: [
    { key: "wifiAvailable", label: "Wi-Fi disponível", type: "boolean", required: false },
    { key: "powerOutlets", label: "Tomadas disponíveis", type: "boolean", required: false },
  ],
};

// Duracao em minutos aproxima uma "diaria" (1440 = 24h) para caber no motor
// de reservas de slot unico da Fase 1. Reservas multi-noite de verdade (com
// range de datas) sao uma evolucao futura do Universal Booking Engine.
const HOSTEL: IndustryTemplate = {
  industry: "HOSTEL",
  label: "Hostel",
  description: "Dormitórios, quartos privados e hospedagem para viajantes.",
  defaultServices: [
    { name: "Cama em dormitório (1 noite)", durationMinutes: 1440 },
    { name: "Quarto privado (1 noite)", durationMinutes: 1440 },
  ],
  serviceFields: [
    { key: "roomType", label: "Tipo de quarto", type: "select", options: ["dormitorio", "privado"], required: false },
    { key: "bedCount", label: "Número de camas", type: "number", required: false },
    { key: "breakfastIncluded", label: "Café da manhã incluído", type: "boolean", required: false },
  ],
  businessFields: [
    { key: "checkInTime", label: "Horário de check-in", type: "text", required: false },
    { key: "checkOutTime", label: "Horário de check-out", type: "text", required: false },
    { key: "hasLockers", label: "Possui lockers", type: "boolean", required: false },
  ],
};

const OTHER: IndustryTemplate = {
  industry: "OTHER",
  label: "Outro tipo de negócio",
  description: "Configuração genérica - adicione seus próprios serviços e campos.",
  defaultServices: [],
  serviceFields: [],
  businessFields: [],
};

const TEMPLATES: Record<BusinessIndustry, IndustryTemplate> = {
  EQUESTRIAN,
  KITE_SCHOOL,
  RESTAURANT,
  COFFEE_SHOP,
  HOSTEL,
  OTHER,
};

export function getIndustryTemplate(industry: BusinessIndustry): IndustryTemplate {
  return TEMPLATES[industry];
}
