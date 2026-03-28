import React from 'react';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const ImageModal = ({ citation, onClose }) => {
  if (!citation) return null;

  const formatImagePath = (path) => {
    if (!path) return '';
    const normalized = path.replace(/\\/g, '/');
    return normalized.startsWith('/') ? normalized : `/${normalized}`;
  };

  return (
    <AnimatePresence>
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80"
        onClick={onClose}
      >
        <motion.div 
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="relative max-w-5xl w-full max-h-[90vh] bg-panelBg rounded-xl overflow-hidden shadow-2xl flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-700 bg-panelBg z-10">
            <div>
              <h3 className="font-semibold text-gray-100">{citation.section_title}</h3>
              <p className="text-sm text-gray-400">Section {citation.section_id} • Page {citation.page}</p>
            </div>
            <button 
              onClick={onClose}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors text-gray-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          {/* Image Container */}
          <div className="flex-1 overflow-auto bg-[#1A1B22] flex items-center justify-center p-6">
            <img 
              src={`http://localhost:8000${formatImagePath(citation.image_path)}`} 
              alt={citation.section_title}
              className="max-w-full max-h-full object-contain rounded-lg shadow-lg border border-gray-800"
            />
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default ImageModal;
