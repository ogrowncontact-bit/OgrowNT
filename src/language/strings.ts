// Strings do fluxo guiado (botoes/listas) traduzidas. Cobrimos pt/en/es hoje
// (mercados mais prováveis no lançamento); uma empresa pode declarar outros
// idiomas em supportedLanguages para fins de deteccao/IA, mas o fluxo guiado
// cai de volta para o idioma padrao da empresa (e depois pt) quando nao ha
// traducao de UI ainda - nunca mostra texto quebrado ou mistura idiomas.
// Adicionar um idioma novo = adicionar mais um dicionario aqui.

export interface UiStrings {
  menuButton: string;
  menuSectionTitle: string;
  menuRowBook: string;
  menuRowMyBookings: string;
  menuRowCancel: string;
  menuRowHuman: string;
  noServicesConfigured: string;
  chooseServiceBody: string;
  chooseServiceButton: string;
  servicesSectionTitle: string;
  noSlotsAvailable: string;
  chooseSlotBody: string;
  chooseSlotButton: string;
  slotsSectionTitle: string;
  noUpcomingBookings: string;
  upcomingBookingLine: (service: string, when: string) => string;
  noUpcomingBookingsToChange: string;
  chooseBookingToChangeBody: string;
  chooseButton: string;
  yourBookingsSectionTitle: string;
  humanHandoffAck: string;
  confirmBooking: (service: string, when: string) => string;
  confirmYes: string;
  confirmNo: string;
  bookingNotConfirmed: string;
  bookingConfirmed: (when: string) => string;
  slotTaken: string;
  whatToDoWithBooking: (service: string, when: string) => string;
  actionCancel: string;
  actionReschedule: string;
  actionKeep: string;
  bookingCancelled: string;
  bookingKept: string;
  bookingRescheduled: (when: string) => string;
  rescheduleSlotTaken: string;
  aiFallback: string;
  aiHandoffToHuman: string;
  defaultGreeting: (agentName: string, businessName: string, withEmoji: boolean) => string;
}

const PT: UiStrings = {
  menuButton: "Ver opcoes",
  menuSectionTitle: "Menu",
  menuRowBook: "Agendar horario",
  menuRowMyBookings: "Meus agendamentos",
  menuRowCancel: "Cancelar/remarcar",
  menuRowHuman: "Falar com atendente",
  noServicesConfigured: "No momento nao temos servicos configurados. Vou avisar um atendente para te ajudar.",
  chooseServiceBody: "Qual servico voce quer agendar?",
  chooseServiceButton: "Escolher servico",
  servicesSectionTitle: "Servicos",
  noSlotsAvailable: "Nao encontrei horarios livres nos proximos dias para esse servico. Quer tentar outro servico ou falar com um atendente?",
  chooseSlotBody: "Escolha um horario:",
  chooseSlotButton: "Ver horarios",
  slotsSectionTitle: "Horarios disponiveis",
  noUpcomingBookings: "Voce nao tem agendamentos futuros.",
  upcomingBookingLine: (service, when) => `- ${service} em ${when}`,
  noUpcomingBookingsToChange: "Voce nao tem agendamentos futuros para cancelar ou remarcar.",
  chooseBookingToChangeBody: "Qual agendamento voce quer alterar?",
  chooseButton: "Escolher",
  yourBookingsSectionTitle: "Seus agendamentos",
  humanHandoffAck: "Certo! Um atendente humano vai te responder por aqui em breve.",
  confirmBooking: (service, when) => `Confirmar *${service}* em ${when}?`,
  confirmYes: "Confirmar",
  confirmNo: "Cancelar",
  bookingNotConfirmed: "Sem problemas, agendamento nao confirmado.",
  bookingConfirmed: (when) => `Agendamento confirmado para ${when}. Te esperamos!`,
  slotTaken: "Ih, esse horario acabou de ser reservado por outra pessoa. Vamos escolher outro?",
  whatToDoWithBooking: (service, when) => `O que deseja fazer com ${service} em ${when}?`,
  actionCancel: "Cancelar",
  actionReschedule: "Remarcar",
  actionKeep: "Manter",
  bookingCancelled: "Agendamento cancelado.",
  bookingKept: "Ok, mantive seu agendamento como estava.",
  bookingRescheduled: (when) => `Prontinho, remarcado para ${when}.`,
  rescheduleSlotTaken: "Esse horario acabou de ser ocupado. Vamos tentar outro?",
  aiFallback: "Nao entendi bem sua mensagem. Digite qualquer coisa para ver o menu de opcoes, ou peca para falar com um atendente.",
  aiHandoffToHuman: "Deixa eu chamar um atendente humano para te ajudar melhor com isso.",
  defaultGreeting: (agentName, businessName, withEmoji) =>
    `Ola! Eu sou ${agentName}, assistente virtual da ${businessName}.${withEmoji ? " 😊" : ""} Como posso ajudar?`,
};

