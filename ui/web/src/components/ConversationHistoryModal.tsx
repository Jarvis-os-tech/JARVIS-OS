import React from 'react';
import { MessageExchange, InputAttachment } from '../types';
import { ConversationExchangeView } from './ConversationExchangeView';
import {
  History,
  X,
  RotateCcw,
  Sparkles,
  MessageSquare,
} from 'lucide-react';

interface ConversationHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  messages: MessageExchange[];
  onRefresh: () => void;
  onPreviewAttachment?: (attachment: InputAttachment) => void;
  onPlayAudio?: (text: string) => void;
}

export const ConversationHistoryModal: React.FC<ConversationHistoryModalProps> = ({
  isOpen,
  onClose,
  messages,
  onRefresh,
  onPreviewAttachment,
  onPlayAudio,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fadeIn">
      <div className="w-full max-w-2xl bg-slate-900/95 border border-cyan-500/40 rounded-2xl p-5 text-slate-100 shadow-[0_0_50px_rgba(6,182,212,0.15)] overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">
              <History className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-white">Continuous Living Conversation</h2>
                <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-cyan-300">
                  Perpetual Memory
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Unbroken context across restarts & reloads • {messages.length} turn{messages.length === 1 ? '' : 's'} recorded
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={onRefresh}
              title="Refresh conversation history from memory engine"
              className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800/60 transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Conversation turns list */}
        <div className="flex-1 overflow-y-auto py-4 custom-scrollbar">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-center text-slate-500 space-y-2">
              <MessageSquare className="w-8 h-8 text-slate-600" />
              <p className="text-sm font-medium text-slate-400">Continuous session is active</p>
              <p className="text-xs text-slate-500 max-w-sm">
                No conversation turns recorded yet. Speak or type to begin logging unbroken turns to the memory vault.
              </p>
            </div>
          ) : (
            <ConversationExchangeView
              messages={messages}
              onPreviewAttachment={onPreviewAttachment}
              onPlayAudio={onPlayAudio}
            />
          )}
        </div>

        {/* Footer Info */}
        <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500 shrink-0">
          <span className="font-mono">SQLite + Vault Journal (conversation.md)</span>
          <span className="text-cyan-400/80 font-mono">Single Continuous Session • Active</span>
        </div>
      </div>
    </div>
  );
};
