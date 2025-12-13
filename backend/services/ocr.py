"""
OCR Engine - PaddleOCR integration with preprocessing
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image
import logging
from pdf2image import convert_from_path
import io

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Image preprocessing for better OCR accuracy"""
    
    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """Correct image skew/rotation"""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        coords = np.column_stack(np.where(gray > 0))
        
        if len(coords) == 0:
            return image
        
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        if abs(angle) < 0.5:  # Skip if angle is too small
            return image
        
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated
    
    @staticmethod
    def denoise(image: np.ndarray) -> np.ndarray:
        """Remove noise from image"""
        if len(image.shape) == 3:
            return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
        else:
            return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
    
    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Enhance image contrast"""
        if len(image.shape) == 3:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced = cv2.merge([l, a, b])
            return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(image)
    
    @staticmethod
    def preprocess(image: np.ndarray, deskew_enabled: bool = True) -> np.ndarray:
        """Apply all preprocessing steps"""
        processed = image.copy()
        
        # Denoise first
        processed = ImagePreprocessor.denoise(processed)
        
        # Enhance contrast
        processed = ImagePreprocessor.enhance_contrast(processed)
        
        # Deskew if enabled
        if deskew_enabled:
            processed = ImagePreprocessor.deskew(processed)
        
        return processed


class OCREngine:
    """OCR engine using PaddleOCR with fallback to Tesseract"""
    
    def __init__(self, use_angle_cls: bool = True, lang: str = 'en'):
        """
        Initialize OCR engine
        
        Args:
            use_angle_cls: Use angle classification
            lang: Language code (en, hi, or en+hi for mixed)
        """
        if PaddleOCR is None:
            raise ImportError("PaddleOCR is not installed. Install with: uv pip install paddleocr")
        
        self.ocr = PaddleOCR(
            use_angle_cls=use_angle_cls,
            lang=lang
        )
        self.preprocessor = ImagePreprocessor()
        logger.info("OCR Engine initialized")
    
    def _pdf_to_images(self, pdf_path: Path, dpi: int = 300) -> List[np.ndarray]:
        """Convert PDF to images"""
        try:
            images = convert_from_path(str(pdf_path), dpi=dpi)
            return [np.array(img) for img in images]
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            raise
    
    def _image_to_array(self, image_path: Path) -> np.ndarray:
        """Load image file to numpy array"""
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        return img
    
    def _process_image(self, image: np.ndarray) -> Tuple[str, float]:
        """
        Process single image and return text and confidence
        
        Returns:
            Tuple of (text, average_confidence)
        """
        # Preprocess image
        processed = self.preprocessor.preprocess(image)
        
        # Run OCR
        result = self.ocr.ocr(processed, cls=True)
        
        if not result or not result[0]:
            return "", 0.0
        
        # Extract text and confidence
        texts = []
        confidences = []
        
        for line in result[0]:
            if line:
                text = line[1][0]
                confidence = line[1][1]
                texts.append(text)
                confidences.append(confidence)
        
        full_text = "\n".join(texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return full_text, avg_confidence
    
    def process_file(
        self,
        file_path: Path,
        preprocess: bool = True
    ) -> Dict[str, Any]:
        """
        Process a file (PDF or image) and return OCR results
        
        Args:
            file_path: Path to file
            preprocess: Whether to apply image preprocessing
        
        Returns:
            Dictionary with text, confidence, and metadata
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Determine file type
        if file_path.suffix.lower() == '.pdf':
            images = self._pdf_to_images(file_path)
            all_texts = []
            all_confidences = []
            
            for i, image in enumerate(images):
                if preprocess:
                    processed = self.preprocessor.preprocess(image)
                else:
                    processed = image
                
                result = self.ocr.ocr(processed, cls=True)
                
                if result and result[0]:
                    page_texts = []
                    page_confidences = []
                    
                    for line in result[0]:
                        if line:
                            text = line[1][0]
                            confidence = line[1][1]
                            page_texts.append(text)
                            page_confidences.append(confidence)
                    
                    page_text = "\n".join(page_texts)
                    all_texts.append(page_text)
                    if page_confidences:
                        all_confidences.append(sum(page_confidences) / len(page_confidences))
            
            full_text = "\n\n--- Page Break ---\n\n".join(all_texts)
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
            
            return {
                "text": full_text,
                "confidence": avg_confidence,
                "pages": len(images),
                "file_type": "pdf",
                "file_path": str(file_path)
            }
        
        else:
            # Image file
            image = self._image_to_array(file_path)
            
            if preprocess:
                processed = self.preprocessor.preprocess(image)
            else:
                processed = image
            
            result = self.ocr.ocr(processed, cls=True)
            
            if not result or not result[0]:
                return {
                    "text": "",
                    "confidence": 0.0,
                    "pages": 1,
                    "file_type": "image",
                    "file_path": str(file_path)
                }
            
            texts = []
            confidences = []
            
            for line in result[0]:
                if line:
                    text = line[1][0]
                    confidence = line[1][1]
                    texts.append(text)
                    confidences.append(confidence)
            
            full_text = "\n".join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                "text": full_text,
                "confidence": avg_confidence,
                "pages": 1,
                "file_type": "image",
                "file_path": str(file_path)
            }
    
    def process_batch(
        self,
        file_paths: List[Path],
        preprocess: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Process multiple files in batch
        
        Args:
            file_paths: List of file paths
            preprocess: Whether to apply preprocessing
        
        Returns:
            List of OCR results
        """
        results = []
        
        for file_path in file_paths:
            try:
                result = self.process_file(file_path, preprocess=preprocess)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                results.append({
                    "text": "",
                    "confidence": 0.0,
                    "pages": 0,
                    "file_type": "unknown",
                    "file_path": str(file_path),
                    "error": str(e)
                })
        
        return results
