import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Element Plus core styles + theme variables
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './styles/theme.css'
import './styles/workspace.css'
import 'nprogress/nprogress.css'

// Modern Lucide Icons (stroke 1.5 - 2px, minimalist developer-first)
import {
  LayoutDashboard, Upload, Play, Sparkles, Network, Database,
  CheckCircle2, FileText, Mail, Smartphone, Share2, Cpu,
  Sun, Moon, User, ChevronDown, PanelLeftClose, PanelLeftOpen,
  Menu, X, Search, Bell, RefreshCw, Copy,
  ShoppingCart, Settings,
  FolderOpen, Folder, FolderPlus, FolderCheck, FolderMinus, Edit3, Plus,
  Trash2, Download, Check, XCircle, Loader2, Terminal, Zap,
  ExternalLink, ShieldCheck, Key, HelpCircle, ScanSearch,
  Gauge, Clock, Users, ClipboardList, Activity,
} from 'lucide-vue-next'

import App from './App.vue'
import router from './router'
import { useI18nStore } from './stores/i18n'
import { initDomTranslator } from './i18n/domTranslator'

// Register Lucide icons with aliases for router & legacy component compatibility
const ICONS = {
  // Lucide direct names
  LayoutDashboard, Upload, Play, Sparkles, Network, Database,
  CheckCircle2, FileText, Mail, Smartphone, Share2, Cpu,
  Sun, Moon, User, ChevronDown, PanelLeftClose, PanelLeftOpen,
  Menu, X, Search, Bell, RefreshCw, Copy,
  ShoppingCart, Settings,
  FolderOpen, Folder, FolderPlus, FolderCheck, FolderMinus, Edit3, Plus,
  Trash2, Download, Check, XCircle, Loader2, Terminal, Zap,
  ExternalLink, ShieldCheck, Key, HelpCircle, ScanSearch,
  Gauge, Clock, Users, ClipboardList, Activity,

  // Router & Element Plus icon name aliases -> mapped to crisp Lucide icons
  Odometer: LayoutDashboard,
  VideoPlay: Play,
  MagicStick: Sparkles,
  Connection: Network,
  Files: Database,
  CircleCheck: CheckCircle2,
  Document: FileText,
  Message: Mail,
  Iphone: Smartphone,
  Share: Share2,
  Monitor: Cpu,
  Fold: PanelLeftClose,
  Expand: PanelLeftOpen,
  Sunny: Sun,
  ArrowDown: ChevronDown,
  Close: X,
  Refresh: RefreshCw,
  CopyDocument: Copy,
  Setting: Settings,
  FolderOpened: FolderOpen,
  FolderAdd: FolderPlus,
  FolderChecked: FolderCheck,
  FolderRemove: FolderMinus,
  EditPen: Edit3,
  Delete: Trash2,
  Select: Check,
  CircleClose: XCircle,
  Loading: Loader2,
  Platform: Terminal,
}

const app = createApp(App)
for (const [name, comp] of Object.entries(ICONS)) app.component(name, comp)

const pinia = createPinia()
app.use(pinia)
app.use(router)

import { ElMessage, ElMessageBox } from 'element-plus'

const i18n = useI18nStore()
app.config.globalProperties.$t = (key, fallback) => i18n.t(key, fallback)
initDomTranslator(i18n, ElMessage, ElMessageBox)

app.mount('#app')
