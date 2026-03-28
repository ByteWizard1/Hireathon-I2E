import React from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user';

  // Component to render inline [1] or (Section X.X) as clickable badging if needed.
  // We'll rely on react-markdown's robust parsing for bullet points.
  // Applying some custom tailwind typography styles via components.
  
  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
      className={`relative w-full py-7 px-4 group ${isUser ? 'bg-chatBg' : 'bg-userBubble/30 border-y border-gray-800'}`}
    >
      <div className="max-w-4xl mx-auto flex gap-6">
        {/* Avatar */}
        <div className="w-9 h-9 shrink-0 flex items-center justify-center rounded-lg shadow-sm">
          {isUser ? (
            <div className="bg-gradient-to-br from-indigo-500 to-purple-600 text-white w-full h-full flex items-center justify-center rounded-lg">
              <User className="w-5 h-5" />
            </div>
          ) : (
            <div className="bg-gradient-to-br from-teal-400 to-emerald-500 text-white w-full h-full flex items-center justify-center rounded-lg shadow-[0_0_15px_rgba(20,184,166,0.5)]">
              <Sparkles className="w-5 h-5" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 prose prose-invert prose-indigo prose-p:leading-relaxed prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700 max-w-none prose-a:text-indigo-400 font-sans mt-1 text-[15px] tracking-[0.01em]">
          <ReactMarkdown
            components={{
              p: ({node, ...props}) => <p className="mb-4 text-gray-200" {...props} />,
              ul: ({node, ...props}) => <ul className="list-disc pl-6 mb-4 text-gray-200 space-y-2 marker:text-indigo-400" {...props} />,
              ol: ({node, ...props}) => <ol className="list-decimal pl-6 mb-4 text-gray-200 space-y-2 marker:text-emerald-400 font-medium" {...props} />,
              li: ({node, ...props}) => <li className="pl-1" {...props} />,
              strong: ({node, ...props}) => <strong className="font-semibold text-white tracking-wide" {...props} />,
              blockquote: ({node, ...props}) => (
                <blockquote className="border-l-4 border-indigo-500 bg-indigo-500/10 py-1 px-4 rounded-r my-4" {...props}/>
              )
            }}
          >
            {message.content}
          </ReactMarkdown>

          {/* Show the citations summarized if assistant */}
          {!isUser && message.citations?.length > 0 && (
            <div className="mt-8 pt-4 border-t border-gray-700/50">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                 References Used
              </span>
              <div className="flex flex-wrap gap-2">
                {message.citations.map((cite, i) => (
                  <div key={i} className="inline-flex items-center px-2.5 py-1 rounded bg-gray-800 border border-gray-700 text-xs font-medium text-gray-300">
                    [{i + 1}] Section {cite.section_id} (p. {cite.page})
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default MessageBubble;
