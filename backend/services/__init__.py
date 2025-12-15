"""Services module for OCR, indexing, etc."""

from .ocr import OCREngine, ImagePreprocessor
from .classification import (
    FileTypeDetector,
    DocumentTypeClassifier,
    CategoryClassifier,
    DocumentClassifier
)
from .parser import (
    ExcelParser,
    PDFParser,
    DataNormalizer,
    DocumentParser
)
from .embedding import EmbeddingGenerator, EmbeddingCache
from .chunking import TextChunker, DocumentChunker
from .indexing import VectorStorage, DocumentIndexer
from .entity_extraction import EntityExtractor
from .context_packer import ContextPacker
from .qa_tracking import QATracker
from .conversation import ConversationContext, ConversationManager, get_conversation_manager
from .cache import Cache, EmbeddingCache, ContextCache, ResponseCache, get_cache, get_embedding_cache, get_context_cache, get_response_cache
from .search import MultiPassRetriever
from .search import SemanticSearch, FullTextSearch, HybridSearch
from .queue import ProcessingQueue, ProcessingTask, ProcessingStatus, ProcessingCache

__all__ = [
    'OCREngine',
    'ImagePreprocessor',
    'FileTypeDetector',
    'DocumentTypeClassifier',
    'CategoryClassifier',
    'DocumentClassifier',
    'ExcelParser',
    'PDFParser',
    'DataNormalizer',
    'DocumentParser',
    'EmbeddingGenerator',
    'EmbeddingCache',
    'TextChunker',
    'DocumentChunker',
    'VectorStorage',
    'EntityExtractor',
    'ContextPacker',
    'QATracker',
    'ConversationContext',
    'ConversationManager',
    'get_conversation_manager',
    'Cache',
    'EmbeddingCache',
    'ContextCache',
    'ResponseCache',
    'get_cache',
    'get_embedding_cache',
    'get_context_cache',
    'get_response_cache',
    'MultiPassRetriever',
    'DocumentIndexer',
    'SemanticSearch',
    'FullTextSearch',
    'HybridSearch',
    'ProcessingQueue',
    'ProcessingTask',
    'ProcessingStatus',
    'ProcessingCache',
]
