import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Rocket } from 'lucide-react';
import MessageBubble from './MessageBubble';
import InputBox from './InputBox';
import SourcesPanel from './SourcesPanel';
import ImageModal from './ImageModal';

const ChatWindow = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeCitations, setActiveCitations] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (text) => {
    const userMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/ask', {
        question: text
      });
      
      const { answer, citations } = response.data;
      
      const aiMessage = { role: 'assistant', content: answer, citations };
      setMessages((prev) => [...prev, aiMessage]);
      setActiveCitations(citations);

    } catch (error) {
      console.error('Error fetching response:', error);
      setMessages((prev) => [
        ...prev, 
        { role: 'assistant', content: 'Sorry, I encountered an error communicating with the backend.' }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex w-full h-screen bg-chatBg overflow-hidden font-sans text-gray-200">
      
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative h-full">
        {/* Header */}
        <header className="sticky top-0 z-10 p-4 border-b border-gray-800 bg-[#25262B]">
          <div className="flex items-center justify-center gap-3">
            <div className="bg-indigo-500/10 p-2 rounded-lg text-indigo-400 border border-indigo-500/20">
              <Rocket className="w-5 h-5" />
            </div>
            <h1 className="text-lg font-bold text-gray-100 tracking-wide">NASA Systems Engineering</h1>
          </div>
        </header>

        {/* Messages */}
        <main className="flex-1 overflow-y-auto custom-scrollbar pt-6 pb-24 scroll-smooth">
          <AnimatePresence>
            {messages.length === 0 ? (
               <motion.div 
                 initial={{ opacity: 0, y: 20 }}
                 animate={{ opacity: 1, y: 0 }}
                 className="flex flex-col items-center justify-center h-full text-center px-4"
               >
                 <Rocket className="w-16 h-16 text-gray-700 mb-6" />
                 <h2 className="text-2xl font-bold mb-4 font-mono tracking-tight bg-gradient-to-r from-gray-200 to-gray-500 bg-clip-text text-transparent">
                   Ready to Launch
                 </h2>
                 <p className="text-gray-400 max-w-md mx-auto leading-relaxed">
                   Ask me anything about project lifecycles, V&V, TRLs, or models from the NASA Systems Engineering Handbook.
                 </p>
                 <div className="mt-10 flex gap-4 text-xs font-mono text-gray-500">
                   <div className="px-3 py-1.5 rounded-md bg-gray-800 border border-gray-700">"Explain the Vee Model"</div>
                   <div className="px-3 py-1.5 rounded-md bg-gray-800 border border-gray-700">"What are the TRLs?"</div>
                 </div>
               </motion.div>
            ) : (
               messages.map((msg, index) => (
                 <MessageBubble key={index} message={msg} />
               ))
            )}
            
            {/* Loading Indicator */}
            {isLoading && (
               <motion.div
                 initial={{ opacity: 0 }}
                 animate={{ opacity: 1 }}
                 className="w-full py-6 px-4 bg-userBubble/10 border-y border-gray-800"
               >
                 <div className="max-w-4xl mx-auto flex gap-6">
                   <div className="w-8 h-8 rounded shrink-0 bg-teal-500/20 text-teal-500 flex items-center justify-center">
                     <div className="w-4 h-4 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
                   </div>
                   <div className="flex-1 py-1 flex items-center gap-1.5">
                     <span className="w-1.5 h-1.5 rounded-full bg-teal-500/60 animate-bounce" style={{ animationDelay: '0ms' }}></span>
                     <span className="w-1.5 h-1.5 rounded-full bg-teal-500/60 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                     <span className="w-1.5 h-1.5 rounded-full bg-teal-500/60 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                   </div>
                 </div>
               </motion.div>
            )}
            <div ref={messagesEndRef} />
          </AnimatePresence>
        </main>

        {/* Input Box fixed at bottom */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-chatBg from-60% pt-10">
          <InputBox onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>

      {/* Sources Panel */}
      <SourcesPanel citations={activeCitations} onCitationClick={(item) => {
         if (item.chunk_type === 'image') {
            setSelectedImage(item);
         }
      }} />

      {/* Modal Overlay */}
      <ImageModal citation={selectedImage} onClose={() => setSelectedImage(null)} />
    </div>
  );
};

export default ChatWindow;
