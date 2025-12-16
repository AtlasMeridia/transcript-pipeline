import { create } from 'zustand';
import type { LogEntry } from '@/src/lib/types';

interface UIState {
  url: string;
  setUrl: (url: string) => void;
  previewMode: boolean;
  setPreviewMode: (mode: boolean) => void;
  activeTab: 'transcript' | 'summary';
  setActiveTab: (tab: 'transcript' | 'summary') => void;
  showDetails: boolean;
  setShowDetails: (show: boolean) => void;
  logs: LogEntry[];
  addLog: (message: string, type?: LogEntry['type']) => void;
  clearLogs: () => void;
  inputFocused: boolean;
  setInputFocused: (focused: boolean) => void;
  hoveredControl: string | null;
  setHoveredControl: (control: string | null) => void;
}

export const useUIStore = create<UIState>((set) => ({
  url: '',
  setUrl: (url) => set({ url }),
  previewMode: true,
  setPreviewMode: (previewMode) => set({ previewMode }),
  activeTab: 'transcript',
  setActiveTab: (activeTab) => set({ activeTab }),
  showDetails: false,
  setShowDetails: (showDetails) => set({ showDetails }),
  logs: [],
  addLog: (message, type = 'default') => {
    const timestamp = new Date().toTimeString().slice(0, 8);
    set((state) => ({
      logs: [...state.logs, { timestamp, message, type }],
    }));
  },
  clearLogs: () => set({ logs: [] }),
  inputFocused: false,
  setInputFocused: (inputFocused) => set({ inputFocused }),
  hoveredControl: null,
  setHoveredControl: (hoveredControl) => set({ hoveredControl }),
}));

