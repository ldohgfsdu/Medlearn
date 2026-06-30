import type { TextbookCatalogPart } from '@/utils/knowledgeTree'

// eslint-disable-next-line @typescript-eslint/no-require-imports
const catalog = require('./catalog.internal-medicine.json') as {
  chapters: TextbookCatalogPart[]
}

export const INTERNAL_MEDICINE_CATALOG_PARTS = catalog.chapters