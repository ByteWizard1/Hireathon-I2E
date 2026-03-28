import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

const InputBox = ({ onSend, isLoading }) => {
  const [text, setText] = useState('');
  const textareaRef = useRef(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [text]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (text.trim() && !isLoading) {
      onSend(text.trim());
      setText('');
      // Reset height instantly after send
      if (textareaRef.current) {
         textareaRef.current.style.height = 'auto';
      }
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto px-4 pb-6 pt-2">
      <motion.div 
        className="relative bg-[#343541] rounded-2xl border border-gray-600 shadow-[0_0_15px_rgba(0,0,0,0.1)] flex shadow-black/20 overflow-hidden"
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question about the NASA Systems Engineering Handbook..."
          className="w-full bg-transparent text-gray-100 placeholder-gray-400 border-0 focus:ring-0 resize-none py-4 px-5 pr-14 max-h-48 overflow-y-auto"
          rows={1}
          disabled={isLoading}
        />
        
        <button
          onClick={handleSubmit}
          disabled={!text.trim() || isLoading}
          className={`absolute right-3 bottom-3 p-2 rounded-xl flex items-center justify-center transition-all ${
            text.trim() && !isLoading 
              ? 'bg-gradient-to-tr from-indigo-500 to-purple-500 text-white hover:opacity-90 shadow-lg' 
              : 'bg-gray-600/50 text-gray-400 cursor-not-allowed'
          }`}
        >
          {isLoading ? (
             <Loader2 className="w-4 h-4 animate-spin text-white" />
          ) : (
             <Send className="w-4 h-4 ml-0.5" />
          )}
        </button>
      </motion.div>
      <div className="text-center mt-3 text-xs text-gray-500 font-medium tracking-wide">
        AI-powered assistant answering strictly from the <span className="text-gray-400">NASA Systems Engineering Handbook v2.0</span>
      </div>
    </div>
  );
};

export default InputBox;
