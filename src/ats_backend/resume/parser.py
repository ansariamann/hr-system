"""Resume parsing engine with PDF text extraction and OCR capabilities."""

import time
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, Union, Tuple
import structlog

# PDF processing
import PyPDF2
from PIL import Image, ImageFilter, ImageOps
import pytesseract

from ats_backend.core.config import settings
from ats_backend.resume.models import ParsedResume, ParsingResult
from ats_backend.resume.extractor import DataExtractor

logger = structlog.get_logger(__name__)


class ResumeParser:
    """Main resume parsing engine with PDF and OCR support."""
    
    def __init__(self):
        """Initialize resume parser with configuration."""
        self.settings = settings
        self.data_extractor = DataExtractor()
        
        # Configure tesseract path if available
        if hasattr(self.settings, 'tesseract_cmd') and self.settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.settings.tesseract_cmd
        
        # Supported file formats
        self.supported_formats = {
            'application/pdf': self._parse_pdf,
            'image/png': self._parse_image,
            'image/jpeg': self._parse_image,
            'image/jpg': self._parse_image,
            'image/tiff': self._parse_image,
            'image/tif': self._parse_image
        }
        
        logger.info("Resume parser initialized")

    def _preprocess_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """Preprocess image to improve OCR quality across scanned resumes."""
        if image.mode != "L":
            image = image.convert("L")

        # Improve contrast, suppress salt-and-pepper noise, then binarize.
        image = ImageOps.autocontrast(image)
        image = image.filter(ImageFilter.MedianFilter(size=3))

        threshold = 165
        image = image.point(lambda px: 255 if px > threshold else 0, mode="1")
        image = image.convert("L")

        # Upscale for small-font resumes to improve OCR character recognition.
        width, height = image.size
        upscale_factor = 2 if max(width, height) < 2200 else 1
        if upscale_factor > 1:
            image = image.resize(
                (width * upscale_factor, height * upscale_factor),
                Image.Resampling.LANCZOS,
            )

        return image

    def _score_ocr_text(self, text: str) -> float:
        """Compute a heuristic score to select best OCR pass."""
        stripped = text.strip()
        if not stripped:
            return 0.0

        length = len(stripped)
        alpha_chars = sum(1 for ch in stripped if ch.isalpha())
        alnum_chars = sum(1 for ch in stripped if ch.isalnum())
        lines = [ln for ln in stripped.splitlines() if ln.strip()]
        avg_line_len = (sum(len(ln.strip()) for ln in lines) / len(lines)) if lines else 0

        alpha_ratio = alpha_chars / max(length, 1)
        alnum_ratio = alnum_chars / max(length, 1)
        structure_bonus = 0.2 if 15 <= avg_line_len <= 120 else 0.0

        return (length * 0.01) + (alpha_ratio * 30) + (alnum_ratio * 10) + structure_bonus

    def _run_best_effort_ocr(self, image: Image.Image) -> Tuple[str, str]:
        """Run multi-pass OCR and return best result + OCR mode used."""
        processed = self._preprocess_image_for_ocr(image)
        psm_modes = [6, 4, 3, 11]

        best_text = ""
        best_score = 0.0
        best_mode = 6

        for psm in psm_modes:
            config = f"--oem 3 --psm {psm} -c preserve_interword_spaces=1"
            text = pytesseract.image_to_string(processed, config=config)
            score = self._score_ocr_text(text)
            if score > best_score:
                best_score = score
                best_text = text
                best_mode = psm

        normalized_text = "\n".join(line.rstrip() for line in best_text.splitlines())
        return normalized_text, f"psm_{best_mode}"
    
    def parse_file(
        self,
        file_path: Union[str, Path],
        content_type: Optional[str] = None
    ) -> ParsingResult:
        """Parse resume file and extract structured data.
        
        Args:
            file_path: Path to the resume file
            content_type: MIME type of the file (optional, will be inferred)
            
        Returns:
            ParsingResult with parsed data or error information
        """
        start_time = time.time()
        file_path = Path(file_path)
        
        try:
            # Validate file exists
            if not file_path.exists():
                return ParsingResult(
                    success=False,
                    error_message=f"File not found: {file_path}",
                    processing_time=time.time() - start_time
                )
            
            # Determine content type if not provided
            if not content_type:
                content_type = self._detect_content_type(file_path)
            
            # Check if format is supported
            if content_type not in self.supported_formats:
                return ParsingResult(
                    success=False,
                    error_message=f"Unsupported file format: {content_type}",
                    processing_time=time.time() - start_time,
                    file_info={"content_type": content_type, "size": file_path.stat().st_size}
                )
            
            logger.info(
                "Starting resume parsing",
                file_path=str(file_path),
                content_type=content_type,
                file_size=file_path.stat().st_size
            )
            
            # Parse file using appropriate method
            parser_func = self.supported_formats[content_type]
            parsing_result = parser_func(file_path)
            
            if not parsing_result['text'] or not parsing_result['text'].strip():
                return ParsingResult(
                    success=False,
                    error_message="No text content extracted from file",
                    processing_time=time.time() - start_time,
                    file_info={"content_type": content_type, "size": file_path.stat().st_size}
                )
            
            # Extract structured data from raw text
            parsed_data = self.data_extractor.extract_data(parsing_result['text'])
            parsed_data['parsing_method'] = parsing_result['method']
            
            # Create parsed resume object
            parsed_resume = ParsedResume(
                raw_text=parsing_result['text'],
                **parsed_data
            )
            
            processing_time = time.time() - start_time
            
            logger.info(
                "Resume parsing completed successfully",
                file_path=str(file_path),
                processing_time=processing_time,
                parsing_method=parsing_result['method'],
                extracted_fields=list(parsed_data.keys())
            )
            
            return ParsingResult(
                success=True,
                parsed_resume=parsed_resume,
                processing_time=processing_time,
                file_info={
                    "content_type": content_type, 
                    "size": file_path.stat().st_size,
                    "parsing_method": parsing_result['method']
                }
            )
            
        except Exception as e:
            logger.error(
                "Resume parsing failed",
                file_path=str(file_path),
                error=str(e),
                processing_time=time.time() - start_time
            )
            
            return ParsingResult(
                success=False,
                error_message=f"Parsing failed: {str(e)}",
                processing_time=time.time() - start_time,
                file_info={"content_type": content_type} if content_type else {}
            )
    
    def _detect_content_type(self, file_path: Path) -> str:
        """Detect content type from file extension and content."""
        # Try mimetypes first
        content_type, _ = mimetypes.guess_type(str(file_path))
        
        if content_type:
            return content_type
        
        # Fallback based on extension
        extension = file_path.suffix.lower()
        extension_map = {
            '.pdf': 'application/pdf',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff'
        }
        
        return extension_map.get(extension, 'application/octet-stream')
    
    def _parse_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Parse PDF file with layout-aware text extraction.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dictionary with extracted text and parsing method
        """
        logger.info("Starting PDF parsing", file_path=str(file_path))
        
        try:
            # First, try direct text extraction
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_content = []
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text and page_text.strip():
                            text_content.append(page_text)
                            logger.debug(f"Extracted text from page {page_num + 1}")
                        else:
                            logger.debug(f"No text found on page {page_num + 1}, may need OCR")
                    except Exception as e:
                        logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                
                # If we got text content, return it
                if text_content:
                    full_text = '\n'.join(text_content)
                    if len(full_text.strip()) > 50:  # Reasonable amount of text
                        logger.info("PDF text extraction successful", 
                                  pages=len(text_content), 
                                  text_length=len(full_text))
                        return {
                            'text': full_text,
                            'method': 'pdf_text_extraction'
                        }
        
        except Exception as e:
            logger.warning(f"PDF text extraction failed: {e}, falling back to OCR")
        
        # If direct text extraction failed or yielded insufficient text, use OCR
        return self._parse_pdf_with_ocr(file_path)
    
    def _parse_pdf_with_ocr(self, file_path: Path) -> Dict[str, Any]:
        """Parse PDF using OCR for image-based content.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dictionary with extracted text and parsing method
        """
        logger.info("Starting PDF OCR parsing", file_path=str(file_path))
        
        try:
            # Try using pdf2image for better PDF to image conversion
            try:
                from pdf2image import convert_from_path
                
                # Convert PDF pages to images
                images = convert_from_path(str(file_path))
                text_content = []
                
                for i, image in enumerate(images):
                    try:
                        ocr_text, ocr_mode = self._run_best_effort_ocr(image)
                        
                        if ocr_text and ocr_text.strip():
                            text_content.append(ocr_text)
                            logger.debug("OCR extracted text from page", page=i + 1, mode=ocr_mode)
                    
                    except Exception as page_e:
                        logger.debug(f"Failed to OCR page {i + 1}: {page_e}")
                
                if text_content:
                    full_text = '\n'.join(text_content)
                    logger.info("PDF OCR extraction successful", 
                              pages_processed=len(text_content), 
                              text_length=len(full_text))
                    return {
                        'text': full_text,
                        'method': 'pdf_ocr_extraction'
                    }
            
            except ImportError:
                logger.warning("pdf2image not available, using fallback OCR method")
                return self._fallback_pdf_ocr(file_path)
            
            # If no text extracted, try fallback
            return self._fallback_pdf_ocr(file_path)
        
        except Exception as e:
            logger.error(f"PDF OCR parsing failed: {e}")
            return {
                'text': '',
                'method': 'pdf_ocr_failed'
            }
    
    def _fallback_pdf_ocr(self, file_path: Path) -> Dict[str, Any]:
        """Fallback OCR method for PDFs that can't be processed normally."""
        logger.info("Using fallback PDF OCR method", file_path=str(file_path))
        
        try:
            # Try to extract text using PyPDF2 with more aggressive settings
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_content = []
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        # Try different extraction methods
                        page_text = page.extract_text()
                        if page_text and page_text.strip():
                            text_content.append(page_text)
                        else:
                            # Try extracting with different parameters
                            try:
                                # Alternative extraction method
                                page_text = ""
                                if hasattr(page, 'extractText'):
                                    page_text = page.extractText()
                                if page_text and page_text.strip():
                                    text_content.append(page_text)
                            except:
                                pass
                    except Exception as e:
                        logger.debug(f"Failed to extract from page {page_num + 1}: {e}")
                
                if text_content:
                    full_text = '\n'.join(text_content)
                    logger.info("Fallback PDF extraction successful", 
                              pages_processed=len(text_content), 
                              text_length=len(full_text))
                    return {
                        'text': full_text,
                        'method': 'pdf_fallback_extraction'
                    }
            
            # If still no text, return empty
            logger.warning("No text could be extracted from PDF")
            return {
                'text': '',
                'method': 'pdf_extraction_failed'
            }
        
        except Exception as e:
            logger.error(f"Fallback PDF extraction failed: {e}")
            return {
                'text': '',
                'method': 'pdf_extraction_failed'
            }
    
    def _parse_image(self, file_path: Path) -> Dict[str, Any]:
        """Parse image file using OCR.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Dictionary with extracted text and parsing method
        """
        logger.info("Starting image OCR parsing", file_path=str(file_path))
        
        try:
            # Open and preprocess image
            image = Image.open(file_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            ocr_text, ocr_mode = self._run_best_effort_ocr(image)
            
            if ocr_text and ocr_text.strip():
                logger.info("Image OCR extraction successful", 
                          text_length=len(ocr_text),
                          image_size=image.size,
                          ocr_mode=ocr_mode)
                return {
                    'text': ocr_text,
                    'method': f'image_ocr_extraction_{ocr_mode}'
                }
            else:
                logger.warning("No text extracted from image")
                return {
                    'text': '',
                    'method': 'image_ocr_no_text'
                }
        
        except Exception as e:
            logger.error(f"Image OCR parsing failed: {e}")
            return {
                'text': '',
                'method': 'image_ocr_failed'
            }
      
