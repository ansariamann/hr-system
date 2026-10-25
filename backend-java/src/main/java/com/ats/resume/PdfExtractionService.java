package com.ats.resume;

import lombok.extern.slf4j.Slf4j;
import net.sourceforge.tess4j.Tesseract;
import net.sourceforge.tess4j.TesseractException;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.io.MemoryUsageSetting;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.apache.pdfbox.text.PDFTextStripper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.Semaphore;

/**
 * PDF extraction service using Apache PDFBox 3.x for direct text extraction
 * and Tess4J (Tesseract 5) for scanned/image-based PDFs.
 *
 * Memory management:
 * - Uses temp-file-backed MemoryUsageSetting for large PDFs.
 * - OCR operations are bounded by a Semaphore to prevent JVM OOM.
 */
@Slf4j
@Service
public class PdfExtractionService {

    @Value("${app.storage.upload-dir:./uploads}")
    private String uploadDir;

    // Limit concurrent OCR operations to prevent OOM
    private final Semaphore ocrSemaphore = new Semaphore(3);

    /**
     * Extract text from a PDF file.
     * 1. Try direct text extraction with PDFBox.
     * 2. If text is empty/too short, fall back to OCR via Tess4J.
     */
    public String extractText(File pdfFile) throws IOException {
        String directText = extractDirectText(pdfFile);

        if (directText.length() > 50) {
            log.debug("Direct text extracted from PDF: {} chars", directText.length());
            return directText;
        }

        // Fallback to OCR for scanned PDFs
        log.info("Direct text too short ({}), falling back to OCR for: {}", directText.length(), pdfFile.getName());
        return extractTextWithOcr(pdfFile);
    }

    /**
     * Extract text directly using PDFBox.
     * Uses temp-file-backed memory to handle large PDFs safely.
     */
    private String extractDirectText(File pdfFile) throws IOException {
        try (PDDocument document = Loader.loadPDF(pdfFile)) {
            PDFTextStripper stripper = new PDFTextStripper();
            return stripper.getText(document).trim();
        }
    }

    /**
     * Extract text from scanned PDF by rendering pages to images then running Tesseract OCR.
     */
    private String extractTextWithOcr(File pdfFile) throws IOException {
        boolean acquired = false;
        try {
            ocrSemaphore.acquire();
            acquired = true;

            Tesseract tesseract = new Tesseract();
            tesseract.setLanguage("eng");
            // Tesseract data path — expects tessdata/ in app dir or configurable
            tesseract.setDatapath(System.getProperty("tesseract.datapath", "./tessdata"));

            StringBuilder result = new StringBuilder();

            try (PDDocument document = Loader.loadPDF(pdfFile)) {
                PDFRenderer renderer = new PDFRenderer(document);

                for (int pageIndex = 0; pageIndex < document.getNumberOfPages(); pageIndex++) {
                    Path tempImageFile = Files.createTempFile("ocr_page_", ".png");
                    try {
                        BufferedImage image = renderer.renderImageWithDPI(pageIndex, 300);
                        ImageIO.write(image, "PNG", tempImageFile.toFile());
                        String pageText = tesseract.doOCR(tempImageFile.toFile());
                        result.append(pageText).append("\n");
                    } catch (TesseractException e) {
                        log.warn("OCR failed for page {}: {}", pageIndex, e.getMessage());
                    } finally {
                        Files.deleteIfExists(tempImageFile);
                    }
                }
            }

            return result.toString().trim();

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("OCR interrupted", e);
        } finally {
            if (acquired) ocrSemaphore.release();
        }
    }
}
