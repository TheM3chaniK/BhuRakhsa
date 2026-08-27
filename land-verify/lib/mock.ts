import { CaseSummary, ExtractedField, ValidationRow } from "./types";

export const extractedFields: ExtractedField[] = [
  { label: "Survey No.", value: "142/3-B", confidence: 94 },
  { label: "Village", value: "Hatgacha", confidence: 91 },
  { label: "Owner Name", value: "Debasish Roy", confidence: 68 },
  { label: "Area", value: "1.20 acre", confidence: 88 },
  { label: "Document Year", value: "1987", confidence: 77 },
  { label: "Boundaries (E)", value: "Plot 142/3-A", confidence: 55 },
];

export const validationRows: ValidationRow[] = [
  { field: "Survey No.", document: "142/3-B", record: "142/3-B", status: "MATCHED" },
  { field: "Village", document: "Hatgacha", record: "Hatgacha", status: "MATCHED" },
  { field: "Owner Name", document: "Debasish Roy", record: "D. Roy", status: "MISMATCH" },
  { field: "Area", document: "1.20 acre", record: "1.05 acre", status: "MISMATCH" },
  { field: "Boundary (E)", document: "Plot 142/3-A", record: "—", status: "MISSING" },
];

export const caseQueue: CaseSummary[] = [
  { id: "SIH-0142", village: "Hatgacha", surveyNo: "142/3-B", owner: "Debasish Roy", risk: "MEDIUM", submitted: "Today, 10:12 AM", reason: "Area mismatch, probable name match" },
  { id: "SIH-0141", village: "Bakultala", surveyNo: "88/1", owner: "Anita Mondal", risk: "HIGH", submitted: "Today, 9:47 AM", reason: "Survey number conflict" },
  { id: "SIH-0140", village: "Rautara", surveyNo: "205/2-A", owner: "S. Chattopadhyay", risk: "LOW", submitted: "Yesterday, 4:03 PM", reason: "Clean match, all fields verified" },
  { id: "SIH-0139", village: "Hatgacha", surveyNo: "56/4", owner: "Manoj Halder", risk: "MEDIUM", submitted: "Yesterday, 2:15 PM", reason: "Low OCR confidence on boundary text" },
];
