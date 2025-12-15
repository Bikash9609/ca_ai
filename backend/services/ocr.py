"""
OCR Engine - RapidOCR integration with preprocessing
"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image, ImageEnhance
import logging
from pdf2image import convert_from_path
import io

# Limit CPU threads to prevent system hangs
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    RapidOCR = None

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Image preprocessing for better OCR accuracy"""
    
    @staticmethod
    def _has_cv2() -> bool:
        """Check if cv2 functions are available"""
        try:
            return hasattr(cv2, 'fastNlMeansDenoisingColored') and hasattr(cv2, 'cvtColor')
        except:
            return False
    
    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """Correct image skew/rotation"""
        if not ImagePreprocessor._has_cv2():
            return image
        
        try:
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
        except Exception as e:
            logger.debug(f"Deskew failed, returning original: {e}")
            return image
    
    @staticmethod
    def denoise(image: np.ndarray) -> np.ndarray:
        """Remove noise from image"""
        if not ImagePreprocessor._has_cv2():
            return image
        
        try:
            if len(image.shape) == 3:
                return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
            else:
                return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
        except Exception as e:
            logger.debug(f"Denoise failed, returning original: {e}")
            return image
    
    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Enhance image contrast"""
        if not ImagePreprocessor._has_cv2():
            # Use PIL for contrast enhancement
            try:
                # Convert BGR to RGB for PIL
                if len(image.shape) == 3 and image.shape[2] == 3:
                    rgb_image = image[:, :, ::-1]
                    pil_img = Image.fromarray(rgb_image)
                else:
                    pil_img = Image.fromarray(image)
                enhancer = ImageEnhance.Contrast(pil_img)
                enhanced = enhancer.enhance(1.2)
                enhanced_array = np.array(enhanced)
                # Convert RGB back to BGR
                if len(enhanced_array.shape) == 3 and enhanced_array.shape[2] == 3:
                    enhanced_array = enhanced_array[:, :, ::-1]
                return enhanced_array
            except Exception as e:
                logger.debug(f"PIL contrast enhancement failed: {e}")
                return image
        
        try:
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
        except Exception as e:
            logger.debug(f"Contrast enhancement failed, returning original: {e}")
            return image
    
    @staticmethod
    def resize_if_large(image: np.ndarray, max_width: int = 2000) -> np.ndarray:
        """Resize image if too large to prevent hangs"""
        h, w = image.shape[:2]
        if w > max_width:
            scale = max_width / w
            new_w = max_width
            new_h = int(h * scale)
            
            # Use PIL for resizing
            try:
                # Convert BGR to RGB for PIL
                if len(image.shape) == 3 and image.shape[2] == 3:
                    rgb_image = image[:, :, ::-1]
                    pil_img = Image.fromarray(rgb_image)
                else:
                    pil_img = Image.fromarray(image)
                resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                resized_array = np.array(resized)
                # Convert RGB back to BGR
                if len(resized_array.shape) == 3 and resized_array.shape[2] == 3:
                    resized_array = resized_array[:, :, ::-1]
                logger.debug(f"Resized image from {w}x{h} to {new_w}x{new_h}")
                return resized_array
            except Exception as e:
                logger.debug(f"Resize failed: {e}")
                return image
        return image
    
    @staticmethod
    def preprocess(image: np.ndarray, deskew_enabled: bool = True) -> np.ndarray:
        """Apply all preprocessing steps"""
        processed = image.copy()
        
        # Resize if too large (prevent hangs)
        processed = ImagePreprocessor.resize_if_large(processed)
        
        # Denoise first (skip if cv2 not available)
        processed = ImagePreprocessor.denoise(processed)
        
        # Enhance contrast
        processed = ImagePreprocessor.enhance_contrast(processed)
        
        # Deskew if enabled (skip if cv2 not available)
        if deskew_enabled:
            processed = ImagePreprocessor.deskew(processed)
        
        return processed


class OCREngine:
    """OCR engine using RapidOCR (ONNX-based, lightweight and fast)"""
    
    def __init__(self, use_angle_cls: bool = True, lang: str = 'en'):
        """
        Initialize OCR engine
        
        Args:
            use_angle_cls: Use angle classification (kept for compatibility, RapidOCR handles this)
            lang: Language code (en, hi, or en+hi for mixed)
        """
        if RapidOCR is None:
            raise ImportError("RapidOCR is not installed. Install with: uv pip install rapidocr-onnxruntime")
        
        # RapidOCR supports multiple languages
        # Convert lang format: 'en' -> ['en'], 'hi' -> ['hi'], 'en+hi' -> ['en', 'hi']
        lang_list = lang.split('+') if '+' in lang else [lang]
        
        self.ocr = RapidOCR()
        self.preprocessor = ImagePreprocessor()
        logger.info(f"OCR Engine initialized with RapidOCR (langs: {lang_list})")
    
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
        try:
            # Use PIL to load image, then convert to OpenCV format (BGR)
            pil_img = Image.open(str(image_path))
            # Convert RGB to BGR for OpenCV compatibility
            img_array = np.array(pil_img)
            if len(img_array.shape) == 3:
                # Convert RGB to BGR
                if img_array.shape[2] == 3:
                    img_array = img_array[:, :, ::-1]  # RGB to BGR
            return img_array
        except Exception as e:
            raise ValueError(f"Could not load image: {image_path}, error: {e}")
    
    def _process_image(self, image: np.ndarray) -> Tuple[str, float]:
        """
        Process single image and return text and confidence
        
        Returns:
            Tuple of (text, average_confidence)
        """
        # Preprocess image
        processed = self.preprocessor.preprocess(image)
        
        # Run OCR - RapidOCR accepts numpy array directly
        try:
            result, _ = self.ocr(processed)
        except Exception as e:
            logger.error(f"OCR failed during image processing: {e}", exc_info=True)
            result = None
        
        if not result:
            return "", 0.0
        
        # Extract text and confidence
        # RapidOCR format: [[bbox, text, confidence], ...]
        texts = []
        confidences = []
        
        for item in result:
            if len(item) >= 3:
                text = item[1]
                confidence = item[2]
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
                
                try:
                    result, _ = self.ocr(processed)
                except Exception as e:
                    logger.error(f"OCR failed on page {i+1} of PDF {file_path}: {e}", exc_info=True)
                    result = None
                
                if result:
                    page_texts = []
                    page_confidences = []
                    
                    for item in result:
                        if len(item) >= 3:
                            text = item[1]
                            confidence = item[2]
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
            
            try:
                result, _ = self.ocr(processed)
            except Exception as e:
                logger.error(f"OCR failed on image {file_path}: {e}", exc_info=True)
                result = None
            
            if not result:
                return {
                    "text": "",
                    "confidence": 0.0,
                    "pages": 1,
                    "file_type": "image",
                    "file_path": str(file_path)
                }
            
            texts = []
            confidences = []
            
            for item in result:
                if len(item) >= 3:
                    text = item[1]
                    confidence = item[2]
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
