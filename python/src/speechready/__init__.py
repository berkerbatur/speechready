"""speechready: prepare text for text-to-speech.

Clean LLM output, verbalize ambiguous tokens, compile pacing intents to a
provider's own syntax, and chunk under the model's request limit. Deterministic,
no network calls, every rewrite reported as a Change.
"""

from .changes import Change
from .chunk import Segmenter, pack, split_sentences
from .clean import CleanOptions, Options, clean
from .lexicon import Entry, Lexicon
from .pipeline import Prepared, prepare
from .profiles import Profile, list_profiles, load_profile, resolve_profile

__version__ = "0.1.0.dev0"

__all__ = [
    "Change",
    "CleanOptions",
    "Options",
    "Entry",
    "Lexicon",
    "Prepared",
    "Profile",
    "Segmenter",
    "__version__",
    "clean",
    "list_profiles",
    "load_profile",
    "pack",
    "prepare",
    "resolve_profile",
    "split_sentences",
]
