# Transcript Pipeline - Next.js Frontend

Modern React/Next.js frontend for the Transcript Pipeline application.

## Features

- **TypeScript** - Full type safety
- **Tailwind CSS** - Utility-first styling with ATLAS Meridia design system
- **TanStack Query** - Server state management
- **Zustand** - Client state management
- **Server-Sent Events** - Real-time progress updates
- **Responsive Design** - Mobile-first, touch-friendly UI

## Development

### Prerequisites

- Node.js 20+
- Running FastAPI backend (see main README)

### Local Development

1. Install dependencies:
```bash
npm install
```

2. Set environment variable (optional, defaults to `http://localhost:8000`):
```bash
export NEXT_PUBLIC_API_URL=http://localhost:8000
```

3. Run development server:
```bash
npm run dev
```

The app will be available at `http://localhost:3000`.

### Building for Production

```bash
npm run build
npm start
```

## Docker

The frontend is included in the main `docker-compose.yml`. To run:

```bash
docker-compose up web
```

Or run both frontend and API:

```bash
docker-compose up web transcript-api
```

## Project Structure

```
web/
├── src/
│   ├── app/              # Next.js App Router pages
│   ├── components/       # React components
│   ├── hooks/            # Custom React hooks
│   ├── lib/              # Utilities, API client, types
│   └── stores/           # Zustand stores
├── app/
│   ├── layout.tsx        # Root layout with fonts
│   ├── page.tsx          # Main page
│   └── globals.css       # Global styles and design tokens
└── Dockerfile            # Docker configuration
```

## Design System

The app uses the ATLAS Meridia design system with:
- Navy color palette (dark theme)
- Amber-gold accents
- Serif display fonts (Cormorant Garamond)
- Sans-serif UI fonts (DM Sans)
- Monospace code fonts (IBM Plex Mono)

All design tokens are defined in `app/globals.css` using CSS custom properties and Tailwind CSS v4.
