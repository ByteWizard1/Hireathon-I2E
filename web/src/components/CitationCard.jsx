import React from 'react';
import { BookOpen, MapPin, Target, Image as ImageIcon } from 'lucide-react';
import { motion } from 'framer-motion';

const CitationCard = ({ citation, index, onClick }) => {
  const isImage = citation.chunk_type === 'image';
  const hasImage = citation.image_path;

  const formatImagePath = (path) => {
    if (!path) return '';
    // Replace Windows backslashes with forward slashes
    const normalized = path.replace(/\\/g, '/');
    // Ensure it starts with a slash
    return normalized.startsWith('/') ? normalized : `/${normalized}`;
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      whileHover={{ scale: 1.02 }}
      className={`relative rounded-xl border border-gray-700 bg-gray-800 p-4 transition-all hover:bg-gray-750 cursor-pointer shadow-sm hover:shadow-md ${isImage ? 'ring-1 ring-blue-500/30' : ''}`}
      onClick={() => onClick(citation)}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          {isImage ? (
            <div className="p-1.5 rounded-md bg-blue-500/20 text-blue-400">
              <ImageIcon className="w-4 h-4" />
            </div>
          ) : (
            <div className="p-1.5 rounded-md bg-teal-500/20 text-teal-400">
              <BookOpen className="w-4 h-4" />
            </div>
          )}
          <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
            Section {citation.section_id}
          </span>
        </div>
        
        {citation.score && (
          <div className="flex items-center gap-1.5 bg-gray-900 px-2 py-0.5 rounded text-xs">
            <Target className="w-3 h-3 text-emerald-400" />
            <span className="text-gray-400 font-mono">{(citation.score * 100).toFixed(0)}%</span>
          </div>
        )}
      </div>

      <h4 className="text-sm font-medium text-gray-200 line-clamp-2 leading-snug mb-3">
        {citation.section_title}
      </h4>

      {hasImage && (
        <div className="relative w-full h-24 mb-3 rounded-md overflow-hidden bg-gray-900 border border-gray-700">
          <img 
            src={`http://localhost:8000${formatImagePath(citation.image_path)}`} 
            alt={citation.section_title} 
            className="w-full h-full object-cover opacity-80 hover:opacity-100 transition-opacity"
            loading="lazy"
          />
          <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 hover:opacity-100 transition-opacity">
            <span className="text-xs font-medium text-white flex items-center gap-1 bg-black/60 px-2 py-1 rounded">
              <ImageIcon className="w-3 h-3"/> View Full
            </span>
          </div>
        </div>
      )}

      <div className="flex items-center text-xs text-gray-500 font-medium">
        <MapPin className="w-3 h-3 mr-1" />
        Page {citation.page}
      </div>
    </motion.div>
  );
};

export default CitationCard;
