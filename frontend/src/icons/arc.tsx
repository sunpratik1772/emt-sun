/**
 * Arc icon pack — Lucide glyphs with consistent stroke + sizing across Studio.
 */
import { forwardRef } from 'react'
import type { LucideIcon, LucideProps } from 'lucide-react'

export type { LucideIcon, LucideProps }

export const ARC_ICON_STROKE = 1.75

export type ArcIconProps = LucideProps & {
  icon: LucideIcon
}

export function ArcIcon({ icon: Icon, size = 16, strokeWidth = ARC_ICON_STROKE, ...props }: ArcIconProps) {
  return <Icon size={size} strokeWidth={strokeWidth} {...props} />
}

/** Wrap a Lucide icon so palette/canvas nodes share Arc stroke defaults. */
export function createArcIcon(Icon: LucideIcon): LucideIcon {
  const Wrapped = forwardRef<SVGSVGElement, LucideProps>(function ArcWrapped(
    { strokeWidth = ARC_ICON_STROKE, ...props },
    ref,
  ) {
    return <Icon ref={ref} strokeWidth={strokeWidth} {...props} />
  })
  Wrapped.displayName = `Arc(${Icon.displayName ?? Icon.name ?? 'Icon'})`
  return Wrapped as LucideIcon
}

export {
  Activity,
  AlertTriangle,
  ArrowLeftRight,
  ArrowRight,
  ArrowUp,
  ArrowUpDown,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Bot,
  Box,
  Boxes,
  Braces,
  CalendarClock,
  CandlestickChart,
  Check,
  CheckCircle2,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  CircleDashed,
  Clock,
  Code2,
  Columns,
  Copy,
  Cpu,
  CreditCard,
  Crosshair,
  Database,
  Download,
  Droplets,
  ExternalLink,
  Eye,
  EyeOff,
  FileClock,
  FileCode2,
  FileJson2,
  FileOutput,
  FilePlus2,
  FileSpreadsheet,
  FileStack,
  FileText,
  Filter,
  Files,
  FunctionSquare,
  Gavel,
  GitBranch,
  Github,
  GitMerge,
  Globe,
  Hammer,
  Highlighter,
  Layers,
  Lock,
  LayoutGrid,
  LayoutTemplate,
  Lightbulb,
  Link2Off,
  ListFilter,
  ListOrdered,
  Loader2,
  LogOut,
  Mail,
  Maximize2,
  Merge,
  MessageSquare,
  MessageSquareText,
  Minimize2,
  Moon,
  MoreHorizontal,
  Mountain,
  NotebookText,
  Palette,
  PanelLeft,
  PanelLeftClose,
  PanelLeftOpen,
  Pause,
  PauseCircle,
  Pencil,
  Play,
  Plug,
  Plus,
  Power,
  RefreshCw,
  Repeat,
  Rocket,
  Save,
  Search,
  Send,
  Server,
  Snowflake,
  Sparkles,
  Settings,
  Settings2,
  Share2,
  Shield,
  ShieldCheck,
  Sidebar,
  Signal,
  Siren,
  Sliders,
  SlidersHorizontal,
  Split,
  StickyNote,
  Sun,
  Table2,
  Target,
  ThumbsDown,
  ThumbsUp,
  Ticket,
  Trash2,
  Upload,
  UserRound,
  Wand2,
  Webhook,
  Workflow,
  Wrench,
  X,
  XCircle,
  Zap,
} from 'lucide-react'
