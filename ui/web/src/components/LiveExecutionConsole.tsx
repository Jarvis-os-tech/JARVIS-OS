import React, { useState, useEffect, useRef } from 'react';
import {
  SelectedTarget,
  SubAgentMeta,
  BackgroundTask,
  AgentLogEntry,
  SkillDisplayCard as SkillDisplayCardType,
} from '../types';
import {
  Terminal,
  Bot,
  ShieldAlert,
  Code2,
  Cpu,
  Activity,
  CheckCircle2,
  AlertCircle,
  Clock,
  Zap,
  RotateCcw,
  Trash2,
  Filter,
  Search,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Layers,
  ArrowRight,
  Radio,
  Play,
} from 'lucide-react';
import { SkillDisplayCard } from './SkillDisplayCard';

interface LiveExecutionConsoleProps {
  selectedTarget: SelectedTarget;
  agents: SubAgentMeta[];
  activeTasks: BackgroundTask[];
  completedTasks: BackgroundTask[];
  logs: AgentLogEntry[];
  onTriggerQuickAction: (actionPrompt: string) => void;
  onCancelTask: (taskId: string) => void;
  onClearLogs: () => void;
  onSelectDisplayCard?: (card: SkillDisplayCardType) => void;
}

export const LiveExecutionConsole: React.FC<LiveExecutionConsoleProps> = ({
  selectedTarget,
  agents,
  activeTasks,
  completedTasks,
  logs,
  onTriggerQuickAction,
  onCancelTask,
  onClearLogs,
  onSelectDisplayCard,
}) => {
  const [levelFilter, setLevelFilter] = useState<'all' | 'info' | 'warn' | 'error'>('all');
  const [logSearchQuery, setLogSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [expandedLogIds, setExpandedLogIds] = useState<Set<string>>(new Set());
  const [nowTime, setNowTime] = useState<number>(Date.now());
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Live timer tick for active tasks
  useEffect(() => {
    const interval = setInterval(() => {
      setNowTime(Date.now());
    }, 250);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll log container to bottom on new logs
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Identify selected agent or task
  const selectedAgent =
    selectedTarget.type === 'agent'
      ? agents.find((a) => a.id === selectedTarget.agentId) || agents[0]
      : null;

  const selectedTask =
    selectedTarget.type === 'task'
      ? activeTasks.find((t) => t.id === selectedTarget.taskId) ||
        completedTasks.find((t) => t.id === selectedTarget.taskId)
      : null;

  // Filter logs based on selection
  const relevantLogs = logs.filter((log) => {
    if (selectedTarget.type === 'agent') {
      if (selectedTarget.agentId !== 'system' && log.agent !== selectedTarget.agentId) {
        return false;
      }
    } else if (selectedTarget.type === 'task') {
      if (log.taskId !== selectedTarget.taskId) {
        return false;
      }
    }

    if (levelFilter !== 'all' && log.level !== levelFilter) {
      return false;
    }

    if (logSearchQuery.trim()) {
      const q = logSearchQuery.toLowerCase();
      const matchMsg = log.message.toLowerCase().includes(q);
      const matchAgent = log.agent.toLowerCase().includes(q);
      const matchDetails = log.details ? JSON.stringify(log.details).toLowerCase().includes(q) : false;
      if (!matchMsg && !matchAgent && !matchDetails) return false;
    }

    return true;
  });

  const toggleExpandLog = (id: string) => {
    setExpandedLogIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const getAgentIcon = (id?: string, className = 'w-4 h-4') => {
    switch (id) {
      case 'hermes':
        return <Bot className={className} />;
      case 'ultron':
        return <ShieldAlert className={className} />;
      case 'prime':
        return <Code2 className={className} />;
      default:
        return <Cpu className={className} />;
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error':
        return 'text-rose-400 bg-rose-950/60 border-rose-700/50';
      case 'warn':
        return 'text-amber-400 bg-amber-950/60 border-amber-700/50';
      case 'success':
        return 'text-emerald-400 bg-emerald-950/60 border-emerald-700/50';
      case 'info':
      default:
        return 'text-cyan-400 bg-cyan-950/60 border-cyan-700/50';
    }
  };

  return (
    <aside
      id="live-execution-console"
      className="w-full h-full flex flex-col bg-slate-950/80 border-l border-cyan-950/50 backdrop-blur-xl text-slate-200 select-none overflow-hidden"
    >
      {/* Console Top Header */}
      <div className="px-4 py-3 border-b border-cyan-950/60 bg-slate-900/40 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Terminal className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold font-mono tracking-wider text-white uppercase flex items-center gap-2">
              <span>Live Inspector</span>
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            </h2>
            <p className="text-[10px] text-slate-400 font-mono">
              {selectedTarget.type === 'agent'
                ? `Active Agent: ${selectedAgent?.name || 'System'}`
                : `Task ID: ${selectedTarget.taskId.slice(-8)}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={() => setAutoScroll((prev) => !prev)}
            title={autoScroll ? 'Disable Auto-Scroll' : 'Enable Auto-Scroll'}
            className={`px-2 py-1 rounded text-[10px] font-mono border transition-colors flex items-center gap-1 ${
              autoScroll
                ? 'bg-cyan-950/80 border-cyan-500/50 text-cyan-300'
                : 'bg-slate-800/60 border-slate-700/50 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Activity className="w-3 h-3" />
            <span>Auto</span>
          </button>

          <button
            onClick={onClearLogs}
            title="Clear Console Logs"
            className="p-1.5 rounded text-slate-400 hover:text-rose-300 hover:bg-rose-950/30 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Target Inspector Card */}
      <div className="p-3.5 border-b border-cyan-950/40 bg-slate-900/20 shrink-0">
        {selectedTarget.type === 'agent' && selectedAgent && (
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div
                  className={`p-2 rounded-xl border ${
                    selectedAgent.id === 'hermes'
                      ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-400'
                      : selectedAgent.id === 'ultron'
                      ? 'bg-rose-950/60 border-rose-500/40 text-rose-400'
                      : selectedAgent.id === 'prime'
                      ? 'bg-indigo-950/60 border-indigo-500/40 text-indigo-400'
                      : 'bg-cyan-950/60 border-cyan-500/40 text-cyan-400'
                  }`}
                >
                  {getAgentIcon(selectedAgent.id, 'w-5 h-5')}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white tracking-wide">
                      {selectedAgent.name}
                    </span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                        selectedAgent.badgeColor === 'emerald'
                          ? 'bg-emerald-950/80 border-emerald-500/40 text-emerald-300'
                          : selectedAgent.badgeColor === 'rose'
                          ? 'bg-rose-950/80 border-rose-500/40 text-rose-300'
                          : selectedAgent.badgeColor === 'indigo'
                          ? 'bg-indigo-950/80 border-indigo-500/40 text-indigo-300'
                          : 'bg-cyan-950/80 border-cyan-500/40 text-cyan-300'
                      }`}
                    >
                      {selectedAgent.badge}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">{selectedAgent.role}</p>
                </div>
              </div>

              <div className="text-right">
                <span className="text-[10px] font-mono text-slate-500 block">MODEL ROUTE</span>
                <span className="text-[11px] font-mono text-cyan-300 font-semibold">
                  {selectedAgent.modelEndpoint || 'Gemini 2.5 Flash'}
                </span>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60">
              {selectedAgent.description}
            </p>

            {/* Capabilities Chips */}
            {selectedAgent.capabilities && selectedAgent.capabilities.length > 0 && (
              <div>
                <span className="text-[10px] font-mono text-slate-500 block mb-1">
                  CORE SUBSYSTEMS & CAPABILITIES
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {selectedAgent.capabilities.map((cap, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-slate-800/70 border border-slate-700/60 text-[10px] text-slate-300 font-mono"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Quick Actions Triggers */}
            {selectedAgent.quickActions && selectedAgent.quickActions.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] font-mono text-slate-500 flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-cyan-400" />
                    <span>INSTANT ACTUATION DISPATCH</span>
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-1.5">
                  {selectedAgent.quickActions.map((qa, i) => (
                    <button
                      key={i}
                      onClick={() => onTriggerQuickAction(qa.prompt)}
                      className="w-full text-left px-2.5 py-1.5 rounded-lg bg-cyan-950/30 hover:bg-cyan-900/50 border border-cyan-800/40 hover:border-cyan-500/60 text-xs font-mono text-cyan-200 transition-all flex items-center justify-between group"
                    >
                      <span className="truncate">{qa.label}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-cyan-400 group-hover:translate-x-0.5 transition-transform shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {selectedTarget.type === 'task' && (
          <div>
            {selectedTask ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span
                        className={`text-[9px] font-mono px-2 py-0.5 rounded-full uppercase font-bold border ${
                          selectedTask.status === 'completed'
                            ? 'bg-emerald-950/80 border-emerald-500/40 text-emerald-300'
                            : selectedTask.status === 'failed'
                            ? 'bg-rose-950/80 border-rose-500/40 text-rose-300'
                            : 'bg-cyan-950/80 border-cyan-500/40 text-cyan-300 animate-pulse'
                        }`}
                      >
                        {selectedTask.status}
                      </span>
                      <span className="text-[10px] font-mono text-slate-500">
                        {selectedTask.category}
                      </span>
                    </div>
                    <h3 className="text-xs font-bold text-white tracking-wide truncate">
                      {selectedTask.title}
                    </h3>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {selectedTask.status === 'running' && (
                      <button
                        onClick={() => onCancelTask(selectedTask.id)}
                        className="px-2 py-1 rounded bg-rose-950/80 hover:bg-rose-900 border border-rose-600/50 text-[10px] font-mono text-rose-300 transition-colors"
                      >
                        Cancel
                      </button>
                    )}
                    {selectedTask.status === 'completed' && selectedTask.displayCard && (
                      <button
                        onClick={() =>
                          onSelectDisplayCard && onSelectDisplayCard(selectedTask.displayCard!)
                        }
                        className="px-2.5 py-1 rounded bg-cyan-500 hover:bg-cyan-400 text-slate-950 text-[10px] font-mono font-bold transition-colors flex items-center gap-1"
                      >
                        <span>Card</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                <div>
                  <div className="flex items-center justify-between text-[10px] font-mono mb-1">
                    <span className="text-slate-400 truncate mr-2">
                      {selectedTask.progressMessage || 'Processing execution graph...'}
                    </span>
                    <span className="text-cyan-300 font-bold">
                      {selectedTask.progressPercent ?? (selectedTask.status === 'completed' ? 100 : 0)}%
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-slate-800/80 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        selectedTask.status === 'completed'
                          ? 'bg-emerald-400'
                          : selectedTask.status === 'failed'
                          ? 'bg-rose-500'
                          : 'bg-gradient-to-r from-cyan-400 to-indigo-500 shadow-[0_0_8px_rgba(6,182,212,0.8)]'
                      }`}
                      style={{
                        width: `${
                          selectedTask.status === 'completed'
                            ? 100
                            : selectedTask.progressPercent ?? 20
                        }%`,
                      }}
                    />
                  </div>
                </div>

                {/* Execution timing metadata */}
                <div className="grid grid-cols-2 gap-2 text-[10px] font-mono bg-slate-950/40 p-2 rounded-lg border border-slate-800/50">
                  <div>
                    <span className="text-slate-500 block">ELAPSED TIME</span>
                    <span className="text-slate-300 font-semibold">
                      {selectedTask.status === 'completed' && selectedTask.durationMs
                        ? `${(selectedTask.durationMs / 1000).toFixed(2)}s total`
                        : `${Math.max(0, (nowTime - selectedTask.startTime) / 1000).toFixed(1)}s active`}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">INITIATED AT</span>
                    <span className="text-slate-300">
                      {new Date(selectedTask.startTime).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </span>
                  </div>
                </div>

                {/* Task Result Summary if completed */}
                {selectedTask.result && (
                  <div className="bg-slate-950/70 p-2.5 rounded-lg border border-emerald-500/30 max-h-36 overflow-y-auto">
                    <span className="text-[10px] font-mono text-emerald-400 font-bold block mb-1">
                      EXECUTION RESULT PAYLOAD
                    </span>
                    <p className="text-xs text-slate-300 whitespace-pre-wrap font-sans">
                      {typeof selectedTask.result === 'string'
                        ? selectedTask.result
                        : selectedTask.result.text || JSON.stringify(selectedTask.result, null, 2)}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-4 text-slate-400 font-mono text-xs">
                Task details expired or unavailable.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Log Controls & Filters */}
      <div className="px-3.5 py-2 border-b border-cyan-950/40 bg-slate-900/30 flex items-center justify-between gap-2 shrink-0">
        {/* Level Filters */}
        <div className="flex items-center gap-1 text-[10px] font-mono">
          {(['all', 'info', 'warn', 'error'] as const).map((lvl) => (
            <button
              key={lvl}
              onClick={() => setLevelFilter(lvl)}
              className={`px-2 py-0.5 rounded uppercase font-semibold transition-colors ${
                levelFilter === lvl
                  ? 'bg-cyan-500 text-slate-950'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>

        {/* Log Search Input */}
        <div className="relative flex-1 max-w-[140px]">
          <Search className="w-3 h-3 text-slate-500 absolute left-2 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search logs..."
            value={logSearchQuery}
            onChange={(e) => setLogSearchQuery(e.target.value)}
            className="w-full pl-6 pr-2 py-1 rounded bg-slate-950/60 border border-slate-800 text-[10px] font-mono text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
      </div>

      {/* Logs Scrollable Stream */}
      <div
        ref={logContainerRef}
        className="flex-1 p-3 overflow-y-auto space-y-2 font-mono text-xs custom-scrollbar"
      >
        {relevantLogs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
            <Radio className="w-8 h-8 text-cyan-500/40 animate-pulse mb-3" />
            <p className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider mb-1">
              Awaiting Telemetry Stream
            </p>
            <p className="text-[10px] font-mono text-slate-600 max-w-[200px]">
              Ready for events from{' '}
              {selectedTarget.type === 'agent'
                ? selectedAgent?.name || 'JARVIS System'
                : 'parallel task worker'}
              .
            </p>
          </div>
        ) : (
          relevantLogs.map((log) => {
            const isExpanded = expandedLogIds.has(log.id);
            const levelClass = getLevelColor(log.level);

            return (
              <div
                key={log.id}
                className="p-2 rounded-lg bg-slate-900/40 hover:bg-slate-900/70 border border-slate-800/70 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[9px] text-slate-500">{log.timestamp}</span>
                    <span
                      className={`text-[9px] uppercase px-1.5 py-0.2 rounded border font-bold ${levelClass}`}
                    >
                      {log.level}
                    </span>
                    <span className="text-[9px] font-bold text-cyan-300/90 uppercase px-1 rounded bg-cyan-950/40">
                      {log.agent}
                    </span>
                    {log.taskId && (
                      <span className="text-[9px] text-slate-400">
                        #{log.taskId.slice(-6)}
                      </span>
                    )}
                  </div>

                  {log.details && (
                    <button
                      onClick={() => toggleExpandLog(log.id)}
                      className="text-slate-400 hover:text-cyan-300 p-0.5"
                    >
                      {isExpanded ? (
                        <ChevronUp className="w-3 h-3" />
                      ) : (
                        <ChevronDown className="w-3 h-3" />
                      )}
                    </button>
                  )}
                </div>

                <p className="text-xs text-slate-200 mt-1.5 leading-relaxed break-words font-mono">
                  {log.message}
                </p>

                {isExpanded && log.details && (
                  <pre className="mt-2 p-2 rounded bg-slate-950 border border-slate-800 text-[10px] text-cyan-300 overflow-x-auto">
                    {typeof log.details === 'string'
                      ? log.details
                      : JSON.stringify(log.details, null, 2)}
                  </pre>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Console Status Footer Bar */}
      <div className="px-3.5 py-1.5 border-t border-cyan-950/40 bg-slate-950 text-[10px] font-mono text-slate-400 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span>SOCKET 16k/24k OK</span>
        </div>
        <span>{relevantLogs.length} LOGS BUFFERED</span>
      </div>
    </aside>
  );
};
