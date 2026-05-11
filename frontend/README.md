# Statement Converter Frontend

React + Vite frontend for uploading bank statements, previewing normalized rows, and downloading the generated CSV.

The frontend is intentionally thin:

- it sends one file to the backend,
- renders the preview response,
- shows parsing status and fallback error hints,
- links to the backend-generated CSV download.

All parsing logic lives in the backend.

## Tech stack

- React 18
- TypeScript
- Vite
- Plain CSS

## Prerequisites

- Node.js 18+
- npm 9+
- Backend API running locally on `http://localhost:8000` for development

## Install

```bash
cd frontend
npm install
```

## Run in development

```bash
cd frontend
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies `/api/*` to the backend.

## Build for production

```bash
cd frontend
npm run build
```

This writes the production bundle to `frontend/dist`.

When `frontend/dist` exists, the FastAPI backend serves it automatically.

## Preview the production bundle locally

```bash
cd frontend
npm run preview
```

## Frontend behavior

The UI flow is:

1. User selects or drops a file.
2. The app sends the file to `POST /api/convert/preview`.
3. On success, the preview panel renders:
   - detected bank,
   - statement kind,
   - conversion source,
   - first 20 normalized rows,
   - download link from the backend.
4. On failure, the UI displays the backend error detail and any fallback layers tried.

## Backend contract

The frontend currently depends on three backend routes:

- `GET /api/health`
- `POST /api/convert/preview`
- `GET /api/download/{token}`

The `POST /api/convert` endpoint also exists, but the React UI currently uses the preview-first flow.

## Detailed project structure

```text
frontend/
|-- README.md
|-- package.json                    # Vite scripts and React/TypeScript dependencies
|-- index.html                      # Root HTML document used by Vite during dev and build
|-- vite.config.ts                  # React plugin setup and /api proxy to the backend
|-- tsconfig.json                   # TypeScript project references
|-- tsconfig.app.json               # Browser app compiler options
|-- tsconfig.node.json              # Node-side compiler options for Vite config
`-- src/
    |-- main.tsx                    # React entrypoint that mounts App into the root element
    |-- App.tsx                     # Main page layout, status state, preview flow, and download CTA
    |-- styles.css                  # Global visual system and component styling
    |-- vite-env.d.ts               # Vite ambient type declarations
    |-- types.ts                    # Shared frontend types for transactions, preview payloads, and API errors
    |-- api/
    |   `-- client.ts               # Fetch wrapper for preview conversion requests
    `-- components/
        |-- FileDropzone.tsx        # File picker and drag-drop input surface
        `-- StatementPreview.tsx    # Preview table and detected statement metadata
```

## File responsibilities in more detail

### `src/App.tsx`

Coordinates the page-level state:

- selected file
- current request status
- status copy shown to the user
- preview payload returned by the backend
- error rendering based on the backend's structured error shape

### `src/api/client.ts`

Contains the network call for preview conversion.

Responsibilities:

- builds multipart form data,
- submits `POST /api/convert/preview`,
- parses JSON success responses,
- throws typed API errors when the backend returns `422` or another non-OK response.

### `src/components/FileDropzone.tsx`

Provides:

- click-to-browse file selection,
- drag-and-drop support,
- disabled state while conversion is in flight.

### `src/components/StatementPreview.tsx`

Renders:

- detected bank and statement kind,
- conversion source,
- row count,
- preview table of normalized transactions.

### `src/styles.css`

Defines the visual system for the frontend:

- color tokens,
- spacing,
- card layout,
- dropzone styling,
- preview table styling,
- responsive layout behavior.

## Suggested local workflow

Start the backend first:

```bash
cd backend
uvicorn app.main:app --reload
```

Then start the frontend:

```bash
cd frontend
npm run dev
```

Use the frontend at `http://localhost:5173` during development.

## Production integration

The intended deployment model is:

1. build the frontend into `frontend/dist`,
2. run the FastAPI backend,
3. let FastAPI serve the built SPA and the API from the same host.

This keeps deployment simple and avoids a separate frontend hosting layer for the current scope.

## Current limitations

- Single-file conversion only
- No upload progress bar yet
- No batch queue or conversion history
- No client-side retry or cancellation control
- CSV preview is capped by the backend response to the first 20 rows