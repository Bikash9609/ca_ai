"""
Entity Extraction - Extract structured entities from documents
Extracts dates, amounts, PAN/GSTIN, names, invoice numbers for better retrieval
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EntityExtractor:
    """Extract entities from text for better retrieval and filtering"""
    
    # PAN pattern: 5 letters, 4 digits, 1 letter
    PAN_PATTERN = r'\b([A-Z]{5}\d{4}[A-Z])\b'
    
    # GSTIN pattern: 15 alphanumeric characters
    GSTIN_PATTERN = r'\b([0-9A-Z]{15})\b'
    
    # Date patterns (Indian format: DD-MM-YYYY, DD/MM/YYYY, etc.)
    DATE_PATTERNS = [
        r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b',  # DD-MM-YYYY or DD/MM/YYYY
        r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',    # YYYY-MM-DD or YYYY/MM/DD
        r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b',  # DD Mon YYYY
    ]
    
    # Amount patterns (currency symbols, numbers with commas)
    AMOUNT_PATTERNS = [
        r'[₹$€£]?\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d{2})?)',  # ₹1,23,456.78
        r'(\d{1,3}(?:,\d{2,3})*(?:\.\d{2})?)\s*(?:INR|USD|EUR|GBP)',  # 1,23,456.78 INR
    ]
    
    # Invoice number patterns
    INVOICE_PATTERNS = [
        r'(?:invoice|bill|inv)[\s#]*:?\s*([A-Z0-9\-/]+)',
        r'invoice[\s]*no[\.:]?\s*([A-Z0-9\-/]+)',
        r'bill[\s]*no[\.:]?\s*([A-Z0-9\-/]+)',
    ]
    
    # Name patterns (capitalized words, 2-50 chars, may contain &, spaces)
    NAME_PATTERNS = [
        r'(?:from|vendor|supplier|seller|client|customer|deductor|deductee)[\s]*:?\s*([A-Z][A-Za-z\s&]{2,50})',
        r'^([A-Z][A-Za-z\s&]{2,50})\s*(?:GSTIN|PAN|Address|Invoice|Ltd|Pvt|Inc)',
    ]
    
    def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract all entities from text
        
        Args:
            text: Input text
        
        Returns:
            Dictionary with extracted entities
        """
        entities = {
            "dates": self.extract_dates(text),
            "amounts": self.extract_amounts(text),
            "pan_numbers": self.extract_pan(text),
            "gstin_numbers": self.extract_gstin(text),
            "invoice_numbers": self.extract_invoice_numbers(text),
            "names": self.extract_names(text),
        }
        
        return entities
    
    def extract_dates(self, text: str) -> List[str]:
        """Extract dates from text"""
        dates = []
        
        for pattern in self.DATE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match.group(1)
                # Validate date
                if self._is_valid_date(date_str):
                    dates.append(date_str)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_dates = []
        for date in dates:
            if date not in seen:
                seen.add(date)
                unique_dates.append(date)
        
        return unique_dates
    
    def extract_amounts(self, text: str) -> List[float]:
        """Extract monetary amounts from text"""
        amounts = []
        
        for pattern in self.AMOUNT_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = float(amount_str)
                    if amount > 0:  # Only positive amounts
                        amounts.append(amount)
                except ValueError:
                    continue
        
        # Remove duplicates and sort
        unique_amounts = sorted(list(set(amounts)), reverse=True)
        return unique_amounts
    
    def extract_pan(self, text: str) -> List[str]:
        """Extract PAN numbers from text"""
        matches = re.finditer(self.PAN_PATTERN, text.upper())
        pan_numbers = [match.group(1) for match in matches]
        
        # Remove duplicates
        return list(dict.fromkeys(pan_numbers))
    
    def extract_gstin(self, text: str) -> List[str]:
        """Extract GSTIN numbers from text"""
        matches = re.finditer(self.GSTIN_PATTERN, text.upper())
        gstin_numbers = [match.group(1) for match in matches]
        
        # Remove duplicates
        return list(dict.fromkeys(gstin_numbers))
    
    def extract_invoice_numbers(self, text: str) -> List[str]:
        """Extract invoice numbers from text"""
        invoice_numbers = []
        
        for pattern in self.INVOICE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                inv_num = match.group(1).strip()
                if len(inv_num) > 2:  # Filter out very short matches
                    invoice_numbers.append(inv_num)
        
        # Remove duplicates
        return list(dict.fromkeys(invoice_numbers))
    
    def extract_names(self, text: str) -> List[str]:
        """Extract names (vendor, client, etc.) from text"""
        names = []
        
        for pattern in self.NAME_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                name = match.group(1).strip()
                # Filter: 3-50 chars, starts with capital, not just numbers
                if 3 <= len(name) <= 50 and name[0].isupper() and not name.replace(' ', '').replace('&', '').isdigit():
                    names.append(name)
        
        # Remove duplicates
        return list(dict.fromkeys(names))
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Validate if a string is a valid date"""
        date_formats = [
            '%d-%m-%Y', '%d/%m/%Y',
            '%Y-%m-%d', '%Y/%m/%d',
            '%d-%m-%y', '%d/%m/%y',
            '%d %b %Y', '%d %B %Y',
            '%d %b %y', '%d %B %y',
        ]
        
        for fmt in date_formats:
            try:
                datetime.strptime(date_str, fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    def extract_from_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract entities from a chunk and add to chunk metadata
        
        Args:
            chunk: Chunk dictionary with 'text' field
        
        Returns:
            Updated chunk with entities in metadata
        """
        text = chunk.get("text", "")
        if not text:
            return chunk
        
        entities = self.extract(text)
        
        # Add entities to chunk metadata
        if "metadata" not in chunk:
            chunk["metadata"] = {}
        
        if "entities" not in chunk["metadata"]:
            chunk["metadata"]["entities"] = {}
        
        chunk["metadata"]["entities"].update(entities)
        
        return chunk
    
    def extract_from_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract entities from multiple chunks
        
        Args:
            chunks: List of chunk dictionaries
        
        Returns:
            List of chunks with entities in metadata
        """
        return [self.extract_from_chunk(chunk) for chunk in chunks]
