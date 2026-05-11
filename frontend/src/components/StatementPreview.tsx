import type { ConversionPreview } from "../types";

type StatementPreviewProps = {
  preview: ConversionPreview;
};

export function StatementPreview({ preview }: StatementPreviewProps) {
  return (
    <section className="preview-card">
      <div className="preview-header">
        <div>
          <p className="section-label">Detected format</p>
          <h2>
            {(preview.detected_bank ?? "Unknown bank").toUpperCase()} · {(preview.statement_kind ?? "unknown").replace("_", " ")}
          </h2>
        </div>
        <div className="stat-pill">{preview.total_rows} rows</div>
      </div>

      <div className="preview-meta">
        <span>Source: {preview.conversion_source}</span>
        <span>Showing first {preview.preview_rows.length} rows</span>
      </div>

      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {preview.preview_rows.map((row, index) => (
              <tr key={`${row.transaction_date}-${index}-${row.amount}`}>
                <td>{row.transaction_date}</td>
                <td>{row.description}</td>
                <td className={Number(row.amount) >= 0 ? "amount positive" : "amount negative"}>{row.amount}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}