import { useState } from "react";

import { previewConversion } from "./api/client";
import { FileDropzone } from "./components/FileDropzone";
import { StatementPreview } from "./components/StatementPreview";
import type { ApiError, ConversionPreview } from "./types";

type Status = "idle" | "working" | "success" | "error";

const STATUS_COPY: Record<Status, string> = {
  idle: "Waiting for a file.",
  working: "Uploading and parsing your statement...",
  success: "Preview ready. Download the normalized CSV when you’re satisfied.",
  error: "The statement could not be processed.",
};

function formatError(error: ApiError | Error): string {
  if ("detail" in error) {
    const layers = error.hints?.layers_tried?.length ? ` Layers tried: ${error.hints.layers_tried.join(", ")}.` : "";
    return `${error.detail}${layers}`.trim();
  }
  return error.message;
}

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState<string>(STATUS_COPY.idle);
  const [preview, setPreview] = useState<ConversionPreview | null>(null);

  async function handleConvert() {
    if (!file) {
      setStatus("error");
      setMessage("Select a statement file first.");
      return;
    }

    setStatus("working");
    setMessage(STATUS_COPY.working);
    setPreview(null);

    try {
      const nextPreview = await previewConversion(file);
      setPreview(nextPreview);
      setStatus("success");
      setMessage(STATUS_COPY.success);
    } catch (error) {
      setStatus("error");
      setMessage(formatError(error as ApiError | Error));
    }
  }

  return (
    <main className="page-shell">
      <section className="hero-panel">
        <p className="eyebrow">Statement Converter</p>
        <h1>Normalize Indian bank statements without hand-cleaning every export.</h1>
        <p className="hero-copy">
          Upload a PDF or CSV, inspect the first rows, and download a normalized output with a consistent date,
          description, and signed amount format.
        </p>
        <div className="hero-tags">
          <span>HDFC</span>
          <span>Kotak</span>
          <span>Canara</span>
          <span>Unknown-bank fallback</span>
        </div>
      </section>

      <section className="workspace-grid">
        <div className="action-card">
          <FileDropzone file={file} disabled={status === "working"} onSelect={setFile} />
          <button className="convert-button" type="button" onClick={handleConvert} disabled={status === "working"}>
            {status === "working" ? "Parsing..." : "Generate preview"}
          </button>
          <div className={`status-card ${status}`}>
            <div className="status-label">{status}</div>
            <p>{message}</p>
          </div>
          {preview ? (
            <a className="download-button" href={preview.download_url} download>
              Download normalized CSV
            </a>
          ) : null}
        </div>

        {preview ? (
          <StatementPreview preview={preview} />
        ) : (
          <section className="preview-placeholder">
            <p className="section-label">Preview</p>
            <h2>Your first 20 normalized rows will appear here.</h2>
            <p>
              Unknown statement formats now route through a generic parser first, then the optional LLM fallback when it
              is configured.
            </p>
          </section>
        )}
      </section>
    </main>
  );
}