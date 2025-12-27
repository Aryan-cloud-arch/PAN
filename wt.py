# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 ULTIMATE PDF MASTER BOT - GOOGLE COLAB VERSION (COMPLETE)
# ═══════════════════════════════════════════════════════════════════════════════
# Features:
# ✅ Advanced Watermark Detection & Removal (shows what will be removed)
# ✅ Add Text/Image/Telegram Logo Watermarks
# ✅ Add/Remove Pages
# ✅ Add Branding (Header, Footer, Logo)
# ✅ Merge, Split, Compress, Rotate PDFs
# ✅ OCR-based watermark detection
# ═══════════════════════════════════════════════════════════════════════════════

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                           INSTALLATION                                        ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

print("📦 Installing required packages...")
import subprocess
import sys

packages = [
    "python-telegram-bot==20.7",
    "PyMuPDF==1.23.7",
    "Pillow==10.1.0",
    "opencv-python-headless==4.8.1.78",
    "numpy==1.24.3",
    "nest_asyncio",
    "reportlab",
    "aiohttp"
]

for package in packages:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])

# Install system dependencies
subprocess.run(["apt-get", "update", "-qq"], capture_output=True)
subprocess.run(["apt-get", "install", "-y", "-qq", "tesseract-ocr", "poppler-utils"], capture_output=True)

print("✅ All packages installed successfully!")

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                              IMPORTS                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

import os
import io
import re
import json
import fitz  # PyMuPDF
import asyncio
import nest_asyncio
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
from telegram.constants import ParseMode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import Color
import tempfile
import shutil
from datetime import datetime
import traceback
from collections import defaultdict

nest_asyncio.apply()

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                         CONFIGURATION                                         ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

# 🔑 PUT YOUR BOT TOKEN HERE
BOT_TOKEN = "8353748222:AAFHmXmCaVr4M2jO-MhvRe8mkHokqoLDbMQ"  # Get from @BotFather

# Storage for user sessions
user_sessions = {}

# Watermark detection patterns
WATERMARK_PATTERNS = [
    # URLs and domains
    r'@\w+', r't\.me/\w+', r'telegram\.me/\w+',
    r'https?://[^\s]+', r'www\.[^\s]+',
    r'\w+\.(com|org|net|ir|io|me|co|info|biz|ru|uk)',
    # Common watermark texts
    r'watermark', r'sample', r'draft', r'confidential', 
    r'copy', r'preview', r'demo', r'trial',
    r'©.*', r'copyright', r'all rights reserved',
    # Channel/Group names
    r'@[a-zA-Z0-9_]+', r'join.*channel', r'subscribe',
    # PDF tools watermarks
    r'pdf.*editor', r'created.*with', r'powered.*by',
    r'ilovepdf', r'smallpdf', r'pdf2go', r'sodapdf'
]

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                      TELEGRAM LOGO CREATOR                                    ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

