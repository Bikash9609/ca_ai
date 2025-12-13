"""
Document Classification - File type, document type, and category classification
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import mimetypes

logger = logging.getLogger(__name__)


class FileTypeDetector:
    """Detect file type using magic bytes, extension, and content"""
    
    # Magic bytes for common file types
    MAGIC_BYTES = {
        b'\x25\x50\x44\x46': 'pdf',  # PDF
        b'\x50\x4B\x03\x04': 'zip',  # ZIP/Excel/Word
        b'\x50\x4B\x05\x06': 'zip',  # ZIP (empty)
        b'\x50\x4B\x07\x08': 'zip',  # ZIP (spanned)
        b'\x89\x50\x4E\x47': 'png',  # PNG
        b'\xFF\xD8\xFF': 'jpg',      # JPEG
        b'\x47\x49\x46\x38': 'gif',  # GIF
        b'\x42\x4D': 'bmp',           # BMP
    }
    
    @staticmethod
    def detect_by_magic_bytes(file_path: Path) -> Optional[str]:
        """Detect file type by reading magic bytes"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                for magic, file_type in FileTypeDetector.MAGIC_BYTES.items():
                    if header.startswith(magic):
                        return file_type
        except Exception as e:
            logger.debug(f"Error reading magic bytes: {e}")
        return None
    
    @staticmethod
    def detect_by_extension(file_path: Path) -> Optional[str]:
        """Detect file type by extension"""
        ext = file_path.suffix.lower().lstrip('.')
        if ext:
            return ext
        return None
    
    @staticmethod
    def detect_by_mimetype(file_path: Path) -> Optional[str]:
        """Detect file type using mimetypes"""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type:
            # Extract extension from mime type
            if 'pdf' in mime_type:
                return 'pdf'
            elif 'excel' in mime_type or 'spreadsheet' in mime_type:
                return 'xlsx'
            elif 'image' in mime_type:
                return mime_type.split('/')[1]
        return None
    
    @staticmethod
    def detect(file_path: Path) -> Dict[str, Any]:
        """
        Detect file type using multiple methods
        
        Returns:
            Dictionary with file_type and detection_method
        """
        # Try magic bytes first (most reliable)
        file_type = FileTypeDetector.detect_by_magic_bytes(file_path)
        method = 'magic_bytes'
        
        # Fallback to extension
        if not file_type:
            file_type = FileTypeDetector.detect_by_extension(file_path)
            method = 'extension'
        
        # Fallback to mimetype
        if not file_type:
            file_type = FileTypeDetector.detect_by_mimetype(file_path)
            method = 'mimetype'
        
        return {
            "file_type": file_type or "unknown",
            "detection_method": method,
            "extension": file_path.suffix.lower().lstrip('.')
        }


class DocumentTypeClassifier:
    """Classify document type (invoice, statement, notice, certificate)"""
    
    # Keywords for different document types
    INVOICE_KEYWORDS = [
        'invoice', 'bill', 'tax invoice', 'gst invoice', 'bill of supply',
        'invoice no', 'invoice number', 'inv no', 'bill no', 'bill number',
        'gstin', 'hsn', 'sac', 'cgst', 'sgst', 'igst', 'taxable value',
        'total amount', 'amount payable', 'invoice date', 'due date'
    ]
    
    STATEMENT_KEYWORDS = [
        'statement', 'account statement', 'bank statement', 'ledger',
        'transaction', 'balance', 'credit', 'debit', 'opening balance',
        'closing balance', 'statement period', 'statement date'
    ]
    
    NOTICE_KEYWORDS = [
        'notice', 'show cause', 'demand', 'assessment', 'order',
        'gst notice', 'tax notice', 'compliance', 'penalty', 'fine',
        'hearing', 'appeal', 'rectification'
    ]
    
    CERTIFICATE_KEYWORDS = [
        'certificate', 'registration', 'gst certificate', 'gst registration',
        'certificate of registration', 'registration certificate',
        'gstin certificate', 'registration number'
    ]
    
    @staticmethod
    def classify(text: str, file_name: str = "") -> Dict[str, Any]:
        """
        Classify document type based on text content and filename
        
        Returns:
            Dictionary with doc_type and confidence
        """
        text_lower = text.lower()
        filename_lower = file_name.lower()
        combined = f"{text_lower} {filename_lower}"
        
        scores = {
            'invoice': 0,
            'statement': 0,
            'notice': 0,
            'certificate': 0,
            'other': 0
        }
        
        # Check for invoice keywords
        for keyword in DocumentTypeClassifier.INVOICE_KEYWORDS:
            if keyword in combined:
                scores['invoice'] += 1
        
        # Check for statement keywords
        for keyword in DocumentTypeClassifier.STATEMENT_KEYWORDS:
            if keyword in combined:
                scores['statement'] += 1
        
        # Check for notice keywords
        for keyword in DocumentTypeClassifier.NOTICE_KEYWORDS:
            if keyword in combined:
                scores['notice'] += 1
        
        # Check for certificate keywords
        for keyword in DocumentTypeClassifier.CERTIFICATE_KEYWORDS:
            if keyword in combined:
                scores['certificate'] += 1
        
        # Determine document type
        max_score = max(scores.values())
        if max_score == 0:
            doc_type = 'other'
            confidence = 0.0
        else:
            doc_type = max(scores, key=scores.get)
            total_keywords = sum(scores.values())
            confidence = max_score / total_keywords if total_keywords > 0 else 0.0
        
        return {
            "doc_type": doc_type,
            "confidence": confidence,
            "scores": scores
        }


