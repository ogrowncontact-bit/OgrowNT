export const STEP = {
  IDLE: "idle",
  MENU: "menu",
  CHOOSING_SERVICE: "choosing_service",
  CHOOSING_QUANTITY: "choosing_quantity",
  CHOOSING_SLOT: "choosing_slot",
  CONFIRMING: "confirming",
  CHOOSING_BOOKING_ACTION: "choosing_booking_action",
  BOOKING_ACTION: "booking_action",
  CHOOSING_RESCHEDULE_SLOT: "choosing_reschedule_slot",
} as const;

export const REPLY = {
  MENU_BOOK: "menu_book",
  MENU_MY_BOOKINGS: "menu_my_bookings",
  MENU_CANCEL: "menu_cancel",
  MENU_HUMAN: "menu_human",
  CONFIRM_YES: "confirm_yes",
  CONFIRM_NO: "confirm_no",
  ACTION_CANCEL: "action_cancel",
  ACTION_RESCHEDULE: "action_reschedule",
  ACTION_KEEP: "action_keep",
} as const;
