import fs from "node:fs/promises";
import path from "node:path";

import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const projectCriteria = [
  "Direct fit to lecture-note, textbook, or higher-education QA",
  "Alignment with this stack: RAG, dense retrieval, BM25/hybrid retrieval, FAISS-like vector search",
  "Usefulness for improving retrieval quality, context construction, citation grounding, or long-context answering",
  "Penalty for domain-specific work that does not transfer well to lecture-note QA",
];

const manualReview = new Map([
  [
    3,
    {
      rank: 1,
      score: 5.0,
      tier: "Core",
      note: "Closest match: textbook QA with RAG over lesson content, directly aligned with educational document answering.",
    },
  ],
  [
    13,
    {
      rank: 2,
      score: 4.9,
      tier: "Core",
      note: "Higher-education chatbot over PDFs, slides, and exercises; strong domain transfer even with a different vector store.",
    },
  ],
  [
    5,
    {
      rank: 3,
      score: 4.8,
      tier: "Core",
      note: "Very close architectural fit: BM25 plus FAISS-style dense retrieval over documents with LLM answer generation.",
    },
  ],
  [
    2,
    {
      rank: 4,
      score: 4.7,
      tier: "Core",
      note: "Useful for document QA over complex source material, especially if lecture notes include diagrams, tables, or OCR-heavy PDFs.",
    },
  ],
  [
    11,
    {
      rank: 5,
      score: 4.6,
      tier: "Core",
      note: "Hybrid semantic plus BM25 retrieval with RRF is highly relevant to this project’s retriever design.",
    },
  ],
  [
    16,
    {
      rank: 6,
      score: 4.5,
      tier: "High",
      note: "Documentation QA is not educational, but its customized retriever and reranker design is highly reusable.",
    },
  ],
  [
    6,
    {
      rank: 7,
      score: 4.4,
      tier: "High",
      note: "Important for long lecture-note contexts and passage ordering; directly useful for prompt/context assembly.",
    },
  ],
  [
    20,
    {
      rank: 8,
      score: 4.3,
      tier: "High",
      note: "Helps justify embedding-model choices and connects retrieval quality to final answer quality.",
    },
  ],
  [
    19,
    {
      rank: 9,
      score: 4.2,
      tier: "High",
      note: "Strong benchmarking paper for comparing retrievers, indexing strategies, similarity metrics, and rerankers.",
    },
  ],
  [
    15,
    {
      rank: 10,
      score: 4.1,
      tier: "High",
      note: "Hypothetical-question indexing could improve retrieval when students ask in question form instead of note language.",
    },
  ],
  [
    10,
    {
      rank: 11,
      score: 4.0,
      tier: "High",
      note: "Question-centric retrieval is useful for student QA, though its university web domain is narrower than lecture-note PDFs.",
    },
  ],
  [
    17,
    {
      rank: 12,
      score: 3.9,
      tier: "High",
      note: "Good supporting work on robustness to noisy or distracting retrieval results.",
    },
  ],
  [
    23,
    {
      rank: 13,
      score: 3.8,
      tier: "Support",
      note: "Valuable survey for selecting open-source embedding models compatible with the current stack.",
    },
  ],
  [
    7,
    {
      rank: 14,
      score: 3.7,
      tier: "Support",
      note: "Useful for stepwise reasoning over long contexts, though less directly tied to a production RAG pipeline.",
    },
  ],
  [
    1,
    {
      rank: 15,
      score: 3.6,
      tier: "Support",
      note: "Education-related and RAG-based, but focused on answer scoring and feedback rather than lecture-note QA retrieval.",
    },
  ],
  [
    28,
    {
      rank: 16,
      score: 3.5,
      tier: "Support",
      note: "Caching is relevant for latency and repeated questions, but it is more of a systems optimization layer.",
    },
  ],
  [
    8,
    {
      rank: 17,
      score: 3.4,
      tier: "Support",
      note: "Useful background for FAISS and vector-store tradeoffs, though it is infrastructure-oriented rather than QA-oriented.",
    },
  ],
  [
    29,
    {
      rank: 18,
      score: 3.3,
      tier: "Support",
      note: "A domain-specific RAG survey with transferable evaluation and interpretability ideas.",
    },
  ],
  [
    4,
    {
      rank: 19,
      score: 3.2,
      tier: "Support",
      note: "Question retrieval and reranking are relevant, but this is community QA rather than document-grounded lecture QA.",
    },
  ],
  [
    18,
    {
      rank: 20,
      score: 3.1,
      tier: "Support",
      note: "Only useful if your sources include many tables; otherwise its impact on lecture-note QA is limited.",
    },
  ],
  [
    25,
    {
      rank: 21,
      score: 3.0,
      tier: "Peripheral",
      note: "Conversational memory ideas are interesting, but this project is primarily document retrieval and answering.",
    },
  ],
  [
    22,
    {
      rank: 22,
      score: 2.9,
      tier: "Peripheral",
      note: "Good precision-retrieval ideas, but the medical knowledge-graph setup transfers only partially.",
    },
  ],
  [
    12,
    {
      rank: 23,
      score: 2.8,
      tier: "Peripheral",
      note: "Advanced multimodal fusion is more ambitious than the current project needs unless you expand beyond PDF text.",
    },
  ],
  [
    30,
    {
      rank: 24,
      score: 2.7,
      tier: "Peripheral",
      note: "Knowledge-base construction for root-cause analysis is fairly far from lecture-note QA.",
    },
  ],
  [
    9,
    {
      rank: 25,
      score: 2.6,
      tier: "Peripheral",
      note: "Some chunking and fusion ideas transfer, but the task is summarization over customer feedback rather than QA.",
    },
  ],
  [
    24,
    {
      rank: 26,
      score: 2.6,
      tier: "Peripheral",
      note: "Duplicate-theme entry with transferable retrieval ideas but limited direct relevance to lecture-note QA.",
    },
  ],
  [
    27,
    {
      rank: 27,
      score: 2.5,
      tier: "Peripheral",
      note: "Agentic analytics and code generation are outside the core scope of a lecture-note QA system.",
    },
  ],
  [
    21,
    {
      rank: 28,
      score: 2.4,
      tier: "Low",
      note: "Recommendation modeling is not close to the project’s question-answering workflow.",
    },
  ],
  [
    26,
    {
      rank: 29,
      score: 2.3,
      tier: "Low",
      note: "Recommender-system survey is largely outside scope for document-grounded educational QA.",
    },
  ],
  [
    14,
    {
      rank: 30,
      score: 2.2,
      tier: "Low",
      note: "Low-level vector-memory architecture has weak direct payoff for this project compared with retrieval/QA papers.",
    },
  ],
]);