def create_telegram_logo(size=200, opacity=180):
    """Create a high-quality Telegram logo with paper plane"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Main circle (Telegram blue)
    padding = size // 20
    draw.ellipse(
        [padding, padding, size - padding, size - padding], 
        fill=(0, 136, 204, opacity)
    )
    
    # Paper plane design - more accurate
    center_x, center_y = size // 2, size // 2
    scale = size / 200
    
    # Main body of paper plane (white)
    plane_points = [
        (int(center_x - 55*scale), int(center_y + 5*scale)),   # Left tip
        (int(center_x + 65*scale), int(center_y - 35*scale)),  # Top right
        (int(center_x + 5*scale), int(center_y + 45*scale))    # Bottom
    ]
    draw.polygon(plane_points, fill=(255, 255, 255, 255))
    
    # Shadow/fold part of plane
    shadow_points = [
        (int(center_x - 5*scale), int(center_y + 10*scale)),
        (int(center_x + 65*scale), int(center_y - 35*scale)),
        (int(center_x + 5*scale), int(center_y + 45*scale)),
        (int(center_x - 10*scale), int(center_y + 25*scale))
    ]
    draw.polygon(shadow_points, fill=(200, 225, 240, 255))
    
    # Inner fold accent
    fold_points = [
        (int(center_x - 25*scale), int(center_y + 20*scale)),
        (int(center_x + 5*scale), int(center_y + 45*scale)),
        (int(center_x - 5*scale), int(center_y + 25*scale))
    ]
    draw.polygon(fold_points, fill=(170, 200, 220, 255))
    
    return img

def create_watermark_image(text, size=(500, 120), opacity=128):
    """Create a text watermark image with styling"""
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Try to use a nice font, fallback to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 42)
        except:
            font = ImageFont.load_default()
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2
    
    # Draw text shadow
    draw.text((x+2, y+2), text, font=font, fill=(100, 100, 100, opacity//2))
    
    # Draw main text
    draw.text((x, y), text, font=font, fill=(128, 128, 128, opacity))
    
    return img

def create_combined_telegram_watermark(channel_name="", size=300, opacity=200):
    """Create Telegram logo with channel name below"""
    logo_size = int(size * 0.6)
    logo = create_telegram_logo(logo_size, opacity)
    
    # Create larger canvas for logo + text
    total_height = size if not channel_name else int(size * 1.3)
    img = Image.new('RGBA', (size, total_height), (0, 0, 0, 0))
    
    # Paste logo centered horizontally
    logo_x = (size - logo_size) // 2
    img.paste(logo, (logo_x, 0), logo)
    
    if channel_name:
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), channel_name, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (size - text_width) // 2
        text_y = logo_size + 10
        
        # Draw channel name
        draw.text((text_x, text_y), channel_name, font=font, fill=(0, 136, 204, opacity))
    
    return img

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                       PDF PROCESSOR CLASS                                     ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

class PDFProcessor:
    """Advanced PDF processing class with all features"""
    
    @staticmethod
    def detect_watermarks(pdf_path):
        """
        Advanced watermark detection - returns detailed info about what will be removed
        """
        doc = fitz.open(pdf_path)
        watermarks = {
            'text_watermarks': [],
            'image_watermarks': [],
            'link_watermarks': [],
            'overlay_watermarks': [],
            'summary': {}
        }
        
        total_text_wm = 0
        total_image_wm = 0
        total_link_wm = 0
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_rect = page.rect
            
            # ═══════════════ TEXT WATERMARK DETECTION ═══════════════
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            font_size = span.get("size", 12)
                            flags = span.get("flags", 0)
                            color = span.get("color", 0)
                            bbox = span.get("bbox", [0,0,0,0])
                            
                            # Check against watermark patterns
                            is_watermark = False
                            watermark_type = ""
                            
                            for pattern in WATERMARK_PATTERNS:
                                if re.search(pattern, text.lower()):
                                    is_watermark = True
                                    watermark_type = pattern
                                    break
                            
                            # Check for diagonal/rotated text (common for watermarks)
                            origin = line.get("dir", (1, 0))
                            if origin != (1, 0) and origin != (1.0, 0.0):
                                is_watermark = True
                                watermark_type = "diagonal_text"
                            
                            # Check for very large/centered text
                            if font_size > 40:
                                text_center_x = (bbox[0] + bbox[2]) / 2
                                page_center_x = page_rect.width / 2
                                if abs(text_center_x - page_center_x) < 100:
                                    is_watermark = True
                                    watermark_type = "large_centered_text"
                            
                            # Check for low opacity text (gray colors)
                            if color != 0:
                                r = (color >> 16) & 0xFF
                                g = (color >> 8) & 0xFF
                                b = color & 0xFF
                                if r == g == b and 100 < r < 200:  # Gray text
                                    if len(text) > 3:
                                        is_watermark = True
                                        watermark_type = "semi_transparent_text"
                            
                            if is_watermark and text:
                                watermarks['text_watermarks'].append({
                                    'page': page_num + 1,
                                    'text': text[:100],
                                    'type': watermark_type,
                                    'font_size': font_size,
                                    'bbox': bbox,
                                    'confidence': 'HIGH' if '@' in text or 't.me' in text.lower() else 'MEDIUM'
                                })
                                total_text_wm += 1
            
            # ═══════════════ LINK WATERMARK DETECTION ═══════════════
            links = page.get_links()
            for link in links:
                uri = link.get("uri", "")
                if uri:
                    watermarks['link_watermarks'].append({
                        'page': page_num + 1,
                        'url': uri[:80],
                        'rect': link.get("from", None),
                        'confidence': 'HIGH'
                    })
                    total_link_wm += 1
            
            # ═══════════════ IMAGE WATERMARK DETECTION ═══════════════
            images = page.get_images(full=True)
            for img_index, img in enumerate(images):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Analyze image for watermark characteristics
                    pil_image = Image.open(io.BytesIO(image_bytes))
                    
                    # Check if image has transparency (alpha channel)
                    has_alpha = pil_image.mode in ('RGBA', 'LA') or \
                                (pil_image.mode == 'P' and 'transparency' in pil_image.info)
                    
                    # Check image position (corners or center often have watermarks)
                    img_rect = page.get_image_rects(xref)
                    
                    is_likely_watermark = False
                    watermark_reason = ""
                    
                    if has_alpha:
                        is_likely_watermark = True
                        watermark_reason = "transparent_image"
                    
                    # Small images in corners are likely logos/watermarks
                    if img_rect:
                        for rect in img_rect:
                            if rect.width < 150 and rect.height < 150:
                                if (rect.x0 < 100 or rect.x0 > page_rect.width - 200) and \
                                   (rect.y0 < 100 or rect.y0 > page_rect.height - 200):
                                    is_likely_watermark = True
                                    watermark_reason = "corner_logo"
                    
                    if is_likely_watermark:
                        watermarks['image_watermarks'].append({
                            'page': page_num + 1,
                            'xref': xref,
                            'size': f"{pil_image.width}x{pil_image.height}",
                            'type': watermark_reason,
                            'has_alpha': has_alpha,
                            'confidence': 'MEDIUM'
                        })
                        total_image_wm += 1
                        
                except Exception as e:
                    pass
            
            # ═══════════════ OVERLAY DETECTION ═══════════════
            try:
                xobjects = page.get_xobjects()
                for xobj in xobjects:
                    if xobj[1] == 1:  # Form XObject
                        watermarks['overlay_watermarks'].append({
                            'page': page_num + 1,
                            'xref': xobj[0],
                            'type': 'form_xobject',
                            'confidence': 'LOW'
                        })
            except:
                pass
        
        # Create summary
        watermarks['summary'] = {
            'total_text_watermarks': total_text_wm,
            'total_image_watermarks': total_image_wm,
            'total_link_watermarks': total_link_wm,
            'total_pages': len(doc),
            'pages_with_watermarks': len(set(
                [w['page'] for w in watermarks['text_watermarks']] +
                [w['page'] for w in watermarks['image_watermarks']] +
                [w['page'] for w in watermarks['link_watermarks']]
            ))
        }
        
        doc.close()
        return watermarks
    
    @staticmethod
    def format_watermark_report(watermarks):
        """Format watermark detection results for display"""
        report = "🔍 **WATERMARK DETECTION REPORT**\n"
        report += "═" * 35 + "\n\n"
        
        summary = watermarks['summary']
        
        # Summary section
        report += "📊 **Summary:**\n"
        report += f"├ 📄 Total Pages: {summary['total_pages']}\n"
        report += f"├ 📝 Text Watermarks: {summary['total_text_watermarks']}\n"
        report += f"├ 🔗 Link Watermarks: {summary['total_link_watermarks']}\n"
        report += f"├ 🖼️ Image Watermarks: {summary['total_image_watermarks']}\n"
        report += f"└ 📑 Affected Pages: {summary['pages_with_watermarks']}\n\n"
        
        # Detailed text watermarks
        if watermarks['text_watermarks']:
            report += "📝 **Text Watermarks Found:**\n"
            shown = 0
            for wm in watermarks['text_watermarks'][:8]:
                confidence_icon = "🔴" if wm['confidence'] == 'HIGH' else "🟡"
                text_preview = wm['text'][:40].replace('`', "'")
                report += f"{confidence_icon} Page {wm['page']}: `{text_preview}`\n"
                shown += 1
            if len(watermarks['text_watermarks']) > 8:
                report += f"   _...and {len(watermarks['text_watermarks']) - 8} more_\n"
            report += "\n"
        
        # Detailed link watermarks
        if watermarks['link_watermarks']:
            report += "🔗 **Link Watermarks Found:**\n"
            for wm in watermarks['link_watermarks'][:5]:
                url_preview = wm['url'][:50].replace('`', "'")
                report += f"🔴 Page {wm['page']}: `{url_preview}`\n"
            if len(watermarks['link_watermarks']) > 5:
                report += f"   _...and {len(watermarks['link_watermarks']) - 5} more_\n"
            report += "\n"
        
        # Detailed image watermarks
        if watermarks['image_watermarks']:
            report += "🖼️ **Image Watermarks Found:**\n"
            for wm in watermarks['image_watermarks'][:5]:
                report += f"🟡 Page {wm['page']}: {wm['type']} ({wm['size']})\n"
            if len(watermarks['image_watermarks']) > 5:
                report += f"   _...and {len(watermarks['image_watermarks']) - 5} more_\n"
            report += "\n"
        
        if not any([watermarks['text_watermarks'], watermarks['link_watermarks'], 
                    watermarks['image_watermarks']]):
            report += "✅ **No watermarks detected!**\n"
        
        return report
    
    @staticmethod
    def remove_watermarks(pdf_path, output_path, options=None):
        """Remove watermarks from PDF with various options"""
        if options is None:
            options = {'remove_text': True, 'remove_links': True, 'remove_images': True}
        
        doc = fitz.open(pdf_path)
        removed_count = {'text': 0, 'links': 0, 'images': 0}
        
        for page in doc:
            
            # ═══════════════ REMOVE TEXT WATERMARKS ═══════════════
            if options.get('remove_text', True):
                blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                
                for block in blocks:
                    if block.get("type") == 0:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "").strip()
                                font_size = span.get("size", 12)
                                
                                # Check if it's a watermark
                                should_remove = False
                                
                                for pattern in WATERMARK_PATTERNS:
                                    if re.search(pattern, text.lower()):
                                        should_remove = True
                                        break
                                
                                # Check for diagonal text
                                origin = line.get("dir", (1, 0))
                                if origin != (1, 0) and origin != (1.0, 0.0):
                                    should_remove = True
                                
                                # Large centered text
                                if font_size > 40:
                                    bbox = span.get("bbox", [0,0,0,0])
                                    text_center_x = (bbox[0] + bbox[2]) / 2
                                    page_center_x = page.rect.width / 2
                                    if abs(text_center_x - page_center_x) < 100:
                                        should_remove = True
                                
                                if should_remove and text:
                                    rect = fitz.Rect(span["bbox"])
                                    rect.x0 -= 2
                                    rect.y0 -= 2
                                    rect.x1 += 2
                                    rect.y1 += 2
                                    page.add_redact_annot(rect, fill=(1, 1, 1))
                                    removed_count['text'] += 1
                
                page.apply_redactions()
            
            # ═══════════════ REMOVE LINK WATERMARKS ═══════════════
            if options.get('remove_links', True):
                links = page.get_links()
                for link in links:
                    if link.get("uri"):
                        page.delete_link(link)
                        removed_count['links'] += 1
            
            # ═══════════════ REMOVE IMAGE WATERMARKS ═══════════════
            if options.get('remove_images', True):
                images = page.get_images(full=True)
                for img in images:
                    xref = img[0]
                    try:
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        pil_image = Image.open(io.BytesIO(image_bytes))
                        
                        has_alpha = pil_image.mode in ('RGBA', 'LA')
                        is_small = pil_image.width < 200 and pil_image.height < 200
                        
                        if has_alpha or is_small:
                            img_rects = page.get_image_rects(xref)
                            for rect in img_rects:
                                page.add_redact_annot(rect, fill=(1, 1, 1))
                                removed_count['images'] += 1
                            page.apply_redactions()
                    except:
                        pass
        
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
        
        return removed_count
    
    @staticmethod
    def add_text_watermark(pdf_path, output_path, text, position="center", 
                          opacity=0.3, color=(128, 128, 128), font_size=50, rotation=45):
        """Add text watermark to PDF"""
        doc = fitz.open(pdf_path)
        
        r, g, b = color
        
        for page in doc:
            rect = page.rect
            
            if position == "tiled":
                step_x = rect.width / 3
                step_y = rect.height / 4
                for i in range(4):
                    for j in range(5):
                        point = fitz.Point(step_x * i, step_y * j + 50)
                        page.insert_text(
                            point, text,
                            fontsize=font_size * 0.6,
                            color=(r/255, g/255, b/255),
                            rotate=rotation,
                            overlay=True
                        )
            elif position == "diagonal":
                point = fitz.Point(rect.width/2 - len(text)*font_size/4, rect.height/2)
                page.insert_text(
                    point, text,
                    fontsize=font_size,
                    color=(r/255, g/255, b/255),
                    rotate=45,
                    overlay=True
                )
            else:
                positions = {
                    "center": fitz.Point(rect.width/2 - len(text)*font_size/4, rect.height/2),
                    "top-left": fitz.Point(50, 80),
                    "top-right": fitz.Point(rect.width - 50 - len(text)*font_size/2, 80),
                    "bottom-left": fitz.Point(50, rect.height - 50),
                    "bottom-right": fitz.Point(rect.width - 50 - len(text)*font_size/2, rect.height - 50),
                }
                point = positions.get(position, positions["center"])
                page.insert_text(
                    point, text,
                    fontsize=font_size,
                    color=(r/255, g/255, b/255),
                    overlay=True
                )
        
        doc.save(output_path)
        doc.close()
    
    @staticmethod
    def add_image_watermark(pdf_path, output_path, image_path, position="center", 
                           opacity=0.5, scale=1.0):
        """Add image watermark to PDF"""
        doc = fitz.open(pdf_path)
        
        for page in doc:
            rect = page.rect
            
            img = Image.open(image_path)
            img_width, img_height = img.size
            img_width *= scale
            img_height *= scale
            
            positions = {
                "center": fitz.Rect(
                    rect.width/2 - img_width/2,
                    rect.height/2 - img_height/2,
                    rect.width/2 + img_width/2,
                    rect.height/2 + img_height/2
                ),
                "top-left": fitz.Rect(20, 20, 20 + img_width, 20 + img_height),
                "top-right": fitz.Rect(
                    rect.width - 20 - img_width, 20,
                    rect.width - 20, 20 + img_height
                ),
                "bottom-left": fitz.Rect(
                    20, rect.height - 20 - img_height,
                    20 + img_width, rect.height - 20
                ),
                "bottom-right": fitz.Rect(
                    rect.width - 20 - img_width, rect.height - 20 - img_height,
                    rect.width - 20, rect.height - 20
                ),
            }
            
            if position == "tiled":
                step_x = rect.width / 3
                step_y = rect.height / 3
                for i in range(4):
                    for j in range(4):
                        img_rect = fitz.Rect(
                            step_x * i, step_y * j,
                            step_x * i + img_width * 0.5, step_y * j + img_height * 0.5
                        )
                        page.insert_image(img_rect, filename=image_path, overlay=True)
            else:
                img_rect = positions.get(position, positions["center"])
                page.insert_image(img_rect, filename=image_path, overlay=True)
        
        doc.save(output_path)
        doc.close()
    
    @staticmethod
    def add_telegram_watermark(pdf_path, output_path, position="bottom-right", 
                               include_text=True, channel_name="", logo_size=80):
        """Add Telegram logo watermark with optional channel name"""
        doc = fitz.open(pdf_path)
        
        # Create Telegram logo
        if channel_name:
            logo = create_combined_telegram_watermark(channel_name, size=150, opacity=220)
            logo_actual_size = 150
        else:
            logo = create_telegram_logo(size=logo_size, opacity=220)
            logo_actual_size = logo_size
        
        # Save logo temporarily
        logo_path = pdf_path.replace('.pdf', '_tg_logo.png')
        logo.save(logo_path)
        
        for page in doc:
            rect = page.rect
            margin = 25
            
            if channel_name:
                # With text, need more space
                positions = {
                    "top-left": (margin, margin),
                    "top-right": (rect.width - margin - logo_actual_size, margin),
                    "bottom-left": (margin, rect.height - margin - logo_actual_size - 40),
                    "bottom-right": (rect.width - margin - logo_actual_size, rect.height - margin - logo_actual_size - 40),
                    "center": (rect.width/2 - logo_actual_size/2, rect.height/2 - logo_actual_size/2)
                }
                height = logo_actual_size + 40
            else:
                positions = {
                    "top-left": (margin, margin),
                    "top-right": (rect.width - margin - logo_actual_size, margin),
                    "bottom-left": (margin, rect.height - margin - logo_actual_size),
                    "bottom-right": (rect.width - margin - logo_actual_size, rect.height - margin - logo_actual_size),
                    "center": (rect.width/2 - logo_actual_size/2, rect.height/2 - logo_actual_size/2)
                }
                height = logo_actual_size
            
            pos = positions.get(position, positions["bottom-right"])
            
            img_rect = fitz.Rect(pos[0], pos[1], pos[0] + logo_actual_size, pos[1] + height)
            page.insert_image(img_rect, filename=logo_path, overlay=True)
        
        doc.save(output_path)
        doc.close()
        
        # Cleanup
        if os.path.exists(logo_path):
            os.remove(logo_path)
    
    @staticmethod
    def add_pages(pdf_path, output_path, num_pages=1, position="end", page_size="same"):
        """Add blank pages to PDF"""
        doc = fitz.open(pdf_path)
        
        # Get page size
        if page_size == "A4":
            width, height = 595, 842
        elif page_size == "Letter":
            width, height = 612, 792
        else:
            first_page = doc[0]
            width, height = first_page.rect.width, first_page.rect.height
        
        # Determine insertion point
        if position == "start":
            insert_idx = 0
        elif position == "end":
            insert_idx = len(doc)
        else:
            try:
                insert_idx = int(position) - 1
                if insert_idx < 0:
                    insert_idx = 0
                if insert_idx > len(doc):
                    insert_idx = len(doc)
            except:
                insert_idx = len(doc)
        
        # Insert pages
        for i in range(num_pages):
            doc.insert_page(insert_idx + i, width=width, height=height)
        
        new_total = len(doc)
        doc.save(output_path)
        doc.close()
        
        return new_total
    
    @staticmethod
    def remove_pages(pdf_path, output_path, pages_to_remove):
        """Remove specific pages from PDF (0-indexed)"""
        doc = fitz.open(pdf_path)
        original_count = len(doc)
        
        # Sort in reverse to avoid index shifting
        for page_num in sorted(pages_to_remove, reverse=True):
            if 0 <= page_num < len(doc):
                doc.delete_page(page_num)
        
        new_count = len(doc)
        doc.save(output_path)
        doc.close()
        
        return original_count - new_count, new_count
    
    @staticmethod
    def add_branding(pdf_path, output_path, header_text="", footer_text="", 
                    logo_path=None, page_numbers=True):
        """Add branding elements to PDF"""
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        for page_num, page in enumerate(doc):
            rect = page.rect
            
            # Add header
            if header_text:
                text_width = len(header_text) * 4
                page.insert_text(
                    fitz.Point((rect.width - text_width) / 2, 30),
                    header_text,
                    fontsize=14,
                    color=(0.15, 0.15, 0.15),
                    overlay=True
                )
                # Header line
                page.draw_line(
                    fitz.Point(50, 45),
                    fitz.Point(rect.width - 50, 45),
                    color=(0.6, 0.6, 0.6),
                    width=0.8
                )
            
            # Footer line
            page.draw_line(
                fitz.Point(50, rect.height - 45),
                fitz.Point(rect.width - 50, rect.height - 45),
                color=(0.6, 0.6, 0.6),
                width=0.8
            )
            
            # Add footer text
            if footer_text:
                page.insert_text(
                    fitz.Point(60, rect.height - 28),
                    footer_text,
                    fontsize=10,
                    color=(0.35, 0.35, 0.35),
                    overlay=True
                )
            
            # Add page numbers
            if page_numbers:
                page_text = f"Page {page_num + 1} of {total_pages}"
                page.insert_text(
                    fitz.Point(rect.width - 120, rect.height - 28),
                    page_text,
                    fontsize=10,
                    color=(0.4, 0.4, 0.4),
                    overlay=True
                )
            
            # Add logo
            if logo_path and os.path.exists(logo_path):
                logo_rect = fitz.Rect(25, 12, 70, 42)
                try:
                    page.insert_image(logo_rect, filename=logo_path, overlay=True)
                except:
                    pass
        
        doc.save(output_path)
        doc.close()
    
    @staticmethod
    def merge_pdfs(pdf_paths, output_path):
        """Merge multiple PDFs into one"""
        result = fitz.open()
        
        for pdf_path in pdf_paths:
            if os.path.exists(pdf_path):
                doc = fitz.open(pdf_path)
                result.insert_pdf(doc)
                doc.close()
        
        result.save(output_path)
        total_pages = len(result)
        result.close()
        
        return total_pages
    
    @staticmethod
    def split_pdf(pdf_path, output_dir, split_type="single"):
        """Split PDF into parts"""
        doc = fitz.open(pdf_path)
        output_files = []
        
        if split_type == "single":
            for page_num in range(len(doc)):
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                output_path = os.path.join(output_dir, f"page_{page_num + 1}.pdf")
                new_doc.save(output_path)
                new_doc.close()
                output_files.append(output_path)
        
        elif split_type == "half":
            mid = len(doc) // 2
            
            new_doc1 = fitz.open()
            new_doc1.insert_pdf(doc, from_page=0, to_page=mid-1)
            path1 = os.path.join(output_dir, "part_1.pdf")
            new_doc1.save(path1)
            new_doc1.close()
            output_files.append(path1)
            
            new_doc2 = fitz.open()
            new_doc2.insert_pdf(doc, from_page=mid, to_page=len(doc)-1)
            path2 = os.path.join(output_dir, "part_2.pdf")
            new_doc2.save(path2)
            new_doc2.close()
            output_files.append(path2)
        
        doc.close()
        return output_files
    
    @staticmethod
    def compress_pdf(pdf_path, output_path, compression_level="medium"):
        """Compress PDF with different levels"""
        doc = fitz.open(pdf_path)
        
        if compression_level == "high":
            doc.save(output_path, garbage=4, deflate=True, clean=True, 
                    linear=True, deflate_images=True, deflate_fonts=True)
        elif compression_level == "medium":
            doc.save(output_path, garbage=3, deflate=True, clean=True)
        else:
            doc.save(output_path, garbage=2, deflate=True)
        
        original_size = os.path.getsize(pdf_path)
        new_size = os.path.getsize(output_path)
        
        doc.close()
        return original_size, new_size
    
    @staticmethod
    def rotate_pages(pdf_path, output_path, rotation, pages=None):
        """Rotate pages in PDF"""
        doc = fitz.open(pdf_path)
        
        if pages is None:
            pages = list(range(len(doc)))
        
        for page_num in pages:
            if 0 <= page_num < len(doc):
                page = doc[page_num]
                page.set_rotation(rotation)
        
        doc.save(output_path)
        doc.close()
        
        return len(pages)
    
    @staticmethod
    def get_pdf_info(pdf_path):
        """Get detailed PDF information"""
        doc = fitz.open(pdf_path)
        
        info = {
            'pages': len(doc),
            'metadata': doc.metadata,
            'file_size': os.path.getsize(pdf_path),
            'is_encrypted': doc.is_encrypted,
            'page_sizes': [],
            'has_images': False,
            'has_text': False
        }
        
        for page in doc:
            info['page_sizes'].append({
                'width': page.rect.width,
                'height': page.rect.height
            })
            
            if page.get_images():
                info['has_images'] = True
            
            if page.get_text().strip():
                info['has_text'] = True
        
        doc.close()
        return info

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                         BOT HANDLERS                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - Welcome message"""
    welcome_text = """
🎉 **Welcome to Ultimate PDF Master Bot!** 🎉

I'm your powerful PDF manipulation assistant with these features:

🔹 **Watermark Tools**
   ├ 🔍 Detect watermarks (see what will be removed!)
   ├ 🚫 Remove text/image/link watermarks  
   ├ 💧 Add text watermarks
   └ 📱 Add Telegram logo watermark

🔹 **Page Tools**
   ├ ➕ Add blank pages
   ├ ➖ Remove specific pages
   └ 🔄 Rotate pages

🔹 **Branding**
   ├ 📝 Add headers & footers
   ├ 🏷️ Add page numbers
   └ 📱 Telegram branding

🔹 **Other Tools**
   ├ 📦 Compress PDF
   ├ ✂️ Split PDF
   └ 🔗 Merge PDFs

━━━━━━━━━━━━━━━━━━━━━━━━━━━

📤 **To start, send me a PDF file!**

🆘 Need help? Use /help
    """
    
    keyboard = [
        [InlineKeyboardButton("📖 How to Use", callback_data="how_to_use")],
        [InlineKeyboardButton("🆘 Help", callback_data="help"), 
         InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            welcome_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_text, 
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = """
📚 **PDF Master Bot - Complete Guide**

━━━ **WATERMARK REMOVAL** ━━━
1. Send your PDF file
2. Click "🔍 View Watermarks" to see detected watermarks
3. Review what will be removed
4. Click "🚫 Remove All" to clean the PDF

**The bot detects:**
• Text watermarks (@channels, URLs, websites)
• Image watermarks (logos, transparent images)
• Link watermarks (embedded clickable URLs)
• Diagonal/rotated text overlays

━━━ **ADD WATERMARKS** ━━━
• **Text**: Custom text with position & style
• **Telegram Logo**: Official-style TG logo
• **Tiled**: Repeated pattern across pages
• **Diagonal**: Angled text across center

━━━ **PAGE OPERATIONS** ━━━
• **Add Pages**: Insert blank pages at start/end/middle
• **Remove Pages**: Delete by page numbers
• Example: `1, 3, 5-10` removes those pages

━━━ **BRANDING** ━━━
• Headers: Top text on every page
• Footers: Bottom text with page numbers
• Logo: Company/channel branding

━━━ **COMMANDS** ━━━
/start - Start the bot
/help - Show this help
/cancel - Cancel current operation

━━━ **TIPS** ━━━
• For best results, use text-based PDFs
• Max file size: 50MB
• Large files may take longer to process
    """
    
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_start")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    user_id = update.effective_user.id
    if user_id in user_sessions:
        temp_dir = user_sessions[user_id].get('temp_dir')
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        del user_sessions[user_id]
    
    await update.message.reply_text(
        "❌ **Operation Cancelled**\n\nSend a PDF to start again!",
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded PDF files"""
    document = update.message.document
    user_id = update.effective_user.id
    
    # Validate file
    if not document.file_name.lower().endswith('.pdf'):
        await update.message.reply_text(
            "⚠️ **Please send a PDF file!**\n\nOnly `.pdf` files are supported.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Check file size (50MB limit)
    if document.file_size > 50 * 1024 * 1024:
        await update.message.reply_text(
            "⚠️ **File too large!**\n\nMaximum file size is 50MB.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Send processing message
    status_msg = await update.message.reply_text(
        "📥 **Downloading PDF...**\n\n⏳ Please wait...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Clean up previous session
        if user_id in user_sessions:
            old_temp = user_sessions[user_id].get('temp_dir')
            if old_temp and os.path.exists(old_temp):
                shutil.rmtree(old_temp, ignore_errors=True)
        
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix=f"pdfbot_{user_id}_")
        
        # Download file
        file = await context.bot.get_file(document.file_id)
        pdf_path = os.path.join(temp_dir, document.file_name)
        await file.download_to_drive(pdf_path)
        
        # Store session
        user_sessions[user_id] = {
            'pdf_path': pdf_path,
            'filename': document.file_name,
            'temp_dir': temp_dir,
            'file_size': document.file_size,
            'waiting_for': None,
            'merge_files': []
        }
        
        # Get PDF info
        pdf_info = PDFProcessor.get_pdf_info(pdf_path)
        
        # Detect watermarks
        await status_msg.edit_text(
            "🔍 **Analyzing PDF...**\n\n⏳ Detecting watermarks...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        watermarks = PDFProcessor.detect_watermarks(pdf_path)
        user_sessions[user_id]['watermarks'] = watermarks
        
        # Format watermark info
        wm_summary = watermarks['summary']
        wm_info = ""
        
        if wm_summary['total_text_watermarks'] > 0 or \
           wm_summary['total_link_watermarks'] > 0 or \
           wm_summary['total_image_watermarks'] > 0:
            wm_info = "\n\n🔍 **Watermarks Detected:**\n"
            if wm_summary['total_text_watermarks'] > 0:
                wm_info += f"├ 📝 Text: {wm_summary['total_text_watermarks']}\n"
            if wm_summary['total_link_watermarks'] > 0:
                wm_info += f"├ 🔗 Links: {wm_summary['total_link_watermarks']}\n"
            if wm_summary['total_image_watermarks'] > 0:
                wm_info += f"└ 🖼️ Images: {wm_summary['total_image_watermarks']}\n"
        else:
            wm_info = "\n\n✅ **No watermarks detected**"
        
        # Create menu
        keyboard = [
            [
                InlineKeyboardButton("🔍 View Watermarks", callback_data="view_watermarks"),
                InlineKeyboardButton("🚫 Remove Watermarks", callback_data="remove_watermarks")
            ],
            [
                InlineKeyboardButton("💧 Add Watermark", callback_data="add_watermark"),
                InlineKeyboardButton("📱 Add TG Logo", callback_data="add_telegram_wm")
            ],
            [
                InlineKeyboardButton("➕ Add Pages", callback_data="add_pages"),
                InlineKeyboardButton("➖ Remove Pages", callback_data="remove_pages")
            ],
            [
                InlineKeyboardButton("🏷️ Add Branding", callback_data="add_branding"),
                InlineKeyboardButton("🔄 Rotate", callback_data="rotate_pages")
            ],
            [
                InlineKeyboardButton("📦 Compress", callback_data="compress"),
                InlineKeyboardButton("✂️ Split", callback_data="split")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        file_size_kb = document.file_size / 1024
        file_size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.2f} MB"
        
        info_text = f"""
✅ **PDF Received Successfully!**

📄 **File:** `{document.file_name}`
📃 **Pages:** {pdf_info['pages']}
📦 **Size:** {file_size_str}
🔒 **Encrypted:** {'Yes ⚠️' if pdf_info['is_encrypted'] else 'No ✅'}
{wm_info}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Choose an operation:**
        """
        
        await status_msg.edit_text(
            info_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ **Error processing PDF:**\n\n`{str(e)}`",
            parse_mode=ParseMode.MARKDOWN
        )
        traceback.print_exc()

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # ═══════════════════════════════════════════════════════════════════
    # NON-SESSION CALLBACKS
    # ═══════════════════════════════════════════════════════════════════
    if data == "help":
        await help_command(update, context)
        return
    
    if data == "about":
        about_text = """
🤖 **Ultimate PDF Master Bot**

**Version:** 3.0.0
**Engine:** PyMuPDF + Advanced AI

━━━━━━━━━━━━━━━━━━━━━━━━

**✨ Features:**
• Advanced watermark detection
• Smart pattern-based removal
• Telegram branding support
• Professional page manipulation
• High-quality PDF compression

**🛠️ Technology:**
• Python 3.10+
• PyMuPDF (fitz)
• Pillow for image processing
• Advanced regex pattern matching

**📊 Capabilities:**
• Detects @channel watermarks
• Removes URL watermarks
• Identifies logo watermarks
• Handles encrypted PDFs

━━━━━━━━━━━━━━━━━━━━━━━━

Made with ❤️ for Telegram users
        """
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_start")]]
        await query.edit_message_text(about_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if data == "how_to_use":
        how_to_text = """
📖 **How to Use PDF Master Bot**

**Step 1:** Send a PDF file to the bot

**Step 2:** Wait for analysis to complete
   • Bot scans for watermarks automatically
   • Shows summary of detected elements

**Step 3:** Choose an operation:

🔍 **View Watermarks**
   → Detailed list of all detected watermarks
   → Shows page numbers and watermark text

🚫 **Remove Watermarks**  
   → Removes all detected watermarks
   → Choose to remove text/links/images

💧 **Add Watermark**
   → Add custom text watermark
   → Multiple position options

📱 **Add TG Logo**
   → Add Telegram logo branding
   → Optional channel name

➕➖ **Add/Remove Pages**
   → Insert blank pages anywhere
   → Delete specific pages

🏷️ **Branding**
   → Add professional headers/footers
   → Automatic page numbering

📦 **Compress**
   → Reduce file size
   → Multiple compression levels

✂️ **Split**
   → Separate into individual pages
   → Or split into halves

**Step 4:** Download your processed PDF!
        """
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_start")]]
        await query.edit_message_text(how_to_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return
    
    if data == "back_start":
        await start(update, context)
        return
    
    if data == "cancel":
        if user_id in user_sessions:
            temp_dir = user_sessions[user_id].get('temp_dir')
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            del user_sessions[user_id]
        
        await query.edit_message_text(
            "❌ **Operation Cancelled**\n\nSend a PDF to start again!",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # SESSION REQUIRED CALLBACKS
    # ═══════════════════════════════════════════════════════════════════
    if user_id not in user_sessions:
        await query.edit_message_text(
            "⚠️ **Session expired!**\n\nPlease send your PDF file again.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    session = user_sessions[user_id]
    pdf_path = session['pdf_path']
    temp_dir = session['temp_dir']
    filename = session['filename']
    
    # ═══════════════════════════════════════════════════════════════════
    # BACK TO MENU
    # ═══════════════════════════════════════════════════════════════════
    if data == "back_to_menu":
        session['waiting_for'] = None
        pdf_info = PDFProcessor.get_pdf_info(pdf_path)
        watermarks = session.get('watermarks', {})
        wm_summary = watermarks.get('summary', {})
        
        wm_info = ""
        if wm_summary.get('total_text_watermarks', 0) > 0 or \
           wm_summary.get('total_link_watermarks', 0) > 0 or \
           wm_summary.get('total_image_watermarks', 0) > 0:
            wm_info = "\n\n🔍 **Watermarks Detected:**\n"
            if wm_summary.get('total_text_watermarks', 0) > 0:
                wm_info += f"├ 📝 Text: {wm_summary['total_text_watermarks']}\n"
            if wm_summary.get('total_link_watermarks', 0) > 0:
                wm_info += f"├ 🔗 Links: {wm_summary['total_link_watermarks']}\n"
            if wm_summary.get('total_image_watermarks', 0) > 0:
                wm_info += f"└ 🖼️ Images: {wm_summary['total_image_watermarks']}\n"
        else:
            wm_info = "\n\n✅ **No watermarks detected**"
        
        keyboard = [
            [
                InlineKeyboardButton("🔍 View Watermarks", callback_data="view_watermarks"),
                InlineKeyboardButton("🚫 Remove Watermarks", callback_data="remove_watermarks")
            ],
            [
                InlineKeyboardButton("💧 Add Watermark", callback_data="add_watermark"),
                InlineKeyboardButton("📱 Add TG Logo", callback_data="add_telegram_wm")
            ],
            [
                InlineKeyboardButton("➕ Add Pages", callback_data="add_pages"),
                InlineKeyboardButton("➖ Remove Pages", callback_data="remove_pages")
            ],
            [
                InlineKeyboardButton("🏷️ Add Branding", callback_data="add_branding"),
                InlineKeyboardButton("🔄 Rotate", callback_data="rotate_pages")
            ],
            [
                InlineKeyboardButton("📦 Compress", callback_data="compress"),
                InlineKeyboardButton("✂️ Split", callback_data="split")
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
        ]
        
        file_size_kb = session['file_size'] / 1024
        file_size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.2f} MB"
        
        info_text = f"""
✅ **PDF Loaded**

📄 **File:** `{filename}`
📃 **Pages:** {pdf_info['pages']}
📦 **Size:** {file_size_str}
{wm_info}

━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Choose an operation:**
        """
        
        await query.edit_message_text(
            info_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # VIEW WATERMARKS
    # ═══════════════════════════════════════════════════════════════════
    if data == "view_watermarks":
        watermarks = session.get('watermarks', PDFProcessor.detect_watermarks(pdf_path))
        report = PDFProcessor.format_watermark_report(watermarks)
        
        keyboard = [
            [InlineKeyboardButton("🚫 Remove All Watermarks", callback_data="confirm_remove_wm")],
            [InlineKeyboardButton("⚙️ Select What to Remove", callback_data="select_remove_options")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            report,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # REMOVE WATERMARKS
    # ═══════════════════════════════════════════════════════════════════
    if data == "remove_watermarks":
        watermarks = session.get('watermarks', PDFProcessor.detect_watermarks(pdf_path))
        
        if watermarks['summary']['total_text_watermarks'] == 0 and \
           watermarks['summary']['total_link_watermarks'] == 0 and \
           watermarks['summary']['total_image_watermarks'] == 0:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ **No watermarks detected in this PDF!**\n\n"
                "The document appears to be clean.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        report = PDFProcessor.format_watermark_report(watermarks)
        preview_text = report + "\n\n⚠️ **Do you want to remove these watermarks?**"
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Remove All", callback_data="confirm_remove_wm")],
            [InlineKeyboardButton("⚙️ Select What to Remove", callback_data="select_remove_options")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            preview_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == "select_remove_options":
        keyboard = [
            [InlineKeyboardButton("📝 Remove Text Only", callback_data="remove_text_only")],
            [InlineKeyboardButton("🔗 Remove Links Only", callback_data="remove_links_only")],
            [InlineKeyboardButton("🖼️ Remove Images Only", callback_data="remove_images_only")],
            [InlineKeyboardButton("📝🔗 Text + Links", callback_data="remove_text_links")],
            [InlineKeyboardButton("🚫 Remove Everything", callback_data="confirm_remove_wm")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            "⚙️ **Select what to remove:**\n\n"
            "Choose which types of watermarks to remove:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data in ["confirm_remove_wm", "remove_text_only", "remove_links_only", 
                "remove_images_only", "remove_text_links"]:
        await query.edit_message_text(
            "⏳ **Removing watermarks...**\n\n"
            "🔄 Processing your PDF...\n"
            "This may take a moment for large files...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            options = {
                'remove_text': data in ["confirm_remove_wm", "remove_text_only", "remove_text_links"],
                'remove_links': data in ["confirm_remove_wm", "remove_links_only", "remove_text_links"],
                'remove_images': data in ["confirm_remove_wm", "remove_images_only"]
            }
            
            output_path = os.path.join(temp_dir, f"clean_{filename}")
            removed = PDFProcessor.remove_watermarks(pdf_path, output_path, options)
            
            # Update session to use cleaned PDF
            session['pdf_path'] = output_path
            
            # Send result
            caption = f"""✅ **Watermarks Removed Successfully!**

📊 **Removal Report:**
├ 📝 Text removed: {removed['text']}
├ 🔗 Links removed: {removed['links']}
└ 🖼️ Images removed: {removed['images']}

📄 Your clean PDF is ready!"""
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"clean_{filename}",
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ **Watermarks removed successfully!**\n\n"
                "📤 Your clean PDF has been sent above ⬆️\n\n"
                "You can continue editing or send a new PDF.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"❌ **Error removing watermarks:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # ADD WATERMARK
    # ═══════════════════════════════════════════════════════════════════
    if data == "add_watermark":
        keyboard = [
            [InlineKeyboardButton("📝 Text Watermark", callback_data="wm_text")],
            [InlineKeyboardButton("📱 Telegram Logo", callback_data="add_telegram_wm")],
            [
                InlineKeyboardButton("🔲 Tiled Pattern", callback_data="wm_tiled"),
                InlineKeyboardButton("↗️ Diagonal", callback_data="wm_diagonal")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            "💧 **Add Watermark**\n\n"
            "Choose watermark type:\n\n"
            "📝 **Text** - Custom text at chosen position\n"
            "📱 **Telegram** - Official TG logo with channel name\n"
            "🔲 **Tiled** - Repeated pattern across page\n"
            "↗️ **Diagonal** - Angled text across center",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == "wm_text":
        session['waiting_for'] = 'watermark_text'
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            "📝 **Add Text Watermark**\n\n"
            "Please send the watermark text you want to add.\n\n"
            "**Examples:**\n"
            "• `CONFIDENTIAL`\n"
            "• `@YourChannel`\n"
            "• `DRAFT - DO NOT DISTRIBUTE`\n"
            "• `© Your Company 2024`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith("wm_pos_"):
        position = data.replace("wm_pos_", "")
        session['watermark_position'] = position
        session['waiting_for'] = None
        
        await query.edit_message_text(
            f"⏳ **Adding watermark...**\n\n"
            f"📍 Position: {position}\n"
            f"📝 Text: {session.get('watermark_text', 'N/A')}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"watermarked_{filename}")
            text = session.get('watermark_text', 'WATERMARK')
            
            PDFProcessor.add_text_watermark(
                pdf_path, output_path, text,
                position=position,
                font_size=45,
                color=(128, 128, 128),
                rotation=45 if position == "diagonal" else 0
            )
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"watermarked_{filename}",
                caption=f"✅ **Watermark Added!**\n\n📝 Text: `{text}`\n📍 Position: {position}"
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ **Watermark added successfully!**\n\n"
                "📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"❌ **Error adding watermark:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    if data == "wm_tiled":
        session['waiting_for'] = 'tiled_text'
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            "🔲 **Tiled Watermark**\n\n"
            "Send the text for tiled watermark.\n"
            "This will repeat across the entire page.\n\n"
            "**Examples:**\n"
            "• `SAMPLE`\n"
            "• `CONFIDENTIAL`\n"
            "• `@Channel`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == "wm_diagonal":
        session['waiting_for'] = 'diagonal_text'
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            "↗️ **Diagonal Watermark**\n\n"
            "Send the text for diagonal watermark.\n"
            "This will appear at 45° angle across center.\n\n"
            "**Examples:**\n"
            "• `DRAFT`\n"
            "• `PREVIEW ONLY`\n"
            "• `@YourChannel`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # ADD TELEGRAM LOGO WATERMARK
    # ═══════════════════════════════════════════════════════════════════
    if data == "add_telegram_wm":
        keyboard = [
            [
                InlineKeyboardButton("↖️ Top-Left", callback_data="tg_pos_top-left"),
                InlineKeyboardButton("↗️ Top-Right", callback_data="tg_pos_top-right")
            ],
            [InlineKeyboardButton("⏺️ Center", callback_data="tg_pos_center")],
            [
                InlineKeyboardButton("↙️ Bottom-Left", callback_data="tg_pos_bottom-left"),
                InlineKeyboardButton("↘️ Bottom-Right", callback_data="tg_pos_bottom-right")
            ],
            [InlineKeyboardButton("📝 Add Channel Name", callback_data="tg_with_channel")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            "📱 **Add Telegram Logo Watermark**\n\n"
            "Choose logo position:\n\n"
            "🔵 Official Telegram logo will be added\n"
            "💡 Optionally add your channel name below logo",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith("tg_pos_"):
        position = data.replace("tg_pos_", "")
        
        await query.edit_message_text(
            f"⏳ **Adding Telegram logo...**\n\n"
            f"📍 Position: {position}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"tg_branded_{filename}")
            channel_name = session.get('channel_name', '')
            
            PDFProcessor.add_telegram_watermark(
                pdf_path, output_path,
                position=position,
                channel_name=channel_name
            )
            
            session['pdf_path'] = output_path
            
            caption = f"✅ **Telegram Logo Added!**\n\n📍 Position: {position}"
            if channel_name:
                caption += f"\n📱 Channel: {channel_name}"
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"tg_branded_{filename}",
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ **Telegram logo added successfully!**\n\n"
                "📤 Your branded PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"❌ **Error adding logo:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    if data == "tg_with_channel":
        session['waiting_for'] = 'channel_name'
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="add_telegram_wm")]]
        
        await query.edit_message_text(
            "📱 **Add Channel Name**\n\n"
            "Send your channel/group name to display below the Telegram logo.\n\n"
            "**Examples:**\n"
            "• `@YourChannel`\n"
            "• `@PDFMasterBot`\n"
            "• `Join @MyGroup`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # ADD PAGES
    # ═══════════════════════════════════════════════════════════════════
    if data == "add_pages":
        keyboard = [
            [
                InlineKeyboardButton("1️⃣ Add 1 Page", callback_data="add_1_page"),
                InlineKeyboardButton("2️⃣ Add 2 Pages", callback_data="add_2_pages")
            ],
            [
                InlineKeyboardButton("5️⃣ Add 5 Pages", callback_data="add_5_pages"),
                InlineKeyboardButton("🔢 Custom", callback_data="add_custom_pages")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        pdf_info = PDFProcessor.get_pdf_info(pdf_path)
        
        await query.edit_message_text(
            f"➕ **Add Blank Pages**\n\n"
            f"📄 Current pages: {pdf_info['pages']}\n\n"
            "How many pages do you want to add?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith("add_") and data.endswith("_page") or data.endswith("_pages"):
        if data == "add_custom_pages":
            session['waiting_for'] = 'custom_page_count'
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="add_pages")]]
            
            await query.edit_message_text(
                "🔢 **Custom Page Count**\n\n"
                "Send the number of pages to add (1-100):",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Parse page count
        num_pages = int(data.split("_")[1])
        session['pages_to_add'] = num_pages
        
        keyboard = [
            [InlineKeyboardButton("📄 At Start", callback_data="insert_start")],
            [InlineKeyboardButton("📄 At End", callback_data="insert_end")],
            [InlineKeyboardButton("📄 After Page...", callback_data="insert_after")],
            [InlineKeyboardButton("🔙 Back", callback_data="add_pages")]
        ]
        
        await query.edit_message_text(
            f"➕ **Add {num_pages} Page(s)**\n\n"
            "Where do you want to insert the blank pages?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith("insert_"):
        position = data.replace("insert_", "")
        
        if position == "after":
            session['waiting_for'] = 'insert_after_page'
            pdf_info = PDFProcessor.get_pdf_info(pdf_path)
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="add_pages")]]
            
            await query.edit_message_text(
                f"📍 **Insert After Which Page?**\n\n"
                f"Current pages: 1 to {pdf_info['pages']}\n\n"
                "Send the page number:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        await query.edit_message_text(
            f"⏳ **Adding pages...**\n\n"
            f"Position: {position}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"pages_added_{filename}")
            num_pages = session.get('pages_to_add', 1)
            
            new_total = PDFProcessor.add_pages(
                pdf_path, output_path,
                num_pages=num_pages,
                position=position
            )
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"pages_added_{filename}",
                caption=f"✅ **{num_pages} Page(s) Added!**\n\n"
                       f"📍 Position: {position}\n"
                       f"📄 New total: {new_total} pages",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ **Pages added successfully!**\n\n"
                "📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"❌ **Error adding pages:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # REMOVE PAGES
    # ═══════════════════════════════════════════════════════════════════
    if data == "remove_pages":
        pdf_info = PDFProcessor.get_pdf_info(pdf_path)
        session['waiting_for'] = 'pages_to_remove'
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_to_menu")]]
        
        await query.edit_message_text(
            f"➖ **Remove Pages**\n\n"
            f"📄 Total pages: {pdf_info['pages']}\n\n"
            "**Send page numbers to remove:**\n\n"
            "**Examples:**\n"
            "• `1` - Remove page 1\n"
            "• `1, 3, 5` - Remove pages 1, 3, and 5\n"
            "• `1-5` - Remove pages 1 to 5\n"
            "• `1, 3-5, 8` - Mixed format",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # ADD BRANDING
    # ═══════════════════════════════════════════════════════════════════
    if data == "add_branding":
        keyboard = [
            [InlineKeyboardButton("📝 Add Header", callback_data="brand_header")],
            [InlineKeyboardButton("📝 Add Footer", callback_data="brand_footer")],
            [InlineKeyboardButton("🔢 Add Page Numbers", callback_data="brand_page_numbers")],
            [InlineKeyboardButton("📝🔢 Header + Footer + Numbers", callback_data="brand_all")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            "🏷️ **Add Branding**\n\n"
            "Choose what to add:\n\n"
            "📝 **Header** - Text at top of every page\n"
            "📝 **Footer** - Text at bottom of every page\n"
            "🔢 **Page Numbers** - Auto page numbering\n"
            "📝🔢 **All** - Complete branding package",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == "brand_header":
        session['waiting_for'] = 'header_text'
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="add_branding")]]
        
        await query.edit_message_text(
            "📝 **Add Header**\n\n"
            "Send the header text to display at the top of every page.\n\n"
            "**Examples:**\n"
            "• `CONFIDENTIAL DOCUMENT`\n"
            "• `Company Name - Internal Use Only`\n"
            "• `@YourChannel`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == "brand_footer":
        session['waiting_for'] = 'footer_text'
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="add_branding")]]
        
        await query.edit_message_text(
            "📝 **Add Footer**\n\n"
            "Send the footer text to display at the bottom of every page.\n\n"
            "**Examples:**\n"
            "• `© 2024 Your Company`\n"
            "• `www.yourwebsite.com`\n"
            "• `Contact: @YourChannel`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data == "brand_page_numbers":
        await query.edit_message_text(
            "⏳ **Adding page numbers...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"numbered_{filename}")
            
            PDFProcessor.add_branding(
                pdf_path, output_path,
                page_numbers=True
            )
            
            session['pdf_path'] = output_path
            pdf_info = PDFProcessor.get_pdf_info(output_path)
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"numbered_{filename}",
                caption=f"✅ **Page Numbers Added!**\n\n"
                       f"📄 Total pages: {pdf_info['pages']}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ **Page numbers added successfully!**\n\n"
                "📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    if data == "brand_all":
        session['waiting_for'] = 'brand_header_all'
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="add_branding")]]
        
        await query.edit_message_text(
            "📝🔢 **Complete Branding**\n\n"
            "**Step 1/2:** Send header text\n\n"
            "(or send `-` to skip header)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # ROTATE PAGES
    # ═══════════════════════════════════════════════════════════════════
    if data == "rotate_pages":
        keyboard = [
            [
                InlineKeyboardButton("↩️ 90° Left", callback_data="rotate_270"),
                InlineKeyboardButton("↪️ 90° Right", callback_data="rotate_90")
            ],
            [InlineKeyboardButton("🔃 180°", callback_data="rotate_180")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            "🔄 **Rotate Pages**\n\n"
            "Choose rotation angle:\n\n"
            "All pages will be rotated.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith("rotate_"):
        rotation = int(data.replace("rotate_", ""))
        
        await query.edit_message_text(
            f"⏳ **Rotating pages by {rotation}°...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"rotated_{filename}")
            
            rotated_count = PDFProcessor.rotate_pages(pdf_path, output_path, rotation)
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"rotated_{filename}",
                caption=f"✅ **Pages Rotated!**\n\n"
                       f"🔄 Rotation: {rotation}°\n"
                       f"📄 Pages rotated: {rotated_count}",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ **Pages rotated successfully!**\n\n"
                "📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # COMPRESS
    # ═══════════════════════════════════════════════════════════════════
    if data == "compress":
        keyboard = [
            [InlineKeyboardButton("🔹 Low (Fast)", callback_data="compress_low")],
            [InlineKeyboardButton("🔸 Medium (Balanced)", callback_data="compress_medium")],
            [InlineKeyboardButton("🔺 High (Smallest)", callback_data="compress_high")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        file_size_kb = session['file_size'] / 1024
        file_size_str = f"{file_size_kb:.1f} KB" if file_size_kb < 1024 else f"{file_size_kb/1024:.2f} MB"
        
        await query.edit_message_text(
            f"📦 **Compress PDF**\n\n"
            f"📄 Current size: {file_size_str}\n\n"
            "Choose compression level:\n\n"
            "🔹 **Low** - Fastest, minimal compression\n"
            "🔸 **Medium** - Balanced speed & size\n"
            "🔺 **High** - Maximum compression",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith("compress_"):
        level = data.replace("compress_", "")
        
        await query.edit_message_text(
            f"⏳ **Compressing PDF...**\n\n"
            f"📊 Level: {level}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"compressed_{filename}")
            
            original_size, new_size = PDFProcessor.compress_pdf(pdf_path, output_path, level)
            
            session['pdf_path'] = output_path
            
            reduction = ((original_size - new_size) / original_size) * 100
            
            orig_str = f"{original_size/1024:.1f} KB" if original_size < 1024*1024 else f"{original_size/1024/1024:.2f} MB"
            new_str = f"{new_size/1024:.1f} KB" if new_size < 1024*1024 else f"{new_size/1024/1024:.2f} MB"
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"compressed_{filename}",
                caption=f"✅ **PDF Compressed!**\n\n"
                       f"📊 Original: {orig_str}\n"
                       f"📦 Compressed: {new_str}\n"
                       f"📉 Reduction: {reduction:.1f}%",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await query.edit_message_text(
                "✅ **PDF compressed successfully!**\n\n"
                "📤 Your compressed PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # SPLIT
    # ═══════════════════════════════════════════════════════════════════
    if data == "split":
        pdf_info = PDFProcessor.get_pdf_info(pdf_path)
        
        keyboard = [
            [InlineKeyboardButton("📄 Individual Pages", callback_data="split_single")],
            [InlineKeyboardButton("✂️ Split in Half", callback_data="split_half")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
        ]
        
        await query.edit_message_text(
            f"✂️ **Split PDF**\n\n"
            f"📄 Total pages: {pdf_info['pages']}\n\n"
            "Choose split method:\n\n"
            "📄 **Individual** - Each page as separate PDF\n"
            "✂️ **Half** - Split into two equal parts",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if data.startswith("split_"):
        split_type = data.replace("split_", "")
        
        await query.edit_message_text(
            f"⏳ **Splitting PDF...**\n\n"
            f"📊 Method: {split_type}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            split_dir = os.path.join(temp_dir, "split_output")
            os.makedirs(split_dir, exist_ok=True)
            
            output_files = PDFProcessor.split_pdf(pdf_path, split_dir, split_type)
            
            # Send files
            for i, file_path in enumerate(output_files[:10]):  # Limit to 10 files
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=open(file_path, 'rb'),
                    filename=os.path.basename(file_path),
                    caption=f"📄 Part {i+1} of {len(output_files)}"
                )
            
            if len(output_files) > 10:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"⚠️ Only first 10 of {len(output_files)} files sent due to limits.",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"✅ **PDF split successfully!**\n\n"
                f"📄 Created {len(output_files)} files\n"
                "📤 Files sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await query.edit_message_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages for input collection"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_sessions:
        await update.message.reply_text(
            "📤 Please send a PDF file to start!",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    session = user_sessions[user_id]
    waiting_for = session.get('waiting_for')
    pdf_path = session['pdf_path']
    temp_dir = session['temp_dir']
    filename = session['filename']
    
    if not waiting_for:
        await update.message.reply_text(
            "🤔 Not sure what to do with that.\n\n"
            "Please use the buttons above or send a new PDF.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # WATERMARK TEXT INPUT
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'watermark_text':
        session['watermark_text'] = text
        session['waiting_for'] = None
        
        keyboard = [
            [
                InlineKeyboardButton("↖️ Top-Left", callback_data="wm_pos_top-left"),
                InlineKeyboardButton("↗️ Top-Right", callback_data="wm_pos_top-right")
            ],
            [InlineKeyboardButton("⏺️ Center", callback_data="wm_pos_center")],
            [
                InlineKeyboardButton("↙️ Bottom-Left", callback_data="wm_pos_bottom-left"),
                InlineKeyboardButton("↘️ Bottom-Right", callback_data="wm_pos_bottom-right")
            ],
            [
                InlineKeyboardButton("↗️ Diagonal", callback_data="wm_pos_diagonal"),
                InlineKeyboardButton("🔲 Tiled", callback_data="wm_pos_tiled")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="add_watermark")]
        ]
        
        await update.message.reply_text(
            f"📝 **Watermark Text:** `{text}`\n\n"
            "Choose watermark position:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # TILED WATERMARK TEXT
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'tiled_text':
        session['waiting_for'] = None
        
        status_msg = await update.message.reply_text(
            "⏳ **Creating tiled watermark...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"tiled_{filename}")
            
            PDFProcessor.add_text_watermark(
                pdf_path, output_path, text,
                position="tiled",
                font_size=35,
                color=(150, 150, 150),
                rotation=45
            )
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"tiled_{filename}",
                caption=f"✅ **Tiled Watermark Added!**\n\n📝 Text: `{text}`",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                "✅ **Tiled watermark added!**\n\n📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # DIAGONAL WATERMARK TEXT
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'diagonal_text':
        session['waiting_for'] = None
        
        status_msg = await update.message.reply_text(
            "⏳ **Creating diagonal watermark...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"diagonal_{filename}")
            
            PDFProcessor.add_text_watermark(
                pdf_path, output_path, text,
                position="diagonal",
                font_size=55,
                color=(140, 140, 140),
                rotation=45
            )
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"diagonal_{filename}",
                caption=f"✅ **Diagonal Watermark Added!**\n\n📝 Text: `{text}`",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                "✅ **Diagonal watermark added!**\n\n📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # CHANNEL NAME FOR TELEGRAM LOGO
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'channel_name':
        session['channel_name'] = text
        session['waiting_for'] = None
        
        keyboard = [
            [
                InlineKeyboardButton("↖️ Top-Left", callback_data="tg_pos_top-left"),
                InlineKeyboardButton("↗️ Top-Right", callback_data="tg_pos_top-right")
            ],
            [InlineKeyboardButton("⏺️ Center", callback_data="tg_pos_center")],
            [
                InlineKeyboardButton("↙️ Bottom-Left", callback_data="tg_pos_bottom-left"),
                InlineKeyboardButton("↘️ Bottom-Right", callback_data="tg_pos_bottom-right")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="add_telegram_wm")]
        ]
        
        await update.message.reply_text(
            f"📱 **Channel Name:** `{text}`\n\n"
            "Choose logo position:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # CUSTOM PAGE COUNT
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'custom_page_count':
        try:
            num_pages = int(text)
            if num_pages < 1 or num_pages > 100:
                raise ValueError("Out of range")
            
            session['pages_to_add'] = num_pages
            session['waiting_for'] = None
            
            keyboard = [
                [InlineKeyboardButton("📄 At Start", callback_data="insert_start")],
                [InlineKeyboardButton("📄 At End", callback_data="insert_end")],
                [InlineKeyboardButton("📄 After Page...", callback_data="insert_after")],
                [InlineKeyboardButton("🔙 Back", callback_data="add_pages")]
            ]
            
            await update.message.reply_text(
                f"➕ **Add {num_pages} Page(s)**\n\n"
                "Where do you want to insert the blank pages?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except ValueError:
            await update.message.reply_text(
                "⚠️ Please enter a valid number between 1 and 100.",
                parse_mode=ParseMode.MARKDOWN
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # INSERT AFTER PAGE NUMBER
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'insert_after_page':
        try:
            page_num = int(text)
            pdf_info = PDFProcessor.get_pdf_info(pdf_path)
            
            if page_num < 0 or page_num > pdf_info['pages']:
                raise ValueError("Out of range")
            
            session['waiting_for'] = None
            
            status_msg = await update.message.reply_text(
                f"⏳ **Adding pages after page {page_num}...**",
                parse_mode=ParseMode.MARKDOWN
            )
            
            output_path = os.path.join(temp_dir, f"pages_added_{filename}")
            num_pages = session.get('pages_to_add', 1)
            
            new_total = PDFProcessor.add_pages(
                pdf_path, output_path,
                num_pages=num_pages,
                position=str(page_num)
            )
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"pages_added_{filename}",
                caption=f"✅ **{num_pages} Page(s) Added!**\n\n"
                       f"📍 After page: {page_num}\n"
                       f"📄 New total: {new_total} pages",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                "✅ **Pages added successfully!**\n\n📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except ValueError:
            pdf_info = PDFProcessor.get_pdf_info(pdf_path)
            await update.message.reply_text(
                f"⚠️ Please enter a valid page number (0 to {pdf_info['pages']}).\n\n"
                "Enter 0 to insert at the beginning.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await update.message.reply_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # PAGES TO REMOVE
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'pages_to_remove':
        try:
            # Parse page numbers (supports: 1, 3, 5-10, etc.)
            pages_to_remove = []
            parts = text.replace(" ", "").split(",")
            
            for part in parts:
                if "-" in part:
                    start, end = part.split("-")
                    pages_to_remove.extend(range(int(start) - 1, int(end)))
                else:
                    pages_to_remove.append(int(part) - 1)
            
            # Validate
            pdf_info = PDFProcessor.get_pdf_info(pdf_path)
            valid_pages = [p for p in pages_to_remove if 0 <= p < pdf_info['pages']]
            
            if not valid_pages:
                raise ValueError("No valid pages")
            
            if len(valid_pages) >= pdf_info['pages']:
                await update.message.reply_text(
                    "⚠️ Cannot remove all pages! At least one page must remain.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            session['waiting_for'] = None
            
            status_msg = await update.message.reply_text(
                f"⏳ **Removing {len(valid_pages)} page(s)...**",
                parse_mode=ParseMode.MARKDOWN
            )
            
            output_path = os.path.join(temp_dir, f"pages_removed_{filename}")
            
            removed_count, new_count = PDFProcessor.remove_pages(pdf_path, output_path, valid_pages)
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"pages_removed_{filename}",
                caption=f"✅ **Pages Removed!**\n\n"
                       f"🗑️ Removed: {removed_count} pages\n"
                       f"📄 Remaining: {new_count} pages",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                "✅ **Pages removed successfully!**\n\n📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except ValueError as e:
            pdf_info = PDFProcessor.get_pdf_info(pdf_path)
            await update.message.reply_text(
                f"⚠️ Invalid format. Please use:\n\n"
                f"• Single pages: `1, 3, 5`\n"
                f"• Ranges: `1-5`\n"
                f"• Mixed: `1, 3-5, 8`\n\n"
                f"Valid pages: 1 to {pdf_info['pages']}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await update.message.reply_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # HEADER TEXT
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'header_text':
        session['waiting_for'] = None
        
        status_msg = await update.message.reply_text(
            "⏳ **Adding header...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"header_{filename}")
            
            PDFProcessor.add_branding(
                pdf_path, output_path,
                header_text=text,
                page_numbers=False
            )
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"header_{filename}",
                caption=f"✅ **Header Added!**\n\n📝 Text: `{text}`",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                "✅ **Header added successfully!**\n\n📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # FOOTER TEXT
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'footer_text':
        session['waiting_for'] = None
        
        status_msg = await update.message.reply_text(
            "⏳ **Adding footer...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"footer_{filename}")
            
            PDFProcessor.add_branding(
                pdf_path, output_path,
                footer_text=text,
                page_numbers=True
            )
            
            session['pdf_path'] = output_path
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"footer_{filename}",
                caption=f"✅ **Footer Added!**\n\n📝 Text: `{text}`",
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                "✅ **Footer added successfully!**\n\n📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # BRAND ALL - HEADER
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'brand_header_all':
        session['brand_header'] = text if text != "-" else ""
        session['waiting_for'] = 'brand_footer_all'
        
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="add_branding")]]
        
        await update.message.reply_text(
            f"✅ Header: `{text if text != '-' else '(none)'}`\n\n"
            "**Step 2/2:** Send footer text\n\n"
            "(or send `-` to skip footer)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ═══════════════════════════════════════════════════════════════════
    # BRAND ALL - FOOTER
    # ═══════════════════════════════════════════════════════════════════
    if waiting_for == 'brand_footer_all':
        session['waiting_for'] = None
        footer_text = text if text != "-" else ""
        header_text = session.get('brand_header', '')
        
        status_msg = await update.message.reply_text(
            "⏳ **Adding branding...**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            output_path = os.path.join(temp_dir, f"branded_{filename}")
            
            PDFProcessor.add_branding(
                pdf_path, output_path,
                header_text=header_text,
                footer_text=footer_text,
                page_numbers=True
            )
            
            session['pdf_path'] = output_path
            
            caption = "✅ **Branding Added!**\n\n"
            if header_text:
                caption += f"📝 Header: `{header_text}`\n"
            if footer_text:
                caption += f"📝 Footer: `{footer_text}`\n"
            caption += "🔢 Page numbers: Added"
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(output_path, 'rb'),
                filename=f"branded_{filename}",
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                "✅ **Branding added successfully!**\n\n📤 Your PDF has been sent above ⬆️",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
        except Exception as e:
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]]
            await status_msg.edit_text(
                f"❌ **Error:**\n\n`{str(e)}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                         ERROR HANDLER                                         ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    print(f"Error: {context.error}")
    traceback.print_exc()
    
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ An error occurred. Please try again or send /start to restart.",
                parse_mode=ParseMode.MARKDOWN
            )
    except:
        pass

# ╔═══════════════════════════════════════════════════════════════════════════════╗
# ║                              MAIN                                             ║
# ╚═══════════════════════════════════════════════════════════════════════════════╝

async def main():
    """Main function to run the bot"""
    print("🚀 Starting Ultimate PDF Master Bot...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    # Document handler
    application.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Text message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    print("✅ Bot is ready!")
    print("📱 Send /start to your bot to begin")
    print("=" * 50)
    
    # Start polling
    await application.run_polling(drop_pending_updates=True)

# Run the bot
if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
else:
    # For Google Colab
    asyncio.get_event_loop().run_until_complete(main())
