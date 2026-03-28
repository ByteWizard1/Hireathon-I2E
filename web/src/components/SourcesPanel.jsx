import React from 'react';
import { AlignLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import CitationCard from './CitationCard';

const SourcesPanel = ({ citations, onCitationClick }) => {
  return (
    <div className="w-80 border-l border-gray-800 bg-panelBg flex flex-col h-full shadow-lg">
      <div className="flex items-center gap-2 p-5 border-b border-gray-800 bg-[#32333A]">
        <AlignLeft className="w-5 h-5 text-indigo-400" />
        <h2 className="text-sm font-bold text-gray-200 uppercase tracking-widest">Sources</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar space-y-4 relative">
        <AnimatePresence>
          {citations.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-center text-gray-500 mt-10"
            >
              <div className="mb-4 inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-800 shadow-inner">
                <ChevronRight className="w-6 h-6 text-gray-600" />
              </div>
              <p className="text-sm px-4">Sources and visual references will appear here as you chat.</p>
            </motion.div>
          ) : (
            citations.map((cite, index) => (
              <CitationCard 
                key={`${cite.section_id}-${index}`} 
                citation={cite} 
                index={index} 
                onClick={onCitationClick}
              />
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default SourcesPanel;