const EN: UiStrings = {
  menuButton: "See options",
  menuSectionTitle: "Menu",
  menuRowBook: "Book an appointment",
  menuRowMyBookings: "My bookings",
  menuRowCancel: "Cancel/reschedule",
  menuRowHuman: "Talk to a person",
  noServicesConfigured: "We don't have any services set up right now. I'll let our team know to help you.",
  chooseServiceBody: "Which service would you like to book?",
  chooseServiceButton: "Choose service",
  servicesSectionTitle: "Services",
  noSlotsAvailable: "I couldn't find any open times for this service in the next few days. Want to try another service or talk to our team?",
  chooseSlotBody: "Choose a time:",
  chooseSlotButton: "See times",
  slotsSectionTitle: "Available times",
  noUpcomingBookings: "You don't have any upcoming bookings.",
  upcomingBookingLine: (service, when) => `- ${service} on ${when}`,
  noUpcomingBookingsToChange: "You don't have any upcoming bookings to cancel or reschedule.",
  chooseBookingToChangeBody: "Which booking would you like to change?",
  chooseButton: "Choose",
  yourBookingsSectionTitle: "Your bookings",
  humanHandoffAck: "Sure! I'll get one of our team members to reply here shortly.",
  confirmBooking: (service, when) => `Confirm *${service}* on ${when}?`,
  confirmYes: "Confirm",
  confirmNo: "Cancel",
  bookingNotConfirmed: "No problem, booking not confirmed.",
  bookingConfirmed: (when) => `Booking confirmed for ${when}. See you then!`,
  slotTaken: "That time was just taken by someone else. Want to pick another one?",
  whatToDoWithBooking: (service, when) => `What would you like to do with ${service} on ${when}?`,
  actionCancel: "Cancel",
  actionReschedule: "Reschedule",
  actionKeep: "Keep it",
  bookingCancelled: "Booking cancelled.",
  bookingKept: "Ok, I kept your booking as it was.",
  bookingRescheduled: (when) => `All set, rescheduled to ${when}.`,
  rescheduleSlotTaken: "That time was just taken. Want to try another one?",
  aiFallback: "I didn't quite catch that. Type anything to see the menu of options, or ask to talk to a person.",
  aiHandoffToHuman: "Let me get a team member to help you better with this.",
  defaultGreeting: (agentName, businessName, withEmoji) =>
    `Hi! I'm ${agentName}, ${businessName}'s virtual assistant.${withEmoji ? " 😊" : ""} How can I help?`,
};

const ES: UiStrings = {
  menuButton: "Ver opciones",
  menuSectionTitle: "Menu",
  menuRowBook: "Reservar horario",
  menuRowMyBookings: "Mis reservas",
  menuRowCancel: "Cancelar/reprogramar",
  menuRowHuman: "Hablar con una persona",
  noServicesConfigured: "En este momento no tenemos servicios configurados. Le avisare a nuestro equipo para ayudarte.",
  chooseServiceBody: "Que servicio te gustaria reservar?",
  chooseServiceButton: "Elegir servicio",
  servicesSectionTitle: "Servicios",
  noSlotsAvailable: "No encontre horarios libres en los proximos dias para ese servicio. Quieres probar otro servicio o hablar con nuestro equipo?",
  chooseSlotBody: "Elige un horario:",
  chooseSlotButton: "Ver horarios",
  slotsSectionTitle: "Horarios disponibles",
  noUpcomingBookings: "No tienes reservas proximas.",
  upcomingBookingLine: (service, when) => `- ${service} el ${when}`,
  noUpcomingBookingsToChange: "No tienes reservas proximas para cancelar o reprogramar.",
  chooseBookingToChangeBody: "Que reserva te gustaria cambiar?",
  chooseButton: "Elegir",
  yourBookingsSectionTitle: "Tus reservas",
  humanHandoffAck: "Claro! Un miembro de nuestro equipo te respondera por aqui en breve.",
  confirmBooking: (service, when) => `Confirmar *${service}* el ${when}?`,
  confirmYes: "Confirmar",
  confirmNo: "Cancelar",
  bookingNotConfirmed: "Sin problema, reserva no confirmada.",
  bookingConfirmed: (when) => `Reserva confirmada para ${when}. Te esperamos!`,
  slotTaken: "Ese horario acaba de ser reservado por otra persona. Elegimos otro?",
  whatToDoWithBooking: (service, when) => `Que deseas hacer con ${service} el ${when}?`,
  actionCancel: "Cancelar",
  actionReschedule: "Reprogramar",
  actionKeep: "Mantener",
  bookingCancelled: "Reserva cancelada.",
  bookingKept: "Ok, mantuve tu reserva como estaba.",
  bookingRescheduled: (when) => `Listo, reprogramada para ${when}.`,
  rescheduleSlotTaken: "Ese horario acaba de ocuparse. Probamos otro?",
  aiFallback: "No entendi bien tu mensaje. Escribe cualquier cosa para ver el menu de opciones, o pide hablar con una persona.",
  aiHandoffToHuman: "Dejame llamar a un miembro de nuestro equipo para ayudarte mejor con esto.",
  defaultGreeting: (agentName, businessName, withEmoji) =>
    `Hola! Soy ${agentName}, asistente virtual de ${businessName}.${withEmoji ? " 😊" : ""} Como puedo ayudarte?`,
};

const DICTIONARIES: Record<string, UiStrings> = { pt: PT, en: EN, es: ES };

export function getUiStrings(language: string, businessDefaultLanguage: string): UiStrings {
  return DICTIONARIES[language] ?? DICTIONARIES[businessDefaultLanguage] ?? PT;
}
