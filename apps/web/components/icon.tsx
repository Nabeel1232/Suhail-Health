import {
  Activity, AlertCircle, AlertTriangle, ArrowDown, ArrowDownRight, ArrowLeft, ArrowRight,
  ArrowUp, ArrowUpRight, BarChart3, Bell, Bot, BriefcaseMedical, Building2,
  CalendarDays, Check, CheckCheck, CheckCircle2, ChevronDown, ChevronRight,
  Circle, ClipboardCheck, Clock3, Command, Download, ExternalLink, Eye,
  FileCheck2, FileText, Filter, GitBranch, Globe2, Heart, HeartPulse,
  HelpCircle, Info, Layers3, LayoutDashboard, Link, List, Loader2, LockKeyhole, LogOut,
  Mail, Menu, MessageCircle, MessageSquare, MoreHorizontal, MousePointer2, Network,
  Play, Plus, RefreshCw, Search, Send, Settings2, ShieldCheck, SlidersHorizontal,
  Sparkles, Stethoscope, Target, Upload, User, Users, X, Zap,
  type LucideIcon, type LucideProps,
} from 'lucide-react';

const icons: Record<string, LucideIcon> = {
  activity: Activity, 'alert-circle': AlertCircle, 'alert-triangle': AlertTriangle,
  'arrow-down': ArrowDown, 'arrow-down-right': ArrowDownRight, 'arrow-left': ArrowLeft, 'arrow-right': ArrowRight,
  'arrow-up': ArrowUp, 'arrow-up-right': ArrowUpRight, chart: BarChart3,
  'bar-chart-3': BarChart3, bell: Bell, bot: Bot, briefcase: BriefcaseMedical,
  building: Building2, 'building-2': Building2, calendar: CalendarDays,
  'calendar-days': CalendarDays, check: Check, 'check-check': CheckCheck,
  'check-circle': CheckCircle2, 'check-circle-2': CheckCircle2,
  'chevron-down': ChevronDown, 'chevron-right': ChevronRight, circle: Circle,
  clipboard: ClipboardCheck, 'clipboard-check': ClipboardCheck, clock: Clock3,
  command: Command, download: Download, 'external-link': ExternalLink, eye: Eye,
  'file-check': FileCheck2, 'file-check-2': FileCheck2, 'file-text': FileText,
  filter: Filter, 'git-branch': GitBranch, globe: Globe2, 'globe-2': Globe2,
  heart: Heart, 'heart-pulse': HeartPulse, 'help-circle': HelpCircle, info: Info,
  layers: Layers3, 'layers-3': Layers3, grid: LayoutDashboard,
  'layout-dashboard': LayoutDashboard, link: Link, list: List, loader: Loader2, 'loader-2': Loader2,
  lock: LockKeyhole, 'lock-keyhole': LockKeyhole, logout: LogOut, 'log-out': LogOut,
  mail: Mail, menu: Menu, 'message-circle': MessageCircle,
  'message-square': MessageSquare, 'more-horizontal': MoreHorizontal,
  'mouse-pointer-2': MousePointer2,
  network: Network, play: Play, plus: Plus, refresh: RefreshCw,
  'refresh-cw': RefreshCw, search: Search, send: Send, settings: Settings2,
  'settings-2': Settings2, shield: ShieldCheck, 'shield-check': ShieldCheck,
  sliders: SlidersHorizontal, 'sliders-horizontal': SlidersHorizontal,
  sparkles: Sparkles, stethoscope: Stethoscope, target: Target, upload: Upload,
  user: User, users: Users, x: X, zap: Zap,
};

export function Icon({name, size=18, strokeWidth=1.8, label, ...props}:
  Omit<LucideProps, 'name'> & {name: string; label?: string}) {
  const key = name.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();
  const Component = icons[key] || Circle;
  return <Component size={size} strokeWidth={strokeWidth} aria-hidden={!label || undefined}
    aria-label={label} role={label ? 'img' : undefined} focusable="false" {...props}/>;
}
