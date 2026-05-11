export type Transaction = {
  transaction_date: string;
  description: string;
  amount: string;
};

export type ConversionPreview = {
  detected_bank: string | null;
  statement_kind: string | null;
  conversion_source: string;
  total_rows: number;
  preview_rows: Transaction[];
  download_token: string;
  download_url: string;
};

export type ApiError = {
  error: string;
  detail: string;
  hints?: {
    detected_bank?: string | null;
    detected_kind?: string | null;
    layers_tried?: string[];
  };
};