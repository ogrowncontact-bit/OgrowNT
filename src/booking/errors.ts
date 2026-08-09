export class BookingConflictError extends Error {
  constructor(message = "Esse horario acabou de ser reservado por outra pessoa.") {
    super(message);
    this.name = "BookingConflictError";
  }
}

export class OutsideBusinessHoursError extends Error {
  constructor(message = "Esse horario esta fora do expediente.") {
    super(message);
    this.name = "OutsideBusinessHoursError";
  }
}

export class NotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NotFoundError";
  }
}
