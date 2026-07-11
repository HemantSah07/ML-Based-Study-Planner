import hashlib
import logging
import json
from flask import current_app
from app import db
from app.models import AICache, Subject, LearningMaterial, Topic, Chapter, Flashcard

logger = logging.getLogger(__name__)


def _get_adaptive_quiz_difficulty(profile) -> str:
    """
    System-calculated quiz difficulty based on the student's mastery/risk level.

    Logic:
    - 'high' risk  → Easy   (lower barrier to build confidence)
    - 'medium' risk → Medium (standard difficulty)
    - 'low' risk   → Hard   (challenge strong performers)
    Falls back to 'Medium' when no risk data is available.

    This replaces the old manual quiz_difficulty field on StudentProfile.
    """
    if not profile:
        return "Medium"

    # Prefer the pre-computed risk_summary from the learning context if passed directly
    risk = getattr(profile, '_risk_summary', None)

    # Fallback: read from the profile's latest prediction record
    if not risk:
        try:
            from app.models import Prediction
            latest_pred = (
                Prediction.query
                .filter_by(student_id=profile.user_id)
                .order_by(Prediction.predicted_at.desc())
                .first()
            )
            if latest_pred:
                label = (latest_pred.result or "").lower()
                if "fail" in label:
                    risk = "high"
                elif "risk" in label or "at risk" in label:
                    risk = "medium"
                else:
                    risk = "low"
        except Exception:
            risk = "medium"

    mapping = {"high": "Easy", "medium": "Medium", "low": "Hard"}
    return mapping.get(risk or "medium", "Medium")


def _get_system_response_length(profile) -> str:
    """
    System-determined response length.  
    Defaults to 'Medium' unless the student is at high risk
    (shorter, more digestible chunks) or the explanation_level is
    'Master' (which warrants more detail).
    """
    if not profile:
        return "Medium"
    risk = getattr(profile, '_risk_summary', None)
    if risk == "high":
        return "Short"
    exp = getattr(profile, 'explanation_level', 'Intermediate') or 'Intermediate'
    if exp == "Master":
        return "Detailed"
    return "Medium"


