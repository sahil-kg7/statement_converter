import { useRef } from "react";

type FileDropzoneProps = {
  file: File | null;
  disabled: boolean;
  onSelect: (file: File | null) => void;
};

export function FileDropzone({ file, disabled, onSelect }: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  function openPicker() {
    if (!disabled) {
      inputRef.current?.click();
    }
  }

  function handleInputChange(event: React.ChangeEvent<HTMLInputElement>) {
    onSelect(event.target.files?.[0] ?? null);
  }

  function handleDrop(event: React.DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    if (disabled) {
      return;
    }
    onSelect(event.dataTransfer.files?.[0] ?? null);
  }

  return (
    <button
      className="dropzone"
      type="button"
      onClick={openPicker}
      onDragOver={(event) => event.preventDefault()}
      onDrop={handleDrop}
      disabled={disabled}
    >
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept=".pdf,.csv,.tsv,.txt"
        onChange={handleInputChange}
      />
      <span className="dropzone-kicker">Drop a file here or browse</span>
      <strong>{file?.name ?? "No file selected"}</strong>
      <span className="dropzone-meta">PDF, CSV, TSV, and TXT statement exports are supported.</span>
    </button>
  );
}