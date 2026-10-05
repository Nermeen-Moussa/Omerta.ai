import React, { useState } from 'react';
import {
  Bot,
  Sparkles,
  Send,
  BookOpen,
  ShieldAlert,
  Network,
  Scale,
  Clock,
  Zap,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  citations?: string[];
}

export const AiAssistantPage: React.FC = () => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-1',
      sender: 'assistant',
      text: `Hello ${user?.full_name || 'Investigator'}. I am the **Omerta.ai Regulatory & Intelligence Copilot**. I will assist you with autonomous case dossiers, money mule link investigations, and regulatory AML compliance queries.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      citations: ['FATF Recommendation 10 & 16', 'Omerta Typology Knowledge Base v2026.1'],
    },
  ]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const samplePrompts = [
    {
      title: 'Analyze Smurfing & Structuring',
      prompt: 'Check for transactions structured just below the 50,000 EGP reporting threshold in the last 48 hours.',
      icon: ShieldAlert,
    },
    {
      title: 'FATF Recommendation 16 Compliance',
      prompt: 'Explain wire transfer Travel Rule requirements for cross-border transactions involving high-risk jurisdictions.',
      icon: Scale,
    },
    {
      title: 'Mule Ring Topology Summary',
      prompt: 'Summarize the multi-account device cluster connected to Device DEV-E7F39AF6.',
      icon: Network,
    },
  ];

  const handleSend = (textToSend?: string) => {
    const query = (textToSend || inputPrompt).trim();
    if (!query) return;

    const userMsg: ChatMessage = {
      id: `usr-${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputPrompt('');
    setIsTyping(true);

    setTimeout(() => {
      const assistantMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: 'assistant',
        text: `**[Stage 3 RAG Knowledge & Multi-Agent Swarm — Coming Soon]**\n\nYour query has been indexed against the financial-crime vector store: \`"${query}"\`.\n\nAutonomous LangGraph multi-agent execution, live vector embeddings, and direct SAR narrative generation will be connected in Stage 3. For immediate investigations, use the **Investigations Dossier** and **Network Analysis Graph** tabs.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: ['Omerta AML Regulatory Corpus (FATF/Egmont)', 'Graph DB: omerta-neo4j:17687'],
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsTyping(false);
    }, 900);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-in fade-in duration-200">
      {/* Top Banner */}
      <div className="omerta-card p-6 border-[#25344A] bg-[#101A2B] shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] flex items-center justify-center text-slate-950 shadow-lg shadow-cyan-500/20">
            <Bot className="w-7 h-7 stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-[#F4F7FC] tracking-tight">
                AI Intelligence & RAG Copilot
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-[#3978F6]/20 text-[#29C5D9] border border-[#3978F6]/40">
                Coming Soon · Stage 3
              </span>
            </div>
            <p className="text-xs text-[#A7B4C8] mt-1">
              Autonomous financial-crime investigation swarm with grounded FATF & Central Bank AML regulatory retrieval.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#080D19] border border-[#25344A] text-xs text-[#A7B4C8]">
          <Zap className="w-4 h-4 text-[#27C58B]" />
          <span>Multi-Agent Swarm Orchestrator Ready</span>
        </div>
      </div>

      {/* Suggested Prompts */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {samplePrompts.map((p, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(p.prompt)}
            className="p-3.5 rounded-xl bg-[#0B1220] hover:bg-[#152238] border border-[#25344A] hover:border-[#3978F6]/40 text-left transition-all group flex flex-col justify-between"
          >
            <div className="flex items-center gap-2 mb-2">
              <p.icon className="w-4 h-4 text-[#29C5D9] group-hover:scale-110 transition-transform" />
              <span className="text-xs font-bold text-[#F4F7FC]">{p.title}</span>
            </div>
            <p className="text-[11px] text-[#71819A] line-clamp-2 leading-relaxed">
              {p.prompt}
            </p>
          </button>
        ))}
      </div>

      {/* Chat Messages Window */}
      <div className="omerta-card border-[#25344A] bg-[#0B1220] flex flex-col h-[480px] shadow-2xl rounded-2xl overflow-hidden">
        <div className="flex-1 p-5 overflow-y-auto space-y-4">
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex gap-3 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {m.sender === 'assistant' && (
                <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] flex items-center justify-center text-slate-950 shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 stroke-[2.5]" />
                </div>
              )}

              <div
                className={`max-w-[78%] rounded-2xl p-4 text-xs leading-relaxed ${
                  m.sender === 'user'
                    ? 'bg-[#3978F6] text-[#F4F7FC] font-medium shadow-md shadow-blue-500/20'
                    : 'bg-[#101A2B] border border-[#25344A] text-[#F4F7FC]'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.text}</div>

                {m.citations && m.citations.length > 0 && (
                  <div className="mt-3 pt-2.5 border-t border-[#25344A] flex flex-wrap items-center gap-1.5 text-[10px] text-[#29C5D9]">
                    <BookOpen className="w-3 h-3" />
                    <span className="font-bold">Citations:</span>
                    {m.citations.map((c, i) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 rounded bg-[#080D19] border border-[#25344A] text-[#A7B4C8]"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}

                <div
                  className={`text-[9px] mt-1.5 flex items-center gap-1 ${
                    m.sender === 'user' ? 'text-blue-200 justify-end' : 'text-[#71819A]'
                  }`}
                >
                  <Clock className="w-2.5 h-2.5" />
                  <span>{m.timestamp}</span>
                </div>
              </div>
            </div>
          ))}

          {isTyping && (
            <div className="flex gap-3 justify-start items-center">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#3978F6] to-[#29C5D9] flex items-center justify-center text-slate-950">
                <Bot className="w-4 h-4 stroke-[2.5]" />
              </div>
              <div className="p-3 rounded-2xl bg-[#101A2B] border border-[#25344A] flex items-center gap-1.5 text-xs text-[#29C5D9]">
                <Sparkles className="w-3.5 h-3.5 animate-spin" />
                <span className="text-[11px] font-semibold">Consulting AML Knowledge Graph & LangGraph Swarm...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-3.5 bg-[#101A2B] border-t border-[#25344A]">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              placeholder="Ask Copilot to analyze suspects, search typologies, or draft SAR dispositions..."
              className="flex-1 px-4 py-2.5 bg-[#080D19] border border-[#25344A] rounded-xl text-xs text-[#F4F7FC] placeholder-[#71819A] focus:outline-none focus:border-[#3978F6]"
            />
            <button
              type="submit"
              disabled={!inputPrompt.trim() || isTyping}
              className="px-4 py-2.5 rounded-xl bg-[#3978F6] hover:bg-[#3978F6]/90 disabled:opacity-50 text-[#F4F7FC] text-xs font-bold transition-all flex items-center gap-1.5 shadow-md shadow-blue-500/20 cursor-pointer"
            >
              <span>Ask</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