const inputPath = path.resolve("source/literature review.xlsx");
const outputDir = path.resolve("outputs/literature-review-rerank");
const outputPath = path.join(outputDir, "literature review - reranked.xlsx");

const input = await FileBlob.load(inputPath);
const workbook = await SpreadsheetFile.importXlsx(input);
const originalSheet = workbook.worksheets.items[0];

const sourceValues = originalSheet.getRange("A1:H31").values;
const reviewedRows = [];

for (let rowIndex = 1; rowIndex < sourceValues.length; rowIndex += 1) {
  const row = sourceValues[rowIndex];
  const originalId = Number(row[0]);
  const review = manualReview.get(originalId);
  if (!review) {
    throw new Error(`Missing review metadata for row ${originalId}`);
  }

  reviewedRows.push([
    review.rank,
    review.score,
    review.tier,
    review.note,
    ...row,
  ]);
}

reviewedRows.sort((a, b) => a[0] - b[0]);

const reviewedSheet = workbook.worksheets.add("Reranked Review");
reviewedSheet.getRange("A1:L31").values = [
  [
    "New Rank",
    "Relevance Score",
    "Tier",
    "Project-Fit Notes",
    "#",
    "Title",
    "Authors",
    "Year",
    "Methods",
    "Input/Output",
    "Advantages",
    "Limitations",
  ],
  ...reviewedRows,
];

const summarySheet = workbook.worksheets.add("Review Summary");
summarySheet.getRange("A1:B9").values = [
  ["Project", "AI-based Lecture Note Q&A System using RAG"],
  ["Review basis", "Lecture-note QA fit, RAG architecture fit, retrieval usefulness, and transferability"],
  ["Core papers", 5],
  ["High-value support papers", 7],
  ["Support / background papers", 8],
  ["Peripheral papers", 7],
  ["Low relevance papers", 3],
  ["Top paper", reviewedRows[0][5]],
  ["Top architectural match", reviewedRows[2][5]],
];
summarySheet.getRange("A11:A15").values = [["Ranking criteria"], ...projectCriteria.map((item) => [item])];

await fs.mkdir(outputDir, { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

console.log(JSON.stringify({ outputPath }, null, 2));