class CategoryClassifier:
    """Classify document category (GST vs IT, Sales vs Purchase, Period)"""
    
    GST_KEYWORDS = [
        'gst', 'gstin', 'cgst', 'sgst', 'igst', 'gstr', 'gstr-1', 'gstr-2',
        'gstr-2b', 'gstr-3b', 'gstr-9', 'gst return', 'gst filing',
        'input tax credit', 'itc', 'output tax', 'tax invoice',
        'bill of supply', 'hsn', 'sac', 'gst rate'
    ]
    
    IT_KEYWORDS = [
        'income tax', 'itr', 'it return', 'tds', 'tds certificate',
        'form 16', 'form 16a', 'form 26as', 'pan', 'assessment year',
        'financial year', 'ay ', 'fy ', 'income tax act'
    ]
    
    SALES_KEYWORDS = [
        'sales', 'sale', 'outward supply', 'output', 'b2b', 'b2c',
        'export', 'interstate', 'intrastate', 'cgst', 'sgst', 'igst',
        'tax invoice', 'bill of supply'
    ]
    
    PURCHASE_KEYWORDS = [
        'purchase', 'inward supply', 'input', 'vendor', 'supplier',
        'gstr-2b', 'input tax credit', 'itc', 'purchase invoice',
        'bill', 'receipt'
    ]
    
    @staticmethod
    def extract_period(text: str) -> Optional[Dict[str, Any]]:
        """
        Extract period (month/year) from text
        
        Returns:
            Dictionary with period, month, year, or None
        """
        # Pattern for month-year (e.g., "April 2024", "04-2024", "2024-04")
        patterns = [
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})',
            r'(\d{1,2})[/-](\d{4})',
            r'(\d{4})[/-](\d{1,2})',
            r'fy\s*(\d{4})[/-](\d{4})',
            r'ay\s*(\d{4})[/-](\d{4})',
        ]
        
        text_lower = text.lower()
        
        for pattern in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Handle month name
                month_names = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                
                if groups[0].lower() in month_names:
                    month = month_names[groups[0].lower()]
                    year = int(groups[1])
                    return {
                        "period": f"{year}-{month:02d}",
                        "month": month,
                        "year": year,
                        "format": "month-year"
                    }
                else:
                    # Try to parse as numbers
                    try:
                        num1 = int(groups[0])
                        num2 = int(groups[1])
                        
                        # Determine which is month and which is year
                        if 1 <= num1 <= 12 and 2000 <= num2 <= 2100:
                            return {
                                "period": f"{num2}-{num1:02d}",
                                "month": num1,
                                "year": num2,
                                "format": "month-year"
                            }
                        elif 1 <= num2 <= 12 and 2000 <= num1 <= 2100:
                            return {
                                "period": f"{num1}-{num2:02d}",
                                "month": num2,
                                "year": num1,
                                "format": "year-month"
                            }
                    except ValueError:
                        continue
        
        return None
    
    @staticmethod
    def classify(text: str) -> Dict[str, Any]:
        """
        Classify document category
        
        Returns:
            Dictionary with category, subcategory, and period
        """
        text_lower = text.lower()
        
        # Check GST vs IT
        gst_score = sum(1 for keyword in CategoryClassifier.GST_KEYWORDS if keyword in text_lower)
        it_score = sum(1 for keyword in CategoryClassifier.IT_KEYWORDS if keyword in text_lower)
        
        if gst_score > it_score:
            category = 'gst'
            category_confidence = gst_score / (gst_score + it_score + 1)
        elif it_score > gst_score:
            category = 'it'
            category_confidence = it_score / (gst_score + it_score + 1)
        else:
            category = 'general'
            category_confidence = 0.5
        
        # Check Sales vs Purchase (only for GST documents)
        subcategory = None
        subcategory_confidence = 0.0
        
        if category == 'gst':
            sales_score = sum(1 for keyword in CategoryClassifier.SALES_KEYWORDS if keyword in text_lower)
            purchase_score = sum(1 for keyword in CategoryClassifier.PURCHASE_KEYWORDS if keyword in text_lower)
            
            if sales_score > purchase_score:
                subcategory = 'sales'
                subcategory_confidence = sales_score / (sales_score + purchase_score + 1)
            elif purchase_score > sales_score:
                subcategory = 'purchase'
                subcategory_confidence = purchase_score / (sales_score + purchase_score + 1)
        
        # Extract period
        period_info = CategoryClassifier.extract_period(text)
        
        return {
            "category": category,
            "category_confidence": category_confidence,
            "subcategory": subcategory,
            "subcategory_confidence": subcategory_confidence,
            "period": period_info
        }


class DocumentClassifier:
    """Main document classifier combining all classification steps"""
    
    def __init__(self):
        self.file_detector = FileTypeDetector()
        self.doc_type_classifier = DocumentTypeClassifier()
        self.category_classifier = CategoryClassifier()
    
    def classify(
        self,
        file_path: Path,
        text: Optional[str] = None,
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classify a document completely
        
        Args:
            file_path: Path to the file
            text: Extracted text (optional, will be empty if not provided)
            file_name: File name (optional, will use file_path.name if not provided)
        
        Returns:
            Complete classification result
        """
        file_path = Path(file_path)
        file_name = file_name or file_path.name
        
        # File type detection
        file_type_info = self.file_detector.detect(file_path)
        
        # Document type classification (requires text)
        doc_type_info = {"doc_type": "unknown", "confidence": 0.0}
        if text:
            doc_type_info = self.doc_type_classifier.classify(text, file_name)
        
        # Category classification (requires text)
        category_info = {
            "category": "general",
            "category_confidence": 0.0,
            "subcategory": None,
            "subcategory_confidence": 0.0,
            "period": None
        }
        if text:
            category_info = self.category_classifier.classify(text)
        
        return {
            "file_type": file_type_info,
            "doc_type": doc_type_info,
            "category": category_info,
            "file_name": file_name,
            "file_path": str(file_path)
        }
