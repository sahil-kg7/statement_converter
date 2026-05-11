import type { ApiError, ConversionPreview } from "../types";

export async function previewConversion(file: File): Promise<ConversionPreview> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/convert/preview", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({
      error: "unprocessable_statement",
      detail: "Conversion failed.",
    }))) as ApiError;
    throw errorBody;
  }

  return (await response.json()) as ConversionPreview;
}