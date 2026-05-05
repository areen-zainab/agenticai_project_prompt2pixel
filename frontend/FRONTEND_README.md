# Project Montage - Frontend

This is the React-based frontend for Project Montage, communicating with the central backend via REST APIs.

## Architecture Overview

```
React Frontend (React 18 + Vite)
    ↓ (HTTP requests)
FastAPI Backend (main.py)
    ↓
Phase 1 & Phase 2 Workflows
```

## Structure

- **src/App.tsx**: Main app component; sets up routing
- **src/Phase1.tsx**: Phase 1 page; displays script, characters, and controls
- **src/Phase2.tsx**: Phase 2 page; displays video results
- **src/styles.css**: Shared design system (CSS variables, components)
- **src/index.css**, **src/main.tsx**: Entry point

## Running the Frontend

### Prerequisites

Ensure the backend is running:

```bash
python main.py
```

### Start the Frontend Dev Server

```bash
cd frontend
npm run dev
```

The app will be available at `http://localhost:5173`

## Key Features

### Phase 1 Page

- **Story Prompt Input**: Text area where users enter their story idea
- **Run Phase 1 Button**: Triggers backend execution
- **Loading State**: Shows progress while Phase 1 runs
- **Results Display**:
  - Pipeline progress indicator (all steps marked complete)
  - Generated script with scenes and dialogue
  - Character profiles with traits and descriptions
  - Output chips (Script, Characters, Images)
  - Event log

- **Proceed to Phase 2**: Button navigates to Phase 2 page after Phase 1 completion

### Phase 2 Page

- **Run Phase 2 Button**: Triggers video generation
- **Results Display**:
  - Scene result cards (success/error status)
  - Video file paths (if generated)
  - Regenerate button for re-running

- **Back to Phase 1**: Button returns to Phase 1 page

## Data Flow

### On App Load

1. `Phase1` component mounts
2. `useEffect` calls `loadPhase1Data()`
3. Attempts to fetch from `/api/phase1/script` and `/api/phase1/characters`
4. If available (from previous run), displays results
5. If not available, shows input form for new execution

### On Run Phase 1

1. User enters story prompt
2. Clicks "Run Phase 1"
3. `handleRunPhase1()` sends POST to `/api/phase1/run`
4. Backend executes Phase 1 workflow
5. Response contains full Phase 1 output
6. Component updates state with script and characters
7. Results are displayed immediately

### Navigation to Phase 2

1. User clicks "Proceed to Phase 2"
2. React Router navigates to `/phase2`
3. `Phase2` component mounts and loads existing results (if any)
4. If no results, shows "Run Phase 2" button

### On Run Phase 2

1. User clicks "Run Phase 2"
2. `handleRunPhase2()` sends POST to `/api/phase2/run`
3. Backend executes Phase 2 workflow
4. Response contains video results
5. Component displays scene results with paths

## API Integration

### Base URL

```typescript
const API_BASE = 'http://localhost:8000/api';
```

### Error Handling

- All API calls wrapped in try-catch
- Errors displayed in error banner
- Loading states prevent duplicate requests

### CORS

The backend enables CORS for frontend communication:

```python
CORSMiddleware(allow_origins=["*"])
```

In production, restrict to the frontend domain.

## Design System

### Colors (CSS Variables)

- `--bg`: Background (#F5F2ED)
- `--surface`: Cards/containers (#FFFFFF)
- `--accent`: Primary action (#B84A1E)
- `--blue`: Secondary (#1E4476)
- `--green`: Success (#245C3E)
- `--red`: Error (#8C1F1F)

### Components

- **Buttons**: `.primary`, `.secondary`
- **Alerts**: `.alert.success`, `.alert.error`, `.alert.info`
- **Cards**: `.char`, `.scene`, `.chip`
- **Layout**: `.app` (flex), `.sidebar`, `.main-content`

## State Management

Currently using React `useState` for local state. Each page manages:

- `script`: Loaded script data
- `characters`: Loaded character profiles
- `loading`: Boolean for loading states
- `error`: Error messages
- `phase1Completed`: Flag for UI state

For larger apps, consider:
- React Context for global state
- Redux for complex state trees
- Zustand for lightweight state management

## Type Safety

The frontend uses TypeScript interfaces for API responses:

```typescript
interface DialogueLine {
  speaker: string;
  line: string;
  visual_cue?: string;
}

interface Scene {
  scene_id: number;
  location: string;
  characters: string[];
  dialogue: DialogueLine[];
}
```

This ensures type-safe API data handling.

## Building for Production

```bash
cd frontend
npm run build
```

Output is in `frontend/dist/`.

Serve with:

```bash
npm run preview
```

## Deployment

For production:

1. Build the frontend: `npm run build`
2. Serve `frontend/dist` via a static file server (e.g., nginx)
3. Ensure backend API is accessible (e.g., via reverse proxy)
4. Update API_BASE in code or use environment variables

Example environment setup:

```typescript
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
```

## Troubleshooting

### "Cannot reach backend"

- Ensure `python main.py` is running
- Check that port 8000 is not in use
- Verify CORS is enabled in backend

### API returns 404

- Confirm Phase 1 has been run before accessing Phase 1 outputs
- Check backend logs for errors

### Blank page after navigation

- Check browser console for JavaScript errors
- Verify React Router is configured correctly
- Ensure components are importing styles.css

## Future Enhancements

- Real-time progress updates via WebSocket
- Polling mechanism for async job tracking
- Multi-scene preview in Phase 2
- Image uploads and viewing
- Export functionality (PDF scripts, etc.)
