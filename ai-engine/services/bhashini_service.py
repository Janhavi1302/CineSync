"""
Bhashini Service — Indian Government AI platform for Indian language dubbing.
Provides ASR, NMT (Translation), and TTS via the Dhruva API.

Key advantages over Edge TTS + Google Translate for Indian languages:
- Higher quality Indian language TTS (AI4Bharat models)
- Better en↔Indian language translation (IndicTrans v2)
- Free / government-subsidized API
- Multiple male/female voices per language

Setup:
1. Register at https://bhashini.gov.in/ulca/user/register
2. Get credentials from profile → My Profile → Generate API Keys
3. Set env vars: BHASHINI_USER_ID, BHASHINI_API_KEY, BHASHINI_INFERENCE_KEY
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import tempfile
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("cinesync.bhashini")

# ── Bhashini API Endpoints ──
PIPELINE_CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
INFERENCE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

# ── Supported Indian Languages ──
BHASHINI_LANGUAGES = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "gu": "Gujarati",
    "mr": "Marathi",
    "pa": "Punjabi",
    "or": "Odia",
    "as": "Assamese",
    "ur": "Urdu",
    "en": "English",
}

# ── TTS Voice Gender Options ──
BHASHINI_TTS_GENDER = {
    "male": "male",
    "female": "female",
}


class BhashiniService:
    """
    Unified Bhashini service for Translation + TTS.
    
    Uses the Dhruva inference pipeline to chain:
    - Translation (NMT): en → Indian language
    - TTS: text → audio (base64 WAV)
    
    Falls back to deep-translator + edge-tts if Bhashini is unavailable.
    """

    def __init__(self):
        self._user_id = os.getenv("BHASHINI_USER_ID", "")
        self._api_key = os.getenv("BHASHINI_API_KEY", "")
        self._inference_key = os.getenv("BHASHINI_INFERENCE_KEY", "")
        
        # Service IDs cache (discovered from pipeline config)
        self._service_ids: Dict[str, Dict] = {}
        self._config_fetched = False
        
        # Translation cache
        self._cache: Dict[str, str] = {}
        
        # TTS audio cache
        self._tts_cache: Dict[str, str] = {}
        
        self._available = bool(self._user_id and self._api_key and self._inference_key)
        
        if self._available:
            logger.info("✅ Bhashini service initialized with credentials")
        else:
            logger.warning(
                "⚠️ Bhashini credentials not found. "
                "Set BHASHINI_USER_ID, BHASHINI_API_KEY, BHASHINI_INFERENCE_KEY. "
                "Register at: https://bhashini.gov.in/ulca/user/register"
            )

    @property
    def is_available(self) -> bool:
        return self._available

    # ── Pipeline Configuration ──
    async def _fetch_pipeline_config(self, source_lang: str, target_lang: str,
                                      tasks: List[str]) -> Dict:
        """Fetch available service IDs for a language pair and task types."""
        import aiohttp

        cache_key = f"{source_lang}_{target_lang}_{'_'.join(tasks)}"
        if cache_key in self._service_ids:
            return self._service_ids[cache_key]

        headers = {
            "userID": self._user_id,
            "ulcaApiKey": self._api_key,
            "Content-Type": "application/json",
        }

        pipeline_tasks = []
        for task in tasks:
            task_config = {"taskType": task}
            if task == "translation":
                task_config["config"] = {
                    "language": {
                        "sourceLanguage": source_lang,
                        "targetLanguage": target_lang,
                    }
                }
            elif task == "tts":
                task_config["config"] = {
                    "language": {"sourceLanguage": target_lang}
                }
            elif task == "asr":
                task_config["config"] = {
                    "language": {"sourceLanguage": source_lang}
                }
            pipeline_tasks.append(task_config)

        payload = {
            "pipelineTasks": pipeline_tasks,
            "pipelineRequestConfig": {
                "pipelineId": "64392f96daac500b55c543cd"
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    PIPELINE_CONFIG_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Bhashini config error ({resp.status}): {error_text[:200]}")
                        return {}
                    
                    data = await resp.json()
                    
            # Extract service IDs and inference endpoint
            result = {
                "inferenceEndpoint": INFERENCE_URL,
                "services": {}
            }

            pipeline_response = data.get("pipelineResponseConfig", [])
            for task_resp in pipeline_response:
                task_type = task_resp.get("taskType", "")
                configs = task_resp.get("config", [])
                if configs and isinstance(configs, list):
                    service_id = configs[0].get("serviceId", "")
                    result["services"][task_type] = service_id
                    logger.info(f"Bhashini {task_type} service: {service_id}")

            # Check for custom inference endpoint
            inference_endpoint = data.get("pipelineInferenceAPIEndPoint", {})
            if inference_endpoint.get("callbackUrl"):
                result["inferenceEndpoint"] = inference_endpoint["callbackUrl"]

            # Also store the inference key from response if provided
            api_key = inference_endpoint.get("inferenceApiKey", {})
            if api_key.get("value"):
                result["inferenceApiKey"] = api_key["value"]

            self._service_ids[cache_key] = result
            self._config_fetched = True
            logger.info(f"Bhashini pipeline configured: {source_lang}→{target_lang}")
            return result

        except Exception as e:
            logger.error(f"Bhashini config fetch error: {e}")
            return {}

    # ── Translation ──
    async def translate(self, text: str, target_lang: str,
                        source_lang: str = "en") -> Optional[str]:
        """
        Translate text using Bhashini NMT (IndicTrans v2).
        
        Returns None if Bhashini is unavailable (caller should fallback).
        """
        if not self._available:
            return None

        if not text or not text.strip():
            return ""

        # Only supported for Indian languages
        if target_lang not in BHASHINI_LANGUAGES:
            return None

        # Cache check
        cache_key = f"nmt|{text[:200]}|{source_lang}|{target_lang}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Get service config
        config = await self._fetch_pipeline_config(
            source_lang, target_lang, ["translation"]
        )
        if not config or "translation" not in config.get("services", {}):
            logger.warning(f"No Bhashini translation service for {source_lang}→{target_lang}")
            return None

        service_id = config["services"]["translation"]
        endpoint = config.get("inferenceEndpoint", INFERENCE_URL)
        inference_key = config.get("inferenceApiKey", self._inference_key)

        headers = {
            "Authorization": inference_key,
            "Content-Type": "application/json",
        }

        payload = {
            "pipelineTasks": [{
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_lang,
                        "targetLanguage": target_lang,
                    },
                    "serviceId": service_id,
                }
            }],
            "inputData": {
                "input": [{"source": text}]
            }
        }

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Bhashini translate error ({resp.status}): {error_text[:200]}")
                        return None

                    data = await resp.json()

            # Extract translated text
            pipeline_resp = data.get("pipelineResponse", [])
            if pipeline_resp:
                outputs = pipeline_resp[0].get("output", [])
                if outputs:
                    translated = outputs[0].get("target", "")
                    if translated:
                        self._cache[cache_key] = translated
                        logger.debug(f"Bhashini NMT [{source_lang}→{target_lang}]: "
                                    f"'{text[:40]}' → '{translated[:40]}'")
                        return translated

            return None

        except Exception as e:
            logger.error(f"Bhashini translation error: {e}")
            return None

    # ── TTS ──
    async def synthesize(self, text: str, language: str,
                          gender: str = "female") -> Optional[str]:
        """
        Synthesize speech using Bhashini TTS (AI4Bharat voices).
        
        Returns path to generated WAV file, or None if unavailable.
        """
        if not self._available:
            return None

        if not text or not text.strip():
            return None

        # Only supported for Indian languages
        if language not in BHASHINI_LANGUAGES or language == "en":
            return None

        # Cache check
        cache_key = f"tts|{hashlib.md5(text.encode()).hexdigest()}|{language}|{gender}"
        if cache_key in self._tts_cache:
            path = self._tts_cache[cache_key]
            if os.path.exists(path):
                return path

        # Get service config
        config = await self._fetch_pipeline_config(
            language, language, ["tts"]
        )
        if not config or "tts" not in config.get("services", {}):
            logger.warning(f"No Bhashini TTS service for {language}")
            return None

        service_id = config["services"]["tts"]
        endpoint = config.get("inferenceEndpoint", INFERENCE_URL)
        inference_key = config.get("inferenceApiKey", self._inference_key)

        headers = {
            "Authorization": inference_key,
            "Content-Type": "application/json",
        }

        payload = {
            "pipelineTasks": [{
                "taskType": "tts",
                "config": {
                    "language": {"sourceLanguage": language},
                    "serviceId": service_id,
                    "gender": gender,
                }
            }],
            "inputData": {
                "input": [{"source": text}]
            }
        }

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Bhashini TTS error ({resp.status}): {error_text[:200]}")
                        return None

                    data = await resp.json()

            # Extract audio (base64 encoded)
            pipeline_resp = data.get("pipelineResponse", [])
            if pipeline_resp:
                audio_list = pipeline_resp[0].get("audio", [])
                if audio_list:
                    audio_b64 = audio_list[0].get("audioContent", "")
                    if audio_b64:
                        # Decode and save to temp file
                        audio_bytes = base64.b64decode(audio_b64)
                        suffix = ".wav"
                        fd, output_path = tempfile.mkstemp(
                            suffix=suffix, prefix="bhashini_tts_"
                        )
                        os.close(fd)
                        with open(output_path, "wb") as f:
                            f.write(audio_bytes)

                        self._tts_cache[cache_key] = output_path
                        logger.debug(f"Bhashini TTS [{language}/{gender}]: "
                                    f"'{text[:30]}' → {output_path}")
                        return output_path

            return None

        except Exception as e:
            logger.error(f"Bhashini TTS error: {e}")
            return None

    # ── Combined Pipeline (Translation + TTS in one call) ──
    async def translate_and_speak(self, text: str, source_lang: str,
                                   target_lang: str,
                                   gender: str = "female") -> Optional[Tuple[str, str]]:
        """
        Translate and synthesize in a single Bhashini pipeline call.
        
        Returns (translated_text, audio_path) or None if unavailable.
        This is more efficient than separate translate + TTS calls.
        """
        if not self._available:
            return None

        if target_lang not in BHASHINI_LANGUAGES or target_lang == "en":
            return None

        # Get service config for both tasks
        config = await self._fetch_pipeline_config(
            source_lang, target_lang, ["translation", "tts"]
        )
        services = config.get("services", {})
        if "translation" not in services or "tts" not in services:
            return None

        endpoint = config.get("inferenceEndpoint", INFERENCE_URL)
        inference_key = config.get("inferenceApiKey", self._inference_key)

        headers = {
            "Authorization": inference_key,
            "Content-Type": "application/json",
        }

        payload = {
            "pipelineTasks": [
                {
                    "taskType": "translation",
                    "config": {
                        "language": {
                            "sourceLanguage": source_lang,
                            "targetLanguage": target_lang,
                        },
                        "serviceId": services["translation"],
                    }
                },
                {
                    "taskType": "tts",
                    "config": {
                        "language": {"sourceLanguage": target_lang},
                        "serviceId": services["tts"],
                        "gender": gender,
                    }
                }
            ],
            "inputData": {
                "input": [{"source": text}]
            }
        }

        try:
            import aiohttp
            t0 = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=45)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Bhashini pipeline error ({resp.status}): {error_text[:200]}")
                        return None

                    data = await resp.json()
            elapsed = time.time() - t0

            translated_text = ""
            audio_path = None

            pipeline_resp = data.get("pipelineResponse", [])
            for task_resp in pipeline_resp:
                task_type = task_resp.get("taskType", "")
                
                if task_type == "translation":
                    outputs = task_resp.get("output", [])
                    if outputs:
                        translated_text = outputs[0].get("target", "")

                elif task_type == "tts":
                    audio_list = task_resp.get("audio", [])
                    if audio_list:
                        audio_b64 = audio_list[0].get("audioContent", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            fd, audio_path = tempfile.mkstemp(
                                suffix=".wav", prefix="bhashini_"
                            )
                            os.close(fd)
                            with open(audio_path, "wb") as f:
                                f.write(audio_bytes)

            if translated_text and audio_path:
                logger.info(f"Bhashini pipeline [{source_lang}→{target_lang}] "
                           f"in {elapsed:.1f}s: '{text[:30]}' → '{translated_text[:30]}'")
                return (translated_text, audio_path)

            return None

        except Exception as e:
            logger.error(f"Bhashini pipeline error: {e}")
            return None

    def clear_cache(self):
        """Clear all caches."""
        self._cache.clear()
        # Clean up TTS temp files
        for path in self._tts_cache.values():
            try:
                if os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass
        self._tts_cache.clear()
        logger.info("Bhashini caches cleared")

    @staticmethod
    def get_supported_languages() -> Dict[str, str]:
        return BHASHINI_LANGUAGES.copy()

    @staticmethod
    def get_registration_url() -> str:
        return "https://bhashini.gov.in/ulca/user/register"
