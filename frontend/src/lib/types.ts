export interface Project {
  id: string;
  name: string;
  description?: string;
  market?: string;
  platform?: string;
}

export interface Document {
  id: string;
  project_id: string;
  title: string;
  content: string;
  doc_type: string;
  market?: string;
  platform?: string;
  version: number;
  family_id: string;
  status: string;
  approved_by?: string | null;
}

export interface FieldDefinition {
  name: string;
  field_type: string;
  description?: string;
  sample_values?: string[];
  llm_prompt?: string;
  expression?: string;
  date_min?: string;
  date_max?: string;
  number_min?: number;
  number_max?: number;
  number_type?: string;
  default?: string;
  required?: boolean;
  unique?: boolean;
  depends_on?: string[];
}

export interface Template {
  id: string;
  project_id?: string | null;
  name: string;
  description?: string;
  gherkin_template: string;
  prompt_template?: string;
  fields: FieldDefinition[];
  test_phase: string;
  test_techniques: string[];
  output_detail: string;
  version: number;
}

export interface Annotation {
  id: string;
  author: string;
  verdict: string;
  comment: string;
  rating?: number | null;
  created_at?: string;
}

export interface BddStep {
  keyword: string;
  text: string;
}

export interface TestCase {
  id: string;
  project_id: string;
  template_id?: string;
  document_ids: string[];
  title: string;
  steps: BddStep[];
  gherkin: string;
  fields: Record<string, any>;
  test_phase: string;
  test_techniques: string[];
  priority: string;
  tags: string[];
  market?: string;
  platform?: string;
  content_hash: string;
  status: string;
  annotations: Annotation[];
  approved_by?: string | null;
  regeneration_history: any[];
}

export const FIELD_TYPES = [
  "enum",
  "sampling",
  "llm_generated",
  "expression",
  "date",
  "number",
  "boolean",
  "string",
];

export const TEST_PHASES = ["unit", "integration", "system", "smoke", "regression", "uat", "e2e"];
export const OUTPUT_DETAILS = ["high_level", "standard", "detailed"];
