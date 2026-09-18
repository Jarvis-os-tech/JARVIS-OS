import React, { useState, useEffect } from 'react';
import {
  SubAgentMeta,
  BackgroundTask,
  SelectedTarget,
  TaskCategory,
} from '../types';
import {
  Bot,
  ShieldAlert,
  Code2,
  Cpu,
  Layers,
  Activity,
  CheckCircle2,
  Clock,
  X,
  Play,
  Search,
  Filter,
  ChevronRight,
  ExternalLink,
  Sparkles,
  Zap,
  Terminal,
  Radio,
} from 'lucide-react';

interface AgentTaskSidebarProps {
  agents: SubAgentMeta[];
  activeTasks: BackgroundTask[];
  completedTasks: BackgroundTask[];
  selectedTarget: SelectedTarget;
  onSelectTarget: (target: SelectedTarget) => void;
  onCancelTask: (taskId: string) => void;
  onClearCompletedTasks?: () => void;
}

export const AgentTaskSidebar: React.FC<AgentTaskSidebarProps> = ({
  agents,
  activeTasks,
  completedTasks,
  selectedTarget,
  onSelectTarget,
  onCancelTask,
  onClearCompletedTasks,
}) => {
  const [filterTab, setFilterTab] = useState<'all' | 'agents' | 'active' | 'completed'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [nowTime, setNowTime] = useState<number>(Date.now());

  // Live timer tick for active task durations
  useEffect(() => {
    if (activeTasks.length === 0) return;
    const interval = setInterval(() => {
      setNowTime(Date.now());
    }, 250);
    return () => clearInterval(interval);
  }, [activeTasks.length]);

  const getAgentIcon = (id: string, className = 'w-4 h-4') => {
    switch (id) {
      case 'hermes':
        return <Bot className={className} />;
      case 'ultron':
        return <ShieldAlert className={className} />;
      case 'prime':
        return <Code2 className={className} />;
      case 'system':
      default:
        return <Cpu className={className} />;
    }
  };

  const getAgentGlow = (id: string, isSelected: boolean) => {
    if (isSelected) {
      switch (id) {
        case 'hermes':
          return 'border-emerald-500/80 bg-emerald-950/30 shadow-[0_0_15px_rgba(16,185,129,0.25)]';
        case 'ultron':
          return 'border-rose-500/80 bg-rose-950/30 shadow-[0_0_15px_rgba(244,63,94,0.25)]';
        case 'prime':
          return 'border-indigo-500/80 bg-indigo-950/30 shadow-[0_0_15px_rgba(99,102,241,0.25)]';
        default:
          return 'border-cyan-500/80 bg-cyan-950/30 shadow-[0_0_15px_rgba(6,182,212,0.25)]';
      }
    }
    return 'border-slate-800/80 bg-slate-900/40 hover:border-slate-700/90 hover:bg-slate-900/70';
  };

  const filteredAgents = agents.filter(
    (a) =>
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredActiveTasks = activeTasks.filter(
    (t) =>
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.prompt && t.prompt.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const filteredCompletedTasks = completedTasks.filter(
    (t) =>
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.prompt && t.prompt.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <aside
      id="jarvis-left-sidebar"
      className="w-full lg:w-72 xl:w-80 h-full flex flex-col bg-slate-950/80 backdrop-blur-2xl border-r border-slate-800/70 select-none overflow-hidden"
    >
      {/* Sidebar Header */}
      <div className="p-3.5 border-b border-slate-800/80 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            <Layers className="w-4 h-4 animate-pulse" />
          </div>
          <div>
            <h2 className="text-xs font-mono font-bold tracking-widest uppercase text-slate-100 flex items-center gap-1.5">
              Sub-Agents & Tasks
            </h2>
            <p className="text-[10px] text-slate-400 font-mono">
              {activeTasks.length} running • {agents.length} agents
            </p>
          </div>
        </div>

        {activeTasks.length > 0 && (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/10 border border-amber-500/30 text-amber-300 animate-pulse">
            <Radio className="w-3 h-3 animate-spin" />
            LIVE
          </span>
        )}
      </div>

      {/* Filter Tabs & Quick Search */}
      <div className="p-2.5 border-b border-slate-800/60 flex flex-col gap-2">
        <div className="relative w-full">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Filter agents or tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-2.5 py-1.5 rounded-lg bg-slate-900/70 border border-slate-800 text-slate-200 placeholder-slate-500 text-xs font-mono focus:outline-none focus:border-cyan-500/50 transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-2 text-slate-500 hover:text-slate-300 text-xs"
            >
              ✕
            </button>
          )}
        </div>

        <div className="flex items-center gap-1 p-0.5 rounded-lg bg-slate-900/60 border border-slate-800/60 text-[11px] font-mono">
          <button
            onClick={() => setFilterTab('all')}
            className={`flex-1 py-1 rounded transition-colors text-center ${
              filterTab === 'all'
                ? 'bg-cyan-500/20 text-cyan-300 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilterTab('agents')}
            className={`flex-1 py-1 rounded transition-colors text-center ${
              filterTab === 'agents'
                ? 'bg-cyan-500/20 text-cyan-300 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Agents ({agents.length})
          </button>
          <button
            onClick={() => setFilterTab('active')}
            className={`flex-1 py-1 rounded transition-colors text-center flex items-center justify-center gap-1 ${
              filterTab === 'active'
                ? 'bg-amber-500/20 text-amber-300 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Tasks ({activeTasks.length})
          </button>
          <button
            onClick={() => setFilterTab('completed')}
            className={`flex-1 py-1 rounded transition-colors text-center ${
              filterTab === 'completed'
                ? 'bg-cyan-500/20 text-cyan-300 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Done ({completedTasks.length})
          </button>
        </div>
      </div>

      {/* Main Scrollable Content */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-4 custom-scrollbar">
        {/* SECTION 1: Active Parallel Tasks (Highest Priority) */}
        {(filterTab === 'all' || filterTab === 'active') && filteredActiveTasks.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-1.5 px-1">
              <span className="text-[10px] font-mono font-bold tracking-wider text-amber-400 uppercase flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                Active Tasks ({filteredActiveTasks.length})
              </span>
            </div>

            <div className="space-y-1.5">
              {filteredActiveTasks.map((task) => {
                const isSelected =
                  selectedTarget.type === 'task' && selectedTarget.taskId === task.id;
                const elapsedSec = Math.max(0, (nowTime - task.startTime) / 1000);

                return (
                  <div
                    key={task.id}
                    onClick={() => onSelectTarget({ type: 'task', taskId: task.id })}
                    className={`p-2.5 rounded-xl border transition-all cursor-pointer relative overflow-hidden group ${
                      isSelected
                        ? 'border-amber-500/80 bg-amber-950/30 shadow-[0_0_15px_rgba(245,158,11,0.2)]'
                        : 'border-slate-800 bg-slate-900/60 hover:border-amber-500/40 hover:bg-slate-900/90'
                    }`}
                  >
                    {/* Live Pulsing Progress Bar background */}
                    <div
                      className="absolute bottom-0 left-0 h-0.5 bg-gradient-to-r from-amber-400 to-cyan-400 transition-all duration-300"
                      style={{ width: `${task.progressPercent ?? 45}%` }}
                    />

                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="p-1 rounded-md bg-amber-500/20 text-amber-300 shrink-0">
                          {getAgentIcon(task.type)}
                        </div>
                        <div className="min-w-0">
                          <h4 className="text-xs font-semibold text-slate-100 truncate">
                            {task.title}
                          </h4>
                          <p className="text-[10px] text-amber-400/90 font-mono truncate">
                            {task.progressMessage || 'Executing autonomously...'}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="text-[10px] font-mono text-amber-300 font-bold bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                          {elapsedSec.toFixed(1)}s
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onCancelTask(task.id);
                          }}
                          className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                          title="Cancel task"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* SECTION 2: Sub-Agents Roster */}
        {(filterTab === 'all' || filterTab === 'agents') && (
          <div>
            <div className="flex items-center justify-between mb-1.5 px-1">
              <span className="text-[10px] font-mono font-bold tracking-wider text-slate-400 uppercase">
                Sub-Agents Roster ({filteredAgents.length})
              </span>
            </div>

            <div className="space-y-2">
              {filteredAgents.map((agent) => {
                const isSelected =
                  selectedTarget.type === 'agent' && selectedTarget.agentId === agent.id;
                const agentRunningCount = activeTasks.filter(
                  (t) => t.type === agent.id || (agent.id === 'ultron' && t.type === 'openclaw')
                ).length;

                return (
                  <div
                    key={agent.id}
                    onClick={() => onSelectTarget({ type: 'agent', agentId: agent.id })}
                    className={`p-3 rounded-xl border transition-all cursor-pointer relative overflow-hidden group ${getAgentGlow(
                      agent.id,
                      isSelected
                    )}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className={`p-2 rounded-lg shrink-0 border transition-colors ${
                            agent.id === 'hermes'
                              ? 'bg-emerald-950/70 border-emerald-500/30 text-emerald-400'
                              : agent.id === 'ultron'
                              ? 'bg-rose-950/70 border-rose-500/30 text-rose-400'
                              : agent.id === 'prime'
                              ? 'bg-indigo-950/70 border-indigo-500/30 text-indigo-400'
                              : 'bg-cyan-950/70 border-cyan-500/30 text-cyan-400'
                          }`}
                        >
                          {getAgentIcon(agent.id, 'w-5 h-5')}
                        </div>

                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <h3 className="text-xs font-bold text-slate-100 truncate">
                              {agent.name}
                            </h3>
                            {agentRunningCount > 0 && (
                              <span className="px-1.5 py-0.2 rounded-full text-[9px] font-mono font-bold bg-amber-500 text-slate-950 animate-pulse">
                                {agentRunningCount} BUSY
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-slate-400 truncate">{agent.role}</p>
                        </div>
                      </div>

                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase tracking-wider border ${
                            agent.status === 'live'
                              ? agent.id === 'hermes'
                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                                : agent.id === 'ultron'
                                ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                                : 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'
                              : 'bg-slate-800/60 border-slate-700/60 text-slate-400'
                          }`}
                        >
                          {agent.badge}
                        </span>
                      </div>
                    </div>

                    {/* Capabilities Tags */}
                    <div className="flex flex-wrap gap-1 mt-2.5">
                      {agent.capabilities.slice(0, 3).map((cap, i) => (
                        <span
                          key={i}
                          className="px-1.5 py-0.5 rounded bg-slate-800/60 border border-slate-700/40 text-[9px] text-slate-400 font-mono"
                        >
                          {cap}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* SECTION 3: Completed / Recent Tasks */}
        {(filterTab === 'all' || filterTab === 'completed') && (
          <div>
            <div className="flex items-center justify-between mb-1.5 px-1 mt-2">
              <span className="text-[10px] font-mono font-bold tracking-wider text-slate-400 uppercase">
                Recent Tasks ({filteredCompletedTasks.length})
              </span>
              {completedTasks.length > 0 && onClearCompletedTasks && (
                <button
                  onClick={onClearCompletedTasks}
                  className="text-[10px] text-slate-500 hover:text-slate-300 font-mono"
                >
                  Clear
                </button>
              )}
            </div>

            {filteredCompletedTasks.length === 0 ? (
              <div className="p-4 rounded-xl border border-dashed border-slate-800/80 text-center text-[11px] text-slate-500 font-mono">
                No completed tasks yet.
              </div>
            ) : (
              <div className="space-y-1.5">
                {filteredCompletedTasks.map((task) => {
                  const isSelected =
                    selectedTarget.type === 'task' && selectedTarget.taskId === task.id;

                  return (
                    <div
                      key={task.id}
                      onClick={() => onSelectTarget({ type: 'task', taskId: task.id })}
                      className={`p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-2 group ${
                        isSelected
                          ? 'border-cyan-500/80 bg-cyan-950/30 shadow-[0_0_12px_rgba(6,182,212,0.2)]'
                          : 'border-slate-800/80 bg-slate-900/30 hover:border-slate-700/80 hover:bg-slate-900/60'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <div
                          className={`p-1 rounded-md shrink-0 ${
                            task.status === 'completed'
                              ? 'bg-emerald-500/20 text-emerald-400'
                              : 'bg-rose-500/20 text-rose-400'
                          }`}
                        >
                          {task.status === 'completed' ? (
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          ) : (
                            <X className="w-3.5 h-3.5" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <h4 className="text-xs font-medium text-slate-200 truncate">
                            {task.title}
                          </h4>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {task.type.toUpperCase()}
                            {task.durationMs && ` • ${(task.durationMs / 1000).toFixed(1)}s`}
                          </span>
                        </div>
                      </div>

                      <ChevronRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-slate-300 transition-colors shrink-0" />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Sidebar Footer Info */}
      <div className="p-2.5 border-t border-slate-800/70 bg-slate-950/90 flex items-center justify-between text-[10px] font-mono text-slate-400">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          Autonomous Dispatcher
        </span>
        <span>Python Core</span>
      </div>
    </aside>
  );
};
