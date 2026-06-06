/**
 * AUTO-GENERATED — do not edit by hand.
 * Run `python backend/scripts/gen_artifacts.py` to regenerate.
 * Maps NodeSpec `ui.icon` strings to Lucide components (tree-shaken).
 */
import type { LucideIcon } from 'lucide-react'
import {
  ArrowRight,
  ArrowUpDown,
  BarChart3,
  Bot,
  CheckSquare,
  Clock,
  Code2,
  Columns,
  Copy,
  Database,
  Download,
  FileSpreadsheet,
  FileText,
  Filter,
  FunctionSquare,
  GitBranch,
  GitPullRequest,
  Github,
  Globe,
  Layers,
  Merge,
  PauseCircle,
  Play,
  RefreshCw,
  ScrollText,
  Share2,
  StickyNote,
  Table2,
  Ticket,
  Wand2,
  Webhook,
  Zap,
} from 'lucide-react'
import { Box, createArcIcon } from '../icons/arc'

export const LUCIDE_ICON_MAP: Record<string, LucideIcon> = {
  ArrowRight: createArcIcon(ArrowRight),
  ArrowUpDown: createArcIcon(ArrowUpDown),
  BarChart3: createArcIcon(BarChart3),
  Bot: createArcIcon(Bot),
  CheckSquare: createArcIcon(CheckSquare),
  Clock: createArcIcon(Clock),
  Code2: createArcIcon(Code2),
  Columns: createArcIcon(Columns),
  Copy: createArcIcon(Copy),
  Database: createArcIcon(Database),
  Download: createArcIcon(Download),
  FileSpreadsheet: createArcIcon(FileSpreadsheet),
  FileText: createArcIcon(FileText),
  Filter: createArcIcon(Filter),
  FunctionSquare: createArcIcon(FunctionSquare),
  GitBranch: createArcIcon(GitBranch),
  GitPullRequest: createArcIcon(GitPullRequest),
  Github: createArcIcon(Github),
  Globe: createArcIcon(Globe),
  Layers: createArcIcon(Layers),
  Merge: createArcIcon(Merge),
  PauseCircle: createArcIcon(PauseCircle),
  Play: createArcIcon(Play),
  RefreshCw: createArcIcon(RefreshCw),
  ScrollText: createArcIcon(ScrollText),
  Share2: createArcIcon(Share2),
  StickyNote: createArcIcon(StickyNote),
  Table2: createArcIcon(Table2),
  Ticket: createArcIcon(Ticket),
  Wand2: createArcIcon(Wand2),
  Webhook: createArcIcon(Webhook),
  Zap: createArcIcon(Zap),
}

export function resolveLucideIcon(name: string | undefined): LucideIcon {
  if (!name) return Box
  return LUCIDE_ICON_MAP[name] ?? Box
}
