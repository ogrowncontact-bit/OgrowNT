import type { AssessmentConfig } from "@inner/assessment-engine";
import { loveAssessment } from "./assessments/love";
import { relationshipAssessment } from "./assessments/relationship";
import { jealousyAssessment } from "./assessments/jealousy";
import { intimacyAssessment } from "./assessments/intimacy";
import { vulnerabilityAssessment } from "./assessments/vulnerability";
import { connectionAssessment } from "./assessments/connection";
import { socialAssessment } from "./assessments/social";
import { communicationAssessment } from "./assessments/communication";
import { hiddenSelfAssessment } from "./assessments/hidden-self";
import { decisionAssessment } from "./assessments/decision";

export { loveAssessment } from "./assessments/love";
export { relationshipAssessment } from "./assessments/relationship";
export { jealousyAssessment } from "./assessments/jealousy";
export { intimacyAssessment } from "./assessments/intimacy";
export { vulnerabilityAssessment } from "./assessments/vulnerability";
export { connectionAssessment } from "./assessments/connection";
export { socialAssessment } from "./assessments/social";
export { communicationAssessment } from "./assessments/communication";
export { hiddenSelfAssessment } from "./assessments/hidden-self";
export { decisionAssessment } from "./assessments/decision";

export { dimensionPool } from "./dimensions";
export type { DimensionDefinition } from "./dimensions";
export { validateAssessmentConfig } from "./validate";

/** All 10 launch experiences — the single list every registry/seed script should iterate over. */
export const allAssessments: AssessmentConfig[] = [
  loveAssessment,
  relationshipAssessment,
  jealousyAssessment,
  intimacyAssessment,
  vulnerabilityAssessment,
  connectionAssessment,
  socialAssessment,
  communicationAssessment,
  hiddenSelfAssessment,
  decisionAssessment,
];