class AIService:
    def __init__(self):
        self._provider = None
        self._claude_provider = None
        self._initialized = False

    def _get_claude(self):
        """Lazy-initialize the Claude (Anthropic) provider."""
        if self._claude_provider is None:
            api_key = current_app.config.get("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    from app.services.providers.claude import ClaudeProvider
                    self._claude_provider = ClaudeProvider(api_key)
                    logger.info("ClaudeProvider initialized successfully.")
                except Exception as e:
                    logger.error(f"Failed to initialize ClaudeProvider: {e}")
        return self._claude_provider

    def _get_provider(self):
        if not self._initialized:
            # Lazy initialize to access Flask current_app config safely
            api_key = current_app.config.get("GEMINI_API_KEY")
            if api_key:
                try:
                    from app.services.providers.gemini import GeminiProvider
                    self._provider = GeminiProvider(api_key)
                    self._initialized = True
                except Exception as e:
                    logger.error(f"Failed to initialize GeminiProvider: {e}")
            else:
                logger.warning("GEMINI_API_KEY not configured in app config. Running in fallback/offline mode.")
            self._initialized = True
        return self._provider

    def _get_cache(self, prompt: str) -> str:
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        try:
            cached = AICache.query.filter_by(prompt_hash=prompt_hash).first()
            if cached:
                logger.info("AICache hit.")
                return cached.response_text
        except Exception as e:
            logger.error(f"Failed to read from AICache: {e}")
        return None

    def _set_cache(self, prompt: str, response_text: str):
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        try:
            cached = AICache(prompt_hash=prompt_hash, prompt=prompt, response_text=response_text)
            db.session.add(cached)
            db.session.commit()
            logger.info("Saved to AICache.")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to save to AICache: {e}")

    def generate_content(self, prompt: str, **kwargs) -> str:
        """Core generation method that tunnels kwargs down to providers."""
        # 1. Check local database cache
        cached_response = self._get_cache(prompt)
        if cached_response:
            return cached_response
            
        # 2. Retrieve underlying provider
        provider = self._get_provider()
        if not provider:
            raise RuntimeError("AI Provider is not configured or unavailable.")
            
        # 3. Call the provider (passes kwargs containing system_instruction safely)
        response_text = provider.generate_content(prompt, **kwargs)
        
        # 4. Save to cache
        self._set_cache(prompt, response_text)
        return response_text

    def chat_with_tutor(self, user_query: str, subject_id: int = None, profile=None) -> str:
        try:
            subj_name = ""
            if subject_id:
                s = Subject.query.get(subject_id)
                if s:
                    subj_name = f" in the context of {s.name} ({s.level_of_study})"
            
            # ── System-derived settings (no longer stored as manual preferences) ──
            adaptive_difficulty = _get_adaptive_quiz_difficulty(profile)
            response_length     = _get_system_response_length(profile)

            context = ""
            if profile:
                context += f"\n- Education Level: {profile.level_of_study}"
                context += f"\n- Country: {profile.country}"
                context += f"\n- Curriculum: {profile.curriculum}"
                if profile.program:
                    context += f"\n- Faculty/Program: {profile.program}"
                if profile.semester:
                    context += f"\n- Semester/Year: {profile.semester}"
                context += f"\n- Preferred Explanation Level: {profile.explanation_level}"
                context += f"\n- Study Goal: {profile.study_goal}"
                context += f"\n- Preferred Output Language: {profile.preferred_language}"
                # System-calculated (not user-controlled)
                context += f"\n- [System] Adaptive Response Length: {response_length}"
                context += f"\n- [System] Adaptive Quiz Difficulty: {adaptive_difficulty}"
            
            system_prompt = (
                "You are Antigravity, a highly personalized, elite Academic AI Tutor. "
                "Help the student by explaining concepts, summarizing chapters, generating quizzes/flashcards, "
                "outlining revision notes, recommending study plans, explaining mistakes, or giving motivational study advice.\n"
                f"Student Profile Context: {context}\n\n"
                "Conform strictly to the explanation level, output language, and study goals listed above. "
                "When generating quizzes, use the [System] Adaptive Quiz Difficulty level specified."
            )
            
            prompt = f"Subject: {subj_name}\nQuestion: {user_query}"
            
            # Utilizing enhanced kwargs implementation to cleanly mount the prompt context instructions
            return self.generate_content(prompt, system_instruction=system_prompt)
        except Exception as e:
            logger.error(f"Tutor chat failed. Engaging local fallback: {e}")
            return self._local_fallback_tutor(user_query, subject_id)

    def chat_with_history(self, history: list, user_query: str,
                          subject_id: int = None, profile=None) -> str:
        """Multi-turn conversation using Claude with a clean layout fallback to Gemini."""
        subj_name = ""
        if subject_id:
            s = Subject.query.get(subject_id)
            if s:
                subj_name = f" — Focus on: {s.name} ({s.level_of_study})"

        # ── System-derived settings ───────────────────────────────────────────
        adaptive_difficulty = _get_adaptive_quiz_difficulty(profile)
        response_length     = _get_system_response_length(profile)

        ctx_lines = []
        if profile:
            ctx_lines += [
                f"Education Level: {getattr(profile, 'level_of_study', 'N/A')}",
                f"Curriculum: {getattr(profile, 'curriculum', 'N/A')}",
                f"Explanation Level: {getattr(profile, 'explanation_level', 'Intermediate')}",
                f"Study Goal: {getattr(profile, 'study_goal', 'Improve Grades')}",
                f"Language Preference: {getattr(profile, 'preferred_language', 'English')}",
                # System-calculated — not stored as manual prefs
                f"[System] Adaptive Response Length: {response_length}",
                f"[System] Adaptive Quiz Difficulty: {adaptive_difficulty}",
            ]
            if getattr(profile, 'program', None):
                ctx_lines.append(f"Program/Faculty: {profile.program}")
            if getattr(profile, 'semester', None):
                ctx_lines.append(f"Semester/Year: {profile.semester}")

        system_prompt = (
            "You are SmartStudy AI — a highly personalized academic tutor built for students "
            "from Class 6 to Master level following Nepal's CDC/NEB/University curriculum.\n\n"
            "Your responsibilities:\n"
            "• Explain concepts clearly and concisely\n"
            "• Generate quizzes, flashcards, revision notes on request\n"
            "• Provide step-by-step worked solutions\n"
            "• Give motivational study advice when needed\n"
            "• Respond in the student's preferred language (English/Nepali/Bilingual)\n"
            "• When generating quizzes, match the [System] Adaptive Quiz Difficulty level\n\n"
            f"Student Profile:\n" + "\n".join(f"  - {l}" for l in ctx_lines) +
            f"\n{subj_name}"
        )

        messages = list(history)  
        messages.append({"role": "user", "content": user_query})

        # 1. Primary route: Try Anthropic Claude
        try:
            claude = self._get_claude()
            if claude:
                return claude.chat(messages, system=system_prompt)
        except Exception as e:
            logger.warning(f"Claude interaction flagged or missing setup, shifting to Gemini: {e}")

        # 2. Secondary fallback route: Gemini 2.5 Flash setup
        try:
            context_history = ""
            for turn in messages:
                role = "Student" if turn["role"] == "user" else "Tutor"
                context_history += f"\n{role}: {turn['content']}"
            
            return self.generate_content(
                prompt=f"Conversation Context:{context_history}\n\nTutor:",
                system_instruction=system_prompt
            )
        except Exception as e:
            logger.error(f"All dynamic cloud infrastructure platforms timed out: {e}")
            return self._local_fallback_tutor(user_query, subject_id)

    def _local_fallback_tutor(self, user_query: str, subject_id: int = None) -> str:
        """Static rule engine executing emergency assistance if all live connections time out."""
        return (
            "### ⚠️ Local Sync Mode Active\n"
            "Your SmartStudy engine cannot process cloud requests right now. "
            "Please review your saved local materials, textbook outlines, or try sending your chat query again shortly!"
        )

# --- INSTANTIATE THE GLOBAL SERVICE OBJECT FOR ROUTE IMPORTS ---
ai_service = AIService()
