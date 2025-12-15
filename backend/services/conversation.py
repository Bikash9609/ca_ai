"""
Conversation Memory - Efficient conversation context management
Reuses vector matches from previous questions, adds only new deltas
"""

from typing import List, Dict, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)


class ConversationContext:
    """Manages conversation context for efficient follow-up questions"""
    
    def __init__(self, client_id: str):
        """
        Initialize conversation context
        
        Args:
            client_id: Client ID
        """
        self.client_id = client_id
        self.previous_questions: List[str] = []
        self.previous_context_chunk_ids: Set[str] = set()
        self.previous_context_bundles: List[List[Dict[str, Any]]] = []
        self.user_corrections: List[Dict[str, Any]] = []
        self.conversation_turn = 0
    
    def add_question(
        self,
        question: str,
        context_chunks: List[Dict[str, Any]],
        answer: Optional[str] = None
    ) -> None:
        """
        Add a question and its context to conversation history
        
        Args:
            question: User question
            context_chunks: Context chunks used for this question
            answer: LLM answer (optional)
        """
        self.conversation_turn += 1
        self.previous_questions.append(question)
        
        # Track chunk IDs used
        chunk_ids = {chunk.get("chunk_id") for chunk in context_chunks if chunk.get("chunk_id")}
        self.previous_context_chunk_ids.update(chunk_ids)
        
        # Store context bundle
        self.previous_context_bundles.append(context_chunks.copy())
        
        # Keep only last 5 turns to prevent memory bloat
        if len(self.previous_questions) > 5:
            self.previous_questions = self.previous_questions[-5:]
            self.previous_context_bundles = self.previous_context_bundles[-5:]
    
    def add_correction(self, correction: Dict[str, Any]) -> None:
        """Add user correction to conversation"""
        self.user_corrections.append(correction)
    
    def get_reusable_chunk_ids(self) -> Set[str]:
        """Get chunk IDs that can be reused from previous context"""
        return self.previous_context_chunk_ids.copy()
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get summary of conversation for context"""
        return {
            "turn": self.conversation_turn,
            "previous_questions_count": len(self.previous_questions),
            "reusable_chunks_count": len(self.previous_context_chunk_ids),
            "corrections_count": len(self.user_corrections),
            "last_question": self.previous_questions[-1] if self.previous_questions else None
        }
    
    def clear(self) -> None:
        """Clear conversation history"""
        self.previous_questions = []
        self.previous_context_chunk_ids = set()
        self.previous_context_bundles = []
        self.user_corrections = []
        self.conversation_turn = 0


class ConversationManager:
    """Manages conversation contexts for multiple clients"""
    
    def __init__(self):
        """Initialize conversation manager"""
        self.contexts: Dict[str, ConversationContext] = {}
    
    def get_context(self, client_id: str) -> ConversationContext:
        """Get or create conversation context for a client"""
        if client_id not in self.contexts:
            self.contexts[client_id] = ConversationContext(client_id)
        return self.contexts[client_id]
    
    def clear_context(self, client_id: str) -> None:
        """Clear conversation context for a client"""
        if client_id in self.contexts:
            self.contexts[client_id].clear()
    
    def optimize_context_retrieval(
        self,
        client_id: str,
        new_chunks: List[Dict[str, Any]],
        max_chunks: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Optimize context retrieval by reusing previous chunks and adding new deltas
        
        Args:
            client_id: Client ID
            new_chunks: New chunks from current retrieval
            max_chunks: Maximum chunks to return
        
        Returns:
            Optimized context bundle
        """
        context = self.get_context(client_id)
        reusable_chunk_ids = context.get_reusable_chunk_ids()
        
        # Separate new chunks from reusable ones
        new_chunk_ids = {chunk.get("chunk_id") for chunk in new_chunks if chunk.get("chunk_id")}
        
        # Find chunks that are both new and reusable (high priority)
        high_priority_chunks = [
            chunk for chunk in new_chunks
            if chunk.get("chunk_id") in reusable_chunk_ids
        ]
        
        # Find completely new chunks
        completely_new_chunks = [
            chunk for chunk in new_chunks
            if chunk.get("chunk_id") not in reusable_chunk_ids
        ]
        
        # Combine: high priority first, then new chunks
        optimized = high_priority_chunks + completely_new_chunks
        
        # Limit to max_chunks
        return optimized[:max_chunks]
    
    def build_conversation_context_prompt(
        self,
        client_id: str,
        current_question: str,
        current_context: List[Dict[str, Any]]
    ) -> str:
        """
        Build conversation context prompt without re-sending entire history
        
        Args:
            client_id: Client ID
            current_question: Current user question
            current_context: Current context chunks
        
        Returns:
            Formatted conversation context
        """
        context = self.get_context(client_id)
        
        # Build context summary
        summary = context.get_conversation_summary()
        
        # Build prompt parts
        parts = []
        
        # Add conversation context if this is a follow-up
        if summary["turn"] > 1:
            parts.append(f"CONVERSATION CONTEXT:")
            parts.append(f"This is turn {summary['turn']} in the conversation.")
            
            if summary["last_question"]:
                parts.append(f"Previous question: {summary['last_question']}")
            
            if context.user_corrections:
                parts.append("USER CORRECTIONS:")
                for correction in context.user_corrections[-3:]:  # Last 3 corrections
                    parts.append(f"- {correction.get('text', '')}")
        
        # Add current context
        parts.append("\nCURRENT CONTEXT:")
        for i, chunk in enumerate(current_context[:10], 1):  # Limit to 10 chunks
            chunk_text = chunk.get("text", "")[:300]  # Truncate long chunks
            parts.append(f"[Chunk {i}]\n{chunk_text}")
        
        # Add current question
        parts.append(f"\nCURRENT QUESTION:\n{current_question}")
        
        return "\n".join(parts)


# Global conversation manager instance
_conversation_manager = ConversationManager()


def get_conversation_manager() -> ConversationManager:
    """Get global conversation manager instance"""
    return _conversation_manager
