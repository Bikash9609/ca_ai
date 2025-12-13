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
    'DocumentIndexer',
    'SemanticSearch',
    'FullTextSearch',
    'HybridSearch',
    'ProcessingQueue',
    'ProcessingTask',
    'ProcessingStatus',
    'ProcessingCache',
]
