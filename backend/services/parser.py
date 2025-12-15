"""
Document Parser - Excel and PDF parsing with data normalization
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging
import json

try:
    import pandas as pd
    import openpyxl
except ImportError:
    pd = None
    openpyxl = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

logger = logging.getLogger(__name__)


class ExcelParser:
    """Parse Excel files (GSTR-2B, bank statements, etc.)"""
    
    # GSTR-2B column mappings
    GSTR2B_COLUMNS = {
        'gstin': ['gstin', 'gstin of supplier', 'supplier gstin'],
        'invoice_number': ['invoice no', 'invoice number', 'inv no', 'bill no', 'bill number'],
        'invoice_date': ['invoice date', 'bill date', 'date'],
        'invoice_value': ['invoice value', 'taxable value', 'base amount', 'amount'],
        'place_of_supply': ['place of supply', 'pos', 'state code'],
        'reverse_charge': ['reverse charge', 'rcm', 'reverse charge mechanism'],
        'gst_rate': ['gst rate', 'rate', 'tax rate'],
        'igst': ['igst', 'integrated tax', 'igst amount'],
        'cgst': ['cgst', 'central tax', 'cgst amount'],
        'sgst': ['sgst', 'state tax', 'sgst amount'],
        'cess': ['cess', 'cess amount'],
        'eligibility': ['eligibility', 'itc eligibility', 'eligible'],
        'hsn': ['hsn', 'hsn code', 'hsn/sac'],
        'description': ['description', 'goods description', 'item description']
    }
    
    # Bank statement column mappings
    BANK_STATEMENT_COLUMNS = {
        'date': ['date', 'transaction date', 'value date', 'tran date'],
        'description': ['description', 'narration', 'particulars', 'transaction details'],
        'debit': ['debit', 'withdrawal', 'dr', 'debit amount'],
        'credit': ['credit', 'deposit', 'cr', 'credit amount'],
        'balance': ['balance', 'closing balance', 'running balance'],
        'cheque_number': ['cheque no', 'cheque number', 'chq no', 'chq number'],
        'reference': ['reference', 'ref no', 'reference number']
    }
    
    @staticmethod
    def normalize_column_names(df: pd.DataFrame, column_mapping: Dict[str, List[str]]) -> pd.DataFrame:
        """Normalize column names based on mapping"""
        df_normalized = df.copy()
        column_map = {}
        
        for standard_name, variations in column_mapping.items():
            for col in df.columns:
                col_lower = str(col).lower().strip()
                if col_lower in [v.lower() for v in variations]:
                    column_map[col] = standard_name
                    break
        
        df_normalized = df_normalized.rename(columns=column_map)
        return df_normalized
    
    @staticmethod
    def detect_schema(df: pd.DataFrame) -> Dict[str, Any]:
        """Detect schema type (GSTR-2B, bank statement, etc.)"""
        columns_lower = [str(col).lower() for col in df.columns]
        
        # Check for GSTR-2B
        gstr2b_score = 0
        for standard_name, variations in ExcelParser.GSTR2B_COLUMNS.items():
            if any(v.lower() in ' '.join(columns_lower) for v in variations):
                gstr2b_score += 1
        
        # Check for bank statement
        bank_score = 0
        for standard_name, variations in ExcelParser.BANK_STATEMENT_COLUMNS.items():
            if any(v.lower() in ' '.join(columns_lower) for v in variations):
                bank_score += 1
        
        if gstr2b_score >= 5:
            return {"schema_type": "gstr2b", "confidence": gstr2b_score / len(ExcelParser.GSTR2B_COLUMNS)}
        elif bank_score >= 3:
            return {"schema_type": "bank_statement", "confidence": bank_score / len(ExcelParser.BANK_STATEMENT_COLUMNS)}
        else:
            return {"schema_type": "unknown", "confidence": 0.0}
    
    @staticmethod
    def parse_gstr2b(file_path: Path, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """Parse GSTR-2B Excel file"""
        if pd is None:
            raise ImportError("pandas is required for Excel parsing")
        
        try:
            # Read Excel file
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                # Try to read first sheet
                excel_file = pd.ExcelFile(file_path)
                df = pd.read_excel(excel_file, sheet_name=excel_file.sheet_names[0])
            
            # Normalize column names
            df_normalized = ExcelParser.normalize_column_names(df, ExcelParser.GSTR2B_COLUMNS)
            
            # Convert to records
            records = df_normalized.to_dict('records')
            
            # Data type conversion and validation
            normalized_records = []
            for record in records:
                normalized = {}
                for key, value in record.items():
                    # Convert date strings
                    if 'date' in key.lower() and isinstance(value, str):
                        try:
                            normalized[key] = pd.to_datetime(value).isoformat()
                        except:
                            normalized[key] = value
                    # Convert numeric values
                    elif any(x in key.lower() for x in ['value', 'amount', 'rate', 'igst', 'cgst', 'sgst', 'cess']):
                        try:
                            normalized[key] = float(value) if pd.notna(value) else 0.0
                        except:
                            normalized[key] = value
                    else:
                        normalized[key] = value
                normalized_records.append(normalized)
            
            return {
                "schema_type": "gstr2b",
                "records": normalized_records,
                "total_records": len(normalized_records),
                "columns": list(df_normalized.columns)
            }
        except Exception as e:
            logger.error(f"Error parsing GSTR-2B: {e}")
            raise
    
    @staticmethod
    def parse_bank_statement(file_path: Path, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """Parse bank statement Excel file"""
        if pd is None:
            raise ImportError("pandas is required for Excel parsing")
        
        try:
            # Read Excel file
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                excel_file = pd.ExcelFile(file_path)
                df = pd.read_excel(excel_file, sheet_name=excel_file.sheet_names[0])
            
            # Normalize column names
            df_normalized = ExcelParser.normalize_column_names(df, ExcelParser.BANK_STATEMENT_COLUMNS)
            
            # Convert to records
            records = df_normalized.to_dict('records')
            
            # Data type conversion
            normalized_records = []
            for record in records:
                normalized = {}
                for key, value in record.items():
                    if 'date' in key.lower() and isinstance(value, str):
                        try:
                            normalized[key] = pd.to_datetime(value).isoformat()
                        except:
                            normalized[key] = value
                    elif any(x in key.lower() for x in ['debit', 'credit', 'balance']):
                        try:
                            normalized[key] = float(value) if pd.notna(value) else 0.0
                        except:
                            normalized[key] = value
                    else:
                        normalized[key] = value
                normalized_records.append(normalized)
            
            return {
                "schema_type": "bank_statement",
                "records": normalized_records,
                "total_records": len(normalized_records),
                "columns": list(df_normalized.columns)
            }
        except Exception as e:
            logger.error(f"Error parsing bank statement: {e}")
            raise
    
    @staticmethod
    def parse(file_path: Path, sheet_name: Optional[str] = None) -> Dict[str, Any]:
        """Parse Excel file with automatic schema detection"""
        if pd is None:
            raise ImportError("pandas is required for Excel parsing")
        
        try:
            # Read first sheet to detect schema
            excel_file = pd.ExcelFile(file_path)
            first_sheet = excel_file.sheet_names[0]
            df = pd.read_excel(excel_file, sheet_name=first_sheet)
            
            # Detect schema
            schema_info = ExcelParser.detect_schema(df)
            
            # Parse based on schema
            if schema_info["schema_type"] == "gstr2b":
                return ExcelParser.parse_gstr2b(file_path, sheet_name)
            elif schema_info["schema_type"] == "bank_statement":
                return ExcelParser.parse_bank_statement(file_path, sheet_name)
            else:
                # Generic parsing
                records = df.to_dict('records')
                return {
                    "schema_type": "generic",
                    "records": records,
                    "total_records": len(records),
                    "columns": list(df.columns),
                    "sheets": excel_file.sheet_names
                }
        except Exception as e:
            logger.error(f"Error parsing Excel file: {e}")
            raise


class PDFParser:
    """Parse PDF files (text extraction, table extraction, form fields)"""
    
    @staticmethod
    def extract_text(file_path: Path) -> str:
        """Extract text from PDF"""
        if pdfplumber is None:
            raise ImportError("pdfplumber is required for PDF parsing")
        
        try:
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise
    
    @staticmethod
    def extract_text_with_pages(file_path: Path) -> List[Dict[str, Any]]:
        """Extract text from PDF with page information"""
        if pdfplumber is None:
            raise ImportError("pdfplumber is required for PDF parsing")
        
        try:
            page_texts = []
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    if text:
                        page_texts.append({
                            "page": page_num,
                            "text": text,
                            "start_char": sum(len(p["text"]) + 2 for p in page_texts),  # +2 for \n\n
                            "end_char": sum(len(p["text"]) + 2 for p in page_texts) + len(text)
                        })
            return page_texts
        except Exception as e:
            logger.error(f"Error extracting text with pages from PDF: {e}")
            raise
    
    @staticmethod
    def extract_tables(file_path: Path) -> List[Dict[str, Any]]:
        """Extract tables from PDF"""
        if pdfplumber is None:
            raise ImportError("pdfplumber is required for PDF parsing")
        
        try:
            all_tables = []
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables, 1):
                        if table:
                            all_tables.append({
                                "page": page_num,
                                "table_number": table_num,
                                "data": table,
                                "rows": len(table),
                                "columns": len(table[0]) if table else 0
                            })
            return all_tables
        except Exception as e:
            logger.error(f"Error extracting tables from PDF: {e}")
            raise
    
    @staticmethod
    def extract_form_fields(file_path: Path) -> Dict[str, Any]:
        """Extract form fields from PDF (if it's a form PDF)"""
        if pdfplumber is None:
            raise ImportError("pdfplumber is required for PDF parsing")
        
        try:
            form_fields = {}
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    # Try to extract form fields (this is basic - may need PyPDF2 for full support)
                    annotations = page.annots if hasattr(page, 'annots') else []
                    if annotations:
                        for annot in annotations:
                            if hasattr(annot, 'get') and annot.get('T'):
                                field_name = annot.get('T')
                                field_value = annot.get('V', '')
                                form_fields[field_name] = field_value
            return form_fields
        except Exception as e:
            logger.debug(f"Error extracting form fields (may not be a form PDF): {e}")
            return {}
    
    @staticmethod
    def parse(file_path: Path) -> Dict[str, Any]:
        """Parse PDF file completely"""
        try:
            text = PDFParser.extract_text(file_path)
            tables = PDFParser.extract_tables(file_path)
            form_fields = PDFParser.extract_form_fields(file_path)
            page_texts = PDFParser.extract_text_with_pages(file_path)
            
            return {
                "text": text,
                "tables": tables,
                "form_fields": form_fields,
                "page_texts": page_texts,  # New: structured page data
                "total_pages": len(page_texts) if page_texts else (len(tables) if tables else 0),
                "has_text": bool(text),
                "has_tables": len(tables) > 0,
                "has_form_fields": len(form_fields) > 0
            }
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            raise


class DataNormalizer:
    """Normalize parsed data"""
    
    @staticmethod
    def standardize_column_names(columns: List[str]) -> List[str]:
        """Standardize column names"""
        standardized = []
        for col in columns:
            # Convert to lowercase
            col_lower = str(col).lower().strip()
            # Replace spaces with underscores
            col_normalized = re.sub(r'\s+', '_', col_lower)
            # Remove special characters
            col_normalized = re.sub(r'[^a-z0-9_]', '', col_normalized)
            standardized.append(col_normalized)
        return standardized
    
    @staticmethod
    def convert_data_types(record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert data types in a record"""
        normalized = {}
        for key, value in record.items():
            if value is None:
                normalized[key] = None
            elif pd and isinstance(value, float) and pd.isna(value):
                normalized[key] = None
            elif isinstance(value, str):
                # Try to convert to number if it looks like one
                if re.match(r'^-?\d+\.?\d*$', value.strip()):
                    try:
                        if '.' in value:
                            normalized[key] = float(value)
                        else:
                            normalized[key] = int(value)
                    except:
                        normalized[key] = value
                else:
                    normalized[key] = value.strip()
            elif isinstance(value, (int, float)):
                normalized[key] = value
            else:
                normalized[key] = str(value)
        return normalized
    
    @staticmethod
    def validate_record(record: Dict[str, Any], schema_type: str) -> Dict[str, Any]:
        """Validate record based on schema type"""
        errors = []
        
        if schema_type == "gstr2b":
            # Validate required fields
            required_fields = ['gstin', 'invoice_number', 'invoice_date']
            for field in required_fields:
                if field not in record or not record[field]:
                    errors.append(f"Missing required field: {field}")
            
            # Validate numeric fields
            numeric_fields = ['invoice_value', 'igst', 'cgst', 'sgst', 'cess']
            for field in numeric_fields:
                if field in record and record[field] is not None:
                    try:
                        float(record[field])
                    except (ValueError, TypeError):
                        errors.append(f"Invalid numeric value for {field}")
        
        elif schema_type == "bank_statement":
            # Validate required fields
            required_fields = ['date']
            for field in required_fields:
                if field not in record or not record[field]:
                    errors.append(f"Missing required field: {field}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


class DocumentParser:
    """Main document parser"""
    
    def __init__(self):
        self.excel_parser = ExcelParser()
        self.pdf_parser = PDFParser()
        self.normalizer = DataNormalizer()
    
    def parse(
        self,
        file_path: Path,
        file_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Parse a document file
        
        Args:
            file_path: Path to the file
            file_type: File type (xlsx, pdf, etc.) - auto-detected if not provided
        
        Returns:
            Parsed data dictionary
        """
        file_path = Path(file_path)
        
        if not file_type:
            # Detect file type from extension
            file_type = file_path.suffix.lower().lstrip('.')
        
        if file_type in ['xlsx', 'xls']:
            result = self.excel_parser.parse(file_path)
            # Normalize column names
            if 'columns' in result:
                result['columns'] = self.normalizer.standardize_column_names(result['columns'])
            # Normalize records
            if 'records' in result:
                normalized_records = []
                for record in result['records']:
                    normalized = self.normalizer.convert_data_types(record)
                    validation = self.normalizer.validate_record(normalized, result.get('schema_type', 'generic'))
                    normalized['_validation'] = validation
                    normalized_records.append(normalized)
                result['records'] = normalized_records
            return result
        
        elif file_type == 'pdf':
            return self.pdf_parser.parse(file_path)
        
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
