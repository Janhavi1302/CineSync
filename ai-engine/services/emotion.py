"""
Emotion Classifier — Text-based emotion detection for dialogue.
Runs on CPU (no VRAM needed). Classifies the emotional tone of transcribed speech.
"""

import logging
import re
from typing import Dict, Optional, Tuple

logger = logging.getLogger("cinesync.emotion")

# Keyword-based emotion classification (fast, no GPU required)
EMOTION_KEYWORDS = {
    "anger": [
        "angry", "furious", "rage", "hate", "damn", "hell", "kill",
        "shut up", "get out", "enough", "stop", "terrible", "disgusting",
        "idiot", "stupid", "fool", "bastard", "die", "destroy"
    ],
    "sadness": [
        "sad", "sorry", "miss", "cry", "tears", "lost", "gone",
        "alone", "hurt", "pain", "broken", "dying", "dead", "death",
        "funeral", "goodbye", "farewell", "never again", "forgive"
    ],
    "joy": [
        "happy", "love", "great", "wonderful", "amazing", "beautiful",
        "laugh", "smile", "celebrate", "win", "perfect", "best",
        "excited", "fantastic", "brilliant", "incredible", "blessed"
    ],
    "fear": [
        "scared", "afraid", "terror", "horror", "run", "hide",
        "danger", "help", "please", "no", "panic", "scream",
        "dark", "monster", "nightmare", "trapped", "escape"
    ],
    "surprise": [
        "wow", "what", "oh", "really", "impossible", "unbelievable",
        "shocked", "unexpected", "sudden", "cant believe", "how",
        "why", "incredible", "amazing", "omg"
    ],
    "excitement": [
        "yes", "lets go", "come on", "now", "fast", "hurry",
        "ready", "fight", "charge", "attack", "run", "quick",
        "move", "action", "go go", "finally"
    ],
    "neutral": []
}

# Intensity modifiers
INTENSITY_AMPLIFIERS = ["very", "extremely", "so", "really", "absolutely", "totally", "completely"]
INTENSITY_DAMPENERS = ["slightly", "a bit", "somewhat", "kind of", "maybe"]


class EmotionClassifier:
    """
    Lightweight text-based emotion classifier.
    
    Uses keyword matching + intensity analysis for real-time
    emotion detection. No GPU required.
    
    For the MVP, this replaces heavy audio-based emotion models
    (like StyleTTS2) that would exceed the 4GB VRAM budget.
    """

    def __init__(self):
        self._emotion_cache: Dict[str, Tuple[str, float]] = {}
        self._transformer_model = None

    def load(self):
        """
        Optionally load a lightweight transformer model for better accuracy.
        Falls back to keyword matching if not available.
        """
        try:
            from transformers import pipeline
            self._transformer_model = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                device=-1  # CPU
            )
            logger.info("Emotion classifier loaded (distilroberta, CPU)")
        except (ImportError, Exception):
            logger.info("Emotion classifier using keyword-based mode")

    def classify(self, text: str) -> Tuple[str, float]:
        """
        Classify the emotion of a text segment.
        
        Returns:
            Tuple of (emotion_label, confidence)
        """
        if not text or not text.strip():
            return ("neutral", 0.0)

        # Check cache
        cache_key = text[:100].lower()
        if cache_key in self._emotion_cache:
            return self._emotion_cache[cache_key]

        # Try transformer model first
        if self._transformer_model is not None:
            result = self._classify_transformer(text)
        else:
            result = self._classify_keywords(text)

        self._emotion_cache[cache_key] = result
        return result

    def _classify_transformer(self, text: str) -> Tuple[str, float]:
        """Classify using the transformer model."""
        try:
            results = self._transformer_model(text[:512])
            if results:
                label = results[0]["label"].lower()
                score = results[0]["score"]
                return (label, round(score, 2))
        except Exception as e:
            logger.debug(f"Transformer classification failed: {e}")
        return self._classify_keywords(text)

    def _classify_keywords(self, text: str) -> Tuple[str, float]:
        """Classify using keyword matching."""
        text_lower = text.lower()
        words = re.findall(r'\w+', text_lower)
        word_set = set(words)

        scores = {}
        for emotion, keywords in EMOTION_KEYWORDS.items():
            if emotion == "neutral":
                continue
            
            match_count = 0
            for kw in keywords:
                if " " in kw:
                    if kw in text_lower:
                        match_count += 1.5
                elif kw in word_set:
                    match_count += 1

            if match_count > 0:
                scores[emotion] = match_count

        if not scores:
            return ("neutral", 0.5)

        # Apply intensity modifiers
        intensity = 1.0
        for amp in INTENSITY_AMPLIFIERS:
            if amp in word_set:
                intensity *= 1.3
                break
        for damp in INTENSITY_DAMPENERS:
            if damp in word_set:
                intensity *= 0.7
                break

        # Exclamation/question marks boost intensity
        if "!" in text:
            intensity *= 1.2
        if "?" in text and any(e in scores for e in ["surprise", "fear"]):
            intensity *= 1.15

        # ALL CAPS detection
        caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
        if caps_ratio > 0.5:
            intensity *= 1.3

        best_emotion = max(scores, key=scores.get)
        raw_score = scores[best_emotion]
        confidence = min(0.95, (raw_score / 5.0) * intensity)

        return (best_emotion, round(confidence, 2))

    def get_cinematic_intensity(self, text: str) -> float:
        """
        Calculate overall cinematic intensity (0-1).
        Useful for the debug overlay to show scene tension.
        """
        _, conf = self.classify(text)
        text_lower = text.lower()

        # Boost for action words
        action_words = ["explosion", "gun", "fight", "chase", "crash", "fire", "bomb"]
        action_score = sum(1 for w in action_words if w in text_lower) * 0.15

        # Boost for exclamation marks
        excl_score = min(0.3, text.count("!") * 0.1)

        return min(1.0, conf + action_score + excl_score)
