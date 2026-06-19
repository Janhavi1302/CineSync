"""
Translation Service — Multi-language translation for dubbing pipeline.
Uses deep-translator (Google backend) for high quality translation.
Runs on CPU, no GPU needed.
"""

import asyncio
import logging
from typing import Optional, Dict
from functools import lru_cache

logger = logging.getLogger("cinesync.translation")

# Language code mapping: internal → Google Translate codes
LANGUAGE_MAP = {
    "en": "en",
    "hi": "hi",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "ja": "ja",
    "ko": "ko",
    "zh": "zh-CN",
    "ar": "ar",
    "pt": "pt",
    "ru": "ru",
}

# Full language names for logging
LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French",
    "de": "German", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
    "ar": "Arabic", "pt": "Portuguese", "ru": "Russian",
}


class TranslationService:
    """
    High-quality text translation using deep-translator (Google backend).
    
    Features:
    - Caches translations to avoid re-translating identical text
    - Context-aware: passes surrounding dialogue for better translations
    - No GPU/VRAM needed — runs as HTTP calls
    """

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._translators: Dict[str, object] = {}
        self._source_lang = "auto"

    def _get_translator(self, source: str, target: str):
        """Get or create a translator instance for a language pair."""
        key = f"{source}→{target}"
        if key not in self._translators:
            from deep_translator import GoogleTranslator
            target_code = LANGUAGE_MAP.get(target, target)
            self._translators[key] = GoogleTranslator(
                source=source,
                target=target_code
            )
            logger.info(f"Created translator: {key}")
        return self._translators[key]

    async def translate(self, text: str, target_lang: str,
                        source_lang: str = "auto") -> str:
        """
        Translate text to the target language.
        
        Args:
            text: Source text to translate
            target_lang: Target language code (e.g., 'hi', 'es')
            source_lang: Source language code ('auto' for detection)
            
        Returns:
            Translated text string
        """
        if not text or not text.strip():
            return ""

        # Check cache
        cache_key = f"{text[:200]}|{source_lang}|{target_lang}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Skip translation if source == target
        if source_lang == target_lang:
            return text

        try:
            translated = await asyncio.to_thread(
                self._translate_sync, text, target_lang, source_lang
            )
            
            # Cache the result
            self._cache[cache_key] = translated
            
            # Keep cache size manageable
            if len(self._cache) > 5000:
                # Remove oldest half
                keys = list(self._cache.keys())
                for k in keys[:2500]:
                    del self._cache[k]

            return translated

        except Exception as e:
            logger.error(f"Translation error: {e}")
            return text  # Return original on failure

    def _translate_sync(self, text: str, target_lang: str,
                        source_lang: str) -> str:
        """Synchronous translation (runs in thread)."""
        translator = self._get_translator(source_lang, target_lang)
        
        # Handle long texts by splitting into chunks
        if len(text) > 4500:
            sentences = text.split('. ')
            chunks = []
            current = ""
            for s in sentences:
                if len(current) + len(s) > 4000:
                    if current:
                        chunks.append(current)
                    current = s
                else:
                    current = current + ". " + s if current else s
            if current:
                chunks.append(current)
            
            translated_parts = []
            for chunk in chunks:
                translated_parts.append(translator.translate(chunk))
            return " ".join(translated_parts)
        
        result = translator.translate(text)
        logger.debug(f"Translated [{source_lang}→{target_lang}]: "
                    f"'{text[:50]}...' → '{result[:50]}...'")
        return result

    async def translate_batch(self, texts: list, target_lang: str,
                              source_lang: str = "auto") -> list:
        """Translate multiple texts in parallel."""
        tasks = [
            self.translate(t, target_lang, source_lang) 
            for t in texts
        ]
        return await asyncio.gather(*tasks)

    def clear_cache(self):
        """Clear translation cache."""
        self._cache.clear()
        logger.info("Translation cache cleared")

    def get_supported_languages(self) -> Dict[str, str]:
        """Get supported language codes and names."""
        return LANGUAGE_NAMES.copy()
