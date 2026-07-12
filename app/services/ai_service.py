import hashlib
import logging
from datetime import date, datetime
from flask import current_app
from app import db
from app.models import AICache, DailyAPIUsage, Subject, LearningMaterial, Topic, Chapter, Flashcard

logger = logging.getLogger(__name__)

import time
from threading import Lock

class SlidingWindowLimiter:
    def __init__(self):
        self._calls = []  # list of float timestamps
        self._lock = Lock()

    def record_call(self):
        now = time.time()
        with self._lock:
            self._calls.append(now)
            self._clean(now)

    def _clean(self, now):
        cutoff = now - 60.0
        self._calls = [t for t in self._calls if t > cutoff]

    def get_count(self) -> int:
        now = time.time()
        with self._lock:
            self._clean(now)
            return len(self._calls)


# Rate limiters for each model / feature
mcq_limiter = SlidingWindowLimiter()
assistant_primary_limiter = SlidingWindowLimiter()


# ── Feature identifiers ────────────────────────────────────────────────────────
FEATURE_MCQ       = "mcq"        # Assessment MCQ generation
FEATURE_ASSISTANT = "assistant"  # AI tutoring chat


class QuotaExceededError(Exception):
    """Raised when a feature's daily API call limit is reached."""
    def __init__(self, feature: str):
        self.feature = feature
        super().__init__(f"Daily quota exceeded for feature '{feature}'")


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

    # ── Provider helpers ───────────────────────────────────────────────────────

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
            api_key = current_app.config.get("GEMINI_API_KEY")
            if api_key:
                try:
                    from app.services.providers.gemini import GeminiProvider
                    self._provider = GeminiProvider(api_key)
                    self._initialized = True
                except Exception as e:
                    logger.error(f"Failed to initialize GeminiProvider: {e}")
            else:
                logger.warning("GEMINI_API_KEY not configured. Running in fallback/offline mode.")
            self._initialized = True
        return self._provider

    # ── Daily quota helpers ────────────────────────────────────────────────────

    def _quota_limit(self, feature: str, model_name: str) -> int:
        """Return the configured daily call limit for *feature* and *model_name*."""
        if feature == FEATURE_MCQ:
            return current_app.config.get("GEMINI_DAILY_LIMIT_MCQ", 450)
        if feature == FEATURE_ASSISTANT:
            primary_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-2.5-flash")
            fallback_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-2.5-flash-lite")
            if model_name == primary_model:
                return current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_PRIMARY", 45)
            elif model_name == fallback_model:
                return current_app.config.get("GEMINI_DAILY_LIMIT_ASSISTANT_FALLBACK", 45)
        return 999  # unknown feature/model → uncapped

    def _today_usage(self, feature: str, model_name: str) -> int:
        """Return how many calls this feature + model has made today (UTC date)."""
        today = date.today()
        try:
            row = DailyAPIUsage.query.filter_by(feature=feature, model_name=model_name, usage_date=today).first()
            return row.call_count if row else 0
        except Exception as e:
            logger.error("Error reading daily usage for '%s' (%s): %s", feature, model_name, e)
            return 0

    def _check_quota(self, feature: str, model_name: str):
        """
        Raise QuotaExceededError if the daily limit is reached AND billing
        is not enabled. If feature is 'mcq', check the per-minute limit too.
        """
        billing_on = current_app.config.get("GEMINI_BILLING_ENABLED", False)
        if billing_on:
            return  # paid tier — no cap

        # 1. Daily usage check
        usage = self._today_usage(feature, model_name)
        limit = self._quota_limit(feature, model_name)
        if usage >= limit:
            logger.warning(
                "Daily quota reached for feature='%s' model='%s': %d/%d calls used today.",
                feature, model_name, usage, limit,
            )
            raise QuotaExceededError(feature)

        # 2. RPM check for MCQ
        if feature == FEATURE_MCQ:
            rpm_limit = current_app.config.get("GEMINI_RPM_LIMIT_MCQ", 10)
            current_rpm = mcq_limiter.get_count()
            if current_rpm >= rpm_limit:
                logger.warning(
                    "RPM limit reached for MCQ feature: %d/%d calls in last 60 seconds.",
                    current_rpm, rpm_limit,
                )
                raise RuntimeError("Assessment generation rate limit reached. Please try again in a moment.")

    def _increment_usage(self, feature: str, model_name: str):
        """
        Atomically increment the daily call counter for *feature* and *model_name*.
        """
        today = date.today()
        try:
            # Attempt 1: insert new row (first call of the day)
            with db.session.begin_nested():
                db.session.add(
                    DailyAPIUsage(feature=feature, model_name=model_name, usage_date=today, call_count=1)
                )
            db.session.commit()
        except Exception:
            # Row already exists — do a single atomic increment at DB level
            try:
                db.session.execute(
                    db.update(DailyAPIUsage)
                    .where(
                        DailyAPIUsage.feature    == feature,
                        DailyAPIUsage.model_name == model_name,
                        DailyAPIUsage.usage_date == today,
                    )
                    .values(call_count=DailyAPIUsage.call_count + 1)
                )
                db.session.commit()
            except Exception as e:
                logger.error("Failed to atomically increment usage for '%s' (%s): %s", feature, model_name, e)

    # ── Cache helpers ──────────────────────────────────────────────────────────

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
            exists = AICache.query.filter_by(prompt_hash=prompt_hash).first()
            if exists:
                logger.debug("AICache: entry already present, skipping insert.")
                return
            with db.session.begin_nested():
                cached = AICache(prompt_hash=prompt_hash, prompt=prompt, response_text=response_text)
                db.session.add(cached)
            db.session.commit()
            logger.info("Saved to AICache.")
        except Exception as e:
            logger.error(f"Failed to save to AICache: {e}")

    # ── Core generation ────────────────────────────────────────────────────────

    def generate_content(self, prompt: str, feature: str = FEATURE_ASSISTANT, **kwargs) -> str:
        """
        Core generation method.

        Parameters
        ----------
        prompt   : the text sent to the model
        feature  : 'mcq' or 'assistant' — controls model selection and quota
        **kwargs : forwarded to the provider (system_instruction, response_schema, …)

        Raises
        ------
        QuotaExceededError  if the daily cap is reached and billing is off
        RuntimeError        if no provider is configured
        """
        # 1. Check local database cache (cache hits don't count against quota/rate limits)
        cached_response = self._get_cache(prompt)
        if cached_response:
            return cached_response

        billing_on = current_app.config.get("GEMINI_BILLING_ENABLED", False)

        if feature == FEATURE_MCQ:
            model = current_app.config.get("GEMINI_MODEL_MCQ", "gemini-3.1-flash-lite")
            
            # Enforce daily limit and per-minute limit
            self._check_quota(FEATURE_MCQ, model)

            # Retrieve provider
            provider = self._get_provider()
            if not provider:
                raise RuntimeError("AI Provider is not configured or unavailable.")

            # Make the call
            kwargs_mcq = dict(kwargs)
            kwargs_mcq["model"] = model
            response_text = provider.generate_content(prompt, **kwargs_mcq)

            # Increment daily counter and RPM limiter
            self._increment_usage(FEATURE_MCQ, model)
            mcq_limiter.record_call()

            # Cache the response
            self._set_cache(prompt, response_text)
            return response_text

        else:  # FEATURE_ASSISTANT
            primary_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-2.5-flash")
            fallback_model = current_app.config.get("GEMINI_MODEL_ASSISTANT_FALLBACK", "gemini-2.5-flash-lite")

            use_primary = True
            if not billing_on:
                # Check daily limit for primary
                p_usage = self._today_usage(FEATURE_ASSISTANT, primary_model)
                p_limit = self._quota_limit(FEATURE_ASSISTANT, primary_model)
                
                # Check RPM limit for primary
                p_rpm = assistant_primary_limiter.get_count()
                p_rpm_limit = current_app.config.get("GEMINI_RPM_LIMIT_ASSISTANT_PRIMARY", 4)

                if p_usage >= p_limit or p_rpm >= p_rpm_limit:
                    use_primary = False
                    logger.info(
                        "Assistant primary model limit reached (usage: %d/%d, RPM: %d/%d). "
                        "Falling back to %s.",
                        p_usage, p_limit, p_rpm, p_rpm_limit, fallback_model
                    )

            if use_primary:
                try:
                    # Double-check daily quota using general check
                    self._check_quota(FEATURE_ASSISTANT, primary_model)

                    provider = self._get_provider()
                    if not provider:
                        raise RuntimeError("AI Provider is not configured or unavailable.")

                    kwargs_primary = dict(kwargs)
                    kwargs_primary["model"] = primary_model

                    response_text = provider.generate_content(prompt, **kwargs_primary)

                    # Success on primary
                    self._increment_usage(FEATURE_ASSISTANT, primary_model)
                    assistant_primary_limiter.record_call()
                    self._set_cache(prompt, response_text)
                    return response_text

                except Exception as e:
                    # If daily limit was reached concurrently or we got a live 429, retry on fallback
                    err_str = str(e)
                    is_rate_limit = any(t in err_str for t in ["429", "ResourceExhausted", "Quota", "quota"])
                    if is_rate_limit:
                        logger.warning(
                            "Primary model returned rate limit/429. Retrying with fallback model %s: %s",
                            fallback_model, e
                        )
                        # We will fall through to execute fallback
                    else:
                        raise

            # Fallback model execution
            self._check_quota(FEATURE_ASSISTANT, fallback_model)

            provider = self._get_provider()
            if not provider:
                raise RuntimeError("AI Provider is not configured or unavailable.")

            kwargs_fallback = dict(kwargs)
            kwargs_fallback["model"] = fallback_model

            response_text = provider.generate_content(prompt, **kwargs_fallback)

            # Success on fallback
            self._increment_usage(FEATURE_ASSISTANT, fallback_model)
            self._set_cache(prompt, response_text)
            return response_text

    # ── Tutor helpers ──────────────────────────────────────────────────────────

    def chat_with_tutor(self, user_query: str, subject_id: int = None, profile=None) -> str:
        try:
            subj_name = ""
            if subject_id:
                s = Subject.query.get(subject_id)
                if s:
                    subj_name = f" in the context of {s.name} ({s.level_of_study})"
            
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
            return self.generate_content(prompt, feature=FEATURE_ASSISTANT, system_instruction=system_prompt)
        except QuotaExceededError:
            return (
                "### ⏳ AI Assistant Temporarily at Capacity\n"
                "We've reached today's AI Assistant limit. "
                "Please try again tomorrow — your questions will be answered then!"
            )
        except Exception as e:
            logger.error(f"Tutor chat failed. Engaging local fallback: {e}")
            return self._local_fallback_tutor(user_query, subject_id)

    def chat_with_history(self, history: list, user_query: str,
                          subject_id: int = None, profile=None) -> str:
        """Multi-turn conversation — Claude primary, Gemini fallback."""
        subj_name = ""
        if subject_id:
            s = Subject.query.get(subject_id)
            if s:
                subj_name = f" — Focus on: {s.name} ({s.level_of_study})"

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

        # 1. Primary: Claude (no quota guard — has its own provider key)
        try:
            claude = self._get_claude()
            if claude:
                return claude.chat(messages, system=system_prompt)
        except Exception as e:
            logger.warning(f"Claude unavailable, falling back to Gemini: {e}")

        # 2. Fallback: Gemini (quota-guarded)
        try:
            context_history = ""
            for turn in messages:
                role = "Student" if turn["role"] == "user" else "Tutor"
                context_history += f"\n{role}: {turn['content']}"

            return self.generate_content(
                prompt=f"Conversation Context:{context_history}\n\nTutor:",
                feature=FEATURE_ASSISTANT,
                system_instruction=system_prompt,
            )
        except QuotaExceededError:
            return (
                "### ⏳ AI Assistant Temporarily at Capacity\n"
                "We've reached today's AI Assistant limit. "
                "Please try again tomorrow — your questions will be answered then!"
            )
        except Exception as e:
            logger.error(f"All AI providers failed: {e}")
            return self._local_fallback_tutor(user_query, subject_id)

    def _local_fallback_tutor(self, user_query: str, subject_id: int = None) -> str:
        return (
            "### ⚠️ Local Sync Mode Active\n"
            "Your SmartStudy engine cannot process cloud requests right now. "
            "Please review your saved local materials, textbook outlines, or try sending your chat query again shortly!"
        )

    # ── Quota status helper (for templates/admin) ──────────────────────────────

    def get_quota_status(self, feature: str) -> dict:
        """Return current usage and limit for *feature* (useful in admin views)."""
        billing_on = current_app.config.get("GEMINI_BILLING_ENABLED", False)
        if feature == FEATURE_MCQ:
            model = current_app.config.get("GEMINI_MODEL_MCQ", "gemini-3.1-flash-lite")
            usage = self._today_usage(feature, model)
            limit = self._quota_limit(feature, model)
        else:  # FEATURE_ASSISTANT
            model = current_app.config.get("GEMINI_MODEL_ASSISTANT_PRIMARY", "gemini-2.5-flash")
            usage = self._today_usage(feature, model)
            limit = self._quota_limit(feature, model)

        return {
            "feature":     feature,
            "used":        usage,
            "limit":       limit,
            "remaining":   max(0, limit - usage),
            "billing_on":  billing_on,
            "capped":      not billing_on and usage >= limit,
        }


# --- INSTANTIATE THE GLOBAL SERVICE OBJECT FOR ROUTE IMPORTS ---
ai_service = AIService()
